# -*- coding: utf-8 -*-
"""
РАСШИРЕНИЕ ВЗГЛЯДА 128x128 -> 224x128: прямоугольный кадр под окно 16:9.

ЗАЧЕМ. Окно игры 854x480 (16:9), а квадратный кадр ужимал горизонталь в 1.75
раза сильнее вертикали: зомби «худой», горизонтальные дистанции — самые
важные в дуэли — искажены вдвое против вертикальных. Пользователь играет и
записывает уроки, глядя на настоящие пропорции; существо обязано видеть их
же. 224x128 даёт почти квадратный пиксель (перекос ~2%).

КАК. Тот же приём, что в peresadit_zrenie.py, но по одной оси и с дробным
множителем 7/4: ядро первого слоя 16x16/8x8 дотягивается по горизонтали до
16x28 с шагом 8x14 (28 = 16*7/4, 14 = 8*7/4 — целые, ради этого и выбрана
ширина 224). Веса по горизонтали интерполируются линейно 16 -> 28 и
умножаются на 16/28, чтобы сумма по ядру сохранилась. Позиции окон совпадают
(старт p на 128 <-> старт 7p/4 на 224), окон снова 15x15 — остальная сеть
не тронута.

В ОТЛИЧИЕ ОТ ПЕРВОЙ ОПЕРАЦИИ тождество здесь НЕ побайтовое: широкий кадр —
не апскейл квадратного, а другой захват той же сцены (мод усредняет клетки
исходного окна по-другому), и линейная интерполяция ядра приближает, а не
повторяет старую свёртку. Офлайн-проверка ниже ловит ошибки хирургии на
синтетическом растяжении; настоящий суд — живые парные кадры (одна
замороженная сцена, снятая 128x128 и 224x128) и опора замороженным мозгом.

Запуск: питон из ~/minecraft-ai/venv, из корня mc-lab-mod, ПОСЛЕ
peresadit_zrenie.py (вход — мозг 128x128).
"""

import shutil
import sys
from pathlib import Path

import numpy as np
import torch as th
import torch.nn.functional as F
import gymnasium as gym
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).parent))
from telo import mir as M          # noqa: E402
from telo import kanaly as KAN     # noqa: E402
from telo.vshivka import stopki_po_otstupam  # noqa: E402
from telo.zrenie import GlazaShirokie  # noqa: E402

ROOT = Path(__file__).parent
MOZG = ROOT / "models" / "ppo_ubijca"
POKAZ = ROOT / "pokaz"
VYSOTA, SHIR_STAR, SHIR_NOV = 128, 128, 224


class MirShirokij(gym.Env):
    """Заглушка с новыми пространствами: только чтобы собрать свежую сеть."""

    def __init__(self):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (3 * M.KADROV_V_PAMYATI, VYSOTA, SHIR_NOV),
                                  np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.MultiDiscrete(KAN.KANALY)

    def reset(self, *, seed=None, options=None):
        return self.observation_space.sample(), {}

    def step(self, action):
        return self.observation_space.sample(), 0.0, False, False, {}


def rastyanut_gorizontal(w):
    """(32,24,16,16) -> (32,24,16,28): линейная интерполяция + сохранение суммы."""
    w2 = F.interpolate(w, size=(w.shape[2], 28), mode="bilinear",
                       align_corners=False)
    return w2 * (w.shape[3] / 28.0)


def logity(model, pov_nhwc, vec):
    obs_t, _ = model.policy.obs_to_tensor({"pov": pov_nhwc, "vec": vec})
    with th.no_grad():
        raspr = model.policy.get_distribution(obs_t).distribution
        cennost = model.policy.predict_values(obs_t)
    return [d.logits for d in raspr], cennost


def boevye_stopki_128():
    """Боевые кадры уроков (64x64), поднятые до 128 тем же путём, что при
    первой пересадке: на них старый 128-мозг заведомо в своей тарелке."""
    fajly = sorted((POKAZ / "staroe").glob("pokaz-*.npz"))
    if not fajly:
        raise SystemExit("Нет записей показа в pokaz/staroe для проверки")
    d = np.load(fajly[-1])
    pov = d["pov"]
    stopki64 = stopki_po_otstupam(pov)
    shag = max(1, len(stopki64) // 192)
    stopki64 = stopki64[::shag][:192]
    stopki128 = np.repeat(np.repeat(stopki64, 2, axis=1), 2, axis=2)
    return stopki128, d["vec"].astype(np.float32)[::shag][:192]


def main():
    staryj = PPO.load(MOZG, device="cpu")
    forma = tuple(staryj.observation_space["pov"].shape)
    if forma != (3 * M.KADROV_V_PAMYATI, VYSOTA, SHIR_STAR):
        raise SystemExit(f"Мозг не 128x128 (а {forma}) — расширять нечего "
                         "или уже расширен; сперва peresadit_zrenie.py")
    print(f"старый мозг: шагов {staryj.num_timesteps}, pov {forma}")

    novyj = PPO("MultiInputPolicy", MirShirokij(), device="cpu", verbose=0,
                policy_kwargs={**staryj.policy_kwargs,
                               "features_extractor_class": GlazaShirokie})

    sd = dict(staryj.policy.state_dict())
    klyuchi = [k for k in sd if k.endswith("extractors.pov.cnn.0.weight")]
    if len(klyuchi) != 3:
        raise SystemExit(f"Ключей первого слоя {len(klyuchi)}, ожидал 3 — {klyuchi}")
    for k in klyuchi:
        w = sd[k]
        sd[k] = rastyanut_gorizontal(w)
        print(f"дотянул {k}: {tuple(w.shape)} -> {tuple(sd[k].shape)}")
    novyj.policy.load_state_dict(sd, strict=True)

    # ── Проверка хирургии: широкий кадр синтезирован из квадратного тем же
    # линейным растяжением — расхождение ловит ошибки резки, не поведение ──
    stopki128, vec = boevye_stopki_128()
    t = th.from_numpy(stopki128.transpose(0, 3, 1, 2).astype(np.float32))
    shirokie = F.interpolate(t, size=(VYSOTA, SHIR_NOV), mode="bilinear",
                             align_corners=False)
    stopki224 = shirokie.numpy().transpose(0, 2, 3, 1).clip(0, 255).astype(np.uint8)

    l_star, v_star = logity(staryj, stopki128, vec)
    l_nov, v_nov = logity(novyj, stopki224, vec)
    d_logit = max(float((a - b).abs().max()) for a, b in zip(l_star, l_nov))
    sovpalo = min(float((a.argmax(1) == b.argmax(1)).float().mean())
                  for a, b in zip(l_star, l_nov))
    print(f"боевых стопок: {len(stopki128)}; max|dLogit|={d_logit:.3f}, "
          f"худший канал argmax={sovpalo:.2%}, "
          f"max|dV|={float((v_star - v_nov).abs().max()):.3f}")
    # Порог мягче побайтового: интерполяция ядра против интерполяции кадра +
    # округление uint8 дают честный зазор, но решения обязаны совпадать почти
    # всюду, иначе хирургия кривая.
    if sovpalo < 0.98:
        raise SystemExit("ПРОВАЛ ХИРУРГИИ: решения разошлись на синтетическом "
                         "растяжении — перенос сделан неверно. НЕ сохраняю.")

    novyj.num_timesteps = staryj.num_timesteps
    zapas = ROOT / "models" / f"do-shiroty-224-{staryj.num_timesteps}.zip"
    shutil.copy2(MOZG.with_suffix(".zip"), zapas)
    novyj.save(MOZG)
    print(f"квадратный мозг убран в {zapas.name}")
    print(f"мозг расширен и сохранён: {MOZG.name}.zip, pov "
          f"{tuple(novyj.observation_space['pov'].shape)}, шагов {novyj.num_timesteps}")
    print("\nДальше по порядку: (1) живые парные кадры одной замороженной "
          "сцены 128x128 против 224x128 — решения должны совпасть; "
          "(2) опора замороженным >=150 боёв против опоры 128 "
          "(простой 99.1%, мечник 44.9%).")


if __name__ == "__main__":
    main()
