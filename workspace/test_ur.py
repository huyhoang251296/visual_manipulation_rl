import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from builtin_interfaces.msg import Duration

class JointControllerNode(Node):
    def __init__(self):
        super().__init__('joint_controller_node')
        self.action_client = ActionClient(
            self, 
            FollowJointTrajectory, 
            '/scaled_joint_trajectory_controller/follow_joint_trajectory'
        )

    def send_goal(self):
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = [
            'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
            'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint'
        ]
        
        # Target angles (in radians)
        point = JointTrajectoryPoint()
        # point.positions = [0.0, -1.57, 1.57, 0.0, 1.57, 0.0]
        point.positions = [0.0, -1.57, 1.57, 0.0, 1.57, 0.0]
        point.time_from_start = Duration(sec=3, nanosec=0)
        
        goal_msg.trajectory.points = [point]
        self.action_client.wait_for_server()
        self.action_client.send_goal_async(goal_msg)

def main(args=None):
    rclpy.init(args=args)
    node = JointControllerNode()
    node.send_goal()
    rclpy.spin(node)

if __name__ == '__main__':
    main()