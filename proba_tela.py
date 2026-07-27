# -*- coding: utf-8 -*-
"""
РЕШАЮЩАЯ ПРОВЕРКА ТЕЛА: дойдут ли наши глаза и руки до живой игры.

Хитрость проверки: мы не верим себе на слово. Нажимаем клавишу — и спрашиваем
у СЕРВЕРА через консоль, сдвинулся ли игрок. Двигаем мышь — и спрашиваем сервер,
повернулся ли обзор. Врать тут нечем: координаты и угол берутся из самой игры.

Перед запуском: щёлкни по окну Minecraft и НЕ трогай мышь с клавиатурой,
пока проверка идёт (около 20 секунд). Иначе ввод уйдёт не туда.

Запуск: proba.bat
"""

import time

import cv2
import numpy as np

import arena as A
import glaza as G
import konsol as K
import ruki as R


def polozhenie(k, igrok):
    """Координаты и угол обзора прямо из игры."""
    otvet = k.komanda(f"data get entity {igrok} Pos")
    chisla = [float(s.rstrip("d")) for s in otvet.replace("[", " ").replace("]", " ")
              .replace(",", " ").split() if s.rstrip("d").replace("-", "").replace(".", "").isdigit()]
    pos = chisla[-3:] if len(chisla) >= 3 else [0, 0, 0]
    otvet = k.komanda(f"data get entity {igrok} Rotation")
    ugly = [float(s.rstrip("f")) for s in otvet.replace("[", " ").replace("]", " ")
            .replace(",", " ").split() if s.rstrip("f").replace("-", "").replace(".", "").isdigit()]
    rot = ugly[-2:] if len(ugly) >= 2 else [0, 0]
    return pos, rot


def main():
    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет. Зайди в игру и запусти проверку снова.")
    print(f"игрок: {igrok}")

    g, zagolovok, oblast = G.glaza_na_okno("Minecraft")
    print(f"окно: «{zagolovok}» | область {oblast}")

    print("\nЩЁЛКНИ ПО ОКНУ MINECRAFT и не трогай мышь с клавиатурой.")
    for i in range(5, 0, -1):
        print(f"  начинаю через {i}...", flush=True)
        time.sleep(1)

    itogi = {}

    # ── 1. ГЛАЗА ──
    kadr = g.kadr_sushchestva()
    yarkost = float(kadr.mean())
    raznoobrazie = float(kadr.std())
    itogi["глаза"] = raznoobrazie > 8      # чёрный или однотонный экран дал бы почти ноль
    print(f"\n1. ГЛАЗА: кадр {kadr.shape}, яркость {yarkost:.1f}, разброс {raznoobrazie:.1f} "
          f"-> {'ВИДИТ' if itogi['глаза'] else 'ПУСТО (окно перекрыто?)'}")
    cv2.imwrite("proba-glaza.png",
                cv2.cvtColor(cv2.resize(kadr, (256, 256), interpolation=cv2.INTER_NEAREST),
                             cv2.COLOR_RGB2BGR))

    # ── 2. НОГИ: клавиша W должна сдвинуть игрока ──
    do, _ = polozhenie(k, igrok)
    R.nazhat("W")
    time.sleep(1.2)
    R.otpustit("W")
    time.sleep(0.3)
    posle, _ = polozhenie(k, igrok)
    sdvig = ((posle[0] - do[0]) ** 2 + (posle[2] - do[2]) ** 2) ** 0.5
    itogi["ноги"] = sdvig > 0.5
    print(f"2. НОГИ: было ({do[0]:.1f},{do[2]:.1f}) стало ({posle[0]:.1f},{posle[2]:.1f}), "
          f"прошёл {sdvig:.2f} блока -> {'ИДУТ' if itogi['ноги'] else 'НЕ РАБОТАЮТ'}")

    # ── 3. ШЕЯ: мышь должна повернуть обзор ──
    _, do_ugl = polozhenie(k, igrok)
    R.myshka(300, 0)
    time.sleep(0.5)
    _, posle_ugl = polozhenie(k, igrok)
    povorot = abs((posle_ugl[0] - do_ugl[0] + 180) % 360 - 180)
    itogi["шея"] = povorot > 3
    print(f"3. ШЕЯ: угол был {do_ugl[0]:.1f}, стал {posle_ugl[0]:.1f}, "
          f"повернулся на {povorot:.1f} градуса -> {'ВЕРТИТСЯ' if itogi['шея'] else 'НЕ РАБОТАЕТ'}")
    if itogi["шея"]:
        print(f"   чувствительность: {povorot / 300:.4f} градуса на единицу мыши")

    # ── 4. РУКА: удар должен нанести урон зомби ──
    k.komanda("kill @e[type=zombie]")
    zx, zy, zz = A.ZOMBIE_SPOT
    k.komanda(f"summon minecraft:zombie {zx} {zy} {zz} "
              '{PersistenceRequired:1b,CanPickUpLoot:0b,Health:20f}')
    k.komanda(f"tp {igrok} 0.5 4 0.5 0 0")
    k.komanda(f"scoreboard players set {igrok} {A.SCHET_URON} 0")
    time.sleep(0.7)
    for _ in range(4):
        R.udar()
        time.sleep(0.7)                    # пауза, чтобы меч накопил замах
    time.sleep(0.5)
    uron = k.chislo_scoreboard(igrok, A.SCHET_URON) or 0
    itogi["рука"] = uron > 0
    print(f"4. РУКА: 4 удара -> урон по счётчику игры {uron} "
          f"({uron / 10:.1f} здоровья) -> {'БЬЁТ' if itogi['рука'] else 'НЕ ДОСТАЁТ'}")

    R.otpustit_vse()
    g.close()
    k.close()

    print("\n=== ИТОГ ===")
    for chto, ok in itogi.items():
        print(f"  {chto:8s} {'работает' if ok else 'НЕ РАБОТАЕТ'}")
    if all(itogi.values()):
        print("\nТЕЛО ГОТОВО. Существо может видеть и действовать без MineRL.")
    else:
        print("\nЧего-то не хватает — разберём по пунктам.")


if __name__ == "__main__":
    main()
