#!/usr/bin/env bash
set -eo pipefail
hcr_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$hcr_root"
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
if [[ ! -f outputs/sorting_station/ros2/install/setup.bash ]]; then
  echo 'Run bash src/sorting_station/hcr/build_sorter.sh first.' >&2
  exit 1
fi
source outputs/sorting_station/ros2/install/setup.bash
exec /usr/bin/python3 -c 'from hcr_sorting.node import main; main()' "$@"
