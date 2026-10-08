# -*- coding: utf-8 -*-
"""
ПРОБА ВШИВКИ — три проверки, и каждая может провалиться. Игра не нужна.

1. ТОЖДЕСТВО. PPOSUrokom с тягой 0 обязан быть штатным PPO до последней цифры:
   оба класса получают ОДИНАКОВЫЙ набор данных и одинаковые стартовые веса,
   делают train() — веса после обязаны совпасть побайтово. Провалится, если
   копия train() разошлась с библиотекой или тяга трогает что-то при нуле.

2. ДЕЙСТВИЕ. С тягой > 0 веса обязаны РАЗОЙТИСЬ со штатными — иначе тяга
   ничего не делает.

3. НАПРАВЛЕНИЕ. Несогласие с уроком (urok_poterya) после шагов с тягой обязано
   УПАСТЬ — иначе тяга тянет не туда.

Запуск: zapusk\\proba-vshivki.bat
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import gymnasium as gym
import numpy as np
import torch as th
from stable_baselines3 import PPO

from telo import kanaly as KAN
from telo import mir as M
from telo.vshivka import PPOSUrokom, zagruzit_urok

ROOT = Path(__file__).parent.parent
MOZG = ROOT / "models" / "ppo_ubijca"


class PustoyMir(gym.Env):
    def __init__(self):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (M.VYSOTA_KADRA, M.SHIRINA_KADRA,
                                           3 * M.KADROV_V_PAMYATI), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.MultiDiscrete(KAN.KANALY)

    def reset(self, *, seed=None, options=None):
        return self.observation_space.sample(), {}

    def step(self, a):
        return self.observation_space.sample(), 0.0, False, False, {}


def zagruzit(klass, n_steps):
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.vec_env import DummyVecEnv
    env = DummyVecEnv([lambda: PustoyMir()])
    m = klass.load(MOZG, env=env, device="cpu",
                   custom_objects={"learning_rate": 8e-5,
                                   "lr_schedule": (lambda _: 8e-5),
                                   "n_steps": n_steps, "batch_size": 128,
                                   "n_epochs": 2, "target_kl": None})
    m.set_logger(configure(None, []))    # train() вне learn() требует журнал
    return m


def nabit_bufer(model, rng):
    """Одинаковый искусственный опыт для всех подопытных."""
    n = model.n_steps
    pov = rng.integers(0, 255, size=(n, M.VYSOTA_KADRA, M.SHIRINA_KADRA,
                                     3 * M.KADROV_V_PAMYATI), dtype=np.uint8)
    vec = rng.random((n, 6), dtype=np.float32)
    model.rollout_buffer.reset()
    obs_n = {"pov": pov, "vec": vec}
    for i in range(n):
        obs_i = {"pov": pov[i:i + 1], "vec": vec[i:i + 1]}
        with th.no_grad():
            t, _ = model.policy.obs_to_tensor(obs_i)
            dejstvie, cennost, logp = model.policy(t)
        # буфер хранит кадры каналами вперёд (CHW) — как их отдаёт VecTransposeImage
        obs_b = {"pov": obs_i["pov"].transpose(0, 3, 1, 2), "vec": obs_i["vec"]}
        model.rollout_buffer.add(
            obs_b, dejstvie.cpu().numpy(),
            np.array([float(rng.random())]),
            np.array([i % 100 == 0]), cennost, logp)
    with th.no_grad():
        t, _ = model.policy.obs_to_tensor({"pov": pov[-1:], "vec": vec[-1:]})
        posl = model.policy.predict_values(t)
    model.rollout_buffer.compute_returns_and_advantage(last_values=posl, dones=np.array([False]))


def main():
    n_steps = 256
    print("готовлю двух подопытных с одинаковыми весами и опытом...")
    th.manual_seed(0)
    obychnyj = zagruzit(PPO, n_steps)
    th.manual_seed(0)
    s_urokom = zagruzit(PPOSUrokom, n_steps)

    pov_u, vec_u, act_u = zagruzit_urok()
    print(f"урок: {len(act_u)} кадров, стопки по отступам {M.OTSTUPY_PAMYATI}")

    # зерно торча перед КАЖДЫМ заполнением: политика сэмплирует действия,
    # и без сброса у подопытных получился бы разный опыт (первый прогон пробы
    # ровно на этом и провалил тождество — виноват был тест, не вшивка)
    th.manual_seed(2); rng = np.random.default_rng(3)
    nabit_bufer(obychnyj, rng)
    th.manual_seed(2); rng = np.random.default_rng(3)
    nabit_bufer(s_urokom, rng)

    # ── 1. ТОЖДЕСТВО при тяге 0 ──
    s_urokom.nastroit_urok(pov_u, vec_u, act_u, tyaga=0.0)
    th.manual_seed(1); np.random.seed(1)
    obychnyj.train()
    th.manual_seed(1); np.random.seed(1)
    s_urokom.train()
    for (ka, va), (kb, vb) in zip(obychnyj.policy.state_dict().items(),
                                  s_urokom.policy.state_dict().items()):
        if not th.equal(va, vb):
            raise SystemExit(f"ПРОВАЛ ТОЖДЕСТВА: вес {ka} разошёлся при тяге 0")
    print("1. ТОЖДЕСТВО: при тяге 0 веса совпали до последней цифры")

    # ── 2. ДЕЙСТВИЕ при тяге > 0 ──
    th.manual_seed(2); rng = np.random.default_rng(3)
    nabit_bufer(s_urokom, rng)
    do = s_urokom._urok_poterya().item()
    s_urokom.nastroit_urok(pov_u, vec_u, act_u, tyaga=0.3)
    th.manual_seed(1); np.random.seed(1)
    s_urokom.train()
    razoshlis = any(not th.equal(va, vb)
                    for (_, va), (_, vb) in zip(obychnyj.policy.state_dict().items(),
                                                s_urokom.policy.state_dict().items()))
    if not razoshlis:
        raise SystemExit("ПРОВАЛ ДЕЙСТВИЯ: тяга 0.3 не изменила ни одного веса")
    print("2. ДЕЙСТВИЕ: тяга 0.3 сдвинула веса относительно штатного PPO")

    # ── 3. НАПРАВЛЕНИЕ ──
    s_urokom.nastroit_urok(pov_u, vec_u, act_u, tyaga=0.0)   # мерим тем же генератором
    posle = s_urokom._urok_poterya().item()
    print(f"3. НАПРАВЛЕНИЕ: несогласие с уроком {do:.3f} -> {posle:.3f}")
    if not posle < do:
        raise SystemExit("ПРОВАЛ НАПРАВЛЕНИЯ: тяга не приблизила политику к уроку")
    print("\nвсе три проверки прошли — вшивка исправна")


if __name__ == "__main__":
    main()
