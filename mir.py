# -*- coding: utf-8 -*-
"""
МИР: среда обучения без MineRL. Глаза — снимок окна, руки — системный ввод,
правда о бое — счётчики самой игры через консоль сервера.

Наблюдение и действия НАРОЧНО те же, что в старой лаборатории:
  * кадр 64x64 RGB — значит зрение старого мозга переносится без переучивания;
  * те же 12 действий в том же порядке — значит переносится и голова.
Один шаг длится 0.2 секунды, как прежние 4 тика, чтобы совпал и темп.

Награда теперь ЧЕСТНАЯ. Счётчик игры ведётся в десятых долях здоровья, поэтому
убийство зомби — это ровно 200 единиц, то есть 20.0 здоровья. Прежняя касса Malmo
показывала за то же убийство 28% и вводила нас в заблуждение полдня.
"""

import time

import gymnasium as gym
import numpy as np

import arena as A
import glaza as G
import konsol as K
import ruki as R

# ── действия: порядок обязан совпадать со старой лабораторией ──
GRADUS = 15.0                    # шаг поворота, как было
NA_GRADUS = 1.0 / 0.15           # единиц мыши на градус (измерено: 0.15 гр/единица)
SHAG_MYSHI = int(GRADUS * NA_GRADUS)   # = 100 единиц

DEJSTVIYA = [
    {},                                        # 0 стоять
    {"klavishi": ["W"]},                       # 1 вперёд
    {"klavishi": ["S"]},                       # 2 назад
    {"klavishi": ["A"]},                       # 3 шаг влево
    {"klavishi": ["D"]},                       # 4 шаг вправо
    {"mysh": (-SHAG_MYSHI, 0)},                # 5 повернуться влево
    {"mysh": (SHAG_MYSHI, 0)},                 # 6 повернуться вправо
    {"mysh": (0, -SHAG_MYSHI)},                # 7 взгляд вверх
    {"mysh": (0, int(12 * NA_GRADUS))},        # 8 взгляд вниз
    {"udar": True},                            # 9 удар
    {"klavishi": ["W", "SPACE"]},              # 10 прыжок вперёд
    {"klavishi": ["W"], "udar": True},         # 11 наступать и бить
    {"klavishi": ["SPACE"]},                   # 12 прыжок НА МЕСТЕ
    {"mysh": (-int(45 * NA_GRADUS), 0)},       # 13 РАЗВОРОТ влево на 45
    {"mysh": (int(45 * NA_GRADUS), 0)},        # 14 РАЗВОРОТ вправо на 45
]
IMENA = ["stoyat", "vpered", "nazad", "shag vlevo", "shag vpravo",
         "povorot vlevo", "povorot vpravo", "vzglyad vverh", "vzglyad vniz",
         "UDAR", "pryzhok vpered", "nastupat+bit", "pryzhok na meste",
         "RAZVOROT vlevo", "RAZVOROT vpravo"]
# КРУПНЫЙ поворот на 45 градусов рядом с мелким на 15. Замер показал, что мышь
# работает точно и линейно (0.15 градуса на единицу), то есть поломки не было —
# существо просто поворачивалось МЕДЛЕННО: чтобы развернуться на 90, нужно было
# шесть шагов подряд, а цель за это время уходила. Человек играет иначе: сперва
# размах, потом доводка. Теперь у существа есть и то, и другое.
# Прыжок на месте добавлен В КОНЕЦ (правило: не перенумеровывать середину).
# Без него ПРОБЕЛ без W не подходил ни под одно действие и падал в «стоять» —
# то есть криты с прыжка, основной приём человека, записывались как «ничего
# не делал». В записи это было видно: урон 8.9 на шагах, помеченных «стоять».
assert len(DEJSTVIYA) == len(IMENA)

SEK_NA_SHAG = 0.2                # как прежние 4 тика по 50 мс
MAX_HEALTH = float(A.MAX_HEALTH)

# ── экономика боя. Теперь считаем от НАСТОЯЩЕГО урона ──
ZA_HP_URONA = 1.0                # 1 очко за единицу нанесённого здоровья -> убийство = 20
KILL_BONUS = 10.0                # сверху за само убийство

# ЦЕНА БОЛИ. Была 0.1 — и здоровье почти ничего не стоило: убийство приносит +30,
# а пропустить 35 урона стоило всего -3.5. Существо честно выучило размениваться
# ударами и добивало зомби полудохлым. На зомби с мечом такая привычка убьёт его
# сразу. Теперь 35 урона стоят -10.5, но убийство всё равно втрое дороже худшего
# исхода (-12), так что бегство невыгодно — а оно уже умеет убивать в 97% боёв,
# поэтому поднимать цену боли теперь безопасно (раньше это дало бы труса).
PAIN_ZA_HP = 0.3
DEATH_PENALTY = 3.0
MAX_SHAGOV = 400                 # предел боя (~80 секунд), чтобы не висеть в пустом загоне


class Bojnya(gym.Env):
    metadata = {"render_modes": ["rgb_array"]}

    def __init__(self, okno="Minecraft"):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (64, 64, 3), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.Discrete(len(DEJSTVIYA))

        self.k = K.Konsol().podklyuchit()
        self.igrok = A.kto_v_mire(self.k)
        if not self.igrok:
            raise SystemExit("В мире никого нет — зайди в игру своим клиентом.")
        self.glaza, zagolovok, _ = G.glaza_na_okno(okno)
        self.hwnd, _ = G.najti_okno(okno)
        print(f"мир: игрок {self.igrok}, окно «{zagolovok}»")

        self.k.komandy(A.pravila_mira())
        self.k.komandy(A.schetchiki())
        self.k.komandy(A.postroit_zagon())
        self.k.komandy(A.podgotovit_bojca(self.igrok))
        self._nazhaty = []
        self.shagov = 0

    # ── чувства ──
    def _sostoyanie(self):
        """Точные числа из игры: урон, боль, убийства, здоровье, моб рядом."""
        s = A.sostoyanie(self.k, self.igrok)
        blizko = "passed" in self.k.komanda(
            "execute if entity @e[type=zombie,distance=..4.5]").lower()
        s["mob_ryadom"] = 1.0 if blizko else 0.0
        return s

    def _obs(self, s):
        zhizn = s["zhizn"] if s["zhizn"] is not None else MAX_HEALTH
        sytost = s.get("sytost")
        vec = np.array([
            min(zhizn / MAX_HEALTH, 1.0),
            # НАСТОЯЩАЯ сытость. Раньше здесь стояла единица — существо не могло
            # заметить голод, а голод отнимает естественное лечение.
            min((sytost if sytost is not None else 20.0) / 20.0, 1.0),
            0.0,                      # ухо на крипера: их тут нет (место сохранено)
            s["mob_ryadom"],          # ухо на враждебного моба
            0.0, 0.0,                 # лава и вода: в загоне их нет
        ], dtype=np.float32)
        return {"pov": self.glaza.kadr_sushchestva(), "vec": vec}

    # ── руки ──
    def _sdelat(self, nomer):
        d = DEJSTVIYA[int(nomer)]
        for k in self._nazhaty:              # снимаем прошлое, иначе побежит само
            R.otpustit(k)
        self._nazhaty = list(d.get("klavishi", []))
        for k in self._nazhaty:
            R.nazhat(k)
        if "mysh" in d:
            R.myshka(*d["mysh"])
        if d.get("udar"):
            R.udar()

    # ── gym ──
    def reset(self, *, seed=None, options=None):
        for k in self._nazhaty:
            R.otpustit(k)
        self._nazhaty = []
        R.otpustit_vse()
        self.k.komandy(A.sbros_boya(self.igrok))
        time.sleep(0.5)                       # даём миру принять сброс
        s = self._sostoyanie()
        self.pred = s
        self.shagov = 0
        self.srok = time.perf_counter() + SEK_NA_SHAG
        return self._obs(s), {"igrok": self.igrok}

    def _proverit_pauzu(self):
        """Escape — пауза, второй Escape — продолжаем.

        Проверяем ДО отправки действий, поэтому в меню игры не улетит ни одного
        щелчка: существо просто не успевает нажать. Все зажатые клавиши снимаем,
        иначе оно осталось бы бежать вперёд, пока ты в меню.

        Мир на выделенном сервере во время паузы НЕ останавливается, поэтому зомби
        на время паузы ЗАМОРАЖИВАЕМ — иначе они спокойно добивали неподвижное
        существо, пока человек отошёл. На возврате размораживаем и перечитываем
        состояние: боль за паузу существу не в вину, оно не действовало.
        """
        if not R.nazhimalas("ESC"):
            return False
        for k in self._nazhaty:
            R.otpustit(k)
        self._nazhaty = []
        R.otpustit_vse()
        A.zamorozit_vseh(self.k, True)
        print("\n  === ПАУЗА === зомби застыли, мышь свободна. "
              "Escape ещё раз — продолжить.\n", flush=True)
        while R.zazhata("ESC"):
            time.sleep(0.05)                  # ждём, пока отпустишь первое нажатие
        while True:
            time.sleep(0.1)
            if R.nazhimalas("ESC"):
                break
        while R.zazhata("ESC"):
            time.sleep(0.05)
        if not A.zamorozit_vseh(self.k, False):
            # Лучше остановиться с ошибкой, чем продолжать с застывшими мишенями:
            # в логе были бы прекрасные 100% побед, а обучение шло бы впустую.
            print("  !!! не удалось разморозить зомби — останавливаюсь", flush=True)
            raise RuntimeError("зомби остались замороженными")
        print("  === ПРОДОЛЖАЮ === щёлкни по окну игры, если фокус ушёл\n", flush=True)
        self.pred = self._sostoyanie()        # боль за паузу существу не в вину
        self.srok = time.perf_counter() + SEK_NA_SHAG
        return True

    def step(self, action):
        # ЖДЁМ фокуса, а не прерываем эпизод. Раньше здесь возвращался truncated,
        # и стоило отвлечься на минуту — обучение получало сотни «прерванных боёв»
        # и столько же сбросов арены, портя весь опыт. Теперь просто пауза.
        if not R.okno_vperedi(self.hwnd):
            for k in self._nazhaty:
                R.otpustit(k)          # не оставляем существо бежать вперёд на паузе
            self._nazhaty = []
            # Зомби замораживаем и здесь. Иначе стоило переключиться в другое окно
            # без Escape — и они спокойно добивали неподвижное существо.
            A.zamorozit_vseh(self.k, True)
            zhdal = 0.0
            while not R.okno_vperedi(self.hwnd):
                if zhdal == 0.0:
                    print("  [пауза: окно игры не впереди — зомби застыли, "
                          "щёлкни по Minecraft]", flush=True)
                time.sleep(0.5)
                zhdal += 0.5
            if not A.zamorozit_vseh(self.k, False):
                print("  !!! не удалось разморозить зомби — останавливаюсь, "
                      "иначе обучение отравится мишенями", flush=True)
                raise RuntimeError("зомби остались замороженными")
            print(f"  [продолжаю, простояли {zhdal:.0f} сек]", flush=True)
            self.pred = self._sostoyanie()     # боль за простой не в вину
            self.srok = time.perf_counter() + SEK_NA_SHAG

        self._proverit_pauzu()      # Escape ловим ДО действий: в меню не улетит щелчок
        self._sdelat(action)
        ostalos = self.srok - time.perf_counter()
        if ostalos > 0:
            time.sleep(ostalos)
        self.srok = time.perf_counter() + SEK_NA_SHAG

        s = self._sostoyanie()
        info, nagrada = {}, 0.0

        d_uron = max((s["uron"] or 0) - (self.pred["uron"] or 0), 0) / 10.0     # в HP
        if d_uron > 0:
            nagrada += d_uron * ZA_HP_URONA
            info["uron"] = d_uron
        d_bol = max((s["bol"] or 0) - (self.pred["bol"] or 0), 0) / 10.0
        if d_bol > 0:
            nagrada -= d_bol * PAIN_ZA_HP
            info["bol"] = d_bol

        done = False
        if (s["ubijstva"] or 0) > (self.pred["ubijstva"] or 0):
            nagrada += KILL_BONUS
            info["kill"] = True
            done = True                       # убил — бой кончен, сразу новый зомби
        zhizn = s["zhizn"] if s["zhizn"] is not None else MAX_HEALTH
        if zhizn <= 0:
            nagrada -= DEATH_PENALTY
            info["death"] = True
            done = True

        self.pred = s
        self.shagov += 1
        obrezan = self.shagov >= MAX_SHAGOV
        info["zhizn"] = zhizn
        return self._obs(s), float(nagrada), done, obrezan, info

    def close(self):
        for k in self._nazhaty:
            R.otpustit(k)
        R.otpustit_vse()
        self.glaza.close()
        self.k.close()
