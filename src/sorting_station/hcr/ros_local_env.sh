# Sourced after ROS setup: same-laptop sorter/control communication.
# Explicit loopback peers avoid tailscale-only host config and root/user SHM.
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$hcr_root/config/cyclonedds_local.xml"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-24}"
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_LOCALHOST_ONLY
