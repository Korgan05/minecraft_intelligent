# -*- coding: utf-8 -*-
"""
ОБУЧЕНИЕ С НАГРАДОЙ в своей лаборатории. Ни MineRL, ни Malmo.

Существо продолжает с мозга после разминки: 176 тысяч шагов старого опыта плюс
подражание твоему показу. Награда честная — из собственных счётчиков Minecraft.

Существо живёт через наш мод, поэтому окну игры НЕ нужен фокус и его можно
закрыть другими окнами: мод читает кадровый буфер игры, а не рабочий стол.
Единственное нельзя — сворачивать окно: свёрнутое система не перерисовывает.

Пока обучение идёт, лучше не заходить в окно игры мышью: если фокус на игре,
твои движения мышью складываются с поворотом существа и портят ему прицел.

Пауза — клавиша P В ИГРЕ. Escape при активном окне тоже останавливает: это
человеческая пауза, мод в неё не лезет.

Остановить: Ctrl+C в этом окне — мозг сохранится.
Запуск: obuchenie.bat
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from telo import arena as A
from telo import mir as M
from telo import pupovina as P

ROOT = Path(__file__).parent
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
LENTA = ROOT / "lenta.log"
LOGI = ROOT / "logs"


# СТОРОЖ. За ночь существо съехало с 92% убийств до 19% и никто этого не видел:
# прогон шёл 156 тысяч шагов без присмотра, и восемьдесят тысяч из них оно
# разучивалось. Мозг спасли только промежуточные снимки.
#
# Теперь обучение само останавливается, если дела стали плохи. Это не замена
# разбору, а страховка от долгой ночи: лучше остановиться на 850-м бою, чем
# доехать до 1331-го.
SLEDIT_ZA_POSLEDNIMI = 100       # по скольким последним боям судим
HUZHE_CHEM = 0.55                # ниже этой доли убийств — останавливаемся
NE_SUDIT_RANSHE = 200            # до этого числа боёв не судим: сперва болтанка


class Lenta(BaseCallback):
    """Что происходит в бою: убийства, итоги жизней, редкие сводки.

    Заодно сторожит качество и останавливает обучение, если оно поехало вниз.
    """

    def __init__(self):
        super().__init__()
        self.itogi = []              # True за победу, False за смерть
        self.boj = 0
        self.ubijstv_vsego = 0
        self.uron_boya = 0.0
        self.shagov_boya = 0
        self.rekord = 0.0
        self.smertej = 0

    def _pishi(self, tekst):
        print(tekst, flush=True)
        with open(LENTA, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%d.%m %H:%M:%S}] {tekst}\n")

    def _on_step(self) -> bool:
        infos = self.locals.get("infos") or [{}]
        inf = infos[0] or {}
        self.uron_boya += float(inf.get("uron", 0.0))
        self.shagov_boya += 1
        # Следим за здоровьем: без этого нельзя было проверить, добивает ли
        # существо зомби полудохлым. Раньше в логе был только нанесённый урон.
        zh = inf.get("zhizn")
        if zh is not None:
            self.zhizn_konec = float(zh)
            self.zhizn_min = min(getattr(self, "zhizn_min", 999.0), float(zh))
        if inf.get("kill"):
            self.ubijstv_vsego += 1
            self._pishi(f"*** УБИЛ ЗОМБИ #{self.ubijstv_vsego} *** "
                        f"(шаг {self.num_timesteps}, бой {self.boj + 1})")
        dones = self.locals.get("dones")
        if dones is not None and np.any(dones):
            self.boj += 1
            pogib = bool(inf.get("death"))
            self.smertej += 1 if pogib else 0
            self.rekord = max(self.rekord, self.uron_boya)
            itog = "УБИЛ" if inf.get("kill") else ("погиб" if pogib else "не успел")
            self.itogi.append(bool(inf.get("kill")))
            zh_min = getattr(self, "zhizn_min", float("nan"))
            self._pishi(f"бой #{self.boj}: {itog} | урон {self.uron_boya:5.1f} HP | "
                        f"здоровье осталось {getattr(self, 'zhizn_konec', 0):4.0f}, "
                        f"минимум {zh_min:4.0f} | шагов {self.shagov_boya:3d} | "
                        f"убийств {self.ubijstv_vsego} | смертей {self.smertej}/{self.boj}")
            self.uron_boya, self.shagov_boya = 0.0, 0
            self.zhizn_min = 999.0
            if self.boj >= NE_SUDIT_RANSHE:
                posl = self.itogi[-SLEDIT_ZA_POSLEDNIMI:]
                dolya = sum(posl) / len(posl)
                if dolya < HUZHE_CHEM:
                    self._pishi(
                        f"!!! СТОРОЖ ОСТАНАВЛИВАЕТ: за последние {len(posl)} боёв "
                        f"убийств {100 * dolya:.0f}%, ниже порога "
                        f"{100 * HUZHE_CHEM:.0f}%. Дальше существо разучивается — "
                        "останавливаюсь и сохраняю. Вернись к снимку получше.")
                    return False
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shagov", type=int, default=2_000_000)
    p.add_argument("--lr", type=float, default=2.5e-4)
    p.add_argument("--protiv-cheloveka", action="store_true",
                   help="противник — человек за вторым клиентом, зомби не призывать")
    args = p.parse_args()

    MODELI.mkdir(exist_ok=True)
    if args.protiv_cheloveka:
        A.PROTIV_CHELOVEKA = True
        print("РЕЖИМ БОЯ ПРОТИВ ЧЕЛОВЕКА: зомби не призываются, "
              "убийство человека считается победой")
    print(f"ступень лестницы: зомби {A.ZOMBI_NA_ARENE}, "
          f"с мечом {'да' if A.ZOMBI_S_MECHOM else 'нет'}")
    # Monitor ОБЯЗАТЕЛЕН: именно он ведёт учёт эпизодов, из которого берутся
    # ep_rew_mean и ep_len_mean — главные показатели обучения. Без него первый
    # прогон записал только fps и служебные потери, а средней награды за бой
    # не было вовсе: мы следили за обучением без главного прибора.
    env = DummyVecEnv([lambda: Monitor(M.Bojnya())])

    zip_put = MOZG.with_suffix(".zip")
    if zip_put.exists():
        model = PPO.load(MOZG, env=env, device="cuda",
                         custom_objects={"learning_rate": args.lr,
                                         "lr_schedule": (lambda _: args.lr)})
        model.tensorboard_log = str(LOGI)      # PPO.load путь к графикам не восстанавливает
        print(f"продолжаю с мозга после разминки: шагов {model.num_timesteps}")
        sbros_schetchika = False
    else:
        raise SystemExit("Мозга нет. Сначала разминка: uchit.bat")

    kolbeki = [
        # Каждые 1000 шагов, а не 2000: ноут выключают, уходя из дома, и при
        # внезапном выключении терять полчаса обучения незачем. Полтора мегабайта
        # на снимок — дешевле, чем переучивать.
        CheckpointCallback(save_freq=1_000, save_path=str(MODELI), name_prefix="ubijca_ckpt"),
        Lenta(),
    ]
    # Фокуса больше не ждём — мод в нём не нуждается. Но в МИРЕ существо быть
    # обязано: если открыт экран или игрок не зашёл, учиться нечему.
    # Спрашиваем ТЕМ соединением, которое уже открыл мир существа. Своё второе
    # открывать нельзя: у мода один собеседник, и второй молча висит в очереди
    # без ответа. Ровно на этом первый запуск и упал загадочным «timed out».
    env.envs[0].unwrapped.zhdat_gotovnosti()
    print("\nОкно игры может стоять позади других — существо видит игру, а не экран.")
    print("Только не сворачивай его: свёрнутое окно не перерисовывается.")
    print("Пока идёт обучение, не заходи в игру мышью: твоя мышь сложится с его прицелом.")
    print("Пауза — клавиша P в игре. Остановить совсем: Ctrl+C в этом окне.\n")

    kod = 0
    try:
        model.learn(total_timesteps=args.shagov, callback=kolbeki,
                    reset_num_timesteps=sbros_schetchika, progress_bar=True,
                    tb_log_name="UBIJCA")
    except KeyboardInterrupt:
        print("\nостановлено вручную — сохраняю мозг")
    except Exception as e:
        print(f"\nавария ({type(e).__name__}: {e}) — мозг всё равно сохраняю")
        kod = 1
    finally:
        model.save(MOZG)
        print(f"мозг сохранён: {zip_put.name} (шагов {model.num_timesteps})")
        try:
            env.close()
        except Exception:
            pass
    raise SystemExit(kod)


if __name__ == "__main__":
    main()
