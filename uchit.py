# -*- coding: utf-8 -*-
"""
РАЗМИНКА ПО ПОКАЗУ: существо подражает твоей игре. Minecraft не нужен.

Что здесь было раньше и чего больше нет. Тут жила операция наращивания головы —
она добавляла новые действия, копируя веса у соседних. Именно она однажды
раздробила «доверни влево» на четыре размаха поровну, и существо начало
перелетать цель. Теперь перестройка головы живёт отдельно (perestroit_golovu.py),
делается один раз и с проверкой, а здесь остаётся только подражание.

Учим НЕДОЛГО и следим за отложенными примерами. Цель не в том, чтобы повторить
тебя дословно: ты и сам ошибаешься, а награда потом всё поправит. Цель — дать
существу твои приёмы как подсказку. Поэтому останавливаемся, как только на
отложенных примерах перестаёт расти: дальше начинается зубрёжка.

Старые записи (до каналов) читаются тоже: их действия переводятся по той же
таблице, по которой переносилась голова.

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


def stopki(pov):
    """Кадры в стопки по четыре: существо видит именно так."""
    n = M.KADROV_V_PAMYATI
    # Первые кадры дополняем повтором самого раннего — как это делает мир
    # в начале боя. Иначе пришлось бы выбрасывать начало каждой записи.
    dopolnenie = [pov[0]] * (n - 1)
    ryad = dopolnenie + list(pov)
    return np.stack([np.concatenate(ryad[i:i + n], axis=2) for i in range(len(pov))])


def zagruzit():
    fajly = sorted(glob.glob(str(POKAZ / "pokaz-*.npz")), key=os.path.getmtime)
    if not fajly:
        raise SystemExit(f"Записей нет. Сначала запиши показ: zapis.bat ({POKAZ})")
    pov_l, vec_l, act_l = [], [], []
    for f in fajly:
        d = np.load(f)
        act = d["act"]
        if act.ndim == 1:
            # Старая запись: одно действие из двадцати. Переводим по той же
            # таблице, по которой переносилась голова, — чтобы уроки, снятые до
            # каналов, не пропали.
            act = np.array([KAN.STAROE_V_KANALY[int(a)] for a in act], dtype=np.int64)
            vid = "старая"
        else:
            vid = "по каналам"
        pov_l.append(stopki(d["pov"]))
        vec_l.append(d["vec"])
        act_l.append(act)
        print(f"  {os.path.basename(f):<32} {len(act):5d} примеров ({vid})")
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
    if vmeste == 0:
        print("  Ноль. Значит кружения с удержанием прицела в показе НЕТ —")
        print("  все записи сделаны до починки записи. Существу неоткуда это взять.")


def tochnost(model, pov, vec, act, idx, paket):
    """Доля совпадений: по каждому каналу и по всем пяти сразу."""
    if len(idx) == 0:
        return np.zeros(len(KAN.KANALY)), 0.0
    po_kanalam = np.zeros(len(KAN.KANALY))
    celikom = 0
    with torch.no_grad():
        for s in range(0, len(idx), paket):
            b = idx[s:s + paket]
            obs_t, _ = model.policy.obs_to_tensor({"pov": pov[b], "vec": vec[b]})
            raspr = model.policy.get_distribution(obs_t).distribution
            vybor = torch.stack([d.probs.argmax(dim=1) for d in raspr], dim=1).cpu().numpy()
            sovpalo = vybor == act[b]
            po_kanalam += sovpalo.sum(axis=0)
            celikom += int(sovpalo.all(axis=1).sum())
    return po_kanalam / len(idx), celikom / len(idx)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epoh", type=int, default=30, help="максимум проходов")
    p.add_argument("--terpenie", type=int, default=3,
                   help="сколько проходов без роста терпим до остановки")
    p.add_argument("--svoboda", type=float, default=0.01, help="бонус за неуверенность")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--paket", type=int, default=128)
    args = p.parse_args()

    if not MOZG.with_suffix(".zip").exists():
        raise SystemExit(f"Мозга нет: {MOZG}.zip")
    print("Читаю показ:")
    pov, vec, act = zagruzit()
    n = len(act)
    print(f"\nвсего примеров: {n}")
    pokazat_chemu_uchim(act)
    if not act[:, 4].any():
        raise SystemExit("\nВ показе НЕТ удара — учить нечему.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = PPO.load(MOZG, device=device)
    print(f"\nустройство: {device} | мозг {model.num_timesteps} шагов")
    if tuple(model.action_space.nvec) != tuple(KAN.KANALY):
        raise SystemExit(f"Мозг ждёт каналы {model.action_space.nvec}, "
                         f"а чертёж {KAN.KANALY}. Сначала perestroit_golovu.py")

    celi = torch.as_tensor(act, dtype=torch.long, device=device)
    rng = np.random.default_rng(0)
    poryadok = rng.permutation(n)
    granica = int(n * 0.85)
    uch, pro = poryadok[:granica], poryadok[granica:]
    print(f"учебных {len(uch)}, отложенных {len(pro)}")

    _, do = tochnost(model, pov, vec, act, pro, args.paket)
    print(f"\nсовпадение с тобой ДО разминки: {do:.1%}")

    model.policy.set_training_mode(True)
    opt = torch.optim.Adam(model.policy.parameters(), lr=args.lr)
    luchshaya, luchshie, bez_rosta = do, None, 0

    for epoha in range(1, args.epoh + 1):
        por = rng.permutation(uch)
        summa, vsego = 0.0, 0
        for s in range(0, len(por), args.paket):
            b = por[s:s + args.paket]
            obs_t, _ = model.policy.obs_to_tensor({"pov": pov[b], "vec": vec[b]})
            raspr = model.policy.get_distribution(obs_t)
            poterya = (-raspr.log_prob(celi[b]).mean()
                       - args.svoboda * raspr.entropy().mean())
            opt.zero_grad()
            poterya.backward()
            torch.nn.utils.clip_grad_norm_(model.policy.parameters(), 0.5)
            opt.step()
            summa += float(poterya) * len(b)
            vsego += len(b)
        po_kanalam_u, t_u = tochnost(model, pov, vec, act, uch, args.paket)
        _, t_p = tochnost(model, pov, vec, act, pro, args.paket)
        zubrit = "  <- ЗУБРИТ" if t_u - t_p > 0.20 else ""
        print(f"  проход {epoha:2d}: потеря {summa / max(vsego, 1):.3f} | "
              f"учебные {t_u:.1%} | ОТЛОЖЕННЫЕ {t_p:.1%}{zubrit}")
        if t_p > luchshaya + 0.002:
            luchshaya, bez_rosta = t_p, 0
            luchshie = {k: v.detach().clone()
                        for k, v in model.policy.state_dict().items()}
        else:
            bez_rosta += 1
            if bez_rosta >= args.terpenie:
                print(f"  на отложенных не растёт {bez_rosta} прохода — останавливаюсь")
                break

    if luchshie is None:
        raise SystemExit(f"\nРазминка НЕ помогла: лучше {do:.1%} не стало. "
                         "Мозг НЕ сохраняю.")
    model.policy.load_state_dict(luchshie)
    model.policy.set_training_mode(False)
    po_kanalam, posle = tochnost(model, pov, vec, act, pro, args.paket)
    print(f"\n=== ИТОГ на отложенных примерах ===")
    for imya, dolya in zip(KAN.IMENA_KANALOV, po_kanalam):
        print(f"  {imya:<9} {dolya:.1%}")
    print(f"  все пять сразу: было {do:.1%}, стало {posle:.1%}")

    zapas = MODELI / f"do-razminki-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    model.save(MOZG)
    print(f"\nпрежний отложен: {zapas.name}")
    print(f"мозг сохранён  : {MOZG.name}.zip")
    print("\nЭто ещё не проверка в бою. Прогони razbor-boya.bat: доля убийств")
    print("не должна упасть ниже 85%, иначе откатываемся к отложенному.")


if __name__ == "__main__":
    main()
