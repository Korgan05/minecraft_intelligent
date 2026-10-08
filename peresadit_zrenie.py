# -*- coding: utf-8 -*-
"""
ПЕРЕСАДКА ЗРЕНИЯ 64 -> 128: новые глаза без потери навыка.

ЗАЧЕМ. Замер показал: на 64x64 полблока дистанции до зомби — 1-2 пикселя,
а 3.5 и 4.0 блока неотличимы вовсе. Дуэль с мечником строится на чувстве
дистанции («выйди из замаха -> войди на удар»), и обе вшивки урока (тяга
0.05 и 0.15) провалились с одной подписью: существо повторяло действия
человека, не видя, КОГДА человек их делал. 128x128 даёт 3-4 пикселя на
полблока.

КАК. Ствол зрения — NatureCNN: conv 8x8/4 -> 4x4/2 -> 3x3/1 -> Linear(1024).
Первое ядро растягиваем 8x8/4 -> 16x16/8: каждый вес размножаем 2x2 и делим
на 4. Позиции окон совпадают (старт p на 64 <-> старт 2p на 128), окон те же
15x15, поэтому выход первого слоя — ровно прежний, и остальную сеть не
трогаем. Следствие: новый мозг в момент операции математически тождествен
старому, смотрящему на усреднённую 2x2 картинку, — на ЛЮБОМ входе, не только
на статичном кадре (правило «новому — ноль, старому — всё» здесь звучит как
«новому — усреднение, старому — всё»). Тонкие детали 128 обучение нарастит
само.

Прошлый ожог «размножить и поделить» (память, dobavit_kanal.py) был про
размножение по КАНАЛАМ разных кадров — там смешалась семантика времени.
Здесь размножение по ПРОСТРАНСТВУ того же ядра — точная линейная алгебра.

ЧЕСТНОСТЬ ПРОВЕРОК. Офлайн-проверка ниже ловит ошибки ХИРУРГИИ (не тот ключ,
не тот делитель, забытый оптимизатор) — на растянутых кадрах тождество
обязано быть по построению, поэтому поведением она НЕ клянётся. Поведение
доказывает только живой замер: опора замороженным мозгом >=150 боёв на 128
против опоры 64 (простой 97.2%, мечник 49.1%). Настоящий рендер игры в 128,
усреднённый 2x2, не обязан совпасть с прежним рендером в 64 (мипмапы,
сглаживание) — вот где пересадка может честно провалиться.

Запуск: питон из ~/minecraft-ai/venv, из корня mc-lab-mod.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch as th
import gymnasium as gym
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).parent))
from telo import mir as M          # noqa: E402
from telo import kanaly as KAN     # noqa: E402
from telo.vshivka import stopki_po_otstupam  # noqa: E402
from telo.zrenie import GlazaShirokie  # noqa: E402

ROOT = Path(__file__).parent
MOZG = ROOT / "models" / "ppo_ubijca"
POKAZ = ROOT / "pokaz"
STARAYA = 64
NOVAYA = M.STORONA_KADRA           # 128 — мир уже переведён


class Mir128(gym.Env):
    """Заглушка с новыми пространствами: только чтобы собрать свежую сеть."""

    def __init__(self):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (3 * M.KADROV_V_PAMYATI, NOVAYA, NOVAYA),
                                  np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.MultiDiscrete(KAN.KANALY)

    def reset(self, *, seed=None, options=None):
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def logity(model, pov_nhwc, vec):
    """Логиты всех шести каналов решения + ценность."""
    obs_t, _ = model.policy.obs_to_tensor({"pov": pov_nhwc, "vec": vec})
    with th.no_grad():
        raspr = model.policy.get_distribution(obs_t).distribution
        cennost = model.policy.predict_values(obs_t)
    return [d.logits for d in raspr], cennost


def boevye_kadry():
    """Настоящие кадры игры из уроков показа — не случайный шум.

    Стопки по отступам памяти, как их видит мир. Проверка хирургии обязана
    идти на том распределении входов, где мозг работает.
    """
    fajly = sorted(POKAZ.glob("pokaz-*.npz")) or sorted((POKAZ / "staroe").glob("pokaz-*.npz"))
    if not fajly:
        raise SystemExit("Нет записей показа для проверки — нужен хотя бы один pokaz-*.npz")
    d = np.load(fajly[-1])
    pov, vec = d["pov"], d["vec"].astype(np.float32)
    if pov.shape[1] != STARAYA:
        raise SystemExit(f"Запись {fajly[-1].name} уже не {STARAYA}x{STARAYA} — "
                         "для проверки пересадки нужна старая запись")
    stopki = stopki_po_otstupam(pov)               # (N, 64, 64, 24)
    shag = max(1, len(stopki) // 256)
    return stopki[::shag][:256], vec[::shag][:256]


def main():
    staryj = PPO.load(MOZG, device="cpu")
    forma = tuple(staryj.observation_space["pov"].shape)
    if forma != (3 * M.KADROV_V_PAMYATI, STARAYA, STARAYA):
        raise SystemExit(f"Мозг не {STARAYA}x{STARAYA}x{3 * M.KADROV_V_PAMYATI} "
                         f"(а {forma}) — пересаживать нечего или уже пересажен")
    print(f"старый мозг: шагов {staryj.num_timesteps}, pov {forma}")

    # Геометрию 16x16/8 задаёт GlazaShirokie — класс уезжает в zip вместе с
    # мозгом (policy_kwargs), и PPO.load при любой будущей загрузке соберёт
    # сеть сразу правильной формы. Первая версия операции меняла модули руками
    # после создания — сохранялось, но не загружалось: load пересобирает сеть
    # штатной и падает на несовпадении форм.
    novyj = PPO("MultiInputPolicy", Mir128(), device="cpu", verbose=0,
                policy_kwargs={**staryj.policy_kwargs,
                               "features_extractor_class": GlazaShirokie})

    sd = dict(staryj.policy.state_dict())
    klyuchi = [k for k in sd if k.endswith("extractors.pov.cnn.0.weight")]
    if len(klyuchi) != 3:
        raise SystemExit(f"Ключей первого слоя {len(klyuchi)}, ожидал 3 — {klyuchi}")
    for k in klyuchi:
        w = sd[k]
        sd[k] = w.repeat_interleave(2, dim=2).repeat_interleave(2, dim=3) / 4.0
        print(f"растянул {k}: {tuple(w.shape)} -> {tuple(sd[k].shape)}")
    novyj.policy.load_state_dict(sd, strict=True)

    # ── Проверка хирургии на БОЕВЫХ кадрах (ловит ошибки резки, не поведение) ──
    stopki64, vec = boevye_kadry()
    stopki128 = np.repeat(np.repeat(stopki64, 2, axis=1), 2, axis=2)
    l_star, v_star = logity(staryj, stopki64, vec)
    l_nov, v_nov = logity(novyj, stopki128, vec)
    d_logit = max(float((a - b).abs().max()) for a, b in zip(l_star, l_nov))
    sovpalo = min(float((a.argmax(1) == b.argmax(1)).float().mean())
                  for a, b in zip(l_star, l_nov))
    d_v = float((v_star - v_nov).abs().max())
    print(f"боевых стопок: {len(stopki64)}; max|dLogit|={d_logit:.2e}, "
          f"худший канал argmax={sovpalo:.2%}, max|dV|={d_v:.2e}")
    if d_logit > 1e-3 or sovpalo < 0.9999:
        raise SystemExit("ПРОВАЛ ХИРУРГИИ: растянутый мозг разошёлся со старым "
                         "на растянутых кадрах — тождество по построению нарушено, "
                         "значит перенос сделан неверно. НЕ сохраняю.")

    novyj.num_timesteps = staryj.num_timesteps
    zapas = ROOT / "models" / f"do-zreniya-128-{staryj.num_timesteps}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    novyj.save(MOZG)
    print(f"старый мозг убран в {zapas.name}")
    print(f"мозг пересажен и сохранён: {MOZG.name}.zip, pov "
          f"{tuple(novyj.observation_space['pov'].shape)}, шагов {novyj.num_timesteps}")
    print("\nХирургия чистая. Поведение НЕ доказано — его доказывает только "
          "опора замороженным (>=150 боёв, lr=0) против опоры 64: "
          "простой 97.2%, мечник 49.1%.")


if __name__ == "__main__":
    main()
