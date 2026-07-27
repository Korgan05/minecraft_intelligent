# -*- coding: utf-8 -*-
"""
РАЗМИНКА ПО ПОКАЗУ в новой лаборатории. Две части:

  1. НАРАЩИВАНИЕ ГОЛОВЫ. Мозг пришёл из старой лаборатории с 12 выходами, а
     действий теперь 13 — добавился прыжок на месте. Наивная замена выбросила бы
     176 тысяч шагов опыта; вместо этого переносим все слои, а новому выходу
     даём начальные веса от родственных действий.
  2. ПОДРАЖАНИЕ показу человека. Учим НЕДОЛГО и следим за отложенными примерами:
     иначе сеть вызубрит кадры наизусть. В прошлый раз на 543 примерах она
     схлопнулась в одно действие — теперь примеров 4341.

Minecraft не нужен. Запуск: uchit.bat
"""

import argparse
import glob
import os
from datetime import datetime
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO

import mir as M

ROOT = Path(__file__).parent
POKAZ = ROOT / "pokaz"
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
STARYJ_MOZG = Path.home() / "mc-killer" / "models" / "ppo_killer"


class _TolkoProstranstva(gym.Env):
    """Пустышка: объявляет форму чувств и действий, Minecraft не нужен."""

    def __init__(self, dejstvij):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (64, 64, 3), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.Discrete(dejstvij)

    def _pusto(self):
        return {"pov": np.zeros((64, 64, 3), np.uint8), "vec": np.zeros(6, np.float32)}

    def reset(self, *, seed=None, options=None):
        return self._pusto(), {}

    def step(self, a):
        return self._pusto(), 0.0, False, False, {}


def novyj_mozg(device, lr):
    return PPO("MultiInputPolicy", _TolkoProstranstva(len(M.DEJSTVIYA)), device=device,
               verbose=0, n_steps=1024, batch_size=256, learning_rate=lr,
               ent_coef=0.02, gamma=0.99)


def rodstvenniki(i, n_old):
    """Кем инициализировать новый выход — родственным действием.

    Смотрим и клавиши, и МЫШЬ. Прыжок на месте делит ПРОБЕЛ с прыжком вперёд.
    А разворот влево на 45 родня мелкому повороту влево — они двигают мышь в одну
    сторону. По одним клавишам родню поворотов найти нельзя: у них клавиш нет
    вовсе, и новый выход начинал бы со средней мешанины по всем действиям.
    """
    d = M.DEJSTVIYA[i]
    kl = set(d.get("klavishi", []))
    mysh = d.get("mysh")
    bratya = []
    for j in range(n_old):
        e = M.DEJSTVIYA[j]
        if kl and kl & set(e.get("klavishi", [])):
            bratya.append(j)
            continue
        m2 = e.get("mysh")
        # Родня — только по ТОЙ ЖЕ ОСИ и в ту же сторону. Без проверки оси
        # «разворот влево» считал роднёй «взгляд вверх»: оба сдвига отрицательные,
        # хоть и по разным осям, и мешанина попала бы в начальные веса.
        if mysh and m2:
            osi = [n for n, a in enumerate(mysh) if a != 0]
            if osi and all(m2[n] != 0 and (mysh[n] > 0) == (m2[n] > 0) for n in osi):
                bratya.append(j)
    return bratya or list(range(n_old))


def perenesti(device, lr):
    """Взять мозг из старой лаборатории и нарастить голову под новые действия."""
    if MOZG.with_suffix(".zip").exists():
        m = PPO.load(MOZG, env=_TolkoProstranstva(len(M.DEJSTVIYA)), device=device)
        print(f"продолжаю с мозга новой лаборатории: шагов {m.num_timesteps}")
        return m
    if not STARYJ_MOZG.with_suffix(".zip").exists():
        print("прежнего мозга нет — начинаю с нуля")
        return novyj_mozg(device, lr)

    staryj = PPO.load(STARYJ_MOZG, device="cpu")
    n_old, n_new = int(staryj.action_space.n), len(M.DEJSTVIYA)
    print(f"беру мозг из старой лаборатории: действий {n_old}, шагов {staryj.num_timesteps}")
    novyj = novyj_mozg(device, lr)
    sd_s, sd_n = staryj.policy.state_dict(), novyj.policy.state_dict()

    perenes = 0
    for k in sd_n:
        if k in sd_s and sd_s[k].shape == sd_n[k].shape:
            sd_n[k] = sd_s[k].clone().to(sd_n[k].device)
            perenes += 1
    print(f"  перенесено слоёв как есть: {perenes} (глаза, чувства, тело сети)")

    if n_new > n_old:
        w_s, b_s = sd_s["action_net.weight"], sd_s["action_net.bias"]
        w_n, b_n = sd_n["action_net.weight"].clone(), sd_n["action_net.bias"].clone()
        w_n[:n_old], b_n[:n_old] = w_s.to(w_n.device), b_s.to(b_n.device)
        for i in range(n_old, n_new):
            br = rodstvenniki(i, n_old)
            w_n[i] = torch.stack([w_s[j] for j in br]).mean(0).to(w_n.device)
            b_n[i] = torch.stack([b_s[j] for j in br]).mean(0).to(b_n.device)
            print(f"  новый выход {i} ({M.IMENA[i]}) начинает как смесь: "
                  + ", ".join(M.IMENA[j] for j in br))
        sd_n["action_net.weight"], sd_n["action_net.bias"] = w_n, b_n
    novyj.policy.load_state_dict(sd_n)
    novyj.num_timesteps = staryj.num_timesteps
    return novyj


def zagruzit():
    fajly = sorted(glob.glob(str(POKAZ / "pokaz-*.npz")), key=os.path.getmtime)
    if not fajly:
        raise SystemExit(f"Записей нет. Сначала запиши показ: zapis.bat ({POKAZ})")
    pov, vec, act = [], [], []
    for f in fajly:
        d = np.load(f)
        pov.append(d["pov"]); vec.append(d["vec"]); act.append(d["act"])
        print(f"  {os.path.basename(f)}: {len(d['act'])} примеров")
    return np.concatenate(pov), np.concatenate(vec), np.concatenate(act)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epoh", type=int, default=40, help="максимум проходов")
    p.add_argument("--cel", type=float, default=0.75,
                   help="точность, на которой останавливаемся (не 1.0 намеренно)")
    p.add_argument("--svoboda", type=float, default=0.01, help="бонус за неуверенность")
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--paket", type=int, default=128)
    args = p.parse_args()

    MODELI.mkdir(exist_ok=True)
    print("Читаю показ:")
    pov, vec, act = zagruzit()
    n = len(act)
    print(f"\nвсего примеров: {n}")
    print("что показано:")
    for i, imya in enumerate(M.IMENA):
        kol = int((act == i).sum())
        if kol:
            print(f"   {imya:<17} {kol:5d}  ({100 * kol / n:5.1f}%)")
    if not np.isin(act, [9, 11]).any():
        raise SystemExit("\nВ показе НЕТ удара — учить нечему.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nустройство: {device}")
    model = perenesti(device, args.lr)

    model.policy.set_training_mode(True)
    opt = torch.optim.Adam(model.policy.parameters(), lr=args.lr)
    celi_vse = torch.as_tensor(act, dtype=torch.long, device=device)

    rng = np.random.default_rng(0)
    poryadok = rng.permutation(n)
    granica = int(n * 0.85)
    uch, pro = poryadok[:granica], poryadok[granica:]
    print(f"учебных {len(uch)}, отложенных {len(pro)}")

    def tochnost(idx):
        if len(idx) == 0:
            return 0.0
        ugadal = 0
        with torch.no_grad():
            for s in range(0, len(idx), args.paket):
                b = idx[s:s + args.paket]
                obs_t, _ = model.policy.obs_to_tensor({"pov": pov[b], "vec": vec[b]})
                probs = model.policy.get_distribution(obs_t).distribution.probs
                ugadal += int((probs.argmax(1) == celi_vse[b]).sum())
        return ugadal / len(idx)

    print(f"\nразминка: до {args.epoh} проходов, остановка при {args.cel:.0%} "
          f"или когда на отложенных перестанет расти")
    luchshaya, luchshie, bez_rosta = -1.0, None, 0
    for epoha in range(1, args.epoh + 1):
        por = rng.permutation(uch)
        summa, vsego = 0.0, 0
        for s in range(0, len(por), args.paket):
            b = por[s:s + args.paket]
            obs_t, _ = model.policy.obs_to_tensor({"pov": pov[b], "vec": vec[b]})
            dist = model.policy.get_distribution(obs_t)
            loss = -dist.log_prob(celi_vse[b]).mean() - args.svoboda * dist.entropy().mean()
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.policy.parameters(), 0.5)
            opt.step()
            summa += float(loss) * len(b)
            vsego += len(b)
        t_u, t_p = tochnost(uch), tochnost(pro)
        zubrit = "  <- ЗУБРИТ" if t_u - t_p > 0.25 else ""
        print(f"  проход {epoha:2d}: потеря {summa / max(vsego,1):.3f} | "
              f"учебные {t_u:.1%} | ОТЛОЖЕННЫЕ {t_p:.1%}{zubrit}")
        if t_p > luchshaya:
            luchshaya, bez_rosta = t_p, 0
            luchshie = {k: v.detach().clone() for k, v in model.policy.state_dict().items()}
        else:
            bez_rosta += 1
        if t_p >= args.cel:
            print("  -> достаточно: дальше пошло бы слепое копирование")
            break
        if bez_rosta >= 4:
            print("  -> на отложенных роста нет четыре прохода: дальше только зубрёжка")
            break
    if luchshie:
        model.policy.load_state_dict(luchshie)
        print(f"\nберу лучшее состояние: {luchshaya:.1%} на невиданных примерах")

    zip_put = MOZG.with_suffix(".zip")
    if zip_put.exists():
        arhiv = MODELI / f"do-razminki-{datetime.now():%Y%m%d-%H%M%S}.zip"
        zip_put.rename(arhiv)
        print(f"прежний отложен: {arhiv.name}")
    model.save(MOZG)
    print(f"мозг сохранён: {zip_put.name} (шагов {model.num_timesteps})")
    print("\nДальше: обучение с наградой в новой лаборатории.")


if __name__ == "__main__":
    main()
