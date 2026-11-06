"""Build and sign through an existing official Tizen SDK profile."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

from font_assets import write_widget_archive
from local_config import ROOT, load_settings, read_password
from private_files import check_signed_widget
from signing_checks import assert_no_reference_identity, preflight, verify_signatures


def sign_posix(command, password=None, timeout=60):
    import pty
    import select
    import signal
    import termios
    # SDK output can include profile credentials. Never copy it to diagnostics.
    pid, terminal = pty.fork()
    if pid == 0:
        try:
            os.execv(command[0], command)
        except BaseException:
            os._exit(127)
    output = b''
    passwords = saves = 0
    status = None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([terminal], [], [], 1)
            if not ready:
                continue
            try:
                chunk = os.read(terminal, 8192)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
            if len(output) > 1024 * 1024:
                raise ValueError('SDK produced excessive signing output.')
            count = output.lower().count(b'password:')
            if count > passwords:
                if password is None:
                    raise ValueError('SDK requested a password. Configure saved profile access or select a protected password file.')
                if count > 2:
                    raise ValueError('SDK requested too many passwords. Check both certificate passwords in the selected profile.')
                attributes = termios.tcgetattr(terminal)
                attributes[3] &= ~termios.ECHO
                termios.tcsetattr(terminal, termios.TCSANOW, attributes)
                os.write(terminal, password + b'\n')
                passwords = count
            count = output.count(b'No: (N) ?')
            if count > saves:
                os.write(terminal, b'n\n')
                saves = count
        else:
            raise ValueError('SDK signing timed out.')
        while time.monotonic() < deadline:
            finished, status = os.waitpid(pid, os.WNOHANG)
            if finished:
                break
            status = None
            time.sleep(0.01)
        if status is None:
            raise ValueError('SDK signing timed out.')
    finally:
        if status is None:
            finished, status = os.waitpid(pid, os.WNOHANG)
            if not finished:
                try:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except PermissionError:
                        os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _, status = os.waitpid(pid, 0)
        os.close(terminal)
    return os.waitstatus_to_exitcode(status)


def sign_subprocess(command, password=None, timeout=60):
    """Windows-safe signer. The password is written only to the process input."""
    import queue
    import threading
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    passwords = saves = 0
    incoming = queue.Queue()

    pipe = proc.stdout.fileno()

    def reader():
        try:
            while True:
                try:
                    chunk = os.read(pipe, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                incoming.put(chunk)
        finally:
            incoming.put(None)

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                raise ValueError('SDK signing timed out.')
            try:
                chunk = incoming.get(timeout=0.2)
            except queue.Empty:
                continue
            if chunk is None:
                break
            output += chunk
            if len(output) > 1024 * 1024:
                raise ValueError('SDK produced excessive signing output.')
            count = bytes(output).lower().count(b'password:')
            if count > passwords:
                if password is None:
                    raise ValueError('SDK requested a password. Configure saved profile access or select a protected password file.')
                if count > 2:
                    raise ValueError('SDK requested too many passwords. Check both certificate passwords in the selected profile.')
                proc.stdin.write(password + b'\n')
                proc.stdin.flush()
                passwords = count
            count = bytes(output).count(b'No: (N) ?')
            if count > saves:
                proc.stdin.write(b'n\n')
                proc.stdin.flush()
                saves = count
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('SDK signing timed out.')
        return proc.wait(timeout=remaining)
    finally:
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        if proc.stdin:
            try:
                proc.stdin.close()
            except OSError:
                pass
        if proc.stdout:
            try:
                proc.stdout.close()
            except OSError:
                pass


def sign(command, password=None, timeout=60, platform=None):
    if (platform or os.name) == 'nt':
        return sign_subprocess(command, password, timeout)
    return sign_posix(command, password, timeout)


def tizen_executable(sdk_path, platform):
    name = 'tizen.bat' if platform == 'nt' else 'tizen'
    return Path(sdk_path) / 'tools' / 'ide' / 'bin' / name


def windows_command_line(argv):
    """Quote a tizen.bat invocation for cmd.exe. Passwords must not be in argv."""
    return ['cmd.exe', '/d', '/s', '/c', subprocess.list2cmdline(list(argv))]


def launch_command(argv, platform):
    if platform == 'nt' and os.name == 'nt' and str(argv[0]).lower().endswith(('.bat', '.cmd')):
        return windows_command_line(argv)
    return list(argv)


def main(root=ROOT, argv=None, platform=None):
    if argv is None:
        argv = []
    platform = platform or os.name
    settings = load_settings(root)
    if argv[:1] == ['--verify']:
        if len(argv) != 2:
            raise ValueError('Use --verify with the signed widget path.')
        for line in verify_signatures(argv[1], settings['identity'], require_own=True):
            print(line)
        return
    if argv:
        raise ValueError('Unknown packaging argument.')
    for line in preflight(settings, root, platform):
        print(line)
    cli = tizen_executable(settings['sdk_path'], platform)
    if not cli.is_file() or (platform != 'nt' and not os.access(cli, os.X_OK)):
        raise ValueError('Tizen CLI missing. Set sdk_path in .local/signing.json; see docs/development.md.')
    password = read_password(settings['password_file'], root=root) if settings['password_file'] else None
    dist = root / 'dist'
    dist.mkdir(exist_ok=True)
    unsigned = dist / 'CleanFrame-unsigned.wgt'
    write_widget_archive(unsigned, root=root, identity=settings['identity'])
    # A fresh folder prevents a previous signed widget masking a failed build.
    signed_dir = Path(tempfile.mkdtemp(prefix='signed-', dir=dist))
    command = launch_command(
        [str(cli), 'package', '-t', 'wgt', '-s', settings['profile'], '-o', str(signed_dir), '--', str(unsigned)],
        platform)
    if password and any(password in str(part).encode() for part in command):
        raise ValueError('Refusing to pass a certificate password on the command line.')
    if sign(command, password, platform=platform):
        raise ValueError('SDK signing failed. Check the selected profile and password access in Certificate Manager.')
    signed = signed_dir / unsigned.name
    check_signed_widget(signed, settings['identity'])
    assert_no_reference_identity(signed, settings['identity'])
    target = dist / 'CleanFrame.wgt'
    # Promote on the same filesystem so a failed copy preserves the last build.
    ready = signed_dir / 'validated.wgt'
    ready.write_bytes(signed.read_bytes())
    ready.replace(target)
    print('Signed widget created: ' + str(target))


if __name__ == '__main__':
    errors = [ValueError, OSError, zipfile.BadZipFile]
    try:
        import termios
        errors.append(termios.error)
    except ImportError:
        pass
    try:
        main(argv=sys.argv[1:])
    except tuple(errors) as error:
        # Known validation messages contain no credentials. Suppress SDK/OS payloads.
        message = str(error) if isinstance(error, ValueError) else 'Cannot complete packaging. Check SDK/profile setup and local file permissions.'
        raise SystemExit(message) from None
