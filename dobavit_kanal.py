# -*- coding: utf-8 -*-
"""
ДОРАСТИТЬ ГОЛОВУ под новый канал. Игра не нужна.

Когда в чертёж (kanaly.py) дописывается новый канал — бег, а позже способности
стенда, — у головы мозга становится больше выходов. Здесь это делается один раз
и с проверкой.

Главное правило, добытое дорого: НОВОМУ ДАЁМ ПОЧТИ НОЛЬ. Именно на этом я уже
ошибался дважды. Память я добавил, размножив веса и поделив на четыре — на
движении получилась каша, и существо перестало находить цель. Размахи поворота
добавил, скопировав веса у соседа — желание «доверни на 15» размазалось на
четыре величины, три из которых перелетают.

Поэтому у нового канала веса нулевые, а смещение подобрано так, чтобы вначале
он почти всегда выбирал «ничего». Существо продолжит вести себя в точности как
раньше, а обучение нарастит новое само, если оно окажется полезным.

Проверка строгая и провалиться может: решения по СТАРЫМ каналам обязаны
совпасть с прежними ТОЧНО, а новый канал должен молчать почти всегда.

Запуск: zapusk\\dobavit-kanal.bat
"""

import glob
import shutil
from datetime import datetime
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO

from telo import kanaly as KAN

ROOT = Path(__file__).parent
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
KADROV_V_PAMYATI = 4
KUSOK = 128
# Насколько реже новое выбирается вначале. Разница смещений в 4 даёт примерно
# 2% против 98% — редко, но не никогда: обучение сможет это нащупать.
PEREVES = 4.0
DOLYA_NOVOGO_PREDEL = 0.10       # если новое выбирается чаще — операция неудачна


class PustoyMir(gym.Env):
    """Мир-заглушка: нужен только чтобы объявить вид входа и выхода."""

    def __init__(self, kanaly):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (64, 64, 3 * KADROV_V_PAMYATI), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.MultiDiscrete(kanaly)

    def reset(self, *, seed=None, options=None):
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def kadry_iz_zapisej(skolko=1500):
    """Настоящие кадры твоей игры: на них и проверяем."""
    stopki, veki = [], []
    for f in sorted(glob.glob(str(ROOT / "pokaz" / "*.npz"))):
        d = np.load(f)
        pov, vec = d["pov"], d["vec"]
        for i in range(KADROV_V_PAMYATI, len(pov)):
            stopki.append(np.concatenate(
                [pov[i - KADROV_V_PAMYATI + 1 + j] for j in range(KADROV_V_PAMYATI)],
                axis=2))
            veki.append(vec[i])
            if len(stopki) >= skolko:
                return np.stack(stopki), np.stack(veki)
    return np.stack(stopki), np.stack(veki)


def vybor(model, stopki, veki):
    """Что мозг выбирает по каждому каналу."""
    kuski = []
    for n in range(0, len(stopki), KUSOK):
        obs = {"pov": stopki[n:n + KUSOK], "vec": veki[n:n + KUSOK]}
        obs_t, _ = model.policy.obs_to_tensor(obs)
        with torch.no_grad():
            raspr = model.policy.get_distribution(obs_t).distribution
            kuski.append(torch.stack([d.probs.argmax(dim=1) for d in raspr],
                                     dim=1).cpu().numpy())
    return np.concatenate(kuski)


def main():
    staryj = PPO.load(MOZG, device="cpu")
    bylo = list(int(x) for x in staryj.action_space.nvec)
    stalo = list(KAN.KANALY)
    print(f"мозг: {staryj.num_timesteps} шагов")
    print(f"каналов было: {bylo}")
    print(f"каналов надо: {stalo}")
    if bylo == stalo:
        raise SystemExit("Голова уже нужного вида — доращивать нечего.")
    if len(stalo) <= len(bylo) or stalo[:len(bylo)] != bylo:
        raise SystemExit("Каналы изменились НЕ дописыванием в конец. Так нельзя: "
                         "сдвинутся выходы, и голова начнёт отвечать не то.")
    novye = stalo[len(bylo):]
    print(f"дописываю каналов: {novye} "
          f"({', '.join(KAN.IMENA_KANALOV[len(bylo):])})")

    stopki, veki = kadry_iz_zapisej()
    print(f"кадров для проверки: {len(stopki)}")
    bylo_vybrano = vybor(staryj, stopki, veki)

    novyj = PPO("MultiInputPolicy", PustoyMir(stalo), device="cpu",
                policy_kwargs=staryj.policy_kwargs, learning_rate=staryj.learning_rate,
                n_steps=staryj.n_steps, batch_size=staryj.batch_size,
                n_epochs=staryj.n_epochs, gamma=staryj.gamma,
                gae_lambda=staryj.gae_lambda, ent_coef=staryj.ent_coef,
                vf_coef=staryj.vf_coef, max_grad_norm=staryj.max_grad_norm, verbose=0)

    sd_s = staryj.policy.state_dict()
    perenos = {k: v for k, v in sd_s.items() if not k.startswith("action_net")}
    itog = novyj.policy.load_state_dict(perenos, strict=False)
    ne_hvatilo = [k for k in itog.missing_keys if not k.startswith("action_net")]
    if itog.unexpected_keys or ne_hvatilo:
        raise SystemExit(f"Перенос неполный: {itog.unexpected_keys} / {ne_hvatilo}")

    # Старые выходы — как были, слово в слово. Новые — нулевые веса, а смещение
    # такое, чтобы «ничего» побеждало почти всегда.
    with torch.no_grad():
        w = torch.zeros_like(novyj.policy.action_net.weight)
        b = torch.zeros_like(novyj.policy.action_net.bias)
        staroe_chislo = sum(bylo)
        w[:staroe_chislo] = sd_s["action_net.weight"]
        b[:staroe_chislo] = sd_s["action_net.bias"]
        mesto = staroe_chislo
        for skolko in novye:
            b[mesto] = PEREVES / 2          # «ничего» в новом канале
            for i in range(1, skolko):
                b[mesto + i] = -PEREVES / 2
            mesto += skolko
        novyj.policy.action_net.weight.copy_(w)
        novyj.policy.action_net.bias.copy_(b)

    stalo_vybrano = vybor(novyj, stopki, veki)
    starye_sovpali = float((stalo_vybrano[:, :len(bylo)] == bylo_vybrano).all(axis=1).mean())
    dolya_novogo = [float((stalo_vybrano[:, len(bylo) + i] != 0).mean())
                    for i in range(len(novye))]

    print(f"\n=== ПРОВЕРКА ===")
    print(f"  решения по старым каналам совпали: {100 * starye_sovpali:.2f}%")
    for i, imya in enumerate(KAN.IMENA_KANALOV[len(bylo):]):
        print(f"  новый канал «{imya}» включается: {100 * dolya_novogo[i]:.1f}% шагов")

    if starye_sovpali < 0.9999:
        raise SystemExit("\nСТАРОЕ ПОВЕДЕНИЕ ИЗМЕНИЛОСЬ. Так быть не должно: "
                         "дописывание канала не имеет права его касаться. НЕ сохраняю.")
    if max(dolya_novogo) > DOLYA_NOVOGO_PREDEL:
        raise SystemExit(f"\nНовый канал включается слишком часто — существо начнёт "
                         f"делать то, чему не училось. НЕ сохраняю.")

    novyj.num_timesteps = staryj.num_timesteps
    zapas = MODELI / f"do-kanala-{len(bylo) + 1}-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    novyj.save(MOZG)
    print(f"\nпрежний отложен: {zapas.name}")
    print(f"мозг сохранён   : {MOZG.name}.zip ({novyj.num_timesteps} шагов)")
    print("\nСтарое поведение сохранено слово в слово. Новое пока почти не")
    print("используется — его нарастит показ и обучение.")


if __name__ == "__main__":
    main()
