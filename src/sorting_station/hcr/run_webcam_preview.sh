#!/usr/bin/env bash
set -euo pipefail
hcr_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$hcr_root"
exec /usr/bin/python3 src/sorting_station/hcr/zone_preview.py --backend opencv "$@"
