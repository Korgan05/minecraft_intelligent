# -*- coding: utf-8 -*-
"""
ПРОВЕРКА ТОЛЬКО МЫШИ: какой способ поворачивает обзор в Minecraft.

Пробуем три способа подряд и после каждого спрашиваем у сервера, изменился ли
угол обзора. Врать нечем: угол берётся из самой игры.

Зачем три: Minecraft 1.16 умеет читать мышь напрямую с устройства («ввод без
обработки»), и тогда обычные приращения игра не видит — кнопки доходят, а
повороты нет. Именно это мы и поймали в первой проверке.

Перед запуском: щёлкни по окну Minecraft, будь В ИГРЕ (не в меню паузы)
и не трогай мышь. Проверка занимает секунд десять.

Запуск: mysh.bat
"""

import time

import arena as A
import konsol as K
import ruki as R
from proba_tela import polozhenie

SPOSOBY = [
    ("приращение через SendInput", R.myshka),
    ("сдвиг курсора Windows", R.myshka_kursorom),
    ("устаревший mouse_event", R.myshka_staraya),
]
SDVIG = 300          # заметно много, чтобы поворот нельзя было списать на дрожание


def main():
    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет. Зайди в игру и запусти снова.")
    print(f"игрок: {igrok}")
    print("\nЩЁЛКНИ ПО ОКНУ MINECRAFT и не трогай мышь.")
    for i in range(4, 0, -1):
        print(f"  начинаю через {i}...", flush=True)
        time.sleep(1)

    rabotaet = []
    print()
    for nazvanie, sposob in SPOSOBY:
        _, do = polozhenie(k, igrok)
        sposob(SDVIG, 0)
        time.sleep(0.6)
        _, posle = polozhenie(k, igrok)
        povorot = abs((posle[0] - do[0] + 180) % 360 - 180)
        ok = povorot > 3
        print(f"  {nazvanie:28s} угол {do[0]:7.1f} -> {posle[0]:7.1f} "
              f"| поворот {povorot:6.1f} гр -> {'РАБОТАЕТ' if ok else 'нет'}")
        if ok:
            rabotaet.append((nazvanie, povorot / SDVIG))
        time.sleep(0.4)

    k.close()
    print("\n=== ИТОГ ===")
    if not rabotaet:
        print("Ни один способ не повернул обзор.")
        print("Проверь в игре: Настройки -> Управление -> Настройки мыши ->")
        print("«Ввод без обработки» (Raw Input) должен быть ВЫКЛЮЧЕН.")
        print("И убедись, что ты в игре, а не в меню паузы (курсор должен быть скрыт).")
    else:
        for nazvanie, chuvst in rabotaet:
            print(f"  подходит: {nazvanie} | чувствительность {chuvst:.4f} градуса на единицу")
        print("\nБерём первый подходящий — существо сможет поворачиваться на нужный угол.")


if __name__ == "__main__":
    main()
