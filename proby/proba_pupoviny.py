# -*- coding: utf-8 -*-
"""
ПРОВЕРКА ПУПОВИНЫ: правда ли мод даёт существу глаза и руки.

Проверяем не на слово, а сверкой с сервером — как и прежде. Мод говорит «я
повернул на 90 градусов», а мы спрашиваем у сервера, на сколько повернулся
игрок на самом деле. Врать тут нечем.

Отдельно проверяем ГЛАВНОЕ обещание мода: работает ли он, когда окно игры НЕ
впереди. Ради этого всё и затевалось.

Запуск: zapusk\\proba-pupoviny.bat
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telo import arena as A
from telo import konsol as K
from telo import pupovina as P
from telo.arena import polozhenie

KUDA = Path(__file__).resolve().parent.parent / "proba-pupoviny"


def uvesti_fokus():
    """Пробуем сами перевести фокус на панель задач.

    Нужно, чтобы проверку «без фокуса» можно было прогнать без человека.
    Windows не всегда отдаёт фокус по просьбе чужой программы, поэтому
    результат обязательно перепроверяем у мода, а не верим вызову.
    """
    try:
        import ctypes
        u = ctypes.windll.user32
        for klass in ("Shell_TrayWnd", "Progman"):
            hwnd = u.FindWindowW(klass, None)
            if hwnd and u.SetForegroundWindow(hwnd):
                return True
    except Exception:
        pass
    return False


def ugol_raznica(bylo, stalo):
    return (stalo - bylo + 180) % 360 - 180


def sohranit(kadr, imya):
    KUDA.mkdir(exist_ok=True)
    krupno = cv2.resize(kadr, (256, 256), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(KUDA / imya), cv2.cvtColor(krupno, cv2.COLOR_RGB2BGR))


def main():
    itogi = {}
    p = P.Pupovina()
    print("мод отвечает:", p.ping())

    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет — зайди клиентом на 127.0.0.1.")
    print(f"игрок: {igrok}")
    # Те же условия, в каких живёт существо: меч, 40 здоровья, правила мира.
    k.komandy(A.pravila_mira())
    k.komandy(A.schetchiki())
    k.komandy(A.podgotovit_bojca(igrok))

    # ── 1. ГЛАЗА ──
    o = p.shag()
    # Открытое меню — не поломка мода, а состояние игры: клавиши в нём не
    # разбираются вовсе. Первый прогон об этом не знал и обвинил ноги и руку.
    if o["menyu"]:
        print("\nВ ИГРЕ ОТКРЫТО МЕНЮ — в меню игра не слушает клавиши, проверять нечего.")
        print("ЩЁЛКНИ ПО ОКНУ MINECRAFT и вернись в мир. Жду до пяти минут.")
        print("Дальше можешь спокойно уйти Alt+Tab — но НЕ нажимай Escape.")
        konec = time.perf_counter() + 300
        while o["menyu"] and time.perf_counter() < konec:
            time.sleep(0.5)
            o = p.shag()
        if o["menyu"]:
            sohranit(o["kadr"], "0-menyu.png")
            raise SystemExit("меню так и не закрылось — прерываю")
        print("меню закрыто, продолжаю\n")
        time.sleep(1.0)
        o = p.shag()
    kadr = o["kadr"]
    itogi["глаза"] = bool(o["v_mire"]) and float(kadr.std()) > 8
    print(f"\n1. ГЛАЗА: кадр {kadr.shape}, яркость {kadr.mean():.1f}, "
          f"разброс {kadr.std():.1f}, в мире: {o['v_mire']} "
          f"-> {'ВИДИТ' if itogi['глаза'] else 'ПУСТО'}")
    print(f"   приборы мода: здоровье {o['zhizn']:.0f}/{o['max_zhizn']:.0f}, "
          f"сытость {o['sytost']:.0f}, взгляд {o['yaw']:.1f}/{o['pitch']:.1f}")
    sohranit(kadr, "1-glaza.png")

    # Приборы мода обязаны сойтись с сервером — иначе мод показывает выдумку.
    s = A.sostoyanie(k, igrok)
    raznica = abs((s["zhizn"] or 0) - o["zhizn"])
    itogi["приборы"] = raznica < 1.0
    print(f"   сверка с сервером: у сервера {s['zhizn']}, у мода {o['zhizn']:.0f}, "
          f"расхождение {raznica:.1f} -> {'СХОДИТСЯ' if itogi['приборы'] else 'ВРЁТ'}")

    # ── 2. ШЕЯ: поворот должен быть ТОЧНЫМ ──
    print("\n2. ШЕЯ: прошу ровные градусы и спрашиваю сервер, что вышло")
    oshibki = []
    for zakaz in (90.0, -45.0, 5.0, -5.0, 180.0):
        _, do = polozhenie(k, igrok)
        p.shag(dyaw=zakaz)
        time.sleep(0.35)                      # даём тику примениться и долететь
        _, posle = polozhenie(k, igrok)
        vyshlo = ugol_raznica(do[0], posle[0])
        oshibka = abs(ugol_raznica(zakaz, vyshlo))
        oshibki.append(oshibka)
        print(f"   просил {zakaz:+7.1f}  вышло {vyshlo:+7.1f}  ошибка {oshibka:.2f}")
    itogi["шея"] = max(oshibki) < 0.5
    print(f"   худшая ошибка {max(oshibki):.2f} градуса "
          f"-> {'ТОЧНО' if itogi['шея'] else 'МИМО'}")

    # ── 3. НОГИ ──
    do_xyz, _ = polozhenie(k, igrok)
    for _ in range(6):                        # 6 шагов по 0.2 сек = чуть больше секунды
        p.shag(vpered=1)
        time.sleep(0.2)
    p.shag()
    time.sleep(0.3)
    posle_xyz, _ = polozhenie(k, igrok)
    proshel = ((posle_xyz[0] - do_xyz[0]) ** 2 + (posle_xyz[2] - do_xyz[2]) ** 2) ** 0.5
    itogi["ноги"] = proshel > 0.5
    print(f"\n3. НОГИ: прошёл {proshel:.2f} блока "
          f"-> {'ИДУТ' if itogi['ноги'] else 'НЕ РАБОТАЮТ'}")

    # ── 4. РУКА ──
    k.komanda("kill @e[tag=boec]")
    zx, zy, zz = A.ZOMBIE_SPOT
    k.komanda(f"summon minecraft:zombie {zx} {zy} {zz} {A.nbt_moba()}")
    k.komanda(f"tp {igrok} 0.5 4 0.5 0 0")
    k.komanda(f"scoreboard players set {igrok} {A.SCHET_URON} 0")
    time.sleep(0.8)
    o = p.shag()
    sohranit(o["kadr"], "4-pered-udarom.png")
    # Спрашиваем саму игру, куда смотрит прицел: «урона нет» — это следствие,
    # а причин десяток. Первый разбор без этого ушёл в гадание.
    print(f"   до удара: {p.diag()}")
    for _ in range(4):
        p.shag(udar=1)
        time.sleep(0.7)                       # пауза на замах меча
    print(f"   после ударов: {p.diag()}")
    time.sleep(0.5)
    uron = k.chislo_scoreboard(igrok, A.SCHET_URON) or 0
    itogi["рука"] = uron > 0
    print(f"4. РУКА: 4 удара -> урон {uron / 10:.1f} здоровья "
          f"-> {'БЬЁТ' if itogi['рука'] else 'НЕ ДОСТАЁТ'}")

    # ── 5. СКОРОСТЬ ──
    n = 40
    nachalo = time.perf_counter()
    for _ in range(n):
        p.shag()
    proshlo = time.perf_counter() - nachalo
    v_sekundu = n / proshlo
    itogi["скорость"] = v_sekundu > 5.0       # шаг существа 0.2 сек, значит нужно 5+
    print(f"\n5. СКОРОСТЬ: {n} обменов за {proshlo:.2f} сек = {v_sekundu:.1f} в секунду "
          f"({1000 * proshlo / n:.0f} мс на шаг) "
          f"-> {'ХВАТАЕТ' if itogi['скорость'] else 'МЕДЛЕННО'}")

    # ── 6. ГЛАВНОЕ: работает ли БЕЗ фокуса окна ──
    print("\n6. БЕЗ ФОКУСА — ради этого всё и делалось.")
    if uvesti_fokus():
        time.sleep(1.5)
    o = p.shag()
    if o["fokus"]:
        print("   сам увести фокус не смог — ПЕРЕКЛЮЧИСЬ НА ДРУГОЕ ОКНО и жди.")
        for i in range(8, 0, -1):
            print(f"     проверяю через {i}...", flush=True)
            time.sleep(1)
        o = p.shag()
    if o["fokus"]:
        print("   окно всё ещё впереди — проверку пропускаю (переключись и запусти снова)")
        itogi["без фокуса"] = None
    else:
        _, do = polozhenie(k, igrok)
        p.shag(dyaw=90.0)
        time.sleep(0.35)
        _, posle = polozhenie(k, igrok)
        vyshlo = ugol_raznica(do[0], posle[0])
        o2 = p.shag()
        kadr_zhivoj = float(o2["kadr"].std()) > 8
        povernulsya = abs(ugol_raznica(90.0, vyshlo)) < 1.0
        itogi["без фокуса"] = kadr_zhivoj and povernulsya
        sohranit(o2["kadr"], "6-bez-fokusa.png")
        print(f"   поворот без фокуса: просил +90, вышло {vyshlo:+.1f}")
        print(f"   кадр без фокуса: разброс {o2['kadr'].std():.1f} "
              f"({'живой' if kadr_zhivoj else 'ПУСТОЙ'})")
        print(f"   -> {'РАБОТАЕТ БЕЗ ФОКУСА' if itogi['без фокуса'] else 'НУЖЕН ФОКУС'}")

    p.close()
    k.close()

    print("\n=== ИТОГ ===")
    for chto, ok in itogi.items():
        znak = "пропущено" if ok is None else ("работает" if ok else "НЕ РАБОТАЕТ")
        print(f"  {chto:12s} {znak}")
    print(f"\nкадры сохранены в {KUDA}")
    plohie = [c for c, ok in itogi.items() if ok is False]
    if not plohie:
        print("ПУПОВИНА РАБОТАЕТ. Существо может жить через мод.")
    else:
        print("Не работает: " + ", ".join(plohie))


if __name__ == "__main__":
    main()
