# -*- coding: utf-8 -*-
"""
ПРОВЕРКА СРЕДЫ до всякого обучения: работает ли круг «увидел — сделал — получил».

Гоняем случайные действия и смотрим, что среда отдаёт: меняется ли кадр, капает
ли награда за урон, ловится ли убийство, укладываемся ли в темп 5 шагов в секунду.

Перед запуском: щёлкни по окну Minecraft, будь В ИГРЕ и не трогай управление.
Существом будет распоряжаться программа.

Запуск: proba-mira.bat
"""

import time

import numpy as np

from telo import mir as M

SHAGOV = 150            # ~30 секунд


def main():
    env = M.Bojnya()
    obs, info = env.reset()
    print(f"\nстарт: жизнь {obs['vec'][0] * M.MAX_HEALTH:.0f}, "
          f"моб рядом {obs['vec'][3]:.0f}")
    print(f"шагов: {SHAGOV} (~{SHAGOV * M.SEK_NA_SHAG:.0f} секунд)\n")

    rng = np.random.default_rng(0)
    nagrada_vsego, uron_vsego, ubijstv, bolno = 0.0, 0.0, 0, 0.0
    kadry, vremena = [], []
    t0 = time.perf_counter()
    for i in range(SHAGOV):
        t = time.perf_counter()
        a = int(rng.integers(len(M.DEJSTVIYA)))
        obs, r, done, obrezan, inf = env.step(a)
        vremena.append(time.perf_counter() - t)
        kadry.append(obs["pov"].astype(np.int16))
        nagrada_vsego += r
        uron_vsego += inf.get("uron", 0.0)
        bolno += inf.get("bol", 0.0)
        if inf.get("okno_ushlo"):
            print("  !!! окно ушло на задний план — существо ослепло, верни фокус")
            time.sleep(1)
            continue
        if inf.get("uron"):
            print(f"  шаг {i:3d}: {M.IMENA[a]:<16} УРОН {inf['uron']:.1f} HP  награда {r:+.1f}")
        if inf.get("kill"):
            ubijstv += 1
            print(f"  шаг {i:3d}: *** УБИЛ ЗОМБИ *** награда {r:+.1f}")
        if inf.get("death"):
            print(f"  шаг {i:3d}: погиб, награда {r:+.1f}")
        if done or obrezan:
            obs, _ = env.reset()

    proshlo = time.perf_counter() - t0
    env.close()

    # меняется ли картинка — иначе существо смотрит в стену
    raznica = float(np.abs(np.diff(np.stack(kadry[:40]), axis=0)).mean()) if len(kadry) > 1 else 0.0

    print("\n=== ИТОГ ===")
    print(f"  шагов               {SHAGOV} за {proshlo:.1f} сек = "
          f"{SHAGOV / proshlo:.1f} в секунду (цель {1 / M.SEK_NA_SHAG:.0f})")
    print(f"  средний шаг         {np.mean(vremena) * 1000:.0f} мс "
          f"(из них ожидание темпа)")
    print(f"  нанесено урона      {uron_vsego:.1f} HP")
    print(f"  получено урона      {bolno:.1f} HP")
    print(f"  убийств             {ubijstv}")
    print(f"  награда всего       {nagrada_vsego:+.1f}")
    print(f"  картинка меняется   {raznica:.2f} (ноль = смотрит в одну точку)")
    print()
    if uron_vsego > 0 and raznica > 1:
        print("СРЕДА РАБОТАЕТ: существо видит, действует и получает честную награду.")
        print("Можно переносить мозг и запускать обучение.")
    elif raznica <= 1:
        print("Картинка не меняется — проверь, что окно игры впереди и не перекрыто.")
    else:
        print("Урона нет: случайные действия могли не попасть по зомби. "
              "Это не обязательно поломка — но посмотри, был ли моб рядом.")


if __name__ == "__main__":
    main()
