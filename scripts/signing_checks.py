"""Read-only identity and certificate-path checks. No signature cryptography."""
import os
from pathlib import Path
import re
import xml.etree.ElementTree as XML
import zipfile

from local_config import APPLICATION, manifest_identity
from private_files import check_signed_widget

REFERENCE_PACKAGE = 'nClrkHome1'
REFERENCE_APP = 'nClrkHome1.FrameHome'
PROFILE_LIMIT = 1024 * 1024


def own_identity_required(settings):
    return (os.environ.get('CLEANFRAME_REQUIRE_OWN_IDENTITY') == '1'
            or settings.get('profiles_path') is not None
            or settings.get('identity_evidence') is not None)


def assert_own_identity(identity):
    if identity.get('package_id') == REFERENCE_PACKAGE or identity.get('app_id') == REFERENCE_APP:
        raise ValueError('Selected identity is the reference installation. Set your own SDK-generated package_id and app_id in .local/signing.json.')


def private_location(path, root, label):
    resolved = Path(path).resolve()
    root_resolved = root.resolve()
    local = (root / '.local').resolve()
    app = (root / 'app').resolve()
    dist = (root / 'dist').resolve()
    if resolved.is_relative_to(app) or resolved.is_relative_to(dist):
        raise ValueError(label + ' must stay outside app/ and dist/.')
    if resolved.is_relative_to(root_resolved) and not resolved.is_relative_to(local):
        raise ValueError(label + ' must stay in .local/ or outside this repository.')
    return resolved


def windows_path(value):
    text = str(value).replace('/', '\\')
    return text.startswith('\\\\') or re.search(r'(^|\\)[A-Za-z]:\\', text) is not None


def path_key(value, platform):
    text = str(value).strip()
    if platform == 'nt':
        text = text.replace('/', '\\')
        while '\\\\' in text:
            text = text.replace('\\\\', '\\')
        if len(text) > 1 and text[1] == ':':
            text = text[0].upper() + text[1:]
        return text.casefold()
    return os.path.normpath(text)


def local_tag(tag):
    return tag.rsplit('}', 1)[-1].lower()


def profile_paths(path, profile_name):
    """Return active name and certificate paths. Password fields are never returned."""
    with open(path, 'rb') as source:
        data = source.read(PROFILE_LIMIT + 1)
    if len(data) > PROFILE_LIMIT:
        raise ValueError('Certificate profile index is too large to inspect.')
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Certificate profile index must be a simple profiles document.')
    try:
        root = XML.fromstring(data)
    except XML.ParseError:
        raise ValueError('Certificate profile index is not valid XML.') from None
    if local_tag(root.tag) != 'profiles':
        raise ValueError('Certificate profile index is not a profiles file.')
    selected = None
    for child in list(root):
        if local_tag(child.tag) == 'profile' and child.get('name') == profile_name:
            selected = child
            break
    if selected is None:
        raise ValueError('Selected certificate profile was not found in the profile index.')
    author = None
    distributors = []
    for item in list(selected):
        kind = local_tag(item.tag)
        key = item.get('key')
        slot = item.get('distributor')
        author_slot = kind == 'author' or (kind == 'profileitem' and slot is not None and slot.strip() == '0')
        distributor_slot = kind == 'distributor' or (kind == 'profileitem' and slot is not None and slot.strip() == '1')
        if author_slot:
            if not key or author:
                raise ValueError('Selected profile must have one author certificate path.')
            author = key
        elif distributor_slot:
            if not key:
                raise ValueError('Selected profile must have one distributor certificate path.')
            distributors.append(key)
    if not author or len(distributors) != 1:
        raise ValueError('Selected profile must have one author path and one distributor path.')
    return {'active': root.get('active'), 'author': author, 'distributor': distributors[0]}


def check_profile(settings, root, platform):
    profiles = settings.get('profiles_path')
    author = settings.get('author_certificate')
    distributor = settings.get('distributor_certificate')
    if profiles is None and author is None and distributor is None:
        return []
    if not profiles or not author or not distributor:
        raise ValueError('Set profiles_path, author_certificate, and distributor_certificate together, or leave all unset.')
    if platform != 'nt' and any(windows_path(item) for item in (profiles, author, distributor)):
        raise ValueError('Certificate paths must be Linux paths. Do not point signing.json at the Windows profile or certificate locations.')
    profiles = private_location(profiles, root, 'Certificate profile index')
    author = private_location(author, root, 'Author certificate')
    distributor = private_location(distributor, root, 'Distributor certificate')
    if not profiles.is_file():
        raise ValueError('Certificate profile index was not found.')
    before = profiles.read_bytes()
    found = profile_paths(profiles, settings['profile'])
    if profiles.read_bytes() != before:
        raise ValueError('Certificate profile index was modified.')
    if platform != 'nt' and any(windows_path(found[name]) for name in ('author', 'distributor')):
        raise ValueError('Profile index contains a Windows certificate path. Register the same certificates in a Linux profile; do not reuse the Windows profile file.')
    if path_key(found['author'], platform) != path_key(author, platform):
        raise ValueError('Author certificate path does not match the selected profile.')
    if path_key(found['distributor'], platform) != path_key(distributor, platform):
        raise ValueError('Distributor certificate path does not match the selected profile.')
    if found.get('active') and found['active'] != settings['profile']:
        raise ValueError('Selected profile is not the active certificate profile. This script does not change the active profile.')
    for label, path in (('Author', author), ('Distributor', distributor)):
        if not path.is_file():
            raise ValueError(label + ' certificate file is missing.')
    return [
        'Profile active: ' + (found.get('active') or 'not recorded'),
        'Author certificate path: match',
        'Distributor certificate path: match',
        'Author certificate file: present',
        'Distributor certificate file: present',
        'Profile index modified: no',
    ]


def required_version(data):
    try:
        item = XML.fromstring(data).find(APPLICATION)
    except XML.ParseError:
        raise ValueError('Widget manifest is not valid XML.') from None
    if item is None or not item.get('required_version'):
        raise ValueError('Manifest has no required_version.')
    return item.get('required_version')


def check_evidence(settings, root):
    evidence = settings.get('identity_evidence')
    if evidence is None:
        return []
    path = private_location(evidence, root, 'Identity evidence')
    source_path = root / 'app' / 'config.xml'
    if not path.is_file():
        raise ValueError('Identity evidence was not found.')
    before = path.read_bytes()
    source = source_path.read_bytes()
    try:
        found = manifest_identity(before)
    except ValueError:
        raise ValueError('Identity evidence does not contain the selected application identity.') from None
    if found != settings['identity']:
        raise ValueError('Identity evidence does not match the selected package_id and app_id.')
    if path.read_bytes() != before or source_path.read_bytes() != source:
        raise ValueError('Identity evidence or source manifest was modified.')
    return [
        'Evidence identity: match',
        'Evidence required_version: ' + required_version(before),
        'Packaged required_version: ' + required_version(source),
        'Evidence file modified: no',
    ]


def preflight(settings, root, platform=None):
    platform = platform or os.name
    lines = []
    if own_identity_required(settings):
        assert_own_identity(settings['identity'])
        lines.extend([
            'Own package id: ' + settings['identity']['package_id'],
            'Own application id: ' + settings['identity']['app_id'],
        ])
    lines.extend(check_evidence(settings, root))
    lines.extend(check_profile(settings, root, platform))
    return lines


def runtime_identity_bytes(data, identity):
    """Point generated runtime files at the selected application id. Leave source bytes unchanged."""
    if identity['package_id'] == REFERENCE_PACKAGE and identity['app_id'] == REFERENCE_APP:
        return data
    return data.replace(REFERENCE_APP.encode(), identity['app_id'].encode())


def assert_no_reference_identity(path, identity):
    if identity['package_id'] == REFERENCE_PACKAGE or identity['app_id'] == REFERENCE_APP:
        return
    needle = REFERENCE_PACKAGE.encode()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if needle in archive.read(info.filename):
                raise ValueError('Generated package still contains the reference identity in ' + info.filename)


def verify_signatures(path, identity, require_own=False):
    """Report file and certificate presence. This does not prove a signature or certificate identity."""
    if require_own:
        assert_own_identity(identity)
        assert_no_reference_identity(path, identity)
    check_signed_widget(path, identity)
    lines = []
    with zipfile.ZipFile(path) as archive:
        manifest = manifest_identity(archive.read('config.xml'))
        lines.append('Manifest package id: ' + manifest['package_id'])
        lines.append('Manifest application id: ' + manifest['app_id'])
        reference = manifest['package_id'] == REFERENCE_PACKAGE or manifest['app_id'] == REFERENCE_APP
        lines.append('Reference manifest identity: ' + ('yes' if reference else 'no'))
        if require_own and reference:
            assert_own_identity(manifest)
        for name in ('author-signature.xml', 'signature1.xml'):
            try:
                root = XML.fromstring(archive.read(name))
            except XML.ParseError:
                raise ValueError(name + ' is not valid XML. File presence is not cryptographic validity.') from None
            tags = {local_tag(elem.tag) for elem in root.iter()}
            if 'signaturevalue' not in tags or 'x509certificate' not in tags:
                raise ValueError(name + ' has no signature value and embedded certificate. File presence is not cryptographic validity.')
            lines.append(name + ' file: present')
            lines.append(name + ' signature value: present')
            lines.append(name + ' embedded certificate: present')
    if require_own:
        lines.append('Reference runtime identity: absent')
    lines.append('Certificate presence is not identity proof')
    lines.append('Cryptographic validity: not_checked')
    return lines
