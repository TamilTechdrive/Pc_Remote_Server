#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv-linux"
DIST="${ROOT}/dist/linux"
BUILD="${ROOT}/build/linux"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Run this script on Linux; PyInstaller does not cross-compile Windows builds to Linux." >&2
    exit 2
fi

python3 -m venv "${VENV}"
"${VENV}/bin/python" -m pip install --upgrade pip
"${VENV}/bin/python" -m pip install -r "${ROOT}/requirements-linux.txt"

mkdir -p "${DIST}" "${BUILD}"
"${VENV}/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --console \
    --name PcRemoteServer \
    --distpath "${DIST}" \
    --workpath "${BUILD}/pyinstaller" \
    --specpath "${BUILD}" \
    "${ROOT}/server.py"

chmod 0755 "${DIST}/PcRemoteServer"
echo "Linux server executable created: ${DIST}/PcRemoteServer"
