import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from sensor_msgs.msg import JointState

import gymnasium as gym
import numpy as np
import time
import torch
import mujoco
import argparse
import os

from arm_reach_env import UR3eReachEnv
from train_ppo_ur3e import ActorCritic


# Placeholder for your model loading import
# e.g., from stable_baselines3 import PPO
# or import torch for custom neural networks
def parse_args():
    parser = argparse.ArgumentParser("CleanRL PPO enjoy for UR3eReachEnv")
    parser.add_argument("--model-path", type=str, required=True, help="Path to the saved model .pth file")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--delay", type=float, default=0.01, help="Seconds to wait between steps for rendering")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"], help="Device for model inference")
    parser.add_argument("--render-mode", type=str, default="human", choices=["human", "rgb_array"], help="Render mode for the environment")
    return parser.parse_args()


class TrainedPolicyRosEnv(Node):
    def __init__(self, args):
        super().__init__('trained_policy_ros_env')
        
        self.args = args
        self.device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")
        # 1. Initialize your existing Gym/MuJoCo Environment
        # Ensure render_mode is set to "human" if you want to watch it run live
        self.get_logger().info("Initializing Gym MuJoCo Environment...")
        self.env = UR3eReachEnv(render_mode=args.render_mode)
        self.env = gym.wrappers.TimeLimit(self.env, max_episode_steps=500)
        
        # Reset the environment to get the initial observation state
        self.obs, _ = self.env.reset()

        # 2. Sync MuJoCo with the current live robot positions BEFORE starting loops
        self.is_synced = False
        self.get_logger().info("Waiting for /joint_states to sync initial environment configuration...")
        
        self.init_sync_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )
        
        self.get_logger().info("Spinning...")
        # Block execution temporarily until the callback sets self.is_synced to True
        while rclpy.ok() and not self.is_synced:
            rclpy.spin_once(self, timeout_sec=0.1)

        # 3. Load your pre-trained model/weights
        self.get_logger().info("Loading pre-trained policy model...")
        # Example using Stable-Baselines3:
        # self.model = PPO.load("ur3e_policy_model.zip")
        self.model = None # Replace this with your actual model object / torch network
        obs_space = self.env.observation_space
        self.act_space = self.env.action_space
        obs_dim = int(np.prod(obs_space.shape))
        act_dim = int(np.prod(self.act_space.shape))

        self.model = ActorCritic(obs_dim, act_dim).to(self.device)
        self.model.load_state_dict(torch.load(args.model_path, map_location=self.device))
        self.model.eval()

        # 4. Create a Subscriber to get your target joint values
        self.publisher_ = self.create_publisher(
            Float64MultiArray, 
            '/forward_position_controller/commands', 
            10
        )
        
        # 5. Create a Timer for your environment execution loop
        # Match this to your Gym environment control frequency (e.g., 50Hz = 0.02s)
        self.timer_period = 0.02 
        self.timer = self.create_timer(self.timer_period, self.env_step_loop)
        
        self.latest_ros_command = None
        self.get_logger().info("Trained Policy ROS 2 wrapper is fully initialized.")

    def joint_state_callback(self, msg):
        """Fires only at startup to snap MuJoCo physics to match the current hardware state."""
        try:
            # Safely unpack the Gymnasium wrapper to touch raw MuJoCo pointers
            raw_env = self.env.unwrapped
            
            # Extract real positions (Ensure the mapping aligns to your XML qpos structure!)
            # Standard UR mapping usually maps the first 6 elements of qpos to your arm joints
            for i in range(6):
                raw_env.data.qpos[i] = msg.position[i]
                raw_env.data.qvel[i] = msg.velocity[i] # Set starting velocity to zero for safety
            
            # Forward kinematics pass to recalculate cartesian matrices in MuJoCo memory
            mujoco.mj_forward(raw_env.model, raw_env.data)
            
            # Refresh your initial Gym observation array from the freshly synced state
            # Some custom Gym envs provide an explicit method for this, otherwise re-assigning works
            if hasattr(raw_env, '_get_obs'):
                self.obs = raw_env._get_obs()
            
            # self.get_logger().info(f"Successfully synced MuJoCo initial state to hardware joints: {list(msg.position[:6])}")
            self.is_synced = True
            self.current_positions = msg.position
            
            # # Clean up the transient subscription so it stops running in the background
            # # self.destroy_subscription(self.init_sync_sub)
            
        except Exception as e:
            self.get_logger().error(f"Failed initial environment synchronization: {str(e)}")

    def joint_command_callback(self, msg):
        """Captures real-time incoming target adjustments from your ROS pipeline."""
        if len(msg.data) == 6:
            self.latest_ros_command = np.array(msg.data, dtype=np.float32)
        else:
            self.get_logger().warn(f"Received invalid command size: {len(msg.data)}")

    def env_step_loop(self):
        """Main environment execution loop handling inference and physics stepping."""
        start_time = time.time()

        # # A. Inject your ROS command context into your model's observations if required
        # if self.latest_ros_command is not None:
        #     # If your policy accepts target joint positions as part of its observation space,
        #     # override or update that portion of self.obs here before inference.
        #     # Example: self.obs['target_joints'] = self.latest_ros_command
        #     pass

        # B. Run model inference (Forward Pass)
        # Using a typical Stable-Baselines3 pattern as an example:
        if self.model is not None:
            obs = torch.tensor(self.obs, dtype=torch.float32, device=self.device)
            with torch.no_grad():
                action, _states = self.model.forward(obs)
        else:
            # Fallback to random actions if no model is loaded yet
            action = self.env.action_space.sample()

        action = action.cpu().numpy()
        print("target: ", obs[-3:])
        print("obs: ", obs)
        print("Action: ", action)      

        action = np.clip(action, self.act_space.low, self.act_space.high)
    
        # C. Step the MuJoCo simulation via your Gym API
        # This processes the action, calculates physics, and auto-renders the window
        self.obs, reward, terminated, truncated, info = self.env.step(action)

        delta_action_limit = np.array([
            0.005,    # Joint0 : Base 191 deg/s     -> 1.91 deg/0.01s -> 0.03 rad/0.01s| use 0.02
            0.005,    # Joint1 : Shoulder 191 deg/s -> 1.91 deg/0.01s -> 0.03 rad/0.01s| use 0.02
            0.005,    # Joint2 : Elbow 191 deg/s    -> 1.91 deg/0.01s -> 0.03 rad/0.01s| use 0.02
            0.02,    # Joint3 : Wrist_1 371 deg/s  -> 3.71 deg/0.01s -> 0.06 rad/0.01s| use 0.04
            0.02,    # Joint4 : Wrist_2 371 deg/s  -> 3.71 deg/0.01s -> 0.06 rad/0.01s| use 0.04
            0.02,    # Joint5 : Wrist_3 371 deg/s  -> 3.71 deg/0.01s -> 0.06 rad/0.01s| use 0.04
            #1  # Gripper range [0, 255] -> completely close in 2s -> 127 / s -> 1.27/0.01s | use 1
            ])
        
        msg = Float64MultiArray()
        target_command = list(self.current_positions)

        for i in range(6):
            target_command[i] = np.clip(
                action[i],
                target_command[i] - delta_action_limit[i], # Min
                target_command[i] + delta_action_limit[i] # Max
            )

        print("target_command: ", target_command)
        msg.data = target_command

        self.publisher_.publish(msg)

        # D. Handle Episode Resets
        if terminated or truncated:
            self.get_logger().info("Episode finished or truncated. Resetting environment...")
            self.obs, _ = self.env.reset()

        # E. Keep ROS execution tightly locked to real-time execution speeds
        elapsed = time.time() - start_time
        if elapsed > self.timer_period:
            self.get_logger().warn(f"Loop timeout: Inference + stepping took {elapsed:.4f}s")
        
        if self.args.render_mode == "human":
            self.env.render()


def main(args=None):
    args = parse_args()
    assert os.path.isfile(args.model_path), f"Model file not found: {args.model_path}"

    rclpy.init()
    node = TrainedPolicyRosEnv(args)
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.env.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()