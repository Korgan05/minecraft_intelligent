# -*- coding: utf-8 -*-
"""
ПОЧИНИТЬ РАЗГОН ADAM после операции над мозгом. Игра не нужна.

Что нашли. Каждая наша операция над мозгом (память, каналы решения, голова)
делается так: создаётся НОВЫЙ PPO и в него переносятся ВЕСА. А у Adam кроме
весов есть свой разгон — накопленные средние градиента и его квадрата
(exp_avg, exp_avg_sq). Он не переносится и остаётся ПУСТЫМ.

Почему это ломает. Adam делит шаг на корень из накопленного квадрата градиента.
Когда накоплений нет, знаменатель берётся из первого же градиента, и поправка на
смещение (bias correction) в первых обновлениях делает шаг порядка скорости
обучения по КАЖДОМУ весу — независимо от того, большой градиент или крошечный.
То есть сразу после операции мозг получает несколько огромных, почти
неизбирательных обновлений.

Совпадение, которое это подтверждает: ОБА обвала случились сразу после операции
над мозгом. Ночной — после починки памяти, черепаха — после расширения памяти.
И приборы прогона черепахи показывают ровно такую подпись: approx_kl 0.20 при
норме 0.01, clip_fraction 0.69 при норме 0.1, и policy_gradient_loss
ПОЛОЖИТЕЛЬНЫЙ на всех пяти обновлениях — цель после обновления становилась хуже.

Что делаем. Берём разгон из снимка ДО операции и переносим в нынешний мозг:
  * веса одинаковой формы — разгон переносится как есть;
  * первый слой зрения стал шире (12 каналов -> 24): прежний разгон уходит в
    ХВОСТ (свежие кадры), а новым каналам ставим НОЛЬ — ровно как самим весам.
    Ноль здесь правильный: по новым каналам градиента ещё не было.

Проверка строгая и провалиться может: ВЕСА обязаны остаться байт в байт теми же,
а число весов с разгоном — вырасти с нуля до всех. Если веса шевельнулись — не
сохраняем.

Запуск: zapusk\\pochinit-razgon.bat
"""

import argparse
import io
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import torch
from stable_baselines3 import PPO

ROOT = Path(__file__).parent
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"


def razgon_iz_snimka(put):
    """Разгон Adam прямо из архива снимка, без сборки мира."""
    z = zipfile.ZipFile(put)
    if "policy.optimizer.pth" not in z.namelist():
        return None
    d = torch.load(io.BytesIO(z.read("policy.optimizer.pth")),
                   map_location="cpu", weights_only=False)
    return d.get("state") or None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--otkuda", default=None,
                   help="снимок, из которого брать разгон (по умолчанию последний do-pamyati-*)")
    args = p.parse_args()

    if args.otkuda:
        otkuda = Path(args.otkuda)
    else:
        svechi = sorted(MODELI.glob("do-pamyati-*.zip"))
        if not svechi:
            raise SystemExit("не нашёл снимок do-pamyati-*.zip — укажи --otkuda")
        otkuda = svechi[-1]
    print(f"разгон беру из: {otkuda.name}")

    model = PPO.load(MOZG, device="cpu")
    parametry = list(model.policy.optimizer.param_groups[0]["params"])
    bylo_s_razgonom = len(model.policy.optimizer.state_dict()["state"])
    print(f"мозг: {model.num_timesteps} шагов, весов {len(parametry)}, "
          f"из них с разгоном {bylo_s_razgonom}")
    if bylo_s_razgonom == len(parametry):
        raise SystemExit("разгон уже на месте — чинить нечего.")

    staryj = razgon_iz_snimka(otkuda)
    if staryj is None:
        raise SystemExit(f"в {otkuda.name} нет разгона — возьми другой снимок.")
    print(f"в снимке весов с разгоном: {len(staryj)}")
    if len(staryj) != len(parametry):
        raise SystemExit(f"весов в снимке {len(staryj)}, а в мозге {len(parametry)} — "
                         "это разные устройства, переносить нельзя.")

    # Слепок весов ДО, чтобы потом доказать, что мы их не тронули.
    do = {i: t.detach().clone() for i, t in enumerate(parametry)}

    novoe, rasshireno, perenes = {}, [], 0
    for i, param in enumerate(parametry):
        star = staryj[i]
        zapis = {}
        for imya, znach in star.items():
            # step тоже тензор, но нулевой размерности — это счётчик, не разгон.
            if not torch.is_tensor(znach) or znach.dim() == 0:
                zapis[imya] = znach.clone() if torch.is_tensor(znach) else znach
                continue
            if znach.shape == param.shape:
                zapis[imya] = znach.clone()
                continue
            # Первый слой зрения стал шире: прежнее в хвост, новому ноль.
            if (znach.dim() == 4 and znach.shape[0] == param.shape[0]
                    and znach.shape[1] < param.shape[1]
                    and znach.shape[2:] == param.shape[2:]):
                t = torch.zeros_like(param)
                t[:, -znach.shape[1]:] = znach
                zapis[imya] = t
                if i not in rasshireno:
                    rasshireno.append(i)
            else:
                raise SystemExit(
                    f"вес {i}, поле {imya}: форма {tuple(znach.shape)} против "
                    f"{tuple(param.shape)} — не знаю, как переносить. Не сохраняю.")
        novoe[i] = zapis
        perenes += 1

    model.policy.optimizer.load_state_dict(
        {"state": novoe, "param_groups": model.policy.optimizer.state_dict()["param_groups"]})

    stalo = model.policy.optimizer.state_dict()["state"]
    posle = list(model.policy.optimizer.param_groups[0]["params"])
    tselo = all(torch.equal(do[i], posle[i].detach()) for i in range(len(posle)))

    print()
    print(f"=== ПРОВЕРКА ===")
    print(f"  весов с разгоном: было {bylo_s_razgonom}, стало {len(stalo)} из {len(parametry)}")
    print(f"  расширено под новую память: веса {rasshireno} "
          f"(прежний разгон в хвост, новым каналам ноль)")
    print(f"  ВЕСА не тронуты: {'да' if tselo else 'НЕТ'}")
    for i in rasshireno:
        sr = stalo[i]["exp_avg_sq"]
        n = sr.shape[1] // 2
        print(f"    вес {i}: разгон по новым каналам {float(sr[:, :n].abs().sum()):.3e} "
              f"(должен быть 0), по прежним {float(sr[:, n:].abs().sum()):.3e}")

    if not tselo:
        raise SystemExit("\nВЕСА ИЗМЕНИЛИСЬ. Перенос разгона не имеет права их касаться. "
                         "Мозг НЕ сохраняю.")
    if len(stalo) != len(parametry):
        raise SystemExit(f"\nразгон перенёсся не для всех весов "
                         f"({len(stalo)} из {len(parametry)}). Мозг НЕ сохраняю.")

    zapas = MODELI / f"do-razgona-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    model.save(MOZG)
    proverka = razgon_iz_snimka(MOZG.with_suffix(".zip"))
    print(f"\nпрежний отложен: {zapas.name}")
    print(f"мозг сохранён   : {MOZG.name}.zip — в файле весов с разгоном: "
          f"{len(proverka) if proverka else 0}")
    if not proverka or len(proverka) != len(parametry):
        raise SystemExit("В ФАЙЛЕ разгона нет. Сохранение не сработало.")
    print("\nТеперь Adam не начнёт с чистого листа, и первые обновления после")
    print("операции над мозгом не будут швырять его наугад.")


if __name__ == "__main__":
    main()
