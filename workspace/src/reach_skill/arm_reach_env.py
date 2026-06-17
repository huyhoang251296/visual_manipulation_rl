import numpy as np
from gymnasium import utils
from gymnasium.envs.mujoco import MujocoEnv
from gymnasium.spaces import Box
import os
import mujoco


class UR3eReachEnv(MujocoEnv, utils.EzPickle):
    metadata = {
        "render_modes": [
            "human",
            "rgb_array",
            "depth_array",
        ],
        "render_fps": 100,
    }

    def __init__(self, episode_len=500, **kwargs):
        utils.EzPickle.__init__(self, **kwargs)

        observation_space = Box(low=-np.inf, high=np.inf, shape=(21,), dtype=np.float64)
        # xml_path = os.path.join(os.path.dirname(__file__), "ur3e_with_gripper.xml")
        xml_path = os.path.join(os.path.dirname(__file__), "combined_robot_gripper.xml")

        MujocoEnv.__init__(
            self,
            xml_path,
            frame_skip=10, # dt = frameskip * model.opt.timestep = 0.01s
            observation_space=observation_space,
            **kwargs,
        )

        # self.dt = self.frame_skip * self.model.opt.timestep
        self.step_number = 0
        self.episode_len = episode_len
        self.target = np.zeros(3, dtype=np.float64)
        self.prev_ee_pos = np.zeros(3, dtype=np.float64)

        self.prev_distance = None

    def step(self, action):
        self.do_simulation(action, self.frame_skip)
        self.step_number += 1

        obs = self._get_obs()
        ee_pos = obs[12:15]
        reward = self._compute_reward(ee_pos)
        done = bool(not np.isfinite(obs).all())
        truncated = self.step_number > self.episode_len

        return obs, reward, done, truncated, {}

    def reset_model(self):
        self.step_number = 0

        qpos = self.init_qpos + self.np_random.uniform(
            size=self.model.nq, low=-0.01, high=0.01
        )
        qvel = self.init_qvel + self.np_random.uniform(
            size=self.model.nv, low=-0.01, high=0.01
        )
        self.set_state(qpos, qvel)
        self.target = self._sample_target()
        self.prev_distance = None

        self._update_target_in_model() # Only for visualization

        self.prev_ee_pos = self._get_ee_pos()
        return self._get_obs()

    def _get_obs(self):
        joint_names = [
            "robot0:shoulder_pan_joint",
            "robot0:shoulder_lift_joint",
            "robot0:elbow_joint",
            "robot0:wrist_1_joint",
            "robot0:wrist_2_joint",
            "robot0:wrist_3_joint",
        ]

        qpos = np.array([self.data.joint(name).qpos for name in joint_names], dtype=np.float64).flatten()
        qvel = np.array([self.data.joint(name).qvel for name in joint_names], dtype=np.float64).flatten()

        ee_pos = self._get_ee_pos()
        ee_vel = (ee_pos - self.prev_ee_pos) / self.dt
        self.prev_ee_pos = ee_pos.copy()

        obs = np.concatenate((qpos, qvel, ee_pos, ee_vel, self.target), axis=0)
        return obs

    def _get_ee_pos(self):
        site_id = self.data.site("wrist_3_linkgrasp_sitegripper").id

        return np.array(self.data.site_xpos[site_id], dtype=np.float64).flatten()

    def _sample_target(self):
        x = self.np_random.uniform(low=-0.7, high=0.7)
        y = self.np_random.uniform(low=-0.3, high=0.3)
        z = self.np_random.uniform(low=0.05, high=0.35)
        return np.array([x, y, z], dtype=np.float64)

    def _update_target_in_model(self):
        target_sphere_id = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_BODY,
            "target_sphere"
        )
        self.model.body_pos[target_sphere_id] = self.target

    # def _compute_reward(self, ee_pos):
    #     distance = np.linalg.norm(ee_pos - self.target)
    #     return -distance

    # def _compute_reward(self, ee_pos):
    #     distance = np.linalg.norm(ee_pos - self.target)
    #     return np.exp(-5.0 * distance)

    def _compute_reward(self, ee_pos):
        distance = np.linalg.norm(ee_pos - self.target)

        reward = -distance * 2.0

        if self.prev_distance is not None:
            reward += 10.0 * (self.prev_distance - distance)

        if distance < 0.05:
            reward += 10.0

        self.prev_distance = distance
        return reward
    