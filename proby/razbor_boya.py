# -*- coding: utf-8 -*-
"""
РАЗБОР БОЯ: что существо делает и видит ли цель. БЕЗ обучения — мозг не меняется.

Зачем. Через мод существо стало убивать раз в восемь боёв вместо девяти из десяти.
Мозг тот же, действия те же, экономика та же. Причин может быть три: не видит цель,
видит но не наводится, наводится но не бьёт. Со стороны питона они выглядят
одинаково — «урона нет». Поэтому спрашиваем саму игру, что у неё в прицеле, и
сверяем с тем, какое действие выбрало существо.

Запуск: zapusk\\razbor-boya.bat
"""

import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telo import mir as M

SHAGOV = 250


def main():
    mozg = PPO.load(Path(__file__).resolve().parent.parent / "models" / "ppo_ubijca",
                    device="cuda")
    mir = M.Bojnya()
    mir.zhdat_gotovnosti()

    obs, _ = mir.reset()
    scheta = Counter()
    v_pricele = 0
    udarov = 0
    udarov_po_celi = 0
    zdorovye = []
    boev, ubijstv, smertej = 0, 0, 0

    print(f"\nразбираю {SHAGOV} шагов. Обучения НЕТ, мозг не изменится.\n")
    for shag in range(SHAGOV):
        # Мозг ждёт наблюдение в том же виде, что и при обучении: словарь с
        # картинкой в порядке «канал, высота, ширина».
        nabl = {"pov": np.transpose(obs["pov"], (2, 0, 1))[None],
                "vec": obs["vec"][None]}
        dejstvie, _ = mozg.predict(nabl, deterministic=True)
        dejstvie = int(np.asarray(dejstvie).flatten()[0])
        scheta[M.IMENA[dejstvie]] += 1

        diag = mir.p.diag()
        cel_v_pricele = "pricel=ENTITY" in diag
        v_pricele += 1 if cel_v_pricele else 0
        bil = bool(M.DEJSTVIYA[dejstvie].get("udar"))
        if bil:
            udarov += 1
            udarov_po_celi += 1 if cel_v_pricele else 0

        obs, nagrada, gotovo, obrezan, info = mir.step(dejstvie)
        zdorovye.append(info.get("zhizn", 0.0))
        if info.get("kill"):
            ubijstv += 1
        if info.get("death"):
            smertej += 1
        if gotovo or obrezan:
            boev += 1
            obs, _ = mir.reset()

    mir.close()

    print("=== ЧТО ВЫБИРАЛО СУЩЕСТВО ===")
    for imya, skolko in scheta.most_common():
        print(f"  {imya:<18} {skolko:4d}  ({100 * skolko / SHAGOV:5.1f}%)")
    print()
    print("=== ВИДЕЛО ЛИ ЦЕЛЬ ===")
    print(f"  зомби был в прицеле: {v_pricele} из {SHAGOV} шагов "
          f"({100 * v_pricele / SHAGOV:.1f}%)")
    print(f"  ударов всего       : {udarov}")
    if udarov:
        print(f"  из них по цели     : {udarov_po_celi} "
              f"({100 * udarov_po_celi / udarov:.1f}%)")
    print()
    print("=== ИТОГ ===")
    print(f"  боёв {boev} | убийств {ubijstv} | смертей {smertej}")
    if zdorovye:
        print(f"  здоровье: в среднем {np.mean(zdorovye):.1f}, "
              f"минимум {np.min(zdorovye):.0f}, максимум {np.max(zdorovye):.0f}")
    print()
    print("Как читать. Если зомби почти никогда не в прицеле — существо не видит")
    print("или не наводится: дело в картинке. Если в прицеле часто, а ударов мало —")
    print("дело в выборе действий. Если ударов много и по цели, а урона нет —")
    print("дело в самом ударе.")


if __name__ == "__main__":
    main()
