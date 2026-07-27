# -*- coding: utf-8 -*-
"""
АРЕНА: строим бойню командами и читаем ТОЧНЫЕ числа игры через консоль.

Это замена всему, что мы терпели в MineRL:
  * арена строится командами вместо XML, который ломался от двух датчиков в корне;
  * сброс боя — несколько команд вместо пересоздания мира (конец семиминутным запускам);
  * урон берётся из собственного счётчика Minecraft, а не из клиентской отсебятины,
    которая занижала его вчетверо и неравномерно;
  * убийства считает сама игра — больше не надо угадывать по гаснущему уху.

Правила мира выставлены так, чтобы существо не страдало ни за что:
  * вечная ночь -> зомби не горит, а значит не поджигает существо (было «1.0 damage from onFire»);
  * инвентарь сохраняется при смерти -> меч не выпадает и зомби его не подберёт;
  * мгновенное возрождение -> экран смерти не закрывает существу глаза;
  * отчёт о командах выключен -> чат не засоряет кадр, который существо видит.
"""

import random

GROUND_Y = 4                     # пол загона
ARENA_R = 5                      # половина ширины: внутри 9x9
WALL_H = 4                       # стены до y=7
ROOF_Y = GROUND_Y + 4            # крыша y=8
SPAWN = (0.5, GROUND_Y, 0.5)     # где стоит существо
ZOMBIE_SPOT = (0.5, GROUND_Y, 3.5)   # середина: осталось для проверок тела
# СЛУЧАЙНЫЙ спавн зомби. При постоянном месте прямо перед лицом задачу можно
# решить не глядя — просто долбить вперёд, что разминка однажды и выучила
# («бить всегда», 100% кадров). Случайное место и случайный поворот заставляют
# существо ИСКАТЬ цель, а не полагаться на то, что она всегда впереди.
MIN_DALNOST = 3.0                # не ближе трёх блоков, иначе бой начнётся вплотную
# Сколько зомби на арене. Это единственный честный способ поднять сложность:
# тело остаётся тем же (40 здоровья, меч), значит и показ человека, и чувства
# существа остаются сопоставимыми. Снижать здоровье одному человеку нельзя —
# в чувствах оно подаётся долей от 40, и его «полное» записалось бы как половина.
ZOMBI_NA_ARENE = 1
MAX_HEALTH = 40

# СИЛА ЗОМБИ. Усложнять надо противника, а НЕ человека: тело человека должно
# совпадать с телом существа (40 здоровья, железный меч), иначе показ станет
# ложью — его «полное здоровье» записалось бы как половина.
# Замер показал, что при обычных зомби человеку слишком легко: за пять минут
# здоровье не падало ниже 33 из 40, кадров опасности НОЛЬ. Учиться отступать
# и лечиться существу было не на чем. Меч в руке зомби это исправляет:
# он бьёт втрое больнее, и отход становится вынужденным, а не украшением.
ZOMBI_S_MECHOM = False
# Скорость НЕ трогаем (None = обычная зомбячья). Прибавку я поставил и был неправ:
# если зомби быстрее человека, отступление перестаёт работать в принципе, и в
# записи оказалось бы не «отошёл и подлечился», а «пытался убежать и умер».
# Показ обязан содержать РАБОТАЮЩИЙ способ, иначе существо скопирует проигрышный.
ZOMBI_SKOROST = None
# ЗАМОРОЗКА зомби. Два разных состояния, и путать их не стоит:
#   "chuchelo"  — NoAI: полностью неподвижен, не бьёт, не поворачивается.
#                 Чистая стрельба по мишени: урона существо не получает вовсе.
#   "vkopannyj" — скорость 0: стоять на месте, но бить и поворачиваться умеет.
#                 Можно подойти и получить, но догонять не будет.
#   None        — обычный зомби.
ZOMBI_ZAMOROZKA = None

# счётчики самой игры (в 1.16 доступны как статистики)
SCHET_URON = "uron"              # minecraft.custom:minecraft.damage_dealt
SCHET_BOL = "bol"                # minecraft.custom:minecraft.damage_taken
SCHET_UBIJSTVA = "ubijstva"      # minecraft.killed:minecraft.zombie


def pravila_mira():
    """Один раз при подъёме сервера."""
    return [
        "gamerule doDaylightCycle false",     # ночь не кончается -> зомби не горит
        "gamerule doWeatherCycle false",
        "gamerule doMobSpawning false",       # никакой толпы: она однажды уронила fps до 1
        "gamerule keepInventory true",        # меч не выпадает при смерти
        "gamerule doImmediateRespawn true",   # экран смерти не закрывает глаза
        "gamerule announceAdvancements false",
        "gamerule sendCommandFeedback false",  # чат не лезет в кадр существа
        "gamerule showDeathMessages false",
        "gamerule doFireTick false",
        "gamerule naturalRegeneration true",   # отход лечит — навык, который оно уже нашло
        "time set midnight",
        "difficulty normal",
        "kill @e[type=item]",
        # Точка возрождения ВНУТРИ загона. Без неё смерть выкидывала наружу, за стену:
        # мир высаживал у своей исходной точки, а она в двухстах блонах отсюда.
        # y=GROUND_Y, то есть на пол, а не в пол — иначе игра выталкивает наверх.
        f"setworldspawn 0 {GROUND_Y} 3",
    ]


def schetchiki():
    """Счётчики игры — наша честная касса вместо той, что занижала урон."""
    return [
        f"scoreboard objectives add {SCHET_URON} minecraft.custom:minecraft.damage_dealt",
        f"scoreboard objectives add {SCHET_BOL} minecraft.custom:minecraft.damage_taken",
        f"scoreboard objectives add {SCHET_UBIJSTVA} minecraft.killed:minecraft.zombie",
    ]


def postroit_zagon():
    """Каменный загон с крышей. Крыша обязательна: без неё солнце подпаливает зомби."""
    R, G, H = ARENA_R, GROUND_Y, WALL_H
    verh = G + H - 1
    k = [
        # пол: ровная площадка, чтобы никто не проваливался
        f"fill {-R} {G-1} {-R} {R} {G-1} {R} minecraft:stone",
        # четыре стены
        f"fill {-R} {G} {-R} {R} {verh} {-R} minecraft:stone",
        f"fill {-R} {G} {R} {R} {verh} {R} minecraft:stone",
        f"fill {-R} {G} {-R} {-R} {verh} {R} minecraft:stone",
        f"fill {R} {G} {-R} {R} {verh} {R} minecraft:stone",
        # крыша
        f"fill {-R} {ROOF_Y} {-R} {R} {ROOF_Y} {R} minecraft:stone",
        # внутри пусто
        f"fill {-R+1} {G} {-R+1} {R-1} {ROOF_Y-1} {R-1} minecraft:air",
    ]
    # светильники в крыше: ночь нужна против огня, но существу нужно ВИДЕТЬ
    for x, z in [(0, 0), (3, 3), (-3, 3), (3, -3), (-3, -3)]:
        k.append(f"setblock {x} {ROOF_Y} {z} minecraft:glowstone")
    return k


def podgotovit_bojca(igrok):
    """Существо: усиленное здоровье, меч в первом слоте и возрождение в загоне."""
    return [
        # ЛИЧНАЯ точка возрождения — она сильнее общей точки мира,
        # поэтому после смерти существо (и ты) окажется в загоне, а не за стеной.
        f"spawnpoint {igrok} 0 {GROUND_Y} 3",
        f"attribute {igrok} minecraft:generic.max_health base set {MAX_HEALTH}",
        f"effect give {igrok} minecraft:instant_health 1 20 true",
        f"clear {igrok}",
        f"replaceitem entity {igrok} hotbar.0 minecraft:iron_sword",
        f"gamemode survival {igrok}",
    ]


def nbt_zombi():
    """Описание зомби. Меч и скорость — единственный честный способ усложнить бой.

    PersistenceRequired — чтобы не исчезал сам. CanPickUpLoot=0 — чтобы не поднимал
    выпавшие вещи (иначе подберёт чужой меч и станет непредсказуемо сильнее).
    """
    chasti = ["PersistenceRequired:1b", "CanPickUpLoot:0b", "Health:20f"]
    if ZOMBI_S_MECHOM:
        chasti.append('HandItems:[{id:"minecraft:iron_sword",Count:1b},{}]')
    skorost = ZOMBI_SKOROST
    if ZOMBI_ZAMOROZKA == "chuchelo":
        chasti.append("NoAI:1b")              # разум выключен: стоит чучелом
    elif ZOMBI_ZAMOROZKA == "vkopannyj":
        skorost = 0.0                          # с места не сойдёт, но ударит
    if skorost is not None:
        chasti.append('Attributes:[{Name:"generic.movement_speed",Base:%g}]' % skorost)
    return "{" + ",".join(chasti) + "}"


def sluchajnoe_mesto_zombi(rng=None):
    """Случайная точка внутри загона, не ближе MIN_DALNOST от существа."""
    rng = rng or random
    vnutri = ARENA_R - 1                      # стены на ±ARENA_R, внутри до ±(R-1)
    px, _, pz = SPAWN
    for _ in range(60):
        x = rng.uniform(-vnutri + 0.5, vnutri - 0.5)
        z = rng.uniform(-vnutri + 0.5, vnutri - 0.5)
        if ((x - px) ** 2 + (z - pz) ** 2) ** 0.5 >= MIN_DALNOST:
            return round(x, 1), GROUND_Y, round(z, 1)
    return ZOMBIE_SPOT                        # на всякий случай


def sbros_boya(igrok, rng=None, zombi=None):
    """Новый бой БЕЗ пересоздания мира — вот ради чего всё затевалось."""
    rng = rng or random
    x, y, z = SPAWN
    yaw = round(rng.uniform(-180, 180), 1)    # существо смотрит куда попало: пусть ищет
    skolko = ZOMBI_NA_ARENE if zombi is None else int(zombi)
    prizyv = []
    for _ in range(max(skolko, 1)):
        zx, zy, zz = sluchajnoe_mesto_zombi(rng)
        prizyv.append(f"summon minecraft:zombie {zx} {zy} {zz} {nbt_zombi()}")
    return [
        "kill @e[type=zombie]",
        "kill @e[type=item]",
        f"tp {igrok} {x} {y} {z} {yaw} 0",             # поворот случайный: цель надо найти
        # снимаем эффекты ДО лечения: наоборот — и лечение смывалось бы вместе с ними
        f"effect clear {igrok}",
        f"effect give {igrok} minecraft:instant_health 1 20 true",
        # Сытость тоже возвращаем к полной. Раньше она только падала и в конце
        # концов дошла бы до нуля: тогда пропадает естественное лечение и
        # начинается урон от голода — боль, которой существо не может избежать.
        f"effect give {igrok} minecraft:saturation 1 20 true",
        f"replaceitem entity {igrok} hotbar.0 minecraft:iron_sword",
        f"scoreboard players set {igrok} {SCHET_URON} 0",
        f"scoreboard players set {igrok} {SCHET_BOL} 0",
        f"scoreboard players set {igrok} {SCHET_UBIJSTVA} 0",
    ] + prizyv


def kto_v_mire(konsol):
    """Имя игрока с сервера: при online-mode=false оно любое, надо узнать фактическое."""
    otvet = konsol.komanda("list")
    # «There are 1 of a max of 4 players online: Korgan»
    if ":" in otvet:
        imena = [s.strip() for s in otvet.split(":", 1)[1].split(",") if s.strip()]
        return imena[0] if imena else None
    return None


def _chislo_iz_otveta(otvet):
    """Вытащить число из ответа вида «Игрок has the following entity data: 17»."""
    for slovo in otvet.replace(",", " ").split():
        t = slovo.rstrip("fdb")
        try:
            return float(t)
        except ValueError:
            continue
    return None


def sostoyanie(konsol, igrok):
    """Точные числа: урон, боль, убийства, здоровье, СЫТОСТЬ.

    Сытость читаем по-настоящему. Раньше в чувства подавалась единица —
    существо не могло заметить, что голодает, а голод отнимает лечение.
    """
    uron = konsol.chislo_scoreboard(igrok, SCHET_URON)
    bol = konsol.chislo_scoreboard(igrok, SCHET_BOL)
    ubijstva = konsol.chislo_scoreboard(igrok, SCHET_UBIJSTVA)
    zhizn = _chislo_iz_otveta(konsol.komanda(f"data get entity {igrok} Health"))
    sytost = _chislo_iz_otveta(konsol.komanda(f"data get entity {igrok} foodLevel"))
    return {"uron": uron, "bol": bol, "ubijstva": ubijstva,
            "zhizn": zhizn, "sytost": sytost}


def zamorozit_vseh(konsol, zamorozit=True, popytok=3):
    """Выключить/включить разум у всех зомби. Возвращает True, если получилось.

    Нужно для паузы: мир на выделенном сервере не останавливается, и без этого
    зомби спокойно добивали неподвижное существо, пока человек отошёл.

    РАЗМОРОЗКУ ОБЯЗАТЕЛЬНО ПРОВЕРЯЕМ и повторяем при неудаче. Если команда молча
    не дойдёт, зомби останутся застывшими навсегда: существо начнёт убивать
    неподвижные мишени без всякого урона, в логе будут прекрасные 100% побед,
    и мы не заметим, что обучение отравлено.
    """
    if not est_zombi(konsol):
        return True                  # некого морозить — это не неудача
    znak = "1b" if zamorozit else "0b"
    for _ in range(popytok):
        konsol.komanda(
            "execute as @e[type=zombie] run data merge entity @s {NoAI:" + znak + "}")
        ostalis = "passed" in konsol.komanda(
            "execute if entity @e[type=zombie,nbt={NoAI:1b}]").lower()
        if ostalis == zamorozit:
            return True
    return False


def est_zombi(konsol):
    """Остался ли хоть один зомби на арене.

    Нужно для порядка «зачистил волну»: новую партию призываем только когда все
    мертвы. Иначе при трёх зомби вышла бы бесконечная подпитка — убил одного,
    появились трое новых, а недобитые остались, и загон бы забился толпой.
    """
    return "passed" in konsol.komanda("execute if entity @e[type=zombie]").lower()
