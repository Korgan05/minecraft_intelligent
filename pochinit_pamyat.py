# -*- coding: utf-8 -*-
"""
ПОЧИНКА ПАМЯТИ. Игра не нужна.

Что я сделал не так. Добавляя память, я размножил веса первого слоя на четыре
кадра и поделил их на четыре. Проверил на НЕПОДВИЖНОМ кадре — расхождение
0.000000. Но на четырёх одинаковых кадрах такое деление тождественно ПО
ПОСТРОЕНИЮ, и провалиться проверка не могла: она ничего не проверяла.

На движении первый слой считает СРЕДНЕЕ четырёх разных видов. При шаге 0.2 секунды
и развороте на 45 градусов соседние кадры почти не похожи, значит на входе каша.
Замер на записанных кадрах: ударов стало 15% вместо 50%, поворотов 78% вместо 41%.
В живом бою — 7 смертей из 8 при девяти победах из десяти прежде.

Как надо было. Добавляя вход, старому отдают ВСЁ, а новому — НОЛЬ. Тогда мозг
ведёт себя в точности как раньше на любом входе, неподвижном и движущемся, а
нули обучение нарастит само, если память окажется полезной.

Здесь так и делаем: весь исходный вес — самому свежему кадру (последние три
канала), трём старым кадрам — нули.

Проверка строгая: после починки решения на ЧЕТЫРЁХ ПОДРЯД ИДУЩИХ кадрах обязаны
СОВПАСТЬ с решениями мозга до операции на самом свежем кадре. Не «почти», а
ровно — иначе починка неверна.

Запуск: zapusk\\pochinit-pamyat.bat
"""

import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO

ROOT = Path(__file__).parent
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
DO_PAMYATI = MODELI / "do-pamyati-20260727-111639"
KADROV = 4
OBRAZCOV = 300


def stopki_iz_zapisi():
    """Настоящие кадры из записи показа: и стопки по четыре, и свежий отдельно."""
    fajly = sorted((ROOT / "pokaz").glob("*.npz"))
    if not fajly:
        return None, None, None
    d = np.load(fajly[-1])
    pov, vec, act = d["pov"], d["vec"], d["act"]
    mesta = [i for i in range(KADROV, len(pov)) if act[i] in (9, 11)][:OBRAZCOV]
    if len(mesta) < 20:
        mesta = list(range(KADROV, KADROV + OBRAZCOV))
    mesta = np.array(mesta)
    podryad = np.stack([np.concatenate([pov[i - KADROV + 1 + j] for j in range(KADROV)],
                                       axis=2) for i in mesta])
    svezhij = np.stack([pov[i] for i in mesta])
    return podryad, svezhij, vec[mesta]


def reshit(mozg, pov, vec):
    d, _ = mozg.predict({"pov": np.transpose(pov, (0, 3, 1, 2)), "vec": vec},
                        deterministic=True)
    return np.asarray(d).flatten()


def main():
    mozg = PPO.load(MOZG, device="cpu")
    sd = mozg.policy.state_dict()
    sloi = [k for k, v in sd.items() if v.dim() == 4 and v.shape[1] == 3 * KADROV]
    if not sloi:
        raise SystemExit("Слоёв с четырьмя кадрами на входе нет — чинить нечего.")
    print(f"мозг: {mozg.num_timesteps} шагов | слоёв с памятью: {len(sloi)}")

    podryad, svezhij, vec = stopki_iz_zapisi()
    if podryad is None:
        raise SystemExit("Нет записей показа — проверить починку будет нечем.")
    do_pochinki = reshit(mozg, podryad, vec)

    # ── сама починка ──
    novye = {}
    for k in sloi:
        w = sd[k]
        # Каждый из четырёх блоков равен исходному ядру, поделённому на четыре.
        ishodnoe = w[:, 3 * (KADROV - 1):] * float(KADROV)
        n = torch.zeros_like(w)
        n[:, 3 * (KADROV - 1):] = ishodnoe        # всё — самому свежему кадру
        novye[k] = n
        print(f"  {k}: старым кадрам нули, свежему полный вес "
              f"(сумма |весов| {float(ishodnoe.abs().sum()):.1f})")
    sd.update(novye)
    mozg.policy.load_state_dict(sd)

    # ── строгая проверка ──
    posle = reshit(mozg, podryad, vec)
    if not DO_PAMYATI.with_suffix(".zip").exists():
        raise SystemExit("Нет мозга до операции — сверить не с чем, не сохраняю.")
    staryj = PPO.load(DO_PAMYATI, device="cpu")
    obrazec = reshit(staryj, svezhij, vec)

    sovpalo = float((posle == obrazec).mean())
    menyalos = float((posle != do_pochinki).mean())
    print(f"\nрешений совпало с мозгом до операции: {100 * sovpalo:.2f}%")
    print(f"решений изменилось починкой          : {100 * menyalos:.1f}%")
    if sovpalo < 0.999:
        raise SystemExit(f"ПОЧИНКА НЕВЕРНА: совпало лишь {100 * sovpalo:.1f}%. "
                         "Мозг НЕ сохраняю.")

    zapas = MODELI / f"slomannaya-pamyat-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    mozg.save(MOZG)
    print(f"\nсломанный вариант отложен: {zapas.name}")
    print(f"починенный мозг сохранён : {MOZG.name}.zip")
    print("\nТеперь память есть, но пока не используется: три старых кадра входят")
    print("с нулевым весом. Обучение нарастит их само, если они окажутся полезны.")


if __name__ == "__main__":
    main()
