# Sign on Windows

Use this path when the official Tizen Studio command-line tools are already installed on Windows. The packager is `tizen.bat package`. `scripts/package-own.ps1` runs that command after the same identity and profile-path checks used on Linux. It does not create a certificate, choose a new package id, install an app, or launch a TV.

The tracked `app/config.xml` and `app/device.js` keep the reference installation identity. The generated widget receives the SDK-generated identity from ignored `.local/signing.json`, including the runtime fallback in the packaged `device.js`. If that reference id remains anywhere in the generated widget, packaging stops.

This host was not available while the wrapper was written. The offline tests construct the `tizen.bat` command and reject a password on that command line. They do not run Samsung's CLI.

## Group 1 — tools already on the PC

Use the existing Tizen Studio install and the existing certificate profile. Do not create a new author certificate or distributor certificate when that profile already contains them.

Samsung's CLI prerequisite is that `<TIZEN_STUDIO>\tools\ide\bin` is on `PATH`. Packaging itself uses Python 3.10 or newer. The `py -3` launcher from python.org satisfies that. Node and npm are not used.

Confirm the CLI before packaging:

```text
C:\tizen-studio\tools\ide\bin\tizen.bat version
```

Expected result: a version line. If the window shows the usage text instead, stop and correct the SDK install from Samsung's installer page. Do not continue with a guessed Java path.

## Group 2 — local configuration

Copy `signing.example.json` to `.local/signing.json`. Set:

| Field | What to enter |
| --- | --- |
| `sdk_path` | Existing SDK directory, the one that contains `tools\ide\bin\tizen.bat` |
| `profile` | Existing active certificate profile name |
| `package_id` | Ten-character package id from the SDK-generated project |
| `app_id` | That package id, a dot, then the SDK project name |
| `profiles_path` | Existing Windows profile index |
| `author_certificate` | Existing author `.p12` |
| `distributor_certificate` | Existing distributor `.p12` |
| `identity_evidence` | The SDK project's `config.xml`, read only |
| `password_file` | `null` |

Leave the SDK project directory unchanged. The evidence file is only read. Passwords stay in Certificate Manager. Do not put one in `signing.json` or on a command line.

Expected result: `git status` does not list `.local/signing.json`.

## Group 3 — package

From the repository root:

```text
powershell -NoProfile -File scripts\package-own.ps1
```

This does not change the execution policy. If Windows blocks that one downloaded script, `Unblock-File .\scripts\package-own.ps1` clears the block on that file only.

The script calls:

```text
tizen.bat package -t wgt -s YOUR_CERTIFICATE_PROFILE -o <dist\signed-directory> -- <dist\CleanFrame-unsigned.wgt>
```

Expected result:

```text
Own package id: <ten-character SDK package id>
Own application id: <SDK package id>.<SDK project name>
Evidence identity: match
Evidence required_version: <value stored in the SDK project>
Packaged required_version: 5.0
Evidence file modified: no
Profile active: <profile name>
Author certificate path: match
Distributor certificate path: match
Author certificate file: present
Distributor certificate file: present
Profile index modified: no
Signed widget created: dist\CleanFrame.wgt
Manifest package id: <ten-character SDK package id>
Manifest application id: <SDK package id>.<SDK project name>
Reference manifest identity: no
Reference runtime identity: absent
author-signature.xml embedded certificate: present
signature1.xml embedded certificate: present
Certificate presence is not identity proof
Cryptographic validity: not_checked
```

A matching certificate path means the profile index points at the `.p12` files named in `.local/signing.json`. It does not open those files and does not prove they produced the signature. An embedded certificate is not identity proof. `Cryptographic validity: not_checked` means the signature math was not checked.

If `tizen.bat` asks for a password, stop. The saved Certificate Manager access is the supported path. Do not pass a password as a program argument.

Samsung's TV CLI also documents packaging a build directory:

```text
tizen.bat package -t wgt -s YOUR_CERTIFICATE_PROFILE -- <directory inside dist>
```

Use that form only if the widget form is rejected. Keep the directory inside `dist`. Do not point it at the SDK evidence project.

## Separate from this package

Do not run `npm run tv:install`, `npm run tv:launch`, or anything under `scripts/native-home/`. Nothing in this signing path enables autostart, changes startup, or contacts a TV.

The Windows `tizen.bat` run, and any signature check that would use the private key, were not executed in the environment that prepared this script.
