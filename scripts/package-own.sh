#!/bin/sh
# Sign with the official Tizen CLI after independent-identity checks.
# Does not install, launch, or query a TV, and does not create certificates.
set -eu
cd "$(dirname "$0")/.."
export CLEANFRAME_REQUIRE_OWN_IDENTITY=1
python3 scripts/package.py
python3 scripts/package.py --verify dist/CleanFrame.wgt
