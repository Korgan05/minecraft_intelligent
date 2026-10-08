# -*- coding: utf-8 -*-
"""
РАЗМИНКА ПО ПОКАЗУ: существо перенимает твои приёмы. Minecraft не нужен.

Первая версия этой разминки СТЁРЛА мозг. Учила всю сеть целиком, пять проходов
на 3893 примерах — и мозг схлопнулся в «не делай ничего»: на 655 кадрах он
отвечал «стоять» 99%, «прямо» 100%, «не бей» 99%. Двести тысяч шагов опыта
перекрыл градиент подражания.

Причина глубже неудачных настроек. Твоё действие на кадре НЕ ОПРЕДЕЛЯЕТСЯ этим
кадром: глядя на одного и того же зомби, ты можешь довернуть влево, вправо или
ударить — и всё правильно. Угадать это нельзя, и самый безопасный ответ для сети
— «отвечай самым частым». Самое частое в показе — стоять и не бить.

Три поправки, каждая лечит свою часть:

1. ЗРЕНИЕ ЗАМОРОЖЕНО. Учится только голова решения. Двести тысяч шагов узнавания
   зомби подражанием не улучшить, а испортить — легко. Заодно это быстро:
   признаки для кадров считаются ОДИН раз, дальше обучение идёт на них.

2. ПОВОДОК К ПРЕЖНЕМУ МОЗГУ. К подражанию добавлена плата за расхождение с тем,
   каким он был до разминки. Причём в ту сторону, которая штрафует за ЗАБЫВАНИЕ:
   если прежний мозг считал действие возможным, а новый обнулил — плата взлетает.
   Ровно это и не даёт схлопнуться. Длину поводка не угадываем, а подбираем.

3. МЕРИМ РАЗНООБРАЗИЕ ОТВЕТОВ, а не совпадение. Прошлая проверка смотрела на
   рост совпадения с 2.9% до 8.4% и сочла это успехом — а 8.4% это в точности
   произведение долей самых частых значений. Цифра росла ИМЕННО ПОТОМУ, что мозг
   вырождался. Проверка не умела отличить обучение от гибели. Эта умеет.

Запуск: zapusk\\uchit.bat
"""

import argparse
import glob
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO

from telo import kanaly as KAN
from telo import mir as M

ROOT = Path(__file__).parent
POKAZ = ROOT / "pokaz"
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
KUSOK = 128
# Поводки от самого слабого к самому крепкому. Берём САМЫЙ СЛАБЫЙ, при котором
# мозг ещё не вырождается: слабее поводок — больше он успеет перенять.
POVODKI = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
# Насколько разрешаем потерять разнообразие ответов. Ниже — считаем вырождением.
DOLYA_RAZNOOBRAZIYA = 0.7


def stopki(pov):
    """Кадры в стопки по четыре: существо видит именно так."""
    n = M.KADROV_V_PAMYATI
    # Первые кадры дополняем повтором самого раннего — как это делает мир
    # в начале боя. Иначе пришлось бы выбрасывать начало каждой записи.
    ryad = [pov[0]] * (n - 1) + list(pov)
    return np.stack([np.concatenate(ryad[i:i + n], axis=2) for i in range(len(pov))])


def zagruzit(brat_starye=False):
    """Уроки для подражания. По умолчанию — только снятые ПОСЛЕ починки записи.

    Старые записи (до каналов) исключены не потому, что старые, а потому, что в
    них два искажения ровно по тем каналам, которые мы лечим:

      * ВСЕ повороты записаны как 15 градусов — и доворот на 12, и разворот на
        180. Размахи 45, 90 и «кругом» встречаются в них ноль раз из 4341;
      * движение и поворот НЕСОВМЕСТИМЫ по построению: запись выбирала одно
        действие на шаг, и поворот был важнее. После перевода в каналы каждый их
        шаг с поворотом говорит «стой и вертись» — наоборот новому уроку.

    Данные, которые спорят друг с другом, хуже, чем данные, которых меньше.
    """
    fajly = sorted(glob.glob(str(POKAZ / "pokaz-*.npz")), key=os.path.getmtime)
    if not fajly:
        raise SystemExit(f"Записей нет. Сначала запиши показ: zapis.bat ({POKAZ})")
    pov_l, vec_l, act_l = [], [], []
    for f in fajly:
        d = np.load(f)
        act = d["act"]
        novaya = act.ndim > 1
        if not novaya:
            if not brat_starye:
                print(f"  {os.path.basename(f):<38} пропускаю (запись до каналов)")
                continue
            act = np.array([KAN.STAROE_V_KANALY[int(a)] for a in act], dtype=np.int64)
        pov_l.append(stopki(d["pov"]))
        vec_l.append(d["vec"])
        act_l.append(act)
        print(f"  {os.path.basename(f):<38} {len(act):5d} примеров"
              f" ({'урок по каналам' if novaya else 'СТАРАЯ, взята по просьбе'})")
    if not act_l:
        raise SystemExit("Ни одного урока по каналам. Запиши показ заново: zapis.bat")
    return np.concatenate(pov_l), np.concatenate(vec_l), np.concatenate(act_l)


def pokazat_chemu_uchim(act):
    n = len(act)
    print("\nчему учит показ:")
    for kanal, imya_kanala in enumerate(KAN.IMENA_KANALOV):
        chasti = [f"{imya} {100 * int((act[:, kanal] == z).sum()) / n:.0f}%"
                  for z, imya in enumerate(KAN.ZNACHENIYA[kanal])
                  if int((act[:, kanal] == z).sum())]
        print(f"  {imya_kanala:<9} {', '.join(chasti)}")
    vmeste = int(((act[:, 0] != 0) & (act[:, 2] != 0)).sum())
    print(f"\n  движение вместе с поворотом: {vmeste} шагов ({100 * vmeste / n:.0f}%)")


def priznaki(model, pov, vec, ustrojstvo, do_smesitelya=False):
    """Признаки кадров ОДИН раз: зрение заморожено, значит они не изменятся.

    do_smesitelya=True отдаёт выход ЗРЕНИЯ (до смесителя), чтобы можно было
    учить и смеситель тоже. False — вход прямо в голову решения.
    """
    kuski = []
    politika = model.policy
    for n in range(0, len(pov), KUSOK):
        obs_t, _ = politika.obs_to_tensor({"pov": pov[n:n + KUSOK],
                                           "vec": vec[n:n + KUSOK]})
        with torch.no_grad():
            p = politika.extract_features(obs_t)
            if isinstance(p, tuple):
                p = p[0]
            kuski.append(p if do_smesitelya
                         else politika.mlp_extractor.forward_actor(p))
    return torch.cat(kuski).to(ustrojstvo)


def razbit(logity):
    kuski, nachalo = [], 0
    for skolko in KAN.KANALY:
        kuski.append(logity[:, nachalo:nachalo + skolko])
        nachalo += skolko
    return kuski


def raznoobrazie(logity):
    """Насколько ответы разные. Ноль — мозг отвечает одно и то же всегда."""
    doli = []
    for k in razbit(logity):
        chastoty = torch.bincount(k.argmax(dim=1), minlength=k.shape[1]).float()
        doli.append(1.0 - float((chastoty / len(k)).max()))
    return float(np.mean(doli))


def sovpadenie(logity, celi):
    vybor = torch.stack([k.argmax(dim=1) for k in razbit(logity)], dim=1)
    return float((vybor == celi).all(dim=1).float().mean())


def perenyal_li(logity, celi):
    """Главное: перенял ли ПРИЁМЫ, а не средние числа.

    Смотрим только кадры, где ты делал что-то новое: шёл боком, доворачивал на
    ходу, бежал. Общее совпадение может расти от вырождения — а это нет.
    """
    vybor = torch.stack([k.argmax(dim=1) for k in razbit(logity)], dim=1)
    itogi = {}
    bokom = torch.isin(celi[:, 0], torch.tensor([3, 4, 5, 6, 7, 8], device=celi.device))
    if bokom.any():
        itogi["шёл боком"] = float((vybor[bokom, 0] == celi[bokom, 0]).float().mean())
    dv = (celi[:, 0] != 0) & (celi[:, 2] != 0)
    if dv.any():
        itogi["двигался и доворачивал"] = float(
            ((vybor[dv, 0] == celi[dv, 0]) & (vybor[dv, 2] == celi[dv, 2])).float().mean())
    beg = celi[:, 5] == 1
    if beg.any():
        itogi["бежал"] = float((vybor[beg, 5] == celi[beg, 5]).float().mean())
    bil = celi[:, 4] == 1
    if bil.any():
        itogi["бил"] = float((vybor[bil, 4] == celi[bil, 4]).float().mean())
    return itogi


def uchit_chast(chasti, vpered, nomera, celi, starye_logity,
                povodok, epoh, lr, paket, rng, uchim_kanaly=None):
    """Учим переданные части сети. vpered(индексы) -> логиты."""
    uchim_kanaly = (set(range(len(KAN.KANALY))) if uchim_kanaly is None
                    else set(uchim_kanaly))
    parametry = [q for ch in chasti for q in ch.parameters()]
    opt = torch.optim.Adam(parametry, lr=lr)
    n = len(nomera)
    for _ in range(epoh):
        for b in np.array_split(rng.permutation(n), max(1, n // paket)):
            bt = nomera[torch.as_tensor(b, device=celi.device)]
            kuski = razbit(vpered(bt))
            starye = razbit(starye_logity[bt])
            # ПОДРАЖАЕМ НЕ ВСЕМУ. Можно указать, какие каналы учить у человека,
            # а какие оставить как есть. Это нашлось дорого: подражание всем
            # каналам сразу рушило удар — существо начинало бить метко, но в
            # восемь раз реже, и переставало убивать. А приём, которого ему не
            # хватает, живёт в одном канале — «ноги». Незачем ради него трогать
            # руку, которая и так работает.
            podrazhanie = sum(
                torch.nn.functional.cross_entropy(k, celi[bt, i])
                for i, k in enumerate(kuski) if i in uchim_kanaly)
            # ПОВОДОК: KL(прежний || новый). Взято именно в эту сторону нарочно —
            # она штрафует за ЗАБЫВАНИЕ: если прежний мозг считал действие
            # возможным, а новый обнулил, плата уходит в бесконечность. Обратная
            # сторона такого не ловит, и мозг спокойно схлопнулся бы.
            zabyvanie = sum(
                torch.nn.functional.kl_div(torch.log_softmax(k, dim=1),
                                           torch.softmax(s, dim=1),
                                           reduction="batchmean")
                for k, s in zip(kuski, starye))
            poterya = podrazhanie + povodok * zabyvanie
            opt.zero_grad()
            poterya.backward()
            torch.nn.utils.clip_grad_norm_(parametry, 1.0)
            opt.step()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epoh", type=int, default=25)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--paket", type=int, default=256)
    p.add_argument("--so-starymi", action="store_true",
                   help="взять и записи до каналов (они спорят с новыми)")
    p.add_argument("--prinuditelno", action="store_true",
                   help="взять лучшую НЕвырожденную ступень, даже если приём по офлайн-мерке "
                        "не перенялся: мерка приёма (доля 'боком') заточена под старые уроки "
                        "и слепа к дуэли. Судья — живой замер после, с воротами.")
    p.add_argument("--povodok", type=float, default=None,
                   help="один поводок, без перебора: учим всю сеть с ним")
    p.add_argument("--kuda", default=None,
                   help="куда сохранить (по умолчанию поверх мозга)")
    p.add_argument("--kanaly", default=None,
                   help="какие каналы учить у человека, через запятую (0=ноги, 5=бег)")
    args = p.parse_args()

    if not MOZG.with_suffix(".zip").exists():
        raise SystemExit(f"Мозга нет: {MOZG}.zip")
    print("Читаю показ:")
    pov, vec, act = zagruzit(args.so_starymi)
    print(f"\nвсего примеров: {len(act)}")
    pokazat_chemu_uchim(act)
    if not act[:, 4].any():
        raise SystemExit("\nВ показе НЕТ удара — учить нечему.")

    ustrojstvo = "cuda" if torch.cuda.is_available() else "cpu"
    model = PPO.load(MOZG, device=ustrojstvo)
    politika = model.policy
    print(f"\nустройство: {ustrojstvo} | мозг {model.num_timesteps} шагов")
    if tuple(model.action_space.nvec) != tuple(KAN.KANALY):
        raise SystemExit(f"Мозг ждёт каналы {list(model.action_space.nvec)}, "
                         f"а чертёж {KAN.KANALY}. Сначала perestroit_golovu.py")

    print("считаю признаки кадров (зрение заморожено — считаем один раз)...")
    latent = priznaki(model, pov, vec, ustrojstvo)                      # вход в голову
    zrenie = priznaki(model, pov, vec, ustrojstvo, do_smesitelya=True)  # выход зрения
    celi = torch.as_tensor(act, dtype=torch.long, device=ustrojstvo)
    with torch.no_grad():
        starye_logity = politika.action_net(latent).detach()
    ishodnoe = {k: v.detach().clone() for k, v in politika.state_dict().items()}

    rng = np.random.default_rng(0)
    poryadok = rng.permutation(len(act))
    granica = int(len(act) * 0.85)
    uch = torch.as_tensor(poryadok[:granica], device=ustrojstvo)
    pro = torch.as_tensor(poryadok[granica:], device=ustrojstvo)

    def cherez_vse(bt):
        """Полный путь от кадров — нужен, когда оттаиваем и зрение."""
        nomera = bt.detach().cpu().numpy()
        obs_t, _ = politika.obs_to_tensor({"pov": pov[nomera], "vec": vec[nomera]})
        pr = politika.extract_features(obs_t)
        if isinstance(pr, tuple):
            pr = pr[0]
        return politika.action_net(politika.mlp_extractor.forward_actor(pr))

    # ТРИ СТУПЕНИ ОТТАИВАНИЯ: от самой щадящей к самой смелой. Берём ПЕРВУЮ,
    # которая перенесла приём и не выродила мозг. Смысл порядка простой: чем
    # меньше трогаем, тем меньше можем сломать. Прошлая разминка сразу учила
    # всё — и стёрла двести тысяч шагов опыта в «не делай ничего».
    stupeni = [
        ("только голова решения",
         lambda: [politika.action_net],
         lambda bt: politika.action_net(latent[bt])),
        ("голова и смеситель",
         lambda: [politika.mlp_extractor, politika.action_net],
         lambda bt: politika.action_net(
             politika.mlp_extractor.forward_actor(zrenie[bt]))),
        ("всё, включая зрение",
         lambda: [politika],
         cherez_vse),
    ]

    with torch.no_grad():
        logity_do = politika.action_net(latent[pro])
    razn_do = raznoobrazie(logity_do)
    sovp_do = sovpadenie(logity_do, celi[pro])
    priem_do = perenyal_li(logity_do, celi[pro])
    porog_razn = razn_do * DOLYA_RAZNOOBRAZIYA
    bokom_do = priem_do.get("шёл боком", 0.0)

    print(f"\nДО разминки: совпадение {sovp_do:.1%}, разнообразие {razn_do:.2f}")
    print("  приёмы: " + ", ".join(f"{k} {v:.0%}" for k, v in priem_do.items()))
    print("\nЧтобы разминку принять, нужно ОДНОВРЕМЕННО:")
    print(f"  * разнообразие ответов не ниже {porog_razn:.2f} — иначе вырождение")
    print(f"  * «шёл боком» вырос хотя бы до {bokom_do + 0.10:.0%} — иначе учить незачем")

    if args.povodok is not None:
        # Один поводок, без ворот. Судьёй будет БОЙ, а не мои мерки: за день они
        # трижды показали рост там, где существо на деле портилось.
        imya_stupeni, dat_chasti, vpered = stupeni[-1]
        print(f"\n--- один поводок {args.povodok}, ступень: {imya_stupeni} ---")
        politika.set_training_mode(True)
        kanaly = ([int(x) for x in args.kanaly.split(",")]
                  if args.kanaly else None)
        if kanaly:
            print("  подражаем только каналам: "
                  + ", ".join(KAN.IMENA_KANALOV[i] for i in kanaly))
        uchit_chast(dat_chasti(), vpered, uch, celi, starye_logity,
                    args.povodok, args.epoh, args.lr, args.paket, rng, kanaly)
        politika.set_training_mode(False)
        with torch.no_grad():
            logity = vpered(pro)
        priem = perenyal_li(logity, celi[pro])
        print(f"  разнообразие {raznoobrazie(logity):.2f}, "
              f"совпадение {sovpadenie(logity, celi[pro]):.1%}")
        print("  приёмы: " + ", ".join(
            f"{k} {priem_do.get(k, 0):.0%}->{v:.0%}" for k, v in priem.items()))
        kuda = Path(args.kuda) if args.kuda else MOZG
        model.save(kuda)
        print(f"\nсохранено: {kuda}.zip")
        print("Это ещё НЕ проверка. Судить будет бой: razbor_boya --mozg " + str(kuda))
        return

    luchshee = None
    zapasnoe = None
    for imya_stupeni, dat_chasti, vpered in stupeni:
        if luchshee:
            break
        print(f"\n--- оттаиваю: {imya_stupeni} ---")
        for povodok in POVODKI:
            politika.load_state_dict(ishodnoe)
            politika.set_training_mode(True)
            uchit_chast(dat_chasti(), vpered, uch, celi, starye_logity,
                        povodok, args.epoh, args.lr, args.paket, rng)
            politika.set_training_mode(False)
            with torch.no_grad():
                logity = vpered(pro)
            razn = raznoobrazie(logity)
            sovp = sovpadenie(logity, celi[pro])
            priem = perenyal_li(logity, celi[pro])
            bokom = priem.get("шёл боком", 0.0)
            zhiv = razn >= porog_razn
            vyros = bokom >= bokom_do + 0.10
            znak = ("ГОДИТСЯ" if zhiv and vyros
                    else ("вырождение" if not zhiv else "приём не перенялся"))
            print(f"  поводок {povodok:<5}: разнообразие {razn:.2f}, "
                  f"боком {bokom:.0%}, совпадение {sovp:.1%} — {znak}")
            if zhiv and not vyros and (zapasnoe is None or sovp > zapasnoe[2]):
                # запасной кандидат для --prinuditelno: живой (не вырожденный),
                # с наибольшим совпадением. Мимо проверки вырождения принуждение
                # НЕ ходит никогда.
                zapasnoe = (imya_stupeni, povodok, sovp, priem, razn,
                            {k: v.detach().clone()
                             for k, v in politika.state_dict().items()})
            if zhiv and vyros:
                luchshee = (imya_stupeni, povodok, sovp, priem, razn,
                            {k: v.detach().clone()
                             for k, v in politika.state_dict().items()})
                break

    if luchshee is None and args.prinuditelno and zapasnoe is not None:
        print("!!! ПРИНУЖДЕНИЕ: офлайн-мерка приёма не прошла ни на одной ступени, "
              "беру лучшую НЕвырожденную (судить будет живой замер)")
        luchshee = zapasnoe
    if luchshee is None:
        politika.load_state_dict(ishodnoe)
        raise SystemExit(
            "\nНИ ОДНА ступень не перенесла приём без вырождения. Мозг НЕ трогаю.\n"
            "Значит подражанием это не берётся, и приёмы придётся нащупывать наградой.")

    imya_stupeni, povodok, sovp, priem, razn, sostoyanie = luchshee
    politika.load_state_dict(sostoyanie)
    print(f"\nвзято: {imya_stupeni}, поводок {povodok}")
    print("\n=== ЧТО ИЗМЕНИЛОСЬ (на отложенных примерах) ===")
    print(f"  разнообразие ответов: {razn_do:.2f} -> {razn:.2f}")
    print(f"  совпадение с тобой  : {sovp_do:.1%} -> {sovp:.1%}")
    print("  перенял приёмы:")
    for chto in priem:
        print(f"    {chto:<24} {priem_do.get(chto, 0):.0%} -> {priem[chto]:.0%}")

    zapas = MODELI / f"do-razminki-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    model.save(MOZG)
    print(f"\nпрежний отложен: {zapas.name}")
    print(f"мозг сохранён  : {MOZG.name}.zip")
    print("\nЭто ещё НЕ проверка в бою. Прогони razbor-boya.bat: доля убийств")
    print("не должна упасть ниже 85%, иначе откатываемся к отложенному.")


if __name__ == "__main__":
    main()
