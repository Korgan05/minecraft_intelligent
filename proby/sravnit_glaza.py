# -*- coding: utf-8 -*-
"""
СРАВНЕНИЕ ДВУХ ГЛАЗ: кадр от мода против кадра со рабочего стола.

Зачем. Существо через мод стало драться заметно хуже: убивает раз в восемь боёв
вместо девяти из десяти. Мозг тот же, действия те же, экономика та же — значит
подозрение на зрение. Догадки тут не годятся, нужен замер: снимаем ОДИН И ТОТ ЖЕ
миг двумя способами и смотрим, насколько картинки расходятся.

Чтобы миг был действительно один, мобов замораживаем и ставим существо в
неподвижную позу: иначе разница между снимками окажется просто разницей во времени.

Запуск: zapusk\\sravnit-glaza.bat
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telo import arena as A
from telo import glaza as G
from telo import konsol as K
from telo import pupovina as P

KUDA = Path(__file__).resolve().parent.parent / "sravnenie-glaz"


def krupno(kadr, imya):
    KUDA.mkdir(exist_ok=True)
    cv2.imwrite(str(KUDA / imya),
                cv2.cvtColor(cv2.resize(kadr, (256, 256), interpolation=cv2.INTER_NEAREST),
                             cv2.COLOR_RGB2BGR))


def main():
    k = K.Konsol().podklyuchit()
    igrok = A.kto_v_mire(k)
    if not igrok:
        raise SystemExit("В мире никого нет.")
    p = P.Pupovina()

    # Неподвижная поза: иначе сравним не глаза, а два разных мгновения.
    k.komanda("kill @e[tag=boec]")
    zx, zy, zz = A.ZOMBIE_SPOT
    k.komanda(f"summon minecraft:zombie {zx} {zy} {zz} {A.nbt_moba()}")
    A.zamorozit_vseh(k, True)
    k.komanda(f"tp {igrok} 0.5 4 0.5 0 0")
    time.sleep(1.5)

    ot_moda = p.sostoyanie()["kadr"]
    glaz, zagolovok, oblast = G.glaza_na_okno("Minecraft")
    so_stola = glaz.kadr_sushchestva()
    polnyj = glaz.kadr_polnyj()
    glaz.close()

    A.zamorozit_vseh(k, False)
    p.close()
    k.close()

    print(f"окно «{zagolovok}»")
    print(f"область захвата: {oblast}  (широта/высота = {oblast[2] / oblast[3]:.2f})")
    print(f"полный снимок рабочего стола: {polnyj.shape}")
    print()
    print(f"от мода    : яркость {ot_moda.mean():6.1f}  разброс {ot_moda.std():5.1f}")
    print(f"со стола   : яркость {so_stola.mean():6.1f}  разброс {so_stola.std():5.1f}")
    raznica = np.abs(ot_moda.astype(np.int16) - so_stola.astype(np.int16))
    print(f"расхождение: в среднем {raznica.mean():5.1f} из 255, "
          f"худшее {raznica.max():3d}")
    dolya = float((raznica.mean(axis=2) > 30).mean())
    print(f"пикселей, разошедшихся больше чем на 30: {100 * dolya:.1f}%")

    krupno(ot_moda, "1-ot-moda.png")
    krupno(so_stola, "2-so-stola.png")
    krupno(raznica.astype(np.uint8), "3-raznica.png")
    if raznica.mean() < 8:
        print("-> мод и старый глаз видят почти одно и то же.")
    else:
        print("-> мод и старый глаз РАСХОДЯТСЯ.")

    # ── ОТПЕЧАТОК РАЗМЕРА ОКНА ──
    # Интерфейс в игре неподвижен, а мир при вращении смазывается. Значит в
    # среднем по многим кадрам остаётся именно интерфейс — и его положение с
    # размером однозначно говорят, какого размера было окно. Сравниваем нынешний
    # отпечаток с отпечатком записи, на которой мозг учился: если они разные,
    # существо смотрит на непривычную картинку, даже если оба глаза согласны.
    print("\n=== ОТПЕЧАТОК: интерфейс в среднем по кадрам ===")
    sejchas = sredniy_teper()
    ranshe = sredniy_iz_zapisi()
    krupno(sejchas, "4-otpechatok-sejchas.png")
    if ranshe is None:
        print("записей показа нет — сравнить не с чем")
        return
    krupno(ranshe, "5-otpechatok-obucheniya.png")
    r = np.abs(sejchas.astype(np.int16) - ranshe.astype(np.int16))
    krupno(r.astype(np.uint8), "6-otpechatki-raznica.png")
    print(f"расхождение отпечатков: в среднем {r.mean():.1f} из 255")
    print(f"  полоса интерфейса (низ кадра): сейчас {sejchas[56:].mean():.1f}, "
          f"при обучении {ranshe[56:].mean():.1f}")
    print(f"  середина кадра (мир)         : сейчас {sejchas[24:40].mean():.1f}, "
          f"при обучении {ranshe[24:40].mean():.1f}")
    print(f"\nкартинки: {KUDA}")
    if r.mean() > 15:
        print("ВЫВОД: окно другого размера или иные настройки — мозг учился на"
              " другой картинке.")
    else:
        print("ВЫВОД: картинка та же. Причина не в зрении, ищем дальше.")


def sredniy_teper(skolko=32):
    """Средний кадр СЕЙЧАС: вертимся, чтобы мир смазался, а интерфейс проявился."""
    p = P.Pupovina()
    kadry = []
    for _ in range(skolko):
        p.shag(dyaw=45.0)
        time.sleep(0.15)
        kadry.append(p.sostoyanie()["kadr"].astype(np.float32))
    p.close()
    return np.mean(kadry, axis=0).astype(np.uint8)


def sredniy_iz_zapisi():
    """Средний кадр из записи показа — то, на чём мозг учился видеть."""
    fajly = sorted((Path(__file__).resolve().parent.parent / "pokaz").glob("*.npz"))
    if not fajly:
        return None
    pov = np.load(fajly[-1])["pov"]
    return pov.astype(np.float32).mean(axis=0).astype(np.uint8)


if __name__ == "__main__":
    main()
