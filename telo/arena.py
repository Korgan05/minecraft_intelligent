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

import math
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
# КОГО зовём на арену. Список: из него выбирается случайно, поэтому можно
# МЕШАТЬ противников. Мешать обязательно: если целиком переключить существо
# на скелетов, оно забудет зомби — старое вытесняется новым.
MOBY = ["zombie"]
METKA = "boec"                   # метим призванных, чтобы не путать со случайными
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

# счётчики самой игры (в 1.16 доступны как статистики)
SCHET_URON = "uron"              # minecraft.custom:minecraft.damage_dealt
SCHET_BOL = "bol"                # minecraft.custom:minecraft.damage_taken
SCHET_UBIJSTVA = "ubijstva"      # minecraft.custom:minecraft.mob_kills — ЛЮБЫЕ мобы
# СМЕРТИ считаем счётчиком игры, а НЕ по «здоровье упало до нуля».
# Причина дорогая. При doImmediateRespawn игра поднимает существо за ОДИН тик,
# а смотрим мы раз в четыре — и ноль между взглядами просто не попадался. Тогда
# бой не заканчивался: зомби оставался тот же, недобитый, а существо вставало с
# обычными 20 здоровья вместо 40 и добивало его вполовину слабее. Со стороны это
# выглядело как честная победа. Счётчик не умеет не заметить.
SCHET_SMERTEJ = "smerti"         # minecraft.custom:minecraft.deaths
# УБИЙСТВА ИГРОКОВ — отдельный счётчик игры. mob_kills человека НЕ считает, и
# без этого существо не получило бы награды за победу над тобой: только за урон.
SCHET_IGROKOV = "ubijstva_igrokov"   # minecraft.custom:minecraft.player_kills

# ПРОТИВНИК-ЧЕЛОВЕК. Когда True, зомби не призываются и волна не сбрасывается по
# «мобов не осталось»: противник — ты, и ты не моб. Иначе мир начинал бы новый
# бой каждый шаг, потому что мобов в загоне и правда нет.
PROTIV_CHELOVEKA = False


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
        f"scoreboard objectives add {SCHET_UBIJSTVA} minecraft.custom:minecraft.mob_kills",
        f"scoreboard objectives add {SCHET_SMERTEJ} minecraft.custom:minecraft.deaths",
        f"scoreboard objectives add {SCHET_IGROKOV} minecraft.custom:minecraft.player_kills",
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


def nbt_moba(kto="zombie"):
    """Описание призываемого моба. Метка нужна, чтобы отличать наших от чужих.

    PersistenceRequired — чтобы не исчезал сам. CanPickUpLoot=0 — чтобы не поднимал
    выпавшие вещи (иначе подберёт чужой меч и станет непредсказуемо сильнее).

    Меч даём только человекоподобным: скелету он не нужен (он стреляет), а
    крипперу и пауку положить его некуда.
    """
    # Здоровье НЕ навязываем: у каждого моба своё (зомби 20, паук 16), и чужое
    # число ломало бы их естественную живучесть.
    chasti = ["PersistenceRequired:1b", "CanPickUpLoot:0b", 'Tags:["%s"]' % METKA]
    if ZOMBI_S_MECHOM and kto in ("zombie", "husk", "drowned", "zombie_villager"):
        chasti.append('HandItems:[{id:"minecraft:iron_sword",Count:1b},{}]')
    skorost = ZOMBI_SKOROST
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


def vse_igroki(konsol):
    """Все, кто сейчас в мире. Нужно для боя человека против существа: там их двое,
    и подготовить надо обоих, иначе человек выйдет с обычными 20 здоровья и без меча —
    то есть бой будет нечестным в другую сторону."""
    otvet = konsol.komanda("list")
    if ":" not in otvet:
        return []
    return [x.strip() for x in otvet.split(":", 1)[1].split(",") if x.strip()]


def rasstavit_protiv(sushchestvo, chelovek):
    """Развести противников по разным сторонам загона, лицом друг к другу.

    Против зомби существо ставится в середину и разворачивается куда попало —
    пусть ищет. Против человека так нельзя: если начинать вплотную, весь бой
    выродится в размен ударами, и ни подход, ни отход не понадобятся.
    """
    d = ARENA_R - 2
    return [
        f"tp {sushchestvo} 0.5 {GROUND_Y} {-d + 0.5} 0 0",     # смотрит на +Z
        f"tp {chelovek} 0.5 {GROUND_Y} {d + 0.5} 180 0",       # смотрит на -Z
    ]


def mesto_szadi(yaw, rng=None, dalnost=4.0):
    """Точка ЗА СПИНОЙ существа, если оно смотрит под углом yaw.

    Нужна для урока «развернуться к тому, кто подошёл со спины». При случайном
    появлении такая ситуация выпадает редко, и человеку пришлось бы стоять и
    ждать её — в запись пошли бы минуты пустого стояния. Лучше подстроить.

    В Minecraft угол 0 смотрит вдоль +Z, 90 — вдоль -X. Значит взгляд это
    (-sin, cos), а спина — то же с обратным знаком.
    """
    rng = rng or random
    ugol = math.radians(float(yaw))
    px, _, pz = SPAWN
    razbros = rng.uniform(-0.6, 0.6)           # чуть в сторону, чтобы не одно и то же
    d = dalnost + rng.uniform(-0.5, 0.5)
    x = px + math.sin(ugol) * d + math.cos(ugol) * razbros
    z = pz - math.cos(ugol) * d + math.sin(ugol) * razbros
    vnutri = ARENA_R - 1.5
    return (round(max(-vnutri, min(vnutri, x)), 1), GROUND_Y,
            round(max(-vnutri, min(vnutri, z)), 1))


def sbros_boya(igrok, rng=None, zombi=None, yaw=None, szadi=False):
    """Новый бой БЕЗ пересоздания мира — вот ради чего всё затевалось."""
    rng = rng or random
    x, y, z = SPAWN
    # По умолчанию существо смотрит куда попало: пусть ищет цель само.
    # Для уроков угол можно задать, чтобы ставить нужную ситуацию нарочно.
    yaw = round(rng.uniform(-180, 180), 1) if yaw is None else round(float(yaw), 1)
    skolko = ZOMBI_NA_ARENE if zombi is None else int(zombi)
    if PROTIV_CHELOVEKA:
        skolko = 0            # противник — человек, зомби только мешали бы
    prizyv = []
    for _ in range(skolko):
        zx, zy, zz = mesto_szadi(yaw, rng) if szadi else sluchajnoe_mesto_zombi(rng)
        kto = rng.choice(MOBY)                # мешаем противников из списка
        prizyv.append(f"summon minecraft:{kto} {zx} {zy} {zz} {nbt_moba(kto)}")
    return [
        "kill @e[tag=boec]",
        "kill @e[type=item]",
        f"tp {igrok} {x} {y} {z} {yaw} 0",             # поворот случайный: цель надо найти
        # Усиленное здоровье выдаём КАЖДЫЙ бой, а не один раз при запуске.
        # При смерти Minecraft сбрасывает свойства игрока к обычным, и максимум
        # падал с 40 до 20: существо дралось вполовину слабее и вдобавок видело
        # своё полное здоровье как 0.5 — в чувствах оно подаётся долей от сорока.
        f"attribute {igrok} minecraft:generic.max_health base set {MAX_HEALTH}",
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
        f"scoreboard players set {igrok} {SCHET_SMERTEJ} 0",
        f"scoreboard players set {igrok} {SCHET_IGROKOV} 0",
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


def rasstoyanie_do_moba(konsol, igrok, cel=None):
    """Сколько блоков до цели. None — цели нет.

    По умолчанию цель — ближайший наш моб. В бою против человека мобов нет вовсе,
    и целью надо передать его имя: иначе расстояние всегда None, и плата за
    простой не сработает ни разу.

    Нужно НАГРАДЕ, а не существу. Это важное разделение: учитель вправе знать
    больше ученика. В чувства существу расстояние не подаётся — оно по-прежнему
    видит только пиксели, и читерства тут нет. Мы лишь можем сказать «горячо» или
    «холодно», как человек, который смотрит на экран со стороны.

    Зачем понадобилось. Замер показал, что существо не выжидает нарочно: долгий
    бой стоит ему 20.6 здоровья против 4.8 у быстрого, то есть медлить прямо
    убыточно. Оно просто НЕ УМЕЕТ быстрее — из восемнадцати секунд боя удары
    занимают три, остальное поиск. А награда до сих пор появлялась только когда
    зомби уже достали мечом: между «повернулся не туда» и «повернулся к цели»
    для существа не было никакой разницы. Теперь есть, на каждом шаге.
    """
    pos_igroka = _koordinaty(konsol, igrok)
    pos_moba = _koordinaty(konsol, cel or f"@e[tag={METKA},limit=1,sort=nearest]")
    if pos_igroka is None or pos_moba is None:
        return None
    return ((pos_igroka[0] - pos_moba[0]) ** 2
            + (pos_igroka[2] - pos_moba[2]) ** 2) ** 0.5


def _koordinaty(konsol, kogo):
    otvet = konsol.komanda(f"data get entity {kogo} Pos")
    chisla = []
    for slovo in otvet.replace("[", " ").replace("]", " ").replace(",", " ").split():
        try:
            chisla.append(float(slovo.rstrip("d")))
        except ValueError:
            continue
    return tuple(chisla[-3:]) if len(chisla) >= 3 else None


def podkrepit_zdorovye(igrok):
    """Выдать усиленное здоровье заново. Отдельно — потому что после смерти это
    приходится повторять: возрождение смывает свойства игрока."""
    return [
        f"attribute {igrok} minecraft:generic.max_health base set {MAX_HEALTH}",
        f"effect clear {igrok}",
        f"effect give {igrok} minecraft:instant_health 1 20 true",
        f"effect give {igrok} minecraft:saturation 1 20 true",
        f"replaceitem entity {igrok} hotbar.0 minecraft:iron_sword",
    ]


def schet_boya(konsol, igrok):
    """Только то, чего мод знать НЕ МОЖЕТ: урон, боль, убийства.

    Здоровье и сытость мод отдаёт бесплатно вместе с кадром, поэтому спрашивать
    их у сервера больше не нужно: это были два лишних запроса на каждый шаг из
    пяти. А урон, боль и убийства — счётчики самой игры, они живут на сервере,
    и врать они не умеют. Именно на них держится честная награда.
    """
    return {"uron": konsol.chislo_scoreboard(igrok, SCHET_URON),
            "bol": konsol.chislo_scoreboard(igrok, SCHET_BOL),
            "ubijstva": konsol.chislo_scoreboard(igrok, SCHET_UBIJSTVA),
            "ubijstva_igrokov": konsol.chislo_scoreboard(igrok, SCHET_IGROKOV),
            "smerti": konsol.chislo_scoreboard(igrok, SCHET_SMERTEJ)}


def zamorozit_vseh(konsol, zamorozit=True, popytok=3):
    """Выключить/включить разум у всех зомби. Возвращает True, если получилось.

    Нужно для паузы: мир на выделенном сервере не останавливается, и без этого
    зомби спокойно добивали неподвижное существо, пока человек отошёл.

    РАЗМОРОЗКУ ОБЯЗАТЕЛЬНО ПРОВЕРЯЕМ и повторяем при неудаче. Если команда молча
    не дойдёт, зомби останутся застывшими навсегда: существо начнёт убивать
    неподвижные мишени без всякого урона, в логе будут прекрасные 100% побед,
    и мы не заметим, что обучение отравлено.
    """
    if not est_mobov(konsol):
        return True                  # некого морозить — это не неудача
    znak = "1b" if zamorozit else "0b"
    for _ in range(popytok):
        konsol.komanda(
            "execute as @e[tag=boec] run data merge entity @s {NoAI:" + znak + "}")
        ostalis = "passed" in konsol.komanda(
            "execute if entity @e[tag=boec,nbt={NoAI:1b}]").lower()
        if ostalis == zamorozit:
            return True
    return False


def est_mobov(konsol):
    """Остался ли хоть один зомби на арене.

    Нужно для порядка «зачистил волну»: новую партию призываем только когда все
    мертвы. Иначе при трёх зомби вышла бы бесконечная подпитка — убил одного,
    появились трое новых, а недобитые остались, и загон бы забился толпой.
    """
    return "passed" in konsol.komanda("execute if entity @e[tag=boec]").lower()


def polozhenie(konsol, igrok):
    """Координаты и угол обзора игрока: ((x,y,z), (yaw,pitch)) прямо из игры.

    Лежала в проверке тела, хотя это работа арены — читать состояние с сервера.
    Ею пользуются и запись показа, и все проверки.
    """
    otvet = konsol.komanda(f"data get entity {igrok} Pos")
    chisla = [float(s.rstrip("d")) for s in otvet.replace("[", " ").replace("]", " ")
              .replace(",", " ").split() if s.rstrip("d").replace("-", "").replace(".", "").isdigit()]
    pos = chisla[-3:] if len(chisla) >= 3 else [0, 0, 0]
    otvet = konsol.komanda(f"data get entity {igrok} Rotation")
    ugly = [float(s.rstrip("f")) for s in otvet.replace("[", " ").replace("]", " ")
            .replace(",", " ").split() if s.rstrip("f").replace("-", "").replace(".", "").isdigit()]
    rot = ugly[-2:] if len(ugly) >= 2 else [0, 0]
    return pos, rot
