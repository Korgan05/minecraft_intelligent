# -*- coding: utf-8 -*-
"""
ЗАПИСЬ ПОКАЗА: ты играешь обычно, а мы переводим твою игру на язык существа.

Что изменилось против прошлой записи, и это важно.

1. КАДР БЕРЁТСЯ ИЗ МОДА, а не с рабочего стола. Значит ты и существо смотрите
   одними глазами буквально, а не почти. Окно можно не держать поверх других.

2. ПОВОРОТ СОХРАНЯЕТСЯ ПО ВЕЛИЧИНЕ. Прошлая запись мерила настоящие градусы, но
   потом их выбрасывала: всё крупнее 10 градусов писалось как 15, мельче — как
   «не поворачивал». В трёх твоих записях размахи 45, 90 и «кругом» встречаются
   РОВНО НОЛЬ раз из 4329 кадров — разворот на 180 записан как лёгкий доворот.
   Теперь выбирается ближайшая из настоящих величин.

3. ДВИЖЕНИЕ И ПОВОРОТ ПИШУТСЯ ВМЕСТЕ. Раньше выбиралось ОДНО действие на шаг, и
   поворот был важнее движения: идёшь боком и доворачиваешь — сохранялся только
   доворот. Именно это делало невозможным показать кружение вокруг цели с
   удержанием прицела. Теперь пишутся все пять частей решения сразу.

Дерись как обычно. Хочешь научить держать прицел — кружи вокруг зомби боком,
не отпуская его из виду: теперь это ляжет в урок целиком.

Запуск: zapusk\\zapis.bat   (проба без сохранения: zapis.bat --proba)
Остановить: Ctrl+C. Запись сохраняется ПО ХОДУ, потерять игру нельзя.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from telo import arena as A
from telo import glaza as G
from telo import kanaly as KAN
from telo import konsol as K
from telo import mir as M
from telo import pupovina as P
from telo import ruki as R

OUT = Path(__file__).parent / "pokaz"
MAX_PODRYAD_STOYAT = 4
# Сохраняем ПО ХОДУ, а не в конце. Первая версия писала файл только после всех
# двадцати минут — и когда окно закрыли, вся игра пропала. Теперь худшее, что
# можно потерять, — последние полминуты.
SHAGOV_MEZHDU_SOHRANENIYAMI = 150      # 150 * 0.2 сек = 30 секунд


def sohranit(fajl, pov_l, vec_l, act_l, nag_l, grad_l):
    if not act_l:
        return False
    # ТОЧНЫЕ ГРАДУСЫ храним рядом со ступеньками. Мозгу сейчас нужны ступеньки —
    # его канал поворота выбирает из десяти величин. Но если позже дадим ему
    # НЕПРЕРЫВНЫЙ поворот, чтобы он вертелся так же плавно, как человек, — уроки
    # переписывать не придётся: точные числа уже здесь.
    np.savez_compressed(fajl, pov=np.stack(pov_l), vec=np.stack(vec_l),
                        act=np.asarray(act_l, dtype=np.int64),
                        nag=np.asarray(nag_l, dtype=np.float32),
                        gradus=np.asarray(grad_l, dtype=np.float32))
    return True


def blizhajshaya(gradusov, velichiny, krugom=False):
    """Ближайшая настоящая величина к тому, на сколько ты повернул.

    Ноль побеждает сам собой, когда поворот мелкий: до 2.5 градусов он ближе к
    нулю, чем к пятёрке. Отдельного порога не нужно — и хорошо, потому что
    именно порогом прошлая запись и выбрасывала мелкую доводку.
    """
    if krugom and abs(gradusov) > 135:
        return velichiny.index(180.0)
    return min((abs(gradusov - g), i) for i, g in enumerate(velichiny)
               if not (krugom and g == 180.0))[1]


def opredelit_reshenie(d_yaw, d_pitch, klavishi, udar):
    """Твоя игра -> решение существа по пяти каналам.

    Ничего больше не теряется: идёшь боком с доворотом и бьёшь — все три части
    сохранятся вместе.
    """
    nogi = frozenset(kl for kl in ("W", "S", "A", "D") if kl in klavishi)
    nomer_nog = KAN.NOGI.index(nogi) if nogi in KAN.NOGI else 0
    return (
        nomer_nog,
        1 if "SPACE" in klavishi else 0,
        blizhajshaya(d_yaw, KAN.POVOROT, krugom=True),
        blizhajshaya(d_pitch, KAN.VZGLYAD),
        1 if udar else 0,
    )


def itog(act_l, grad_l, ubijstv, uron_vsego, fajl, sohranyat):
    n = len(act_l)
    print(f"\nнаиграно примеров: {n} | убийств: {ubijstv} | урона: {uron_vsego:.1f} HP")
    if not n:
        return
    act = np.asarray(act_l)
    print("\nчто попало в урок, по каналам:")
    for kanal, imya_kanala in enumerate(KAN.IMENA_KANALOV):
        stolbec = act[:, kanal]
        chasti = [f"{imya} {100 * int((stolbec == z).sum()) / n:.0f}%"
                  for z, imya in enumerate(KAN.ZNACHENIYA[kanal])
                  if int((stolbec == z).sum())]
        print(f"  {imya_kanala:<9} {', '.join(chasti)}")

    krupnye = int(np.isin(act[:, 2], [i for i, g in enumerate(KAN.POVOROT)
                                      if abs(g) >= 45]).sum())
    vmeste = int(((act[:, 0] != 0) & (act[:, 2] != 0)).sum())
    print(f"\nкрупных поворотов (45 и больше): {krupnye}")
    if krupnye == 0:
        print("  ноль — либо ты не разворачивался, либо запись опять теряет величину")
    print(f"движение И поворот вместе: {vmeste} шагов ({100 * vmeste / n:.0f}%)")
    if vmeste == 0:
        print("  ноль — а ведь этому мы и хотели научить: кружить, не отпуская прицел")
    if grad_l:
        g = np.abs(np.asarray(grad_l, dtype=np.float32)[:, 0])
        krutil = g[g > 0.5]
        print("\nточные градусы поворота (храним их для будущего):")
        print(f"  шагов с поворотом: {len(krutil)} из {n}")
        if len(krutil):
            print(f"  в среднем {krutil.mean():.1f} гр за шаг, "
                  f"самый крупный {krutil.max():.0f} гр")
    print(f"\n{'сохранено: ' + str(fajl) if sohranyat else 'ПРОБА: ничего не сохранено.'}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proba", action="store_true", help="привыкаю: НЕ сохранять запись")
    p.add_argument("--minut", type=float, default=20.0, help="сколько минут записывать")
    p.add_argument("--metka", default="", help="имя урока: попадёт в название файла")
    p.add_argument("--szadi", action="store_true",
                   help="зомби появляется ЗА СПИНОЙ: урок разворота к цели")
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
    sbros = lambda: A.sbros_boya(igrok, szadi=args.szadi)
    k.komandy(sbros())

    # Смотрим глазами существа: тот же кадр, те же приборы, тот же угол.
    # Команда SOSTOYANIE ничего не нажимает, так что играешь только ты.
    svyaz = P.Pupovina()
    svyaz.razmer_kadra(64, 64)
    hwnd, zagolovok = G.najti_okno("Minecraft")
    metka = ("-" + args.metka) if args.metka else ""
    fajl = OUT / f"pokaz{metka}-{datetime.now():%Y%m%d-%H%M%S}.npz"

    print(f"игрок {igrok} | окно «{zagolovok}» | {svyaz.ping()}")
    print(f"пиши {args.minut:g} минут. Остановить — Ctrl+C В ЭТОМ ОКНЕ.")
    print(f"сохраняю по ходу каждые 30 секунд -> {fajl.name}\n")
    print("Запись теперь сохраняет ВЕЛИЧИНУ поворота и движение вместе с ним.")
    print("Хочешь научить держать прицел — кружи вокруг зомби боком, не отпуская его.")
    print("ЩЁЛКНИ ПО ОКНУ MINECRAFT сейчас, иначе запись будет на паузе.\n")

    pov_l, vec_l, act_l, nag_l, grad_l = [], [], [], [], []
    nachalo = svyaz.sostoyanie()
    pred_yaw, pred_pitch = nachalo["yaw"], nachalo["pitch"]
    pred = A.schet_boya(k, igrok)
    stoyal, ubijstv, uron_vsego = 0, 0, 0.0
    srok = time.perf_counter() + M.SEK_NA_SHAG
    # Отсчёт начинаем с ПЕРВОГО записанного кадра, а не с запуска. Первая версия
    # считала время от запуска — и все четыре минуты пробы утекли, пока человек
    # читал, что от него требуется. Записалось ноль примеров.
    konec = None
    zhalovalsya = False

    try:
        while konec is None or time.perf_counter() < konec:
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
            if zhalovalsya:
                print("  окно впереди — пишу")
            zhalovalsya = False
            if konec is None:
                konec = time.perf_counter() + args.minut * 60
                print(f"  === ПОШЛА ЗАПИСЬ: {args.minut:g} минут с этой секунды ===",
                      flush=True)

            o = svyaz.sostoyanie()
            if o["menyu"] or not o["v_mire"]:
                continue
            klavishi = {imya for imya in ("W", "A", "S", "D", "SPACE")
                        if R.nazhimalas(imya)}
            udar = R.nazhimalas("MYSH_LEVAYA")   # щелчки короче шага — ловим и их

            d_yaw = (o["yaw"] - pred_yaw + 180) % 360 - 180
            d_pitch = o["pitch"] - pred_pitch
            pred_yaw, pred_pitch = o["yaw"], o["pitch"]

            reshenie = opredelit_reshenie(d_yaw, d_pitch, klavishi, udar)
            s = A.schet_boya(k, igrok)
            d_uron = max((s["uron"] or 0) - (pred["uron"] or 0), 0) / 10.0
            uron_vsego += d_uron
            if (s["ubijstva"] or 0) > (pred["ubijstva"] or 0):
                ubijstv += 1
                print(f"  *** убил зомби #{ubijstv} *** (записано {len(act_l)})")
            # Новая волна ТОЛЬКО когда все мертвы. Раньше призывал на первом же
            # убийстве — при трёх зомби это дало бы бесконечную подпитку.
            if not A.est_mobov(k):
                print(f"  --- волна зачищена, новые {A.ZOMBI_NA_ARENE} на арене ---")
                k.komandy(sbros())
                time.sleep(0.4)
                s = A.schet_boya(k, igrok)
                o = svyaz.sostoyanie()
                pred_yaw, pred_pitch = o["yaw"], o["pitch"]
            pred = s

            # «ничего не делал» пишем не больше нескольких подряд: раздумья не
            # должны стать уроком.
            nichego = all(x == 0 for x in reshenie)
            stoyal = stoyal + 1 if nichego else 0
            if not nichego or stoyal <= MAX_PODRYAD_STOYAT:
                pov_l.append(o["kadr"].copy())
                vec_l.append(np.array([
                    min(o["zhizn"] / M.MAX_HEALTH, 1.0),
                    min(o["sytost"] / 20.0, 1.0), 0.0, 1.0, 0.0, 0.0],
                    dtype=np.float32))
                act_l.append(reshenie)
                nag_l.append(d_uron * M.ZA_HP_URONA)
                grad_l.append((d_yaw, d_pitch))
                if d_uron > 0:
                    print(f"  попал: {d_uron:.1f} HP ({KAN.slovami(reshenie)}, "
                          f"записано {len(act_l)})")
                if not args.proba and len(act_l) % SHAGOV_MEZHDU_SOHRANENIYAMI == 0:
                    sohranit(fajl, pov_l, vec_l, act_l, nag_l, grad_l)
                    print(f"  [сохранено по ходу: {len(act_l)} примеров]")
    except KeyboardInterrupt:
        print("\nостановлено вручную")
    finally:
        if not args.proba:
            sohranit(fajl, pov_l, vec_l, act_l, nag_l, grad_l)
        try:
            svyaz.close()
            k.close()
        except Exception:
            pass
        itog(act_l, grad_l, ubijstv, uron_vsego, fajl, not args.proba)


if __name__ == "__main__":
    main()
