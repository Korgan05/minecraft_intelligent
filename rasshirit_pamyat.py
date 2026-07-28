# -*- coding: utf-8 -*-
"""
РАСШИРИТЬ ПАМЯТЬ: четыре кадра -> восемь. Игра не нужна.

Зачем. Память на четыре кадра это 0.8 секунды, а полный оборот вокруг себя
существо делает за 1.6 — то есть к концу разворота оно уже забыло начало и не
может знать, что сзади никого. Мысль человека: оно потому и вертится без конца.

Что убедило меня взяться. Вес памяти в первом слое зрения рос сам, без подсказок:
0% сразу после починки, потом 5.4%, 16%, 19.8%, 23%. Причём вес СВЕЖЕГО кадра
не менялся (560.0 -> 562.0) — значит память нарастала СВЕРХУ, не отбирая
внимания у настоящего. Существо само вложило в прошлое почти четверть зрения.

ГЛАВНОЕ ПРАВИЛО, добытое дорого: НОВОМУ ДАЁМ НОЛЬ, СТАРОМУ ОСТАВЛЯЕМ ВСЁ.
Именно на этом я дважды ошибался. Память в первый раз добавил, размножив веса и
поделив на четыре — на движении получилась каша, и существо перестало находить
цель (ударов 15% вместо 50%, семь смертей из восьми боёв). Размахи поворота
добавил копированием весов соседа — желание доворота размазалось на четыре
величины, три из которых перелетают.

Правильный приём сработал уже дважды: так добавлен канал бега (старое поведение
совпало 100.00%, новый канал начал с нуля и оброс сам) и так же исправлена
память. Здесь делаем то же: четыре НОВЫХ кадра входят с нулевым весом, четыре
прежних сохраняют свои веса до последней цифры.

Порядок кадров важен: свежий последний. Значит новые (более старые) кадры
встают В НАЧАЛО, а прежние веса сдвигаются в конец.

Проверка строгая и провалиться может: решения на настоящих кадрах твоей игры
обязаны совпасть со старым мозгом РОВНО. Не «почти» — иначе не сохраняем.

Запуск: zapusk\\rasshirit-pamyat.bat
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
BYLO_KADROV = 4
STALO_KADROV = 8
KUSOK = 64
OBRAZCOV = 600


class PustoyMir(gym.Env):
    """Мир-заглушка: нужен только чтобы объявить вид входа и выхода."""

    def __init__(self, kadrov):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (64, 64, 3 * kadrov), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.MultiDiscrete(KAN.KANALY)

    def reset(self, *, seed=None, options=None):
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def kadry_iz_zapisej():
    """Настоящие кадры твоей игры: на них и проверяем.

    Собираем сразу две стопки одного и того же мгновения — на четыре кадра для
    старого мозга и на восемь для нового. Свежий кадр в обеих один и тот же.
    """
    chetyre, vosem, veki = [], [], []
    for f in sorted(glob.glob(str(ROOT / "pokaz" / "*.npz"))):
        d = np.load(f)
        pov, vec = d["pov"], d["vec"]
        for i in range(STALO_KADROV, len(pov)):
            chetyre.append(np.concatenate(
                [pov[i - BYLO_KADROV + 1 + j] for j in range(BYLO_KADROV)], axis=2))
            vosem.append(np.concatenate(
                [pov[i - STALO_KADROV + 1 + j] for j in range(STALO_KADROV)], axis=2))
            veki.append(vec[i])
            if len(veki) >= OBRAZCOV:
                return np.stack(chetyre), np.stack(vosem), np.stack(veki)
    return np.stack(chetyre), np.stack(vosem), np.stack(veki)


def vybor(model, pov, vec):
    """Что мозг выбирает по каждому каналу."""
    kuski = []
    for n in range(0, len(pov), KUSOK):
        obs_t, _ = model.policy.obs_to_tensor({"pov": pov[n:n + KUSOK],
                                               "vec": vec[n:n + KUSOK]})
        with torch.no_grad():
            raspr = model.policy.get_distribution(obs_t).distribution
            kuski.append(torch.stack([d.probs.argmax(dim=1) for d in raspr],
                                     dim=1).cpu().numpy())
    return np.concatenate(kuski)


def main():
    staryj = PPO.load(MOZG, device="cpu")
    kanalov = staryj.observation_space["pov"].shape[0]
    print(f"мозг: {staryj.num_timesteps} шагов, зрение {staryj.observation_space['pov'].shape}")
    if kanalov != 3 * BYLO_KADROV:
        raise SystemExit(f"Ожидал {3 * BYLO_KADROV} каналов зрения, а их {kanalov}. "
                         "Похоже, память уже другого размера.")

    print("\nберу настоящие кадры из твоих записей...")
    chetyre, vosem, veki = kadry_iz_zapisej()
    print(f"  кадров для сверки: {len(veki)}")
    bylo_vybrano = vybor(staryj, chetyre, veki)

    novyj = PPO("MultiInputPolicy", PustoyMir(STALO_KADROV), device="cpu",
                policy_kwargs=staryj.policy_kwargs, learning_rate=staryj.learning_rate,
                n_steps=staryj.n_steps, batch_size=staryj.batch_size,
                n_epochs=staryj.n_epochs, gamma=staryj.gamma,
                gae_lambda=staryj.gae_lambda, ent_coef=staryj.ent_coef,
                vf_coef=staryj.vf_coef, max_grad_norm=staryj.max_grad_norm, verbose=0)

    sd_s = staryj.policy.state_dict()
    # Переносим всё, кроме первого слоя зрения: у него изменилось число входов.
    pervyj = [k for k, v in sd_s.items() if v.dim() == 4 and v.shape[1] == kanalov]
    if not pervyj:
        raise SystemExit("Не нашёл первый слой зрения — операция небезопасна.")
    print(f"  слоёв зрения на входе: {len(pervyj)}")
    perenos = {k: v for k, v in sd_s.items() if k not in pervyj}
    itog = novyj.policy.load_state_dict(perenos, strict=False)
    ne_hvatilo = [k for k in itog.missing_keys if k not in pervyj]
    if itog.unexpected_keys or ne_hvatilo:
        raise SystemExit(f"Перенос неполный: {itog.unexpected_keys} / {ne_hvatilo}")

    # Первый слой: прежние веса уходят в КОНЕЦ (свежие кадры), новым — нули.
    #
    # Через набор весов целиком, а не по отдельным слоям: три имени
    # (features_extractor, pi_features_extractor, vf_features_extractor) — это
    # ОДИН И ТОТ ЖЕ слой под тремя ярлыками, и по имени он не достаётся.
    sd_n = novyj.policy.state_dict()
    for imya in pervyj:
        n = torch.zeros_like(sd_n[imya])
        n[:, -kanalov:] = sd_s[imya]          # прежние четыре кадра — в конец
        sd_n[imya] = n
    novyj.policy.load_state_dict(sd_n)
    print(f"  четыре НОВЫХ кадра вошли с нулевым весом, прежние сохранены")

    stalo_vybrano = vybor(novyj, vosem, veki)
    sovpalo = float((stalo_vybrano == bylo_vybrano).all(axis=1).mean())
    po_kanalam = (stalo_vybrano == bylo_vybrano).mean(axis=0)

    print(f"\n=== ПРОВЕРКА на {len(veki)} кадрах твоей игры ===")
    for imya, dolya in zip(KAN.IMENA_KANALOV, po_kanalam):
        print(f"  {imya:<9} совпало {100 * dolya:6.2f}%")
    print(f"  ВСЕ ШЕСТЬ СРАЗУ  {100 * sovpalo:6.2f}%")

    if sovpalo < 0.9999:
        raise SystemExit(
            "\nПОВЕДЕНИЕ ИЗМЕНИЛОСЬ. Так быть не должно: добавление кадров не имеет "
            "права его касаться, новые входят с нулём. Мозг НЕ сохраняю.")

    novyj.num_timesteps = staryj.num_timesteps
    zapas = MODELI / f"do-pamyati-{STALO_KADROV}-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    novyj.save(MOZG)
    print(f"\nпрежний отложен: {zapas.name}")
    print(f"мозг сохранён   : {MOZG.name}.zip ({novyj.num_timesteps} шагов)")
    print(f"\nПамять теперь {STALO_KADROV} кадров = {STALO_KADROV * 0.2:.1f} секунды —")
    print("ровно один полный оборот вокруг себя.")
    print(f"\nТЕПЕРЬ ОБЯЗАТЕЛЬНО: поставь KADROV_V_PAMYATI = {STALO_KADROV} в telo/mir.py,")
    print("иначе мир будет подавать четыре кадра там, где мозг ждёт восемь.")


if __name__ == "__main__":
    main()
