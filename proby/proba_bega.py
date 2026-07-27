# -*- coding: utf-8 -*-
"""
ПРОВЕРКА БЕГА. Две разные вещи, и вторая важнее.

1. ВИДИТ ЛИ МОД ТВОЙ БЕГ. Нужно для записи показа: если признак не приходит,
   урок «удар в спринте» запишется без спринта, и пять минут игры уйдут впустую.

2. БЕГАЕТ ЛИ САМО СУЩЕСТВО, когда мод просит. Это важнее: на бег мы завели целый
   канал, и если он ничего не делает, существо будет тратить на него решения даром.
   Проверяем не по признаку, а ПО ПРОЙДЕННОМУ РАССТОЯНИЮ — шагом около 4.3 блока
   в секунду, бегом около 5.6. Признак мог бы врать, расстояние не врёт.

Запуск: zapusk\\proba-bega.bat
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telo import arena as A
from telo import konsol as K
from telo import pupovina as P
from telo.arena import polozhenie

SHAGOV = 6              # 6 * 0.2 сек = 1.2 секунды пути

# ОТКУДА И КУДА БЕЖАТЬ. Первая версия этой пробы ставила существо в угол
# (-4,-4) и разворачивала на +45 — а это направление В СТЕНУ: угол 45 в игре
# смотрит на -X и +Z, то есть из угла наружу загона. Существо тёрлось об стену,
# спринт от этого гаснет, и проба объявила бег сломанным. Числа выдавали ошибку
# сразу: бегом получилось МЕНЬШЕ, чем шагом.
#
# Из угла (-4,-4) свободно на +X и +Z, это направление даёт угол -45.
# По диагонали загона выходит 11.3 блока — хватает и шагом, и бегом.
UGOL_STARTA = (-4, 4, -4)
YAW_STARTA = -45


def projti(p, k, igrok, bezhat):
    """Пройти вперёд по прямой и измерить путь у сервера."""
    p.shag()                                  # снять всё лишнее
    time.sleep(0.3)
    do, _ = polozhenie(k, igrok)
    for _ in range(SHAGOV):
        p.shag(vpered=1, bezhat=1 if bezhat else 0)
        time.sleep(0.2)
    o = p.sostoyanie()
    p.shag()
    time.sleep(0.3)
    posle, _ = polozhenie(k, igrok)
    put = ((posle[0] - do[0]) ** 2 + (posle[2] - do[2]) ** 2) ** 0.5
    return put, o["bezhit"]


def proverit_tvoj_beg(p, itogi):
    print("1. ВИДИТ ЛИ МОД ТВОЙ БЕГ")
    print("   Щёлкни по игре и БЕГИ вперёд (W + Ctrl, или двойной W). Жду 12 секунд.")
    uvidel = False
    konec = time.perf_counter() + 12
    while time.perf_counter() < konec:
        if p.sostoyanie()["bezhit"]:
            uvidel = True
            break
        time.sleep(0.3)
    itogi["твой бег"] = uvidel
    print(f"   -> {'ВИДИТ' if uvidel else 'НЕ ВИДИТ — записывать урок бесполезно'}")


def main():
    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет.")
    p = P.Pupovina()
    itogi = {}
    tolko_sushchestvo = "--bez-menya" in sys.argv

    # ── 1. видит ли мод ТВОЙ бег ──
    if not tolko_sushchestvo:
        proverit_tvoj_beg(p, itogi)

    # ── 2. бегает ли существо ──
    print("\n2. БЕГАЕТ ЛИ САМО СУЩЕСТВО (мерим путь, а не признак)")
    print("   Не трогай управление, освободи место — существо пойдёт по прямой.")
    k.komanda("kill @e[tag=boec]")
    for i in range(3, 0, -1):
        print(f"     начинаю через {i}...", flush=True)
        time.sleep(1)

    x, y, z = UGOL_STARTA
    k.komanda(f"tp {igrok} {x} {y} {z} {YAW_STARTA} 0")
    time.sleep(0.6)
    shagom, priznak_shagom = projti(p, k, igrok, False)
    k.komanda(f"tp {igrok} {x} {y} {z} {YAW_STARTA} 0")
    time.sleep(0.6)
    begom, priznak_begom = projti(p, k, igrok, True)

    print(f"   шагом: прошёл {shagom:.2f} блока, признак бега {priznak_shagom}")
    print(f"   бегом: прошёл {begom:.2f} блока, признак бега {priznak_begom}")
    bystree = begom > shagom * 1.15
    itogi["бег существа"] = bool(bystree and priznak_begom)
    if not priznak_begom:
        print("   -> игра НЕ считает существо бегущим: канал бега пустой")
    elif not bystree:
        print(f"   -> признак есть, но быстрее не стало ({begom / max(shagom, 0.01):.2f}x)")
    else:
        print(f"   -> БЕГАЕТ, быстрее в {begom / max(shagom, 0.01):.2f} раза")

    p.close()
    k.close()
    print("\n=== ИТОГ ===")
    for chto, ok in itogi.items():
        print(f"  {chto:<14} {'работает' if ok else 'НЕ РАБОТАЕТ'}")
    if all(itogi.values()):
        print("\nБег в порядке. Можно записывать урок с ударом в спринте.")
    else:
        print("\nЕсть поломка — разберём до записи, чтобы не тратить игру впустую.")


if __name__ == "__main__":
    main()
