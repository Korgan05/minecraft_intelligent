# -*- coding: utf-8 -*-
"""
ВШИВКА УРОКА В ОБУЧЕНИЕ: RL идёт как обычно, но к каждому шагу градиента
добавляется мягкая тяга к действиям человека на кадрах его урока.

ЗАЧЕМ. Дуэль с мечником не берётся ни наградой, ни подражанием по отдельности,
и это доказано дорого:
  * пять разных прогонов RL (экономика, чистые мечники, толстая маржа, целая
    ночь на 2962 боя) — разведка не открывает связку «выйди из замаха → войди →
    ударь → выйди»: она из нескольких согласованных шагов, и каждая неполная
    попытка наказывается смертью раньше, чем связка сложится;
  * чистое подражание (разминка) дважды отказалось честно и один раз сломало
    мозг принуждением: у него некому требовать побед, и оно сплющивает политику
    в «среднее по уроку».
Вшивка — скрещивание: урок делает приём ВЕРОЯТНЫМ (существо начинает его
пробовать), а награда решает, что закреплять. Урок предлагает, награда
распоряжается. Так учили стартовые версии AlphaStar и кикстартеры DeepMind.

КАК УСТРОЕНО. Наследник PPO с переписанным train(): тело скопировано из
установленной библиотеки (ppo/ppo.py, строки 184-300) БЕЗ ИЗМЕНЕНИЙ, кроме
одного добавления перед loss.backward():

    loss = loss + tyaga * (-log_prob(действия человека на кадрах урока))

При tyaga == 0 добавка не вычисляется вовсе — ни одного лишнего обращения к
случайности, ни одного лишнего тензора. Тождество со штатным PPO при нулевой
тяге ПРОВЕРЯЕТСЯ побайтово: proby/proba_vshivki.py гоняет оба класса на
одинаковом наборе и требует равенства весов до последней цифры. Эта проверка
может провалиться — например, если новая версия библиотеки изменит train().

РАСКЛАДКА ПАМЯТИ — ГЛАВНОЕ ОТЛИЧИЕ ОТ РАЗМИНКИ. uchit.stopki() складывала
кадры урока ПОДРЯД (i..i+8), а мир подаёт память с отступами
[16,12,8,5,3,2,1,0] — тот же класс ошибки, что аудит нашёл в проверке пересадки
памяти. Разминка училась на неправильной раскладке времени: офлайн сходилось,
в игре мозг видел другие стопки. Здесь стопки строятся по настоящим отступам.
"""

import glob
import os
from pathlib import Path

import numpy as np
import torch as th
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.utils import explained_variance
from torch.nn import functional as F

from . import mir as M

POKAZ = Path(__file__).parent.parent / "pokaz"
UROK_PAKET = 256                 # кадров урока на один шаг градиента


def stopki_po_otstupam(pov):
    """Кадры урока в стопки ПО ОТСТУПАМ ПАМЯТИ — ровно как их видит мир.

    Начало дополняем повтором первого кадра — как мир в начале боя.
    """
    otstupy = M.OTSTUPY_PAMYATI
    glub = M.GLUBINA_BUFERA
    ryad = [pov[0]] * (glub - 1) + list(pov)
    return np.stack([
        np.concatenate([ryad[i + glub - 1 - o] for o in otstupy], axis=2)
        for i in range(len(pov))
    ])


def zagruzit_urok(metka="duel-mechnik"):
    """Только уроки с меткой: вшиваем именно дуэль, не всё подряд."""
    fajly = sorted(glob.glob(str(POKAZ / f"pokaz-*{metka}*.npz")), key=os.path.getmtime)
    if not fajly:
        raise SystemExit(f"Уроков с меткой «{metka}» нет в {POKAZ}")
    pov_l, vec_l, act_l = [], [], []
    for f in fajly:
        d = np.load(f)
        if d["act"].ndim < 2:
            continue                       # записи до каналов вшивке не годятся
        if len(d["pov"]) != len(d["act"]):
            raise SystemExit(f"урок {os.path.basename(f)} рассогласован: "
                             f"кадров {len(d['pov'])}, действий {len(d['act'])}")
        pov_l.append(stopki_po_otstupam(d["pov"]))
        vec_l.append(d["vec"])
        act_l.append(d["act"])
        print(f"  урок {os.path.basename(f)}: {len(d['act'])} кадров")
    pov = np.concatenate(pov_l).astype(np.uint8)
    vec = np.concatenate(vec_l).astype(np.float32)
    act = np.concatenate(act_l).astype(np.int64)
    return pov, vec, act


class PPOSUrokom(PPO):
    """PPO с тягой к уроку человека. При tyaga=0 тождествен штатному PPO."""

    tyaga = 0.0
    urok_pov = None
    urok_vec = None
    urok_act = None
    _urok_rng = None

    def nastroit_urok(self, pov, vec, act, tyaga):
        self.urok_pov = pov
        self.urok_vec = vec
        self.urok_act = act
        self.tyaga = float(tyaga)
        # Свой генератор случайности: не трогаем глобальные потоки, иначе
        # тождество при tyaga=0 стало бы недоказуемым.
        self._urok_rng = np.random.default_rng(7)

    def _urok_poterya(self):
        """Насколько политика не согласна с человеком на случайной пачке урока."""
        n = min(UROK_PAKET, len(self.urok_act))
        idx = self._urok_rng.integers(0, len(self.urok_act), size=n)
        obs, _ = self.policy.obs_to_tensor(
            {"pov": self.urok_pov[idx], "vec": self.urok_vec[idx]})
        raspr = self.policy.get_distribution(obs)
        celi = th.as_tensor(self.urok_act[idx], device=self.device, dtype=th.long)
        return -raspr.log_prob(celi).mean()

    def train(self) -> None:
        # ── скопировано из установленной stable_baselines3/ppo/ppo.py ──
        self.policy.set_training_mode(True)
        self._update_learning_rate(self.policy.optimizer)
        clip_range = self.clip_range(self._current_progress_remaining)
        if self.clip_range_vf is not None:
            clip_range_vf = self.clip_range_vf(self._current_progress_remaining)

        entropy_losses = []
        pg_losses, value_losses = [], []
        clip_fractions = []
        urok_poteri = []                                       # ДОБАВЛЕНО

        continue_training = True
        for epoch in range(self.n_epochs):
            approx_kl_divs = []
            for rollout_data in self.rollout_buffer.get(self.batch_size):
                actions = rollout_data.actions
                if isinstance(self.action_space, spaces.Discrete):
                    actions = rollout_data.actions.long().flatten()

                values, log_prob, entropy = self.policy.evaluate_actions(
                    rollout_data.observations, actions)
                values = values.flatten()
                advantages = rollout_data.advantages
                if self.normalize_advantage and len(advantages) > 1:
                    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

                ratio = th.exp(log_prob - rollout_data.old_log_prob)
                policy_loss_1 = advantages * ratio
                policy_loss_2 = advantages * th.clamp(ratio, 1 - clip_range, 1 + clip_range)
                policy_loss = -th.min(policy_loss_1, policy_loss_2).mean()

                pg_losses.append(policy_loss.item())
                clip_fraction = th.mean((th.abs(ratio - 1) > clip_range).float()).item()
                clip_fractions.append(clip_fraction)

                if self.clip_range_vf is None:
                    values_pred = values
                else:
                    values_pred = rollout_data.old_values + th.clamp(
                        values - rollout_data.old_values, -clip_range_vf, clip_range_vf)
                value_loss = F.mse_loss(rollout_data.returns, values_pred)
                value_losses.append(value_loss.item())

                if entropy is None:
                    entropy_loss = -th.mean(-log_prob)
                else:
                    entropy_loss = -th.mean(entropy)
                entropy_losses.append(entropy_loss.item())

                loss = policy_loss + self.ent_coef * entropy_loss + self.vf_coef * value_loss

                # ── ДОБАВЛЕНО: тяга к уроку. Урок предлагает, награда решает ──
                if self.tyaga > 0.0 and self.urok_act is not None:
                    urok = self._urok_poterya()
                    urok_poteri.append(urok.item())
                    loss = loss + self.tyaga * urok
                # ──────────────────────────────────────────────────────────────

                with th.no_grad():
                    log_ratio = log_prob - rollout_data.old_log_prob
                    approx_kl_div = th.mean((th.exp(log_ratio) - 1) - log_ratio).cpu().numpy()
                    approx_kl_divs.append(approx_kl_div)

                if self.target_kl is not None and approx_kl_div > 1.5 * self.target_kl:
                    continue_training = False
                    if self.verbose >= 1:
                        print(f"Early stopping at step {epoch} due to reaching max kl: {approx_kl_div:.2f}")
                    break

                self.policy.optimizer.zero_grad()
                loss.backward()
                th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.policy.optimizer.step()

            self._n_updates += 1
            if not continue_training:
                break

        explained_var = explained_variance(
            self.rollout_buffer.values.flatten(), self.rollout_buffer.returns.flatten())

        self.logger.record("train/entropy_loss", np.mean(entropy_losses))
        self.logger.record("train/policy_gradient_loss", np.mean(pg_losses))
        self.logger.record("train/value_loss", np.mean(value_losses))
        self.logger.record("train/approx_kl", np.mean(approx_kl_divs))
        self.logger.record("train/clip_fraction", np.mean(clip_fractions))
        self.logger.record("train/loss", loss.item())
        self.logger.record("train/explained_variance", explained_var)
        if urok_poteri:                                        # ДОБАВЛЕНО
            self.logger.record("train/urok", np.mean(urok_poteri))
        if hasattr(self.policy, "log_std"):
            self.logger.record("train/std", th.exp(self.policy.log_std).mean().item())
        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/clip_range", clip_range)
        if self.clip_range_vf is not None:
            self.logger.record("train/clip_range_vf", clip_range_vf)
