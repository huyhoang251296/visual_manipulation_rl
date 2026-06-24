import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from sensor_msgs.msg import JointState


class URDirectPositionController(Node):
    def __init__(self):
        super().__init__('ur_direct_position_controller')
        
        # Publisher to the active controller
        self.publisher_ = self.create_publisher(
            Float64MultiArray, 
            '/forward_position_controller/commands', 
            10
        )
        
        # Subscribe to joint states to maintain an aware baseline loop
        self.joint_subscription = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_callback,
            10
        )
        
        self.current_positions = None
        
        # High frequency control loop timer (e.g., 50Hz / every 0.02 seconds)
        self.timer = self.create_timer(0.02, self.control_loop)
        self.get_logger().info('Direct controller interface initialized.')

    def joint_callback(self, msg):
        # Cache current positions so we always have a safe starting baseline
        # Note: In production, explicitly check msg.name to align indices perfectly
        self.current_positions = msg.position

    def control_loop(self):
        if self.current_positions is None:
            return # Wait until we have active state feedback
            
        msg = Float64MultiArray()
        
        # Base command off real-time positions
        target_command = list(self.current_positions)
        
        # EXAMPLE STRATEGY: Safely nudging just the final wrist joint (wrist_3) slightly 
        # replace this logic with your real controller algorithm
        # target_command[5] += 0.005 
        target_command[5] += 0.04

        # msg.data = [
        #     0.0,                 0 # Base
        #     math.radians(-90.0), 1 # Shoulder
        #     math.radians(-1.0),  2 # Elbow
        #     math.radians(-90.0), 3 # Wrist 1
        #     0.0,                 4 # Wrist 2
        #     0.0                  5 # Wrist 3
        # ]
        
        msg.data = target_command
        self.publisher_.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = URDirectPositionController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()