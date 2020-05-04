#!/bin/bash

set -exo pipefail

nox -s "${NOX_SESSION}"
