#!/bin/bash

set -exo pipefail

if [[ "$(uname -s)" == "Darwin" && "$NOX_SESSION" == "tests-2.7" ]]; then
    export PATH="/Library/Frameworks/Python.framework/Versions/2.7/bin":$PATH
fi

# Explicitly use python3 as `nox` is not in the PATH on macOS
python3 -m nox -s "${NOX_SESSION}"
