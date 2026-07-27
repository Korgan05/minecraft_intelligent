# -*- coding: utf-8 -*-
"""
ОБУЧЕНИЕ С НАГРАДОЙ в своей лаборатории. Ни MineRL, ни Malmo.

Существо продолжает с мозга после разминки: 176 тысяч шагов старого опыта плюс
подражание твоему показу. Награда честная — из собственных счётчиков Minecraft.

Окно игры должно быть ВПЕРЕДИ и не перекрыто: существо видит экран. Если фокус
уйдёт, обучение само встанет на паузу и дождётся возвращения.

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
from stable_baselines3.common.vec_env import DummyVecEnv

import arena as A
import mir as M

ROOT = Path(__file__).parent
MODELI = ROOT / "models"
MOZG = MODELI / "ppo_ubijca"
LENTA = ROOT / "lenta.log"
LOGI = ROOT / "logs"


class Lenta(BaseCallback):
    """Что происходит в бою: убийства, итоги жизней, редкие сводки."""

    def __init__(self):
        super().__init__()
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
            zh_min = getattr(self, "zhizn_min", float("nan"))
            self._pishi(f"бой #{self.boj}: {itog} | урон {self.uron_boya:5.1f} HP | "
                        f"здоровье осталось {getattr(self, 'zhizn_konec', 0):4.0f}, "
                        f"минимум {zh_min:4.0f} | шагов {self.shagov_boya:3d} | "
                        f"убийств {self.ubijstv_vsego} | смертей {self.smertej}/{self.boj}")
            self.uron_boya, self.shagov_boya = 0.0, 0
            self.zhizn_min = 999.0
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shagov", type=int, default=2_000_000)
    p.add_argument("--lr", type=float, default=2.5e-4)
    args = p.parse_args()

    MODELI.mkdir(exist_ok=True)
    print(f"ступень лестницы: зомби {A.ZOMBI_NA_ARENE}, "
          f"с мечом {'да' if A.ZOMBI_S_MECHOM else 'нет'}")
    env = DummyVecEnv([lambda: M.Bojnya()])

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
        CheckpointCallback(save_freq=2_000, save_path=str(MODELI), name_prefix="ubijca_ckpt"),
        Lenta(),
    ]
    # Даём время переключиться: раньше обучение начиналось сразу, и первые секунды
    # существо действовало в пустоту, пока фокус был на консоли.
    import ruki as R
    import glaza as G
    hwnd, _ = G.najti_okno("Minecraft")
    print("\nЩЁЛКНИ ПО ОКНУ MINECRAFT — жду.")
    while not R.okno_vperedi(hwnd):
        time.sleep(0.3)
    for i in range(3, 0, -1):
        print(f"  начинаю через {i}...", flush=True)
        time.sleep(1)
    print("\nESCAPE — пауза (мышь освободится). Escape ещё раз — продолжить.")
    print("Остановить совсем: Ctrl+C в этом окне.\n")

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
