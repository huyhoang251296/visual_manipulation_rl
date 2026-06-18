source /opt/ros/humble/setup.bash

apt update

rosdep update
rosdep install --from-paths src --ignore-src -r -y

colcon build --symlink-install

source install/setup.bash
