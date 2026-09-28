#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# This is a local operator-edited shell file, not a downloaded config.
if [[ -f config/hardware.local.env ]]; then
  source config/hardware.local.env
fi
LEADER_PORT="${LEADER_PORT:-/dev/serial/by-id/usb-ROBOTIS_OpenRB-150_3B3256F3503059384C2E3120FF0A1E24-if00}"
FOLLOWER_PORT="${FOLLOWER_PORT:-/dev/serial/by-id/usb-ROBOTIS_OpenRB-150_6965FF80503059384C2E3120FF08222F-if00}"
CAMERAS_CONFIG="${CAMERAS_CONFIG:-config/cameras.local.json}"
[[ -f "$CAMERAS_CONFIG" ]] || CAMERAS_CONFIG=config/cameras.example.json
PY="${LEROBOT_PY:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || { echo 'Run bash scripts/setup.sh first'; exit 1; }
exec "$PY" src/sorting_station/collect_real_pepper_demos.py \
  --leader-port "$LEADER_PORT" --follower-port "$FOLLOWER_PORT" \
  --leader-id "${LEADER_ID:-omx_leader_arm}" --follower-id "${FOLLOWER_ID:-omx_follower_arm}" \
  --leader-calibration-dir "${LEADER_CALIBRATION_DIR:-profiles/omx_pair/leader}" \
  --follower-calibration-dir "${FOLLOWER_CALIBRATION_DIR:-profiles/omx_pair/follower}" \
  --cameras "$CAMERAS_CONFIG" --episodes "${EPISODES:-20}" \
  --color "${COLOR_MODE:-alternate}" --fps "${FPS:-30}" "$@"
