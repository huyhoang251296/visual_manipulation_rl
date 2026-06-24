# Launch UR with scaled_joint_trajectory_controller
ros2 launch ur_robot_driver ur_control.launch.py \
    ur_type:=ur3e \
    robot_ip:=192.168.58.20 \
    kinematics_params_file:=/workspace/my_robot_calibration.yaml \
    initial_joint_controller:=scaled_joint_trajectory_controller

# # Launch UR with forward_position_controller
# ros2 launch ur_robot_driver ur_control.launch.py \
#     ur_type:=ur3e \
#     robot_ip:=192.168.58.20 \
#     kinematics_params_file:=/workspace/my_robot_calibration.yaml \
#     initial_joint_controller:=forward_position_controller
