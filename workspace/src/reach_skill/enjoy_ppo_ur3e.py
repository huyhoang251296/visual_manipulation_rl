#!/usr/bin/env python3
import argparse
import os
import time

import gymnasium as gym
import numpy as np
import torch

from arm_reach_env import UR3eReachEnv
from train_ppo_ur3e import ActorCritic


def parse_args():
    parser = argparse.ArgumentParser("CleanRL PPO enjoy for UR3eReachEnv")
    parser.add_argument("--model-path", type=str, required=True, help="Path to the saved model .pth file")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--delay", type=float, default=0.01, help="Seconds to wait between steps for rendering")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"], help="Device for model inference")
    parser.add_argument("--render-mode", type=str, default="human", choices=["human", "rgb_array"], help="Render mode for the environment")
    return parser.parse_args()


def main():
    args = parse_args()
    assert os.path.isfile(args.model_path), f"Model file not found: {args.model_path}"

    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")
    print(f"[enjoy] loading model from {args.model_path} on {device}")

    env = UR3eReachEnv(render_mode=args.render_mode)
    env = gym.wrappers.TimeLimit(env, max_episode_steps=500)
    print(f"[enjoy] created environment with render_mode={args.render_mode}")
    obs, _ = env.reset(seed=args.seed)
    print(f"[enjoy] environment reset with seed={args.seed}")

    obs_space = env.observation_space
    act_space = env.action_space
    obs_dim = int(np.prod(obs_space.shape))
    act_dim = int(np.prod(act_space.shape))

    model = ActorCritic(obs_dim, act_dim).to(device)
    model.load_state_dict(torch.load(args.model_path, map_location=device))
    model.eval()
    print("[enjoy] model loaded and ready")

    for episode in range(1, args.episodes + 1):
        print(f"[enjoy] starting episode {episode}/{args.episodes}")
        obs, _ = env.reset(seed=args.seed + episode)
        obs = torch.tensor(obs, dtype=torch.float32, device=device)
        done = False
        truncated = False
        episode_reward = 0.0
        step = 0

        while not (done or truncated):
            with torch.no_grad():
                mean, _ = model.forward(obs)
                action = mean

            action = action.cpu().numpy()
            print("obs: ", obs)
            print("Action: ", action)
            action = np.clip(action, act_space.low, act_space.high)
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            step += 1

            if args.render_mode == "human":
                env.render()
                time.sleep(args.delay)

            obs = torch.tensor(obs, dtype=torch.float32, device=device)
            done = terminated

            if step % 50 == 0:
                print(f"[enjoy] episode={episode}, step={step}, reward={episode_reward:.2f}")

        print(f"[enjoy] finished episode {episode}/{args.episodes}: reward={episode_reward:.2f}, steps={step}")

    env.close()


if __name__ == "__main__":
    main()
