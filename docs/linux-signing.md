# Sign on Linux

Use this path for an independent CleanFrame package on Linux, including an Ubuntu virtual machine. The packager is Samsung's `tizen package` command. `sh scripts/package-own.sh` runs that command after local checks. It does not create a certificate, choose a new package id, install an app, or launch a TV.

The tracked `app/config.xml` keeps the reference installation identity. That guard stays. The widget manifest is the file that receives the SDK-generated identity from ignored `.local/signing.json`.

Samsung documents Tizen Studio for Ubuntu. Use the Ubuntu release listed in the current [Tizen Studio prerequisites](https://docs.tizen.org/application/tizen-studio/setup/prerequisites/). This repository does not select a distro or install a virtual machine. Start the groups below only after `tizen version` prints a version in that machine.

## Group 1 — local configuration

Copy `signing.example.json` to `.local/signing.json`. Replace the placeholders. Leave `password_file` null unless a later group says the packager asked for a password.

| Field | What to enter |
| --- | --- |
| `sdk_path` | Linux directory that contains `tools/ide/bin/tizen` |
| `profile` | Existing certificate profile name |
| `package_id` | Ten-character package id from the SDK-generated project |
| `app_id` | That package id, a dot, then the SDK project name |
| `profiles_path` | Linux profile index created in Group 2 |
| `author_certificate` | Linux path of the same author `.p12` |
| `distributor_certificate` | Linux path of the same distributor `.p12` |
| `identity_evidence` | Optional copy of the SDK project's `config.xml`, outside this repository |

Expected result: the file is ignored by Git. It contains no password. The application id is the existing SDK id, not a newly generated one.

`sh scripts/package-own.sh` stops if the selected identity is the reference installation. `npm run package` runs the same path checks when the three certificate fields are set. Use `package-own.sh` so the identity guard and the signature report both run.

## Group 2 — same certificates, Linux paths

Copy the existing author `.p12` and distributor `.p12` into the virtual machine yourself. Do not copy the Windows profile index. That file contains Windows paths and secrets, and this packager will reject those paths on Linux.

Do not commit the `.p12` files, send them to a chat, or put a password in `signing.json`.

Register those Linux files once, in a terminal on the virtual machine. The [Tizen CLI profile command](https://docs.tizen.org/application/tizen-studio/web-tools/cli/) accepts the existing files. Type the passwords only in that terminal. Do not save the finished command. Omitting the distributor file makes Tizen Studio substitute its built-in distributor certificate, which is a different certificate.

```sh
tizen security-profiles add -n YOUR_CERTIFICATE_PROFILE \
  -a "$HOME/SamsungCertificate/YOUR_CERTIFICATE_PROFILE/author.p12" \
  -p 'TYPE_THE_AUTHOR_PASSWORD' \
  -d "$HOME/SamsungCertificate/YOUR_CERTIFICATE_PROFILE/distributor.p12" \
  -dp 'TYPE_THE_DISTRIBUTOR_PASSWORD'
```

Expected result: the command writes a Linux profile index. `tizen cli-config -l` shows `default.profiles.path` pointing at that Linux file. Put that file and the two Linux `.p12` paths into `.local/signing.json`. If the active profile name is different, change the active profile in Certificate Manager. The packaging script does not change it and does not run `security-profiles`.

Expected preflight lines after Group 3 starts:

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
```

`Packaged required_version` stays the CleanFrame manifest value. The script does not copy the SDK project's required version and does not write the evidence file. If `identity_evidence` is omitted, the evidence lines are absent.

A Windows path in `signing.json` or in the profile index stops the script before it calls `tizen`. The profile file's password fields are not printed.

## Group 3 — package with the official CLI

From the repository root:

```sh
sh scripts/package-own.sh
```

The script sets `CLEANFRAME_REQUIRE_OWN_IDENTITY=1`, builds `dist/CleanFrame-unsigned.wgt`, and runs:

```sh
tizen package -t wgt -s YOUR_CERTIFICATE_PROFILE -o <dist/signed-directory> -- <dist/CleanFrame-unsigned.wgt>
```

It then checks the promoted `dist/CleanFrame.wgt`. Samsung's TV CLI also documents packaging a build directory with `tizen package -t wgt -s YOUR_CERTIFICATE_PROFILE -- <directory>`. Use that form only if the widget form is rejected. Keep the directory inside `dist/`. Do not point it at the SDK evidence project.

Expected result:

```text
Signed widget created: dist/CleanFrame.wgt
Manifest package id: <ten-character SDK package id>
Manifest application id: <SDK package id>.<SDK project name>
Reference manifest identity: no
author-signature.xml file: present
author-signature.xml signature value: present
author-signature.xml embedded certificate: present
signature1.xml file: present
signature1.xml signature value: present
signature1.xml embedded certificate: present
Packaged script reference fallback: present
Cryptographic validity: not_checked
```

`Packaged script reference fallback: present` means `app/device.js` still contains the reference id used when the TV does not report the current application. The installed identity is the manifest above. This script does not rewrite that fallback.

File names, signature values, and embedded certificates show that the official packager attached its signature files. `Cryptographic validity: not_checked` means this repository did not prove those signatures mathematically. Do not treat presence as validity.

If the packager asks for a password, stop. Prefer the access saved by Certificate Manager. The optional `password_file` in `.local/signing.json` can point at one owner-only password file with mode `600`; both prompts receive that same password. Do not put the password in JSON or in the `tizen` command used by this repository.

A machine without the private font files packages the public fonts. That is the expected VM result.

## Separate from this package

Do not run `npm run tv:install`, `npm run tv:launch`, or anything under `scripts/native-home/`. Those commands are not part of signing. Nothing in this signing path enables autostart, changes startup, or contacts a TV.

App discovery uses the public privileges `http://tizen.org/privilege/application.info` and `http://tizen.org/privilege/application.launch` already declared in the manifest. That is not a test that those calls succeed on a television.

## Checks not run by this preparation

- No Ubuntu installer, VirtualBox machine, or Tizen Studio install was run.
- No real `tizen security-profiles` or `tizen package` command was run.
- No signature was checked with the author's or distributor's private key.
- No widget was installed or launched.
