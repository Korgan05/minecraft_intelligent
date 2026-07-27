# -*- coding: utf-8 -*-
"""
ЗАМЕР ПОВОРОТА: сколько градусов даёт какой сдвиг мыши.

Зачем: существо поворачивается «на миллиметр», хотя по расчёту должно на 15
градусов. Подозрение — ускорение мыши в Windows делает связь НЕЛИНЕЙНОЙ: мелкие
сдвиги подавляются, крупные усиливаются. Чувствительность я мерил на сдвиге 300,
а существу даю 100 — и если связь нелинейна, мой расчёт неверен.

Правду спрашиваем у сервера: угол обзора берётся из самой игры.

Перед запуском: щёлкни по окну Minecraft, будь В ИГРЕ, не трогай мышь.
Запуск: povorot.bat
"""

import time

import arena as A
import konsol as K
import ruki as R
from proba_tela import polozhenie

SDVIGI = [10, 25, 50, 100, 150, 200, 300, 600]
POVTOROV = 3


def main():
    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет — зайди в игру.")
    print(f"игрок: {igrok}")
    print("\nЩЁЛКНИ ПО ОКНУ MINECRAFT и не трогай мышь.")
    for i in range(4, 0, -1):
        print(f"  начинаю через {i}...", flush=True)
        time.sleep(1)

    print("\n сдвиг | получилось градусов | градусов на единицу")
    itogi = []
    for sdvig in SDVIGI:
        gradusy = []
        for _ in range(POVTOROV):
            _, do = polozhenie(k, igrok)
            R.myshka(sdvig, 0)
            time.sleep(0.35)
            _, posle = polozhenie(k, igrok)
            gradusy.append(abs((posle[0] - do[0] + 180) % 360 - 180))
            time.sleep(0.15)
        sred = sum(gradusy) / len(gradusy)
        na_edinicu = sred / sdvig
        itogi.append((sdvig, sred, na_edinicu))
        print(f"  {sdvig:5d} | {sred:19.1f} | {na_edinicu:.4f}   "
              f"(замеры: {', '.join(f'{g:.0f}' for g in gradusy)})")

    k.close()
    print("\n=== ВЫВОД ===")
    linejno = all(abs(t[2] - itogi[-1][2]) < itogi[-1][2] * 0.25 for t in itogi if t[1] > 1)
    if linejno:
        print("Связь ЛИНЕЙНАЯ — ускорение не мешает, дело в другом.")
    else:
        print("Связь НЕЛИНЕЙНАЯ: мелкие сдвиги подавляются ускорением мыши.")
        print("Значит мой расчёт «100 единиц = 15 градусов» неверен.")
    # какой сдвиг нужен для 15 и для 30 градусов
    for cel in (15, 30, 45):
        podhodyat = [t for t in itogi if t[1] >= cel]
        if podhodyat:
            t = min(podhodyat, key=lambda t: t[1])
            print(f"  для {cel} градусов нужен сдвиг около {t[0]} (даёт {t[1]:.0f})")
        else:
            print(f"  для {cel} градусов ни один из проверенных сдвигов не хватает")


if __name__ == "__main__":
    main()
