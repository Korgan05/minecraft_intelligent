# -*- coding: utf-8 -*-
"""
РАЗБОР РАЗВАЛА: почему существо разучивается. Игра не нужна.

Зачем понадобился. Дважды за сутки существо съезжало: за ночь с 92% убийств до
19%, и потом за 57 боёв с 100% до 42%. Я оба раза винил экономику награды и
четыре раза менял в ней числа — три правки навредили. Замер, которого не хватало,
делается в одну строку: НАГРАДА ЗА БОЙ ВОССТАНАВЛИВАЕТСЯ ИЗ ЛЕНТЫ. И она
ПАДАЛА вместе с убийствами (+12.8 -> -10.8 за ночь, +15 -> -33 за 57 боёв).

Это решает спор. Кто пользуется дырой в правилах, получает БОЛЬШЕ награды —
на том дыры и находят. Кто получает меньше, тот просто разучивается. Значит
виновата не арифметика награды, а само обучение.

Здесь три мерки, каждая может провалиться:

1. СКОЛЬКО МОЗГ ПРОХОДИТ ЗА ОДНО ОБНОВЛЕНИЕ. Считаем долю решений, изменившихся
   между соседними снимками (1000 шагов друг от друга) на настоящих кадрах твоей
   игры. Если за 1000 шагов меняется четверть решений — политику швыряет, и дело
   в скорости обучения, а не в награде.

2. КУДА СМЕЩАЕТСЯ ВЫБОР. Для каждого канала смотрим, какое значение существо
   стало выбирать чаще. Развал в сторону «стоять» и «не бить» — это уход в
   бездействие; в сторону разброса — это давление бонуса за неуверенность.

3. ВИНОВАТЫ ЛИ СВЕЖИЕ ВЕСА ПАМЯТИ. Обнуляем в испорченном мозге те входные
   каналы, которые вошли нулём при расширении памяти. Если решения возвращаются
   к прежним — виноваты они. Если нет — виновато остальное.

Запуск: zapusk\\razbor-razvala.bat
"""

import argparse
import glob
import re
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO

from telo import kanaly as KAN
from telo import mir as M

ROOT = Path(__file__).parent.parent
OBRAZCOV = 400
KUSOK = 64


def kadry():
    """Настоящие кадры твоей игры, собранные так же, как их видит существо."""
    pov, vec = [], []
    for f in sorted(glob.glob(str(ROOT / "pokaz" / "*.npz"))):
        d = np.load(f)
        p, v = d["pov"], d["vec"]
        for i in range(M.GLUBINA_BUFERA, len(p)):
            pov.append(np.concatenate([p[i - o] for o in M.OTSTUPY_PAMYATI], axis=2))
            vec.append(v[i])
            if len(vec) >= OBRAZCOV:
                return np.stack(pov), np.stack(vec)
    return np.stack(pov), np.stack(vec)


def vybor(model, pov, vec):
    kuski = []
    for n in range(0, len(pov), KUSOK):
        t, _ = model.policy.obs_to_tensor({"pov": pov[n:n + KUSOK], "vec": vec[n:n + KUSOK]})
        with torch.no_grad():
            r = model.policy.get_distribution(t).distribution
            kuski.append(torch.stack([d.probs.argmax(dim=1) for d in r], dim=1).cpu().numpy())
    return np.concatenate(kuski)


def snimki(ot, do):
    out = []
    for f in glob.glob(str(ROOT / "models" / "ubijca_ckpt_*_steps.zip")):
        sh = int(re.search(r"_(\d+)_steps", f)[1])
        if ot <= sh <= do:
            out.append((sh, f[:-4]))
    return sorted(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ot", type=int, default=279_000)
    p.add_argument("--do", type=int, default=286_000)
    p.add_argument("--horoshij", default="models/ppo_ubijca")
    p.add_argument("--slomannyj", default="models/cherepaha-285095-10smertej")
    args = p.parse_args()

    pov, vec = kadry()
    print(f"кадров твоей игры для сверки: {len(vec)}\n")

    spisok = snimki(args.ot, args.do)
    if len(spisok) < 2:
        print(f"снимков в промежутке {args.ot}..{args.do} меньше двух — мерку 1 пропускаю")
    else:
        print("=== 1. СКОЛЬКО МЕНЯЕТСЯ ЗА 1000 ШАГОВ ===")
        pred_v, pred_sh = None, None
        for sh, f in spisok:
            m = PPO.load(f, device="cpu")
            if m.observation_space["pov"].shape[0] != 3 * M.KADROV_V_PAMYATI:
                continue                     # снимок другого размера памяти
            v = vybor(m, pov, vec)
            if pred_v is not None:
                menya = 100 * (1 - (v == pred_v).all(axis=1).mean())
                po_kan = "  ".join(
                    f"{i}:{100 * (1 - (v[:, k] == pred_v[:, k]).mean()):4.1f}%"
                    for k, i in enumerate(KAN.IMENA_KANALOV))
                print(f"  {pred_sh} -> {sh}: изменилось {menya:5.1f}% решений   {po_kan}")
            pred_v, pred_sh = v, sh

    print("\n=== 2. КУДА СМЕЩАЕТСЯ ВЫБОР ===")
    horoshij = PPO.load(args.horoshij, device="cpu")
    slomannyj = PPO.load(args.slomannyj, device="cpu")
    A, B = vybor(horoshij, pov, vec), vybor(slomannyj, pov, vec)
    print(f"  хороший ({horoshij.num_timesteps}) против испорченного "
          f"({slomannyj.num_timesteps}): совпало {100 * (A == B).all(axis=1).mean():.2f}%")
    for k, imya in enumerate(KAN.IMENA_KANALOV):
        bylo = np.bincount(A[:, k], minlength=KAN.KANALY[k])
        stalo = np.bincount(B[:, k], minlength=KAN.KANALY[k])
        print(f"  {imya:<9} было  {bylo}")
        print(f"  {'':<9} стало {stalo}")

    print("\n=== 3. ВИНОВАТЫ ЛИ СВЕЖИЕ ВЕСА ПАМЯТИ ===")
    novyh = 3 * (M.KADROV_V_PAMYATI // 2)     # расширение вдвое: свежими вошла первая половина
    sd = slomannyj.policy.state_dict()
    imena = [k for k, v in sd.items()
             if v.dim() == 4 and v.shape[1] == 3 * M.KADROV_V_PAMYATI]
    if not imena:
        raise SystemExit("не нашёл первый слой зрения")
    for im in imena:
        v = sd[im].clone()
        v[:, :novyh] = 0.0
        sd[im] = v
    slomannyj.policy.load_state_dict(sd)
    C = vybor(slomannyj, pov, vec)
    print(f"  испорченный с обнулёнными новыми кадрами против хорошего: "
          f"{100 * (A == C).all(axis=1).mean():.2f}%")
    print(f"  само обнуление сдвинуло его решения на "
          f"{100 * (1 - (B == C).all(axis=1).mean()):.2f}%")
    print("\n  Как читать: если во второй строке цифра ЗАМЕТНО выше, чем совпадение")
    print("  в мерке 2, то развал шёл через свежие веса памяти. Если нет — они не")
    print("  при чём, и виноваты остальные веса, то есть обычное забывание.")


if __name__ == "__main__":
    main()
