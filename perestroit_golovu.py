# -*- coding: utf-8 -*-
"""
ПЕРЕСТРОЙКА ГОЛОВЫ на пять каналов. Игра не нужна.

Что переносится и что пересобирается:
  * ЗРЕНИЕ (свёрточная часть) — переносится БЕЗ ИЗМЕНЕНИЙ. Это самое дорогое,
    что есть у существа: узнавать зомби на 64x64 оно училось двести тысяч шагов.
  * оценка положения (сколько стоит нынешняя обстановка) — тоже переносится;
  * ГОЛОВА РЕШЕНИЯ пересобирается: было двадцать выходов, стало двадцать шесть,
    разложенных по пяти каналам.

Как переносится поведение. Старая голова на каждом кадре даёт вероятности
двадцати действий. Каждое из них раскладывается по каналам (таблица в kanaly.py),
и складывая вероятности, получаем, чего старый мозг хотел ОТ КАЖДОГО КАНАЛА
в отдельности. Новую голову подгоняем повторять именно это.

Сочетания, которых у старого мозга не было (шаг вбок с доворотом, прыжок с
ударом), получаются при этом сами собой и с МАЛОЙ вероятностью — потому что
складывать в них было нечего. Это и нужно: тот самый урок, который я усвоил на
памяти и на размахах. Новому даём почти ноль, обучение нарастит само.

Проверка строгая и провалиться может: на отложенных кадрах самое вероятное
сочетание новой головы обязано совпасть с выбором старой. Не совпало — не
сохраняем.

Запуск: zapusk\\perestroit-golovu.bat
"""

import glob
import shutil
from datetime import datetime
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO

from telo import kanaly as KAN

ROOT = Path(__file__).parent
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
KADROV_V_PAMYATI = 4
KUSOK = 128                 # сколько кадров прогонять через зрение за раз
SHAGOV_PODGONKI = 6000
DOLYA_OTLOZHENNYH = 0.25    # четверть кадров не участвует в подгонке — на проверку

# ДВЕ ПЛАНКИ, и вторая важнее.
#
# Первая мерка — совпадение на всех кадрах подряд — оказалась плохо задумана.
# Пять независимых решений в принципе не могут повторить все границы одного
# выбора из двадцати, и она упирается в потолок около 90% при любой подгонке.
# Строгость тут ложная: расхождение на кадре, где старый мозг сам метался между
# двумя равными вариантами, ничего не стоит.
#
# Вторая мерка честнее: совпадение ТАМ, ГДЕ СТАРЫЙ МОЗГ БЫЛ УВЕРЕН. Если он
# твёрдо выбирал удар, а новая голова говорит «поворот» — вот это поломка.
PLANKA = 0.85               # на всех кадрах подряд
PLANKA_UVERENNYH = 0.95     # на кадрах, где старый мозг был уверен
UVERENNOST = 0.5            # с какой вероятности считаем выбор твёрдым


class PustoyMir(gym.Env):
    """Мир-заглушка: нужен только чтобы объявить, какого вида вход и выход."""

    def __init__(self):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (64, 64, 3 * KADROV_V_PAMYATI), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.MultiDiscrete(KAN.KANALY)

    def reset(self, *, seed=None, options=None):
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def kadry_iz_zapisej():
    """Настоящие кадры твоей игры: на них и подгоняем, и проверяем."""
    stopki, veki = [], []
    for f in sorted(glob.glob(str(ROOT / "pokaz" / "*.npz"))):
        d = np.load(f)
        pov, vec = d["pov"], d["vec"]
        for i in range(KADROV_V_PAMYATI, len(pov)):
            stopki.append(np.concatenate(
                [pov[i - KADROV_V_PAMYATI + 1 + j] for j in range(KADROV_V_PAMYATI)],
                axis=2))
            veki.append(vec[i])
    return np.stack(stopki), np.stack(veki)


def latent_i_veroyatnosti(mozg, stopki, veki):
    """Прогоняем кадры через зрение старого мозга: что оно видит и чего хочет."""
    latenty, veroyatnosti = [], []
    politika = mozg.policy
    for n in range(0, len(stopki), KUSOK):
        obs = {
            "pov": torch.as_tensor(np.transpose(stopki[n:n + KUSOK], (0, 3, 1, 2))),
            "vec": torch.as_tensor(veki[n:n + KUSOK]),
        }
        with torch.no_grad():
            priznaki = politika.extract_features(obs)
            if isinstance(priznaki, tuple):
                priznaki = priznaki[0]
            lat = politika.mlp_extractor.forward_actor(priznaki)
            latenty.append(lat)
            veroyatnosti.append(torch.softmax(politika.action_net(lat), dim=1))
    return torch.cat(latenty), torch.cat(veroyatnosti)


def celi_po_kanalam(veroyatnosti, ostrota=1.0):
    """Чего старый мозг хотел от каждого канала в отдельности.

    Про ОСТРОТУ. Складывать вероятности как есть — честно, но губительно для
    выбора. Пример из замера: старый мозг даёт удару 24%, повороту влево 20%,
    остальное размазано. Удар побеждает и выбирается. Но в канале «рука» это
    складывается всего в 29% против 71% «ничего», и канал выбирает «ничего».
    Каждый канал по отдельности прав, а вместе они теряют решение — совпало
    всего 59% при пяти каналах сразу.

    Поэтому цель заостряем: возводим вероятности в степень 1/острота. При
    остроте 1 всё как есть, при малой остаётся почти только то, что старый мозг
    реально ВЫБРАЛ. Нужную величину не угадываем, а подбираем замером ниже.
    """
    p = veroyatnosti
    if ostrota != 1.0:
        p = torch.softmax(torch.log(p.clamp_min(1e-9)) / ostrota, dim=1)
    celi = []
    for kanal, skolko in enumerate(KAN.KANALY):
        q = torch.zeros(len(p), skolko)
        for staroe, tuple_kanalov in enumerate(KAN.STAROE_V_KANALY):
            q[:, tuple_kanalov[kanal]] += p[:, staroe]
        celi.append(q)
    return celi


def razbit_po_kanalam(logity):
    """Двадцать шесть выходов -> пять кусков, по одному на канал."""
    kuski, nachalo = [], 0
    for skolko in KAN.KANALY:
        kuski.append(logity[:, nachalo:nachalo + skolko])
        nachalo += skolko
    return kuski


def podognat(golova, latent, celi, shagov=SHAGOV_PODGONKI, tiho=False):
    """Учим новую голову хотеть от каждого канала того же, чего хотел старый мозг."""
    opt = torch.optim.Adam(golova.parameters(), lr=3e-3)
    shag_lr = torch.optim.lr_scheduler.CosineAnnealingLR(opt, shagov, eta_min=1e-4)
    for shag in range(shagov):
        opt.zero_grad()
        kuski = razbit_po_kanalam(golova(latent))
        poterya = sum((-(c * torch.log_softmax(k, dim=1)).sum(dim=1)).mean()
                      for k, c in zip(kuski, celi))
        poterya.backward()
        opt.step()
        shag_lr.step()
        if not tiho and (shag % 500 == 0 or shag == shagov - 1):
            print(f"   подгонка {shag + 1:5d}/{shagov}: расхождение {float(poterya):.4f}")
    return golova


def vybor(golova, latent):
    """Самое вероятное сочетание по каждому каналу."""
    return torch.stack([k.argmax(dim=1) for k in razbit_po_kanalam(golova(latent))], dim=1)


def main():
    staryj = PPO.load(MOZG, device="cpu")
    print(f"старый мозг: {staryj.num_timesteps} шагов, действий {staryj.action_space.n}")
    if staryj.action_space.n != len(KAN.STAROE_V_KANALY):
        raise SystemExit(f"Ожидал {len(KAN.STAROE_V_KANALY)} действий, а их "
                         f"{staryj.action_space.n}. Таблица перевода не подходит.")

    print("\nберу кадры из твоих записей...")
    stopki, veki = kadry_iz_zapisej()
    print(f"  кадров: {len(stopki)}")
    latent, veroyatnosti = latent_i_veroyatnosti(staryj, stopki, veki)
    staryj_vybor = veroyatnosti.argmax(dim=1)

    # Часть кадров откладываем: подгонять и проверять на одном и том же нельзя,
    # иначе проверка снова окажется такой, которая не может провалиться.
    n = len(latent)
    otlozheno = int(n * DOLYA_OTLOZHENNYH)
    poryadok = torch.randperm(n)
    uchebnye, proverochnye = poryadok[otlozheno:], poryadok[:otlozheno]
    print(f"  на подгонку {len(uchebnye)}, отложено на проверку {len(proverochnye)}")

    print("\nсобираю новый мозг: зрение переносится, голова пересобирается")
    novyj = PPO("MultiInputPolicy", PustoyMir(), device="cpu",
                policy_kwargs=staryj.policy_kwargs, learning_rate=staryj.learning_rate,
                n_steps=staryj.n_steps, batch_size=staryj.batch_size,
                n_epochs=staryj.n_epochs, gamma=staryj.gamma,
                gae_lambda=staryj.gae_lambda, ent_coef=staryj.ent_coef,
                vf_coef=staryj.vf_coef, max_grad_norm=staryj.max_grad_norm,
                verbose=0)
    perenos = {k: v for k, v in staryj.policy.state_dict().items()
               if not k.startswith("action_net")}
    itog = novyj.policy.load_state_dict(perenos, strict=False)
    lishnie = [k for k in itog.unexpected_keys]
    ne_hvatilo = [k for k in itog.missing_keys if not k.startswith("action_net")]
    if lishnie or ne_hvatilo:
        raise SystemExit(f"Перенос неполный. Лишние: {lishnie}. Не хватило: {ne_hvatilo}")
    print(f"  перенесено слоёв: {len(perenos)}, голова новая: "
          f"{novyj.policy.action_net.out_features} выходов")

    dolzhno = torch.tensor([KAN.STAROE_V_KANALY[int(a)]
                            for a in staryj_vybor[proverochnye]])
    ishodnaya_golova = {k: v.clone()
                        for k, v in novyj.policy.action_net.state_dict().items()}

    # Остроту цели не угадываем, а подбираем: берём САМУЮ МЯГКУЮ, которая
    # проходит планку. Мягче — значит ближе к настоящим сомнениям старого мозга,
    # а не к его самоуверенности, и значит существо сохранит разнообразие в бою.
    print("\nподбираю остроту цели (мягче — лучше, если проходит планку):")
    luchshee = None
    for ostrota in (1.0, 0.5, 0.25, 0.1, 0.03):
        novyj.policy.action_net.load_state_dict(ishodnaya_golova)
        celi = celi_po_kanalam(veroyatnosti, ostrota)
        podognat(novyj.policy.action_net, latent[uchebnye],
                 [c[uchebnye] for c in celi], tiho=True)
        with torch.no_grad():
            novyj_vybor = vybor(novyj.policy.action_net, latent[proverochnye])
            kuski = razbit_po_kanalam(novyj.policy.action_net(latent[proverochnye]))
            entropiya = float(sum(
                -(torch.softmax(k, 1) * torch.log_softmax(k, 1)).sum(1).mean()
                for k in kuski))
        sovpalo = (novyj_vybor == dolzhno).all(dim=1)
        celikom = float(sovpalo.float().mean())
        uverennye = veroyatnosti[proverochnye].max(dim=1).values >= UVERENNOST
        na_uverennyh = float(sovpalo[uverennye].float().mean()) if uverennye.any() else 0.0
        print(f"  острота {ostrota:<5}: совпало {100 * celikom:5.1f}%, "
              f"на уверенных {100 * na_uverennyh:5.1f}%, разнообразие {entropiya:.2f}")
        if celikom >= PLANKA and na_uverennyh >= PLANKA_UVERENNYH and luchshee is None:
            luchshee = (ostrota, celikom, na_uverennyh,
                        {k: v.clone()
                         for k, v in novyj.policy.action_net.state_dict().items()})

    if luchshee is None:
        raise SystemExit(f"\nОПЕРАЦИЯ НЕУДАЧНА: ни одна острота не дала "
                         f"{100 * PLANKA:.0f}% на всех и {100 * PLANKA_UVERENNYH:.0f}% "
                         f"на уверенных. Мозг НЕ сохраняю.")
    ostrota, celikom, na_uverennyh, golova = luchshee
    novyj.policy.action_net.load_state_dict(golova)
    print(f"\nвыбрана острота {ostrota}: совпало {100 * celikom:.1f}%, "
          f"на уверенных кадрах {100 * na_uverennyh:.1f}%")

    with torch.no_grad():
        novyj_vybor = vybor(novyj.policy.action_net, latent[proverochnye])
    po_kanalam = (novyj_vybor == dolzhno).float().mean(dim=0)
    print("\n=== ПРОВЕРКА на отложенных кадрах ===")
    for imya, dolya in zip(KAN.IMENA_KANALOV, po_kanalam):
        print(f"  {imya:<9} совпало {100 * float(dolya):5.1f}%")
    print(f"  ВСЕ ПЯТЬ СРАЗУ  {100 * celikom:5.1f}%")

    novyj.num_timesteps = staryj.num_timesteps
    zapas = MODELI / f"do-kanalov-{datetime.now():%Y%m%d-%H%M%S}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    novyj.save(MOZG)
    print(f"\nстарый мозг отложен: {zapas.name}")
    print(f"новый сохранён      : {MOZG.name}.zip ({novyj.num_timesteps} шагов)")
    print("\nТеперь существо может идти боком и доворачивать прицел одновременно.")
    print("Сочетания, которых у него не было, начинают с малой вероятностью —")
    print("обучение нарастит те, что окажутся полезны.")


if __name__ == "__main__":
    main()
