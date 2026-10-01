#!/usr/bin/env bash
set -eo pipefail
hcr_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$hcr_root"
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
colcon --log-base outputs/sorting_station/ros2/log build \
  --base-paths src/smartfarm_interfaces src/sorting_station/hcr_sorting \
  --build-base outputs/sorting_station/ros2/build \
  --install-base outputs/sorting_station/ros2/install \
  --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3 -DPYTHON_EXECUTABLE=/usr/bin/python3
