# -*- coding: utf-8 -*-
"""
ЗАПИСЬ ПОКАЗА в новой лаборатории: ты играешь ОБЫЧНО, а мы переводим твою игру
на язык существа.

Отличие от прошлой записи, где ты мучился: никакого окна 64x64 и никаких клавиш
J/L. Полный экран, нормальная мышь, свой клиент. Каждые 0.2 секунды мы:
  * снимаем кадр 64x64 — ровно то, что видит существо;
  * читаем зажатые физические клавиши и кнопку мыши;
  * спрашиваем у СЕРВЕРА, насколько повернулся твой обзор;
и складываем из этого одно из 12 действий существа.

Честная потеря: поворот у существа ступеньками по 15 градусов, поэтому доворот
на 5 градусов округлится до «не поворачивал». Крупные повороты запишутся точно.

Запуск: zapis.bat   (проба без сохранения: zapis.bat --proba)
Остановить: Ctrl+C. Запись сохраняется ПО ХОДУ, потерять игру нельзя.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from telo import arena as A
from telo import glaza as G
from telo import konsol as K
from telo import mir as M
from telo import ruki as R
from telo.arena import polozhenie

POROG_POVOROTA = 10.0                  # градусов за шаг, чтобы счесть поворот намеренным
OUT = Path(__file__).parent / "pokaz"
MAX_PODRYAD_STOYAT = 4
# Сохраняем ПО ХОДУ, а не в конце. Первая версия писала файл только после всех
# двадцати минут — и когда окно закрыли, вся игра пропала. Теперь худшее, что
# можно потерять, — последние полминуты.
SHAGOV_MEZHDU_SOHRANENIYAMI = 150      # 150 * 0.2 сек = 30 секунд


def sohranit(fajl, pov_l, vec_l, act_l, nag_l):
    if not act_l:
        return False
    np.savez_compressed(fajl, pov=np.stack(pov_l), vec=np.stack(vec_l),
                        act=np.asarray(act_l, dtype=np.int64),
                        nag=np.asarray(nag_l, dtype=np.float32))
    return True


def opredelit_dejstvie(d_yaw, d_pitch, klavishi, udar):
    """Игра человека -> номер действия существа.

    Сперва КРУПНЫЙ поворот (существу важнее всего научиться наводиться), затем
    удар, затем движение. Порог 10 градусов отсекает дрожь мыши, которую в
    ступеньки по 15 всё равно не перевести.
    """
    if abs(d_yaw) > POROG_POVOROTA:
        return 6 if d_yaw > 0 else 5
    if udar:
        return 11 if "W" in klavishi else 9
    if abs(d_pitch) > POROG_POVOROTA:
        return 8 if d_pitch > 0 else 7
    if "W" in klavishi and "SPACE" in klavishi:
        return 10
    if "SPACE" in klavishi:
        return 12                      # прыжок на месте: раньше падал в «стоять»
    for k, nomer in (("W", 1), ("S", 2), ("A", 3), ("D", 4)):
        if k in klavishi:
            return nomer
    return 0


def itog(act_l, nag_l, ubijstv, uron_vsego, fajl, sohranyat):
    n = len(act_l)
    print(f"\nнаиграно примеров: {n} | убийств: {ubijstv} | урона: {uron_vsego:.1f} HP")
    if n:
        act = np.asarray(act_l)
        print("разбивка:")
        for i, imya in enumerate(M.IMENA):
            kol = int((act == i).sum())
            if kol:
                print(f"   {imya:<16} {kol:5d}  ({100 * kol / n:5.1f}%)")
        povorotov = int(((act == 5) | (act == 6)).sum())
        if povorotov == 0:
            print("\nВНИМАНИЕ: поворотов НЕТ — а именно им существо и не научилось.")
        else:
            print(f"\nповоротов в уроке: {povorotov} — то, чего существу не хватало")
    if sohranyat and n:
        print(f"сохранено: {fajl}")
    elif not sohranyat:
        print("ПРОБА: ничего не сохранено.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proba", action="store_true", help="привыкаю: НЕ сохранять запись")
    p.add_argument("--minut", type=float, default=20.0, help="сколько минут записывать")
    args = p.parse_args()

    OUT.mkdir(exist_ok=True)
    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет — зайди в игру своим клиентом.")
    k.komandy(A.pravila_mira())
    k.komandy(A.schetchiki())
    k.komandy(A.postroit_zagon())
    k.komandy(A.podgotovit_bojca(igrok))
    k.komandy(A.sbros_boya(igrok))

    glaza, zagolovok, _ = G.glaza_na_okno("Minecraft")
    hwnd, _ = G.najti_okno("Minecraft")
    fajl = OUT / f"pokaz-{datetime.now():%Y%m%d-%H%M%S}.npz"

    print(f"игрок {igrok} | окно «{zagolovok}»")
    print(f"пиши {args.minut:g} минут. Остановить — Ctrl+C В ЭТОМ ОКНЕ.")
    print(f"сохраняю по ходу каждые 30 секунд -> {fajl.name}\n")
    print("Дерись обычно: подходи, наводись мышью, бей. Убил — призову нового.")
    print("ЩЁЛКНИ ПО ОКНУ MINECRAFT сейчас, иначе запись будет на паузе.\n")

    pov_l, vec_l, act_l, nag_l = [], [], [], []
    _, pred_rot = polozhenie(k, igrok)
    pred = A.sostoyanie(k, igrok)
    stoyal, ubijstv, uron_vsego = 0, 0, 0.0
    srok = time.perf_counter() + M.SEK_NA_SHAG
    konec = time.perf_counter() + args.minut * 60
    zhalovalsya = False

    try:
        while time.perf_counter() < konec:
            ostalos = srok - time.perf_counter()
            if ostalos > 0:
                time.sleep(ostalos)
            srok = time.perf_counter() + M.SEK_NA_SHAG

            if not R.okno_vperedi(hwnd):
                if not zhalovalsya:
                    print("  окно не впереди — запись на паузе, щёлкни по игре")
                    zhalovalsya = True
                time.sleep(0.3)
                continue
            zhalovalsya = False

            kadr = glaza.kadr_sushchestva()
            klavishi = {imya for imya in ("W", "A", "S", "D", "SPACE") if R.nazhimalas(imya)}
            udar = R.nazhimalas("MYSH_LEVAYA")   # щелчки короче шага — ловим и их

            s = A.sostoyanie(k, igrok)
            _, rot = polozhenie(k, igrok)
            d_yaw = (rot[0] - pred_rot[0] + 180) % 360 - 180
            d_pitch = rot[1] - pred_rot[1]
            pred_rot = rot

            dejstvie = opredelit_dejstvie(d_yaw, d_pitch, klavishi, udar)
            d_uron = max((s["uron"] or 0) - (pred["uron"] or 0), 0) / 10.0
            uron_vsego += d_uron
            if (s["ubijstva"] or 0) > (pred["ubijstva"] or 0):
                ubijstv += 1
                print(f"  *** убил зомби #{ubijstv} *** (записано {len(act_l)})")
            # Новая волна ТОЛЬКО когда все мертвы. Раньше призывал на первом же
            # убийстве — при трёх зомби это дало бы бесконечную подпитку: убил
            # одного, появились трое новых, недобитые остались, и загон забился бы.
            if not A.est_mobov(k):
                print(f"  --- волна зачищена, новые {A.ZOMBI_NA_ARENE} на арене ---")
                k.komandy(A.sbros_boya(igrok))
                time.sleep(0.4)
                s = A.sostoyanie(k, igrok)
                _, pred_rot = polozhenie(k, igrok)
            pred = s

            # «стоять» пишем не больше нескольких подряд: раздумья не должны стать уроком
            stoyal = stoyal + 1 if dejstvie == 0 else 0
            if dejstvie != 0 or stoyal <= MAX_PODRYAD_STOYAT:
                zhizn = s["zhizn"] if s["zhizn"] is not None else M.MAX_HEALTH
                pov_l.append(kadr.copy())
                vec_l.append(np.array([min(zhizn / M.MAX_HEALTH, 1.0),
                                       min(float(s.get("sytost") or 20.0) / 20.0, 1.0), 0.0,
                                       float(s.get("mob_ryadom", 1.0)), 0.0, 0.0],
                                      dtype=np.float32))
                act_l.append(dejstvie)
                nag_l.append(d_uron * M.ZA_HP_URONA)
                if d_uron > 0:
                    print(f"  попал: {d_uron:.1f} HP ({M.IMENA[dejstvie]}, "
                          f"записано {len(act_l)})")
                if not args.proba and len(act_l) % SHAGOV_MEZHDU_SOHRANENIYAMI == 0:
                    sohranit(fajl, pov_l, vec_l, act_l, nag_l)
                    print(f"  [сохранено по ходу: {len(act_l)} примеров]")
    except KeyboardInterrupt:
        print("\nостановлено вручную")
    finally:
        if not args.proba:
            sohranit(fajl, pov_l, vec_l, act_l, nag_l)
        try:
            glaza.close()
            k.close()
        except Exception:
            pass
        itog(act_l, nag_l, ubijstv, uron_vsego, fajl, not args.proba)


if __name__ == "__main__":
    main()
