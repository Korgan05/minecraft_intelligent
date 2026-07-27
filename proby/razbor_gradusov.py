# -*- coding: utf-8 -*-
"""
РАЗБОР ГРАДУСОВ: как поворачивает человек и что из этого теряет существо.

У существа поворот ступенчатый — десять величин: 0, ±5, ±15, ±45, ±90 и «кругом».
Человек же ведёт мышь непрерывно. Запись хранит и то, и другое: выбранную
ступеньку и НАСТОЯЩЕЕ число градусов.

Здесь мы смотрим, насколько ступеньки огрубляют твою игру. Если ошибка мелкая —
десяти величин достаточно. Если крупная — стоит дать существу непрерывный
поворот, и тогда переписывать уроки не придётся: точные числа уже сохранены.

Игра не нужна. Запуск: zapusk\\razbor-gradusov.bat
"""

import glob
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from telo import kanaly as KAN


def stupenka(gradusov):
    """Какую ступеньку выберет запись для этого настоящего поворота."""
    if abs(gradusov) > 135:
        return 180.0
    return min(KAN.POVOROT, key=lambda g: abs(gradusov - g) if g != 180.0 else 1e9)


def main():
    fajly = [f for f in sorted(glob.glob(str(ROOT / "pokaz" / "*.npz")))
             if "gradus" in np.load(f)]
    if not fajly:
        raise SystemExit("Нет записей с точными градусами — они появились только "
                         "в новых уроках.")

    vse = []
    print("уроки с точными градусами:")
    for f in fajly:
        g = np.load(f)["gradus"][:, 0]
        vse.append(g)
        krutil = np.abs(g[np.abs(g) > 0.5])
        print(f"  {Path(f).name:<38} {len(g):5d} шагов, "
              f"поворотов {len(krutil):5d}, среднее {krutil.mean():5.1f} гр")
    g = np.concatenate(vse)
    a = np.abs(g)
    krutil = a[a > 0.5]
    n = len(krutil)

    print(f"\nвсего шагов: {len(g)}, из них с поворотом: {n}")
    print("\nКАК ТЫ ПОВОРАЧИВАЕШЬ (настоящие градусы за шаг 0.2 сек):")
    granicy = [0.5, 2.5, 5, 10, 20, 35, 60, 100, 140, 181]
    for niz, verh in zip(granicy[:-1], granicy[1:]):
        k = int(((krutil >= niz) & (krutil < verh)).sum())
        if k:
            polosa = "#" * max(1, round(60 * k / n))
            print(f"  {niz:5.1f}-{verh:<5.0f} гр  {k:5d} {100 * k / n:5.1f}%  {polosa}")

    print("\nЧТО ТЕРЯЕТСЯ НА СТУПЕНЬКАХ:")
    vybrano = np.array([stupenka(x) for x in g])
    oshibka = np.abs(np.abs(g) - np.abs(vybrano))
    ok = oshibka[a > 0.5]
    print(f"  ошибка округления: в среднем {ok.mean():.2f} гр, "
          f"худшая {ok.max():.1f} гр")
    for porog in (1, 2, 5, 10):
        print(f"  поворотов, где ошибка меньше {porog:2d} гр: "
              f"{100 * float((ok < porog).mean()):5.1f}%")

    print("\nСКОЛЬКО НАКАПЛИВАЕТСЯ ЗА БОЙ:")
    # Ошибки не гасят друг друга: они одного знака, если ты ведёшь мышь в одну
    # сторону. За семьдесят шагов боя это может увести прицел заметно.
    znak = np.sign(g)
    smeshchenie = (np.abs(g) - np.abs(vybrano)) * znak
    print(f"  за 70 шагов (средний бой) в худшем случае "
          f"{np.abs(smeshchenie).sum() / len(g) * 70:.1f} градуса")

    print("\nВЫВОД:")
    if ok.mean() < 3:
        print("  Ступеньки огрубляют мало — десяти величин существу хватает.")
    else:
        print("  Ступеньки огрубляют заметно. Непрерывный поворот дал бы существу")
        print("  точность человека, и уроки для этого уже готовы.")


if __name__ == "__main__":
    main()
