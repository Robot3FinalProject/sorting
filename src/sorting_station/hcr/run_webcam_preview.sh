#!/usr/bin/env bash
set -euo pipefail
hcr_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$hcr_root"
# Default to the identified external webcam, never silently use the laptop camera.
hcr_has_camera=false
for hcr_arg in "$@"; do
  case "$hcr_arg" in --camera|--camera=*) hcr_has_camera=true ;; esac
done
if [[ "$hcr_has_camera" == false ]]; then
  hcr_webcams=()
  for hcr_device in /sys/class/video4linux/video*; do
    [[ -r "$hcr_device/name" && -r "$hcr_device/index" ]] || continue
    if [[ "$(cat "$hcr_device/name")" == 'Wed Camera: Wed Camera' && "$(cat "$hcr_device/index")" == 0 ]]; then
      hcr_webcams+=("/dev/$(basename "$hcr_device")")
    fi
  done
  if [[ ${#hcr_webcams[@]} != 1 ]]; then
    echo 'External Wed Camera not uniquely found. Specify --camera /dev/videoN.' >&2
    exit 1
  fi
  echo "Using USB webcam: ${hcr_webcams[0]}" >&2
  set -- --camera "${hcr_webcams[0]}" "$@"
fi
exec /usr/bin/python3 src/sorting_station/hcr/zone_preview.py --backend opencv "$@"
