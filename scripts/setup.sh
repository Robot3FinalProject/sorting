#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), "Use Python 3.10, 3.11 or 3.12"'
"$PYTHON" -m venv .venv
PY="$ROOT/.venv/bin/python"
"$PY" -m pip install --upgrade pip
# Collection needs no CUDA. Install a matching CPU pair before resolving LeRobot.
"$PY" -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.10.0 torchvision==0.25.0
"$PY" -m pip install -r requirements.txt torchcodec==0.10.0
# LeRobot declares headless OpenCV; the interactive collector needs its GUI wheel.
# Both wheels own cv2, so remove both before installing exactly one variant.
"$PY" -m pip uninstall -y opencv-python-headless opencv-python
"$PY" -m pip install opencv-python==4.12.0.88
"$PY" scripts/doctor.py
printf '\nSetup complete. See README.md for device configuration and collection.\n'
