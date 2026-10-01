#!/usr/bin/env bash
set -euo pipefail
hcr_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
hcr_python="$hcr_root/outputs/sorting_station/hcr_preview/venv/bin/python"
if [[ ! -x "$hcr_python" ]]; then
  echo 'D435 Python environment missing. See hcr/README.md installation instructions.' >&2
  exit 1
fi
exec "$hcr_python" "$hcr_root/src/sorting_station/hcr/zone_preview.py" --backend realsense "$@"
