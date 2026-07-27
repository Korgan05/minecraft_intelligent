# -*- coding: utf-8 -*-
"""
МИР существа — теперь через свой мод, а не через Windows.

Что осталось ТОЧНО КАК БЫЛО, и это главное:
  * кадр 64x64 RGB, четыре кадра памяти — значит зрение мозга переносится;
  * те же 20 действий в том же порядке — значит переносится и голова;
  * шаг 0.2 секунды и та же экономика боя — значит сравнение будет честным.
Иначе нельзя было бы сказать, стало лучше от мода или просто изменились правила.

Что изменилось:
  * поворот задаётся В ГРАДУСАХ. Раньше мы просили мышь сдвинуться на
    int(5 / 0.15) = 33 единицы, что давало 4.95 градуса вместо пяти. Теперь
    просим ровно 5.0 — и получаем ровно 5.0, проверено сверкой с сервером;
  * окну игры не нужен фокус, и его можно закрыть другими окнами: мод читает
    кадровый буфер игры, а не прямоугольник рабочего стола. Сворачивать нельзя;
  * здоровье и сытость приходят вместе с кадром — на два запроса к серверу
    меньше на каждом шаге;
  * пауза — клавиша P В ИГРЕ, а не Escape через Windows. Прежний способ ловил
    Escape в любой программе: нажал в браузере — обучение встало.

Читерства не прибавилось. Мод отдаёт только то, что видно человеку: пиксели,
здоровье и сытость с полосок, собственный угол взгляда. Ни координат зомби,
ни расстояний до них.
"""

import time

import gymnasium as gym
import numpy as np

from . import arena as A
from . import konsol as K
from . import pupovina as P

# ── действия: порядок обязан совпадать со старой лабораторией ──
# Теперь это ГРАДУСЫ, а не единицы мыши. Значения те же самые.
DEJSTVIYA = [
    {},                                        # 0 стоять
    {"klavishi": ["W"]},                       # 1 вперёд
    {"klavishi": ["S"]},                       # 2 назад
    {"klavishi": ["A"]},                       # 3 шаг влево
    {"klavishi": ["D"]},                       # 4 шаг вправо
    {"yaw": -15.0},                            # 5 повернуться влево
    {"yaw": 15.0},                             # 6 повернуться вправо
    {"pitch": -15.0},                          # 7 взгляд вверх
    {"pitch": 12.0},                           # 8 взгляд вниз
    {"udar": True},                            # 9 удар
    {"klavishi": ["W", "SPACE"]},              # 10 прыжок вперёд
    {"klavishi": ["W"], "udar": True},         # 11 наступать и бить
    {"klavishi": ["SPACE"]},                   # 12 прыжок НА МЕСТЕ
    {"yaw": -45.0},                            # 13 РАЗВОРОТ влево на 45
    {"yaw": 45.0},                             # 14 РАЗВОРОТ вправо на 45
    {"yaw": -5.0},                             # 15 доводка влево на 5
    {"yaw": 5.0},                              # 16 доводка вправо на 5
    {"yaw": -90.0},                            # 17 четверть оборота влево
    {"yaw": 90.0},                             # 18 четверть оборота вправо
    {"yaw": 180.0},                            # 19 КРУГОМ
]
IMENA = ["stoyat", "vpered", "nazad", "shag vlevo", "shag vpravo",
         "povorot vlevo", "povorot vpravo", "vzglyad vverh", "vzglyad vniz",
         "UDAR", "pryzhok vpered", "nastupat+bit", "pryzhok na meste",
         "RAZVOROT vlevo", "RAZVOROT vpravo",
         "dovodka vlevo", "dovodka vpravo",
         "chetvert vlevo", "chetvert vpravo", "KRUGOM"]
# ЧЕТЫРЕ размаха поворота в каждую сторону: 5, 15, 45, 90 — и «кругом» на 180.
# Так существо может и точно доводить прицел, и мгновенно оборачиваться.
# Раньше был один шаг в 15 градусов: развернуться на 90 стоило шести шагов,
# то есть полутора секунд, за которые цель уходила.
#
# «Кругом» — ОДНО действие, а не два: влево на 180 и вправо на 180 приводят
# в одну и ту же точку. Нужно, когда зомби заходит со спины.
#
# Вертикаль (взгляд вверх-вниз) не расширяю нарочно: пол ровный, зомби одного
# роста с существом, и лишние выходы только размыли бы выбор.
#
# ЖЕЛЕЗНОЕ ПРАВИЛО: действия можно только ДОБАВЛЯТЬ в конец. Удаление или
# вставка в середину сдвигает номера — и голова мозга начинает отвечать не то,
# что имела в виду. Один раз мы так уже обнулили обученную голову.
assert len(DEJSTVIYA) == len(IMENA)

# Клавиши существа -> имена, которые понимает мод.
KLAVISHI_MODA = {"W": "vpered", "S": "nazad", "A": "vlevo", "D": "vpravo",
                 "SPACE": "pryzhok"}

SEK_NA_SHAG = 0.2                # как прежние 4 тика по 50 мс

# ПАМЯТЬ. Существо видит не один кадр, а несколько последних сразу — сложенных
# в один снимок по глубине цвета. Из одного кадра нельзя понять, приближается
# противник или отходит: видно только где он, но не куда движется. Скелет отходит
# и стреляет, криппер подбегает — их особенность именно в изменении расстояния.
# Четыре кадра при шаге 0.2 сек = память на 0.8 секунды. Разворот кругом занимает
# один шаг, значит после поворота существо ещё три кадра «помнит», что было позади.
KADROV_V_PAMYATI = 4
MAX_HEALTH = float(A.MAX_HEALTH)

# ── экономика боя: НЕ МЕНЯТЬ, иначе сравнение с прошлым мозгом бессмысленно ──
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

    def __init__(self, port=P.PORT):
        self.observation_space = gym.spaces.Dict({
            "pov": gym.spaces.Box(0, 255, (64, 64, 3 * KADROV_V_PAMYATI), np.uint8),
            "vec": gym.spaces.Box(0.0, 1.0, (6,), np.float32),
        })
        self.action_space = gym.spaces.Discrete(len(DEJSTVIYA))

        self.k = K.Konsol().podklyuchit()
        self.igrok = A.kto_v_mire(self.k)
        if not self.igrok:
            raise SystemExit("В мире никого нет — зайди в игру своим клиентом.")
        self.p = P.Pupovina(port=port)
        self.p.razmer_kadra(64, 64)
        print(f"мир через мод: игрок {self.igrok}, {self.p.ping()}")

        self.k.komandy(A.pravila_mira())
        self.k.komandy(A.schetchiki())
        self.k.komandy(A.postroit_zagon())
        self.k.komandy(A.podgotovit_bojca(self.igrok))
        self._pamyat = []
        self._posl = self.p.sostoyanie()      # последний взгляд: из него читаем флаги
        self.shagov = 0

    # ── чувства ──
    def _blizko(self):
        """Ухо на враждебного моба рядом. Единственное, что ещё нужно от сервера."""
        return 1.0 if "passed" in self.k.komanda(
            "execute if entity @e[tag=boec,distance=..4.5]").lower() else 0.0

    def _obs(self, o, blizko):
        vec = np.array([
            min(o["zhizn"] / MAX_HEALTH, 1.0),
            min(o["sytost"] / 20.0, 1.0),
            0.0,                      # ухо на крипера: их тут нет (место сохранено)
            blizko,                   # ухо на враждебного моба
            0.0, 0.0,                 # лава и вода: в загоне их нет
        ], dtype=np.float32)
        self._pamyat.append(o["kadr"].copy())
        while len(self._pamyat) > KADROV_V_PAMYATI:
            self._pamyat.pop(0)
        # склеиваем по глубине цвета: свежий кадр последний
        return {"pov": np.concatenate(self._pamyat, axis=2), "vec": vec}

    # ── руки ──
    def _zakaz(self, nomer):
        """Действие существа -> заказ для мода."""
        d = DEJSTVIYA[int(nomer)]
        z = {k: 0 for k in KLAVISHI_MODA.values()}
        for kl in d.get("klavishi", []):
            z[KLAVISHI_MODA[kl]] = 1
        z["udar"] = 1 if d.get("udar") else 0
        z["dyaw"] = d.get("yaw", 0.0)
        z["dpitch"] = d.get("pitch", 0.0)
        return z

    # ── gym ──
    def reset(self, *, seed=None, options=None):
        # Пустой шаг, а НЕ otpustit_vse: он снимает клавиши, но власть остаётся.
        # Отпускать власть между боями нельзя — мод тут же вернул бы человеку
        # настройку «пауза при потере фокуса», а сброс боя длится больше
        # полусекунды, ровно столько игре и нужно, чтобы открыть меню самой.
        # За сотню боёв это случилось бы наверняка.
        self.p.shag()
        self.k.komandy(A.sbros_boya(self.igrok))
        time.sleep(0.5)                       # даём миру принять сброс
        o = self._obespechit_zdorovye()
        # Память заполняем ОДНИМ И ТЕМ ЖЕ кадром: в начале боя движения ещё нет,
        # и честнее показать неподвижность, чем обрывки прошлого боя.
        self._pamyat = [o["kadr"].copy()] * KADROV_V_PAMYATI
        self._posl = o
        self.pred = A.schet_boya(self.k, self.igrok)
        self.shagov = 0
        self.srok = time.perf_counter() + SEK_NA_SHAG
        return self._obs(o, self._blizko()), {"igrok": self.igrok}

    def _obespechit_zdorovye(self):
        """Убедиться, что усиленное здоровье ДЕЙСТВИТЕЛЬНО выдано.

        Тут нельзя действовать на веру, и вот почему. При смерти Minecraft
        сбрасывает свойства игрока к обычным. Мы выдаём усиление в сбросе боя —
        но если он успел уйти РАНЬШЕ возрождения, возрождение всё смывает, и
        существо встаёт с 20 здоровья вместо 40. Оно тогда и дерётся вполовину
        слабее, и видит своё полное здоровье как 0.5 — ведь в чувства подаётся
        доля от сорока. Заметить это по логам почти невозможно.
        Мод отдаёт максимум здоровья бесплатно вместе с кадром, так что проверить
        ничего не стоит. Не верим — смотрим.
        """
        o = self.p.sostoyanie()
        for _ in range(6):
            if o["v_mire"] and o["zhizn"] > 0 and abs(o["max_zhizn"] - MAX_HEALTH) < 0.5:
                return o
            self.k.komandy(A.podkrepit_zdorovye(self.igrok))
            time.sleep(0.3)
            o = self.p.sostoyanie()
        print(f"  !!! здоровье не выдалось: {o['zhizn']:.0f}/{o['max_zhizn']:.0f}",
              flush=True)
        return o

    def zhdat_gotovnosti(self):
        """Ждём, пока человек окажется в мире.

        Живёт здесь, а не в обучении, по важной причине: у мода ОДИН собеседник,
        и второе соединение молча висит в очереди без ответа. Обучение однажды
        так и упало — открыло свою связь вдобавок к этой и словило таймаут.
        Значит спрашивать надо тем соединением, которое уже есть.
        """
        while True:
            o = self.p.sostoyanie()
            prichina = self._nuzhna_pauza(o)
            if prichina is None:
                self._posl = o
                return o
            print(f"  жду: {prichina} ...", flush=True)
            time.sleep(1.0)

    def _nuzhna_pauza(self, o):
        """Три причины встать: человек нажал P, вмешался руками, или вышел из мира.

        Про меню тонкость, на которой я один раз уже сделал тупик. Открытый экран
        считается вмешательством ТОЛЬКО если окно игры впереди: значит человек
        смотрит в игру и сам нажал Escape. Если окно позади, то меню открыла сама
        игра при уходе фокуса — и его закроет мод, как только возьмёт власть.
        Считать это паузой было нельзя: питон ждал бы закрытия меню, а закрыть
        его мог только мод, который в ожидании власти не берёт. Вечное ожидание.
        """
        if o["pauza"]:
            return "человек нажал P"
        if o["menyu"] and o["fokus"]:
            return "человек открыл меню, глядя в игру"
        if not o["v_mire"]:
            return "игрок не в мире"
        return None

    def _pauza(self, prichina):
        """Пауза: зомби застывают, клавиатура возвращается человеку.

        Мир на выделенном сервере во время паузы НЕ останавливается, поэтому
        зомби на время паузы ЗАМОРАЖИВАЕМ — иначе они спокойно добивали
        неподвижное существо, пока человек отошёл.

        Пока ждём, спрашиваем мод только SOSTOYANIE. Это важно: любой SHAG берёт
        власть над клавиатурой на секунду, и человек не смог бы ходить в свою же
        паузу. Здесь мод не трогает ввод вообще.
        """
        self.p.otpustit_vse()
        A.zamorozit_vseh(self.k, True)
        print(f"\n  === ПАУЗА ({prichina}) === зомби застыли, клавиатура твоя.")
        print("  Продолжить: клавиша P в игре (или вернись в мир).\n", flush=True)
        while True:
            time.sleep(0.3)
            o = self.p.sostoyanie()
            if self._nuzhna_pauza(o) is None:
                break
        if not A.zamorozit_vseh(self.k, False):
            # Лучше остановиться с ошибкой, чем продолжать с застывшими мишенями:
            # в логе были бы прекрасные 100% побед, а обучение шло бы впустую.
            print("  !!! не удалось разморозить зомби — останавливаюсь", flush=True)
            raise RuntimeError("зомби остались замороженными")
        print("  === ПРОДОЛЖАЮ ===\n", flush=True)
        self._posl = o
        self.pred = A.schet_boya(self.k, self.igrok)   # боль за простой не в вину
        self.srok = time.perf_counter() + SEK_NA_SHAG

    def step(self, action):
        prichina = self._nuzhna_pauza(self._posl)
        if prichina:
            self._pauza(prichina)

        self.p.shag(**self._zakaz(action))
        ostalos = self.srok - time.perf_counter()
        if ostalos > 0:
            time.sleep(ostalos)
        self.srok = time.perf_counter() + SEK_NA_SHAG

        # Смотрим ПОСЛЕ действия и ничего при этом не нажимаем: клавиши и так
        # держатся с прошлого заказа, а лишний SHAG добавил бы второй поворот.
        o = self.p.sostoyanie()
        self._posl = o
        s = A.schet_boya(self.k, self.igrok)
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
        zhizn = o["zhizn"]
        # Смерть — ПО СЧЁТЧИКУ игры. Проверка «здоровье <= 0» пропускала смерти:
        # игра возрождает за один тик, а смотрим мы раз в четыре. Оставляю её
        # второй строкой обороны, но полагаться на неё нельзя.
        if (s["smerti"] or 0) > (self.pred["smerti"] or 0) or zhizn <= 0:
            nagrada -= DEATH_PENALTY
            info["death"] = True
            done = True

        self.pred = s
        self.shagov += 1
        obrezan = self.shagov >= MAX_SHAGOV
        info["zhizn"] = zhizn
        return self._obs(o, self._blizko()), float(nagrada), done, obrezan, info

    def close(self):
        try:
            self.p.close()
        finally:
            self.k.close()
