# -*- coding: utf-8 -*-
"""Перебор экономики боя: кем станет существо при каждой настройке.

Постоянные (из telo/mir.py и из мира): ZA_HP_URONA=1, KILL_BONUS=10,
здоровье существа 40, здоровье зомби 20, шаг = 0.2 с.

Замеры для «типичного» боя взяты из наших лент:
  победа  — 70 шагов, получено 14 HP урона;
  гибель  — 150-й шаг, успело нанести 17 HP из 20.
"""
import itertools

ZA_HP_URONA = 1.0
KILL_BONUS = 10.0
HP_SVOI = 40.0
HP_ZOMBI = 20.0
POBEDA_CHISTAYA = HP_ZOMBI * ZA_HP_URONA + KILL_BONUS   # 30

N_POBEDY = 70      # типичный победный бой, шагов
B_POBEDY = 14.0    # типичный полученный урон при победе, HP
N_GIBELI = 150     # типичный шаг гибели
D_GIBELI = 17.0    # типичный нанесённый урон к моменту гибели

SETKA = dict(
    ZA_SHAG=[0, 0.01, 0.02, 0.05, 0.1, 0.2],
    DEATH_PENALTY=[3, 10, 20, 30, 50, 100],
    MAX_SHAGOV=[100, 150, 200, 400],
    PAIN_ZA_HP=[0.1, 0.3],
    ZA_PROSTOJ_VDALI=[0, 0.3],
)


def porogi(s, d, M, p, q):
    """Все пороги для одной настройки."""
    n_gib = min(N_GIBELI, M)
    n_pob = min(N_POBEDY, M)
    n_150 = min(150, M)

    cena_promedleniya_chest = s * M              # тянуть, работая ногами
    cena_promedleniya_prost = (s + q) * M        # тянуть, стоя вдали столбом
    cena_smerti = d + p * HP_SVOI                # смерть + полная боль
    # ценности исходов (награда за бой)
    pobeda = POBEDA_CHISTAYA - s * n_pob - p * B_POBEDY
    gibel = D_GIBELI - d - p * HP_SVOI - s * n_gib
    otkaz = -s * M                               # самый дешёвый отказ: ноги работают
    samoubijstvo_srazu = -(d + p * HP_SVOI)      # подставиться сразу
    pobeda_150 = POBEDA_CHISTAYA - s * n_150 - p * B_POBEDY
    pobeda_150_prostoj = POBEDA_CHISTAYA - (s + q) * n_150 - p * B_POBEDY

    # порог отказа: p*Победа + (1-p)*Гибель = Отказ
    if pobeda - gibel > 1e-9:
        p_otkaza = (otkaz - gibel) / (pobeda - gibel)
    else:
        p_otkaza = float("inf")

    cena_ostorozhnosti = float("inf") if s == 0 else d / s
    return dict(
        promedlenie=cena_promedleniya_chest,
        promedlenie_prostoj=cena_promedleniya_prost,
        smert=cena_smerti,
        pobeda=pobeda,
        gibel=gibel,
        otkaz=otkaz,
        samoubijstvo=samoubijstvo_srazu,
        pobeda_150=pobeda_150,
        pobeda_150_prostoj=pobeda_150_prostoj,
        p_otkaza=p_otkaza,
        ostorozhnost=cena_ostorozhnosti,
        n_150=n_150,
    )


def klass(s, d, M, p, q):
    t = porogi(s, d, M, p, q)
    yarlyki = []
    if t["smert"] < t["promedlenie_prostoj"] - 1e-9:
        # умереть дешевле, чем дотянуть до предела
        chest = t["smert"] < t["promedlenie"] - 1e-9
        yarlyki.append("самоубийца" + ("" if chest else " (через простой)"))
    if t["ostorozhnost"] > M + 1e-9:
        yarlyki.append("черепаха")
    if t["p_otkaza"] > 0.5:
        yarlyki.append("трус")
    if d < POBEDA_CHISTAYA - 1e-9:
        yarlyki.append("безрассудный")
    if t["pobeda_150"] < -1e-9:
        yarlyki.append("победа в убыток")
    return (yarlyki or ["боец"]), t


def perebor():
    rez = []
    for s, d, M, p, q in itertools.product(
            SETKA["ZA_SHAG"], SETKA["DEATH_PENALTY"], SETKA["MAX_SHAGOV"],
            SETKA["PAIN_ZA_HP"], SETKA["ZA_PROSTOJ_VDALI"]):
        ya, t = klass(s, d, M, p, q)
        rez.append((s, d, M, p, q, ya, t))
    return rez


def stroka(s, d, M, p, q, ya, t):
    return (f"s={s:<5} D={d:<4} M={M:<4} pain={p:<4} prostoj={q:<4} | "
            f"промедл={t['promedlenie']:>5.1f}/{t['promedlenie_prostoj']:>5.1f} "
            f"смерть={t['smert']:>5.1f} остор={t['ostorozhnost'] if t['ostorozhnost']!=float('inf') else 9999:>6.0f} "
            f"поб={t['pobeda']:>6.1f} поб150={t['pobeda_150']:>6.1f} "
            f"p*={t['p_otkaza']*100 if t['p_otkaza']!=float('inf') else 999:>5.1f}% | "
            + ", ".join(ya))


def main():
    rez = perebor()
    print(f"всего настроек: {len(rez)}")
    bojcy = [r for r in rez if r[5] == ["боец"]]
    print(f"\n=== БОЕЦ ({len(bojcy)} из {len(rez)}) ===")
    for r in bojcy:
        print(stroka(*r))

    print("\n=== сколько раз встречается каждый ярлык ===")
    schet = {}
    for r in rez:
        for y in r[5]:
            schet[y] = schet.get(y, 0) + 1
    for y, n in sorted(schet.items(), key=lambda kv: -kv[1]):
        print(f"{y:<28} {n}")

    print("\n=== показательные вырождения ===")
    pokaz = [
        (0, 3, 400, 0.3, 0, "нет платы за время (lenta-5)"),
        (0.1, 3, 400, 0.3, 0, "плата за время, смерть 3 (lenta-6)"),
        (0.1, 3, 400, 0.3, 0.3, "НОЧНОЙ ОБВАЛ (lenta-8)"),
        (0.1, 50, 400, 0.3, 0.3, "НЫНЕШНЯЯ ЧЕРЕПАХА (lenta-9)"),
        (0.1, 50, 400, 0.3, 0, "то же без платы за простой"),
        (0.2, 100, 400, 0.3, 0.3, "всё выкручено вверх"),
        (0.05, 100, 100, 0.1, 0, "дорогая смерть, короткий бой"),
        (0.2, 30, 150, 0.1, 0, "быстрый бой, дешёвая боль"),
    ]
    for s, d, M, p, q, imya in pokaz:
        ya, t = klass(s, d, M, p, q)
        print(f"{imya:<38} " + stroka(s, d, M, p, q, ya, t))

    print("\n=== тонкая сетка: ищем максимальный запас по всем порогам ===")
    luchshie = []
    for d in [30, 35, 40, 45, 50, 60]:
        for M in [200, 250, 300, 350, 400]:
            for si in range(1, 41):
                s = round(si * 0.005, 3)
                p, q = 0.3, 0
                ya, t = klass(s, d, M, p, q)
                if ya != ["боец"]:
                    continue
                # запасы (относительные, чем больше тем надёжнее)
                z_cherepaha = (M - t["ostorozhnost"]) / M
                z_samoub = (t["smert"] - t["promedlenie_prostoj"]) / t["smert"]
                z_trus = (0.5 - t["p_otkaza"]) / 0.5
                z_ubytok = t["pobeda_150"] / POBEDA_CHISTAYA
                z_bezrass = (d - POBEDA_CHISTAYA) / POBEDA_CHISTAYA
                zapas = min(z_cherepaha, z_samoub, z_trus, z_ubytok, z_bezrass)
                luchshie.append((zapas, s, d, M, p, q, t))
    luchshie.sort(reverse=True, key=lambda x: x[0])
    for zapas, s, d, M, p, q, t in luchshie[:12]:
        print(f"запас={zapas:.3f}  ZA_SHAG={s} DEATH={d} MAX={M} pain={p} prostoj={q} "
              f"| остор={t['ostorozhnost']:.0f}/{M} смерть={t['smert']:.1f}>промедл={t['promedlenie_prostoj']:.1f} "
              f"поб150={t['pobeda_150']:.1f} p*={t['p_otkaza']*100:.1f}%")

    print("\n=== проверка рекомендации на трёх сценариях ===")
    for reko in [(0.15, 40, 300, 0.3, 0), (0.14, 50, 400, 0.3, 0), (0.1, 30, 400, 0.3, 0)]:
        s, d, M, p, q = reko
        ya, t = klass(s, d, M, p, q)
        print(f"\nZA_SHAG={s} DEATH={d} MAX_SHAGOV={M} PAIN={p} PROSTOJ={q} -> {', '.join(ya)}")
        print(f"  победа={t['pobeda']:.1f}  гибель={t['gibel']:.1f}  "
              f"отказ(тянуть)={t['otkaz']:.1f}  умереть сразу={t['samoubijstvo']:.1f}  "
              f"p*={t['p_otkaza']*100:.1f}%")
        for pw in (0.95, 0.70, 0.40):
            drka = pw * t["pobeda"] + (1 - pw) * t["gibel"]
            luchshee = max(drka, t["otkaz"], t["samoubijstvo"])
            kto = ("ДРАТЬСЯ" if luchshee == drka else
                   "ТЯНУТЬ" if luchshee == t["otkaz"] else "УМЕРЕТЬ")
            print(f"  шанс {pw*100:>4.0f}%: драться={drka:>7.2f}  тянуть={t['otkaz']:>7.2f}  "
                  f"умереть={t['samoubijstvo']:>7.2f}  -> {kto}"
                  f"  (перевес над тянуть {drka - t['otkaz']:+.1f}, над умереть {drka - t['samoubijstvo']:+.1f})")


if __name__ == "__main__":
    main()
