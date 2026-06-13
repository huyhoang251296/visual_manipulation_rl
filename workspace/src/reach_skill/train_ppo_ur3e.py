#!/usr/bin/env python3
import argparse
import os
import random
import time
from collections import deque
import json

import gymnasium as gym
import numpy as np
import torch
import torch.nn as nn
from gymnasium.vector import SyncVectorEnv
from torch.distributions import Normal
from torch.utils.tensorboard import SummaryWriter

from arm_reach_env import UR3eReachEnv


def parse_args():
    parser = argparse.ArgumentParser("CleanRL PPO for UR3eReachEnv")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--total-timesteps", type=int, default=2_000_000)
    parser.add_argument("--learning-rate", type=float, default=2.5e-4)
    parser.add_argument("--num-envs", type=int, default=8)
    parser.add_argument("--num-steps", type=int, default=2048)
    parser.add_argument("--update-epochs", type=int, default=10)
    parser.add_argument("--minibatch-size", type=int, default=64)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--clip-coef", type=float, default=0.2)
    parser.add_argument("--max-grad-norm", type=float, default=0.5)
    parser.add_argument("--ent-coef", type=float, default=0.0)
    parser.add_argument("--vf-coef", type=float, default=0.5)
    parser.add_argument("--target-save-dir", type=str, default="models")
    parser.add_argument("--log-interval", type=int, default=10)
    parser.add_argument("--tensorboard-log", type=str, default="runs")
    return parser.parse_args()


def make_env(seed, rank):
    def thunk():
        env = UR3eReachEnv()
        env = gym.wrappers.TimeLimit(env, max_episode_steps=500)
        env = gym.wrappers.RecordEpisodeStatistics(env)
        env.reset(seed=seed + rank)
        np.random.seed(seed + rank)
        return env

    return thunk


def layer_init(layer, std=np.sqrt(2), bias_const=0.0):
    nn.init.orthogonal_(layer.weight, std)
    nn.init.constant_(layer.bias, bias_const)
    return layer


class ActorCritic(nn.Module):
    def __init__(self, obs_dim, act_dim, hidden_size=256):
        super().__init__()
        self.net = nn.Sequential(
            layer_init(nn.Linear(obs_dim, hidden_size)),
            nn.Tanh(),
            layer_init(nn.Linear(hidden_size, hidden_size)),
            nn.Tanh(),
        )

        self.actor_mean = layer_init(nn.Linear(hidden_size, act_dim), std=0.01)
        self.critic = layer_init(nn.Linear(hidden_size, 1), std=1.0)
        self.log_std = nn.Parameter(torch.zeros(act_dim))

    def forward(self, obs):
        hidden = self.net(obs)
        return self.actor_mean(hidden), self.critic(hidden).squeeze(-1)

    def get_action_and_value(self, obs, action=None):
        mean, value = self.forward(obs)
        std = self.log_std.exp()
        dist = Normal(mean, std)
        if action is None:
            action = dist.sample()
        logprob = dist.log_prob(action).sum(-1)
        entropy = dist.entropy().sum(-1)
        return action, logprob, entropy, value


def compute_gae(rewards, values, dones, last_value, gamma, gae_lambda):
    advantages = np.zeros_like(rewards)
    last_advantage = 0
    for t in reversed(range(rewards.shape[0])):
        mask = 1.0 - dones[t]
        delta = rewards[t] + gamma * last_value * mask - values[t]
        advantages[t] = delta + gamma * gae_lambda * last_advantage * mask
        last_advantage = advantages[t]
        last_value = values[t]
    return advantages


def main():
    args = parse_args()
    run_name = f"cleanrl_ppo_ur3e_seed_{args.seed}"
    os.makedirs(args.target_save_dir, exist_ok=True)
    os.makedirs(args.tensorboard_log, exist_ok=True)

    # create a base run directory (timestamped) and save hyperparameters there
    base_run_name = f"{run_name}_{int(time.time())}"
    base_log_dir = os.path.join(args.tensorboard_log, base_run_name)
    os.makedirs(base_log_dir, exist_ok=True)

    # write hyperparameters to a JSON file and to TensorBoard text
    hparams = vars(args).copy()
    with open(os.path.join(base_log_dir, "hyperparams.json"), "w") as hf:
        json.dump(hparams, hf, indent=2)

    writer = SummaryWriter(log_dir=base_log_dir)
    writer.add_text("hyperparameters", json.dumps(hparams, indent=2))

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    envs = SyncVectorEnv([make_env(args.seed, i) for i in range(args.num_envs)])
    obs_space = envs.single_observation_space
    act_space = envs.single_action_space

    assert isinstance(obs_space, gym.spaces.Box)
    assert isinstance(act_space, gym.spaces.Box)

    obs_dim = int(np.prod(obs_space.shape))
    act_dim = int(np.prod(act_space.shape))

    envs.single_observation_space = obs_space
    envs.single_action_space = act_space

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ActorCritic(obs_dim, act_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate, eps=1e-5)

    global_step = 0
    num_updates = args.total_timesteps // (args.num_steps * args.num_envs)
    obs, _ = envs.reset(seed=args.seed)
    obs = torch.tensor(obs, dtype=torch.float32, device=device)

    reward_buffer = deque(maxlen=100)
    episode_lengths = deque(maxlen=100)
    best_reward = float("-inf")

    for update in range(1, num_updates + 1):
        obs_buffer = np.zeros((args.num_steps, args.num_envs, obs_dim), dtype=np.float32)
        actions_buffer = np.zeros((args.num_steps, args.num_envs, act_dim), dtype=np.float32)
        logprobs_buffer = np.zeros((args.num_steps, args.num_envs), dtype=np.float32)
        rewards_buffer = np.zeros((args.num_steps, args.num_envs), dtype=np.float32)
        dones_buffer = np.zeros((args.num_steps, args.num_envs), dtype=np.float32)
        values_buffer = np.zeros((args.num_steps, args.num_envs), dtype=np.float32)

        for step in range(args.num_steps):
            with torch.no_grad():
                action, logprob, entropy, value = model.get_action_and_value(obs)
            action = action.cpu().numpy()
            clipped_action = np.clip(action, act_space.low, act_space.high)
            next_obs, rewards, terminated, truncated, infos = envs.step(clipped_action)
            dones = np.logical_or(terminated, truncated).astype(np.float32)

            obs_buffer[step] = obs.cpu().numpy()
            actions_buffer[step] = action
            logprobs_buffer[step] = logprob.cpu().numpy()
            rewards_buffer[step] = rewards
            dones_buffer[step] = dones
            values_buffer[step] = value.cpu().numpy()

            global_step += args.num_envs
            obs = torch.tensor(next_obs, dtype=torch.float32, device=device)

            if "episode" in infos:
                reward_buffer.extend(infos["episode"]["r"])
                episode_lengths.extend(infos["episode"]["l"])

        with torch.no_grad():
            _, _, _, next_value = model.get_action_and_value(obs)
            next_value = next_value.cpu().numpy()

        advantages = compute_gae(rewards_buffer, values_buffer, dones_buffer, next_value, args.gamma, args.gae_lambda)
        returns = advantages + values_buffer
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        b_obs = obs_buffer.reshape(-1, obs_dim)
        b_actions = actions_buffer.reshape(-1, act_dim)
        b_logprobs = logprobs_buffer.reshape(-1)
        b_returns = returns.reshape(-1)
        b_values = values_buffer.reshape(-1)
        b_advantages = advantages.reshape(-1)

        batch_size = args.num_envs * args.num_steps
        batch_inds = np.arange(batch_size)

        # track clip fraction across minibatches for this update
        clip_frac_accum = 0.0
        clip_frac_count = 0

        for epoch in range(args.update_epochs):
            np.random.shuffle(batch_inds)
            for start in range(0, batch_size, args.minibatch_size):
                end = start + args.minibatch_size
                mb_inds = batch_inds[start:end]

                mb_obs = torch.tensor(b_obs[mb_inds], dtype=torch.float32, device=device)
                mb_actions = torch.tensor(b_actions[mb_inds], dtype=torch.float32, device=device)
                mb_advantages = torch.tensor(b_advantages[mb_inds], dtype=torch.float32, device=device)
                mb_returns = torch.tensor(b_returns[mb_inds], dtype=torch.float32, device=device)
                mb_old_logprobs = torch.tensor(b_logprobs[mb_inds], dtype=torch.float32, device=device)

                new_actions, new_logprobs, entropy, values = model.get_action_and_value(mb_obs, mb_actions)
                values = values.view(-1)
                entropy = entropy.mean()

                logratio = new_logprobs - mb_old_logprobs
                ratio = logratio.exp()
                # track how often ratio is outside clipping range
                try:
                    clip_frac_batch = ((ratio > 1 + args.clip_coef) | (ratio < 1 - args.clip_coef)).float().mean().item()
                except Exception:
                    clip_frac_batch = 0.0
                clip_frac_accum += clip_frac_batch
                clip_frac_count += 1
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(ratio, 1 - args.clip_coef, 1 + args.clip_coef)
                policy_loss = torch.max(pg_loss1, pg_loss2).mean()

                value_loss = 0.5 * (mb_returns - values).pow(2).mean()
                loss = policy_loss + args.vf_coef * value_loss - args.ent_coef * entropy

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                optimizer.step()

            # Log epoch-level scalars to the single main SummaryWriter to avoid creating many folders
            try:
                # use consistent tags so all epochs appear in the same graphs
                step = global_step + epoch
                writer.add_scalar("losses/loss_epoch", loss.item(), step)
                writer.add_scalar("losses/value_loss_epoch", value_loss.item(), step)
                writer.add_scalar("losses/policy_loss_epoch", policy_loss.item(), step)
                writer.add_scalar("losses/entropy_epoch", entropy.item(), step)
            except Exception:
                pass

        # After all epochs for this update, log aggregate RL metrics
        try:
            clip_fraction = clip_frac_accum / clip_frac_count if clip_frac_count > 0 else 0.0
            explained_var = 1 - np.var(b_returns - b_values) / (np.var(b_returns) + 1e-8)
            returns_mean = float(np.mean(b_returns))
            adv_mean = float(np.mean(b_advantages))
            adv_std = float(np.std(b_advantages))
            value_mean = float(np.mean(b_values))
            value_std = float(np.std(b_values))
            lr = float(optimizer.param_groups[0]["lr"]) if optimizer.param_groups else 0.0

            writer.add_scalar("rl/returns_mean", returns_mean, global_step)
            writer.add_scalar("rl/adv_mean", adv_mean, global_step)
            writer.add_scalar("rl/adv_std", adv_std, global_step)
            writer.add_scalar("rl/explained_variance", explained_var, global_step)
            writer.add_scalar("rl/value_mean", value_mean, global_step)
            writer.add_scalar("rl/value_std", value_std, global_step)
            writer.add_scalar("optimizer/learning_rate", lr, global_step)
            writer.add_scalar("stats/clip_fraction", clip_fraction, global_step)
        except Exception:
            pass

        if update % args.log_interval == 0:
            mean_reward = np.mean(reward_buffer) if reward_buffer else float("nan")
            mean_length = np.mean(episode_lengths) if episode_lengths else float("nan")
            print(
                f"Update {update}/{num_updates}, global_step={global_step}, "
                f"mean_reward={mean_reward:.2f}, mean_length={mean_length:.2f}, "
                f"loss={loss.item():.4f}, value_loss={value_loss.item():.4f}, policy_loss={policy_loss.item():.4f}, entropy={entropy.item():.4f}"
            )
            writer.add_scalar("charts/mean_reward", mean_reward, global_step)
            writer.add_scalar("charts/mean_length", mean_length, global_step)
            writer.add_scalar("losses/loss", loss.item(), global_step)
            writer.add_scalar("losses/value_loss", value_loss.item(), global_step)
            writer.add_scalar("losses/policy_loss", policy_loss.item(), global_step)
            writer.add_scalar("losses/entropy", entropy.item(), global_step)
            # Save best model by reward
            if not np.isnan(mean_reward) and mean_reward > best_reward:
                best_reward = mean_reward
                torch.save(model.state_dict(), os.path.join(args.target_save_dir, f"ppo_ur3e_best_{base_run_name}.pth"))
                writer.add_scalar("charts/best_reward", best_reward, global_step)
                print(f"  -> New best reward: {best_reward:.2f} (saved to ppo_ur3e_{base_run_name}_best.pth)")

            if reward_buffer:
                torch.save(model.state_dict(), os.path.join(args.target_save_dir, f"ppo_ur3e_{base_run_name}.pth"))

    envs.close()
    writer.close()
    torch.save(model.state_dict(), os.path.join(args.target_save_dir, f"ppo_ur3e_{base_run_name}.pth"))


if __name__ == "__main__":
    main()
