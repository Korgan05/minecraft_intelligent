# -*- coding: utf-8 -*-
"""
ПРОВЕРКА ПАМЯТИ на записанных кадрах. Игра НЕ нужна, мозг не меняется.

Подозрение на самого себя. Память я добавил так: размножил веса первого слоя на
четыре кадра и поделил их на четыре. Проверил тогда на НЕПОДВИЖНОМ кадре — и
получил расхождение решений 0.000000. Но на неподвижном кадре такое деление
тождественно ПО ПОСТРОЕНИЮ: четыре одинаковых кадра, поделённые на четыре, дают
ровно исходный. То есть проверка не могла провалиться и ничего не проверяла.

На движении всё иначе: четыре кадра разные, и первый слой видит их СРЕДНЕЕ —
смазанную кашу. При шаге 0.2 секунды и развороте на 45 градусов соседние кадры
почти не похожи, значит каша полная.

Сравниваем на настоящих записанных кадрах:
  * мозг с памятью на ЧЕТЫРЁХ ОДИНАКОВЫХ кадрах (как в той пустой проверке);
  * тот же мозг на ЧЕТЫРЁХ ПОДРЯД ИДУЩИХ кадрах — то есть как в бою;
  * мозг ДО операции, на одном кадре — то самое, что убивало в 97% боёв.
Если на одинаковых он ведёт себя разумно, а на подряд идущих начинает крутиться,
виновата операция, а не мод.

Запуск: zapusk\\proverit-pamyat.bat
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from telo import mir as M

OBRAZCOV = 400


def zapis():
    fajly = sorted((ROOT / "pokaz").glob("*.npz"))
    if not fajly:
        raise SystemExit("Нет записей показа в pokaz/")
    d = np.load(fajly[-1])
    return d["pov"], d["vec"], d["act"], fajly[-1].name


def reshit(mozg, pov_stopka, vec):
    nabl = {"pov": np.transpose(pov_stopka, (0, 3, 1, 2)), "vec": vec}
    d, _ = mozg.predict(nabl, deterministic=True)
    return np.asarray(d).flatten()


def razbivka(imya, dejstviya, imena):
    s = Counter(imena[int(d)] for d in dejstviya)
    print(f"\n{imya}")
    for chto, skolko in s.most_common(5):
        print(f"   {chto:<18} {skolko:4d}  ({100 * skolko / len(dejstviya):5.1f}%)")
    povorotov = sum(k for c, k in s.items() if "povorot" in c or "RAZVOROT" in c
                    or "chetvert" in c or "KRUGOM" in c or "dovodka" in c)
    udarov = sum(k for c, k in s.items() if "UDAR" in c or "bit" in c)
    print(f"   -> поворотов {100 * povorotov / len(dejstviya):.0f}%, "
          f"ударов {100 * udarov / len(dejstviya):.0f}%")
    return povorotov / len(dejstviya)


def main():
    pov, vec, act, imya = zapis()
    n = min(OBRAZCOV, len(pov) - M.KADROV_V_PAMYATI)
    print(f"запись: {imya} | беру {n} мест из {len(pov)}")
    # Берём места, где ЧЕЛОВЕК бил: там цель точно была перед носом.
    mesta = [i for i in range(M.KADROV_V_PAMYATI, len(pov)) if act[i] in (9, 11)][:n]
    if len(mesta) < 20:
        mesta = list(range(M.KADROV_V_PAMYATI, M.KADROV_V_PAMYATI + n))
    print(f"мест, где человек бил: {len(mesta)}")
    mesta = np.array(mesta)

    odinakovye = np.stack([np.concatenate([pov[i]] * M.KADROV_V_PAMYATI, axis=2)
                           for i in mesta])
    podryad = np.stack([np.concatenate(
        [pov[i - M.KADROV_V_PAMYATI + 1 + j] for j in range(M.KADROV_V_PAMYATI)], axis=2)
        for i in mesta])
    v = vec[mesta]

    mozg = PPO.load(ROOT / "models" / "ppo_ubijca", device="cpu")
    print(f"\nмозг с памятью: {mozg.num_timesteps} шагов, "
          f"вход {mozg.observation_space['pov'].shape}")
    dolya_odin = razbivka("на ЧЕТЫРЁХ ОДИНАКОВЫХ кадрах (та самая пустая проверка):",
                          reshit(mozg, odinakovye, v), M.IMENA)
    dolya_podryad = razbivka("на ЧЕТЫРЁХ ПОДРЯД ИДУЩИХ кадрах (как в бою):",
                             reshit(mozg, podryad, v), M.IMENA)

    staryj_put = ROOT / "models" / "do-pamyati-20260727-111639"
    if staryj_put.with_suffix(".zip").exists():
        staryj = PPO.load(staryj_put, device="cpu")
        print(f"\nмозг ДО операции: {staryj.num_timesteps} шагов, "
              f"вход {staryj.observation_space['pov'].shape}")
        odin_kadr = np.stack([pov[i] for i in mesta])
        dolya_do = razbivka("на ОДНОМ кадре (как он и жил, убивая в 97% боёв):",
                            reshit(staryj, odin_kadr, v), M.IMENA)
    else:
        dolya_do = None

    print("\n=== ВЫВОД ===")
    print(f"поворотов на одинаковых кадрах : {100 * dolya_odin:.0f}%")
    print(f"поворотов на подряд идущих     : {100 * dolya_podryad:.0f}%")
    if dolya_do is not None:
        print(f"поворотов у мозга до операции  : {100 * dolya_do:.0f}%")
    if dolya_podryad - dolya_odin > 0.2:
        print("\nОперация с памятью и виновата: на движении мозг теряет цель,")
        print("потому что первый слой усредняет четыре разных вида в кашу.")
    elif dolya_do is not None and dolya_odin - dolya_do > 0.2:
        print("\nОперация испортила мозг сразу, ещё до всякого движения.")
    else:
        print("\nПамять не виновата — ищем дальше.")


if __name__ == "__main__":
    main()
