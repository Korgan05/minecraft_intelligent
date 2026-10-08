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
# ЛЕСТНИЦА ЗДОРОВЬЯ: 40 -> 30 (30.07.2026). Прогон на 218 боёв показал, что на
# 40 HP расти больше некуда: обучение стало безопасным (10 обновлений без
# срыва, оценщик ожил до EV +0.36), но политика неотличима от замороженной
# опоры (89.0% против 87.3%, z=0.75; шаги на победу 95.6 против 98.2, t=0.84).
# Задача решена, сигнал упёрся в шум. Новое давление — меньше здоровья: тот же
# противник, та же картинка, дорожает только размен. Цель лестницы — дефолтные
# 20 HP (у человека столько, и бой с ним иначе нечестен): 40 -> 30 -> 24 -> 20.
#
# Мозг НЕ трогается: в чувства идёт доля zhizn/MAX_HEALTH, полное здоровье
# остаётся 1.0. Меняется цена ошибки: удар зомби был 7.5% полосы, стал 10%;
# выдерживает 9 ударов вместо 13.
#
# ВНИМАНИЕ: все опоры до этой строки (87.3% убийств, 92-98 шагов на победу) —
# про 40 HP, теперь НЕДЕЙСТВИТЕЛЬНЫ. Первым делом на новой ступени — свежая
# опора замороженным прогоном. Замеренные константы заслона экономики (боль
# гибели 57 и др.) тоже сняты при 40 HP — пересчитать по новой опоре.
#
# СТУПЕНЬ 30 РЕШЕНА ЗА НОЧЬ 30-31.07: 2395 боёв, последние 1400 без смертей,
# 100% убийств, 51 шаг на победу, из боя выходит с 24.6/30. Чемпион ступени —
# CHEMPION-30HP-FINAL-492127.zip, опора ступени была 64.7% (173 боя).
#
# 30 -> 20, ЧЕРЕЗ СТУПЕНЬ, и вот почему это не лихачество. Хвост риска по
# последним 500 ночным боям: здоровье проседало ниже 10 (что при потолке 20
# означало бы смерть) всего в 0.8% боёв. Значит на 24 HP он сразу играл бы
# ~99% — пустая ступень без сигнала, а на 20 ожидаемо ~95-98% — и сигнал есть,
# и это уже ДЕФОЛТ: честное человеческое здоровье, порог для боя с человеком.
# ЛЕСТНИЦА ВНИЗ ДЛЯ ДУЭЛИ (31.07, вечер). Три прогона подряд разучивали дуэль
# с железным мечником на 20 HP (49% -> 13/23/23% по вскрытиям), включая чистых
# мечников с выгодным бонусом — ни экономика, ни перенос от простых не при чём.
# Оставшаяся версия: МАРЖА. На 20 HP мечник убивает за 2-3 удара, большинство
# эпизодов — смерти, и шквал отрицательных советов глушит победный сигнал.
# Обучение блистало там, где опора была >=65% (ступень 30 HP: 65% -> 100% за
# ночь). Рабочая гипотеза-правило: ступень годна для обучения, если опора на
# ней не ниже ~55-60%.
# План А (30 HP) дал опору 73.4%, но обучение и там тихо съезжало (73 -> 65 за
# 450 боёв). Решение: ПОКАЗ (запись урока дуэли человеком) — и по предложению
# человека пишем его сразу на честных 20 HP: под таким давлением демонстратор
# сам играет чисто, урок содержит целевую технику без ленивых разменов, и если
# показ поднимет опору дуэли на 20 выше ~60% — учим сразу на дефолте, минуя
# спуск 30 -> 24 -> 20.
MAX_HEALTH = 20

# СИЛА ЗОМБИ. Усложнять надо противника, а НЕ человека: тело человека должно
# совпадать с телом существа (40 здоровья, железный меч), иначе показ станет
# ложью — его «полное здоровье» записалось бы как половина.
# Замер показал, что при обычных зомби человеку слишком легко: за пять минут
# здоровье не падало ниже 33 из 40, кадров опасности НОЛЬ. Учиться отступать
# и лечиться существу было не на чем. Меч в руке зомби это исправляет:
# он бьёт втрое больнее, и отход становится вынужденным, а не украшением.
# СТУПЕНЬ С МЕЧОМ (31.07.2026) — теперь не выключатель, а ДОЛЯ. Смешивание
# обязательно (см. выше про забывание): половина боёв — мечник, половина —
# простой. Лента пишет тип противника в каждую строку, так что победы по
# каждому типу видны отдельно — это встроенный прибор «не забыл ли простого».
#
# Толчок ступени: первый спарринг с человеком — 4:48, существо беспомощно
# против вооружённого противника, который двигается и наказывает размен.
# Мечник — первый шаг к этому навыку: его удар (~втрое больнее укуса) делает
# привычный размен смертельным на честных 20 HP.
# ЧИСТЫЕ МЕЧНИКИ — решающий опыт на механизм порчи (31.07). Два прогона на
# смеси 50/50 подряд разучивали дуэль (49% -> 13% и 49% -> 23% по вскрытиям),
# второй — при ВЫГОДНОЙ экономике (+10 за мечника), так что версия «награда
# учит отказу» мертва. Главная версия: перетягивание стилем — 55% опыта против
# простых стабильно награждают размен, и этот градиент перезаписывает
# осторожность дуэли. Проверка: обучение БЕЗ простых. Дуэль растёт -> перенос
# доказан, смесь строить иначе. Падает и тут -> дело в марже (умирает раньше,
# чем учится), тогда ступень мягче: деревянный меч.
DOLYA_S_MECHOM = 0.5
ZOMBI_S_MECHOM = False           # прежний выключатель «все с мечом»: оставлен для проб
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

# Состав последнего призыва («мечник»/«простой»), заполняется в sbros_boya.
# Модульная переменная, а не возврат из функции: sbros_boya отдаёт список команд,
# и менять её вид пришлось бы во всех местах вызова. Читает mir.reset.
POSLEDNIJ_SOSTAV = []


def pravila_mira():
    """Один раз при подъёме сервера."""
    return [
        "gamerule doDaylightCycle false",     # ночь не кончается -> зомби не горит
        "gamerule doWeatherCycle false",
        # никакой толпы: она однажды уронила fps до 1
        "gamerule doMobSpawning false",
        "gamerule keepInventory true",        # меч не выпадает при смерти
        "gamerule doImmediateRespawn true",   # экран смерти не закрывает глаза
        "gamerule announceAdvancements false",
        "gamerule sendCommandFeedback false",  # чат не лезет в кадр существа
        "gamerule showDeathMessages false",
        "gamerule doFireTick false",
        # отход лечит — навык, который оно уже нашло
        "gamerule naturalRegeneration true",
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


def nbt_moba(kto="zombie", s_mechom=False):
    """Описание призываемого моба. Метка нужна, чтобы отличать наших от чужих.

    PersistenceRequired — чтобы не исчезал сам. CanPickUpLoot=0 — чтобы не поднимал
    выпавшие вещи (иначе подберёт чужой меч и станет непредсказуемо сильнее).

    Меч даём только человекоподобным: скелету он не нужен (он стреляет), а
    крипперу и пауку положить его некуда.
    """
    # Здоровье НЕ навязываем: у каждого моба своё (зомби 20, паук 16), и чужое
    # число ломало бы их естественную живучесть.
    chasti = ["PersistenceRequired:1b",
              "CanPickUpLoot:0b", 'Tags:["%s"]' % METKA]
    if (s_mechom or ZOMBI_S_MECHOM) and kto in ("zombie", "husk", "drowned", "zombie_villager"):
        # HandDropChances нули: иначе убитый мечник роняет меч, тот валяется в
        # загоне и попадает существу в кадр (а поднять его CanPickUpLoot=0
        # запрещает только мобам — существо-то подберёт, у него слот занят, но
        # мусор в кадре останется). Тестовые зомби этим уже намусорили.
        chasti.append('HandItems:[{id:"minecraft:iron_sword",Count:1b},{}]')
        chasti.append('HandDropChances:[0.0f,0.0f]')
    skorost = ZOMBI_SKOROST
    if skorost is not None:
        chasti.append(
            'Attributes:[{Name:"generic.movement_speed",Base:%g}]' % skorost)
    return "{" + ",".join(chasti) + "}"


def sluchajnoe_mesto_zombi(rng=None):
    """Случайная точка внутри загона, не ближе MIN_DALNOST от существа."""
    rng = rng or random
    # стены на ±ARENA_R, внутри до ±(R-1)
    vnutri = ARENA_R - 1
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
    # чуть в сторону, чтобы не одно и то же
    razbros = rng.uniform(-0.6, 0.6)
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
    yaw = round(rng.uniform(-180, 180),
                1) if yaw is None else round(float(yaw), 1)
    skolko = ZOMBI_NA_ARENE if zombi is None else int(zombi)
    if PROTIV_CHELOVEKA:
        skolko = 0            # противник — человек, зомби только мешали бы
    prizyv = []
    global POSLEDNIJ_SOSTAV
    POSLEDNIJ_SOSTAV = []
    for _ in range(skolko):
        zx, zy, zz = mesto_szadi(
            yaw, rng) if szadi else sluchajnoe_mesto_zombi(rng)
        kto = rng.choice(MOBY)                # мешаем противников из списка
        s_mechom = rng.random() < DOLYA_S_MECHOM
        POSLEDNIJ_SOSTAV.append(
            ("мечник" if s_mechom else "простой") if kto == "zombie" else kto)
        prizyv.append(
            f"summon minecraft:{kto} {zx} {zy} {zz} {nbt_moba(kto, s_mechom)}")
    return [
        "kill @e[tag=boec]",
        "kill @e[type=item]",
        # поворот случайный: цель надо найти
        f"tp {igrok} {x} {y} {z} {yaw} 0",
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


# Имя, под которым живёт КЛИЕНТ СУЩЕСТВА (его запускает igra.py). Нужно, чтобы
# отличать существо от человека, когда в мире двое.
IMYA_SUSHCHESTVA = "xX_ryunosuke"


def kto_v_mire(konsol):
    """Имя игрока-СУЩЕСТВА. При двух игроках раньше тут была скрытая мина.

    Старый код брал ПЕРВОЕ имя из списка. Пока игрок был один — работало. В
    первом же спарринге с человеком в мире оказалось двое, и первым в списке
    стоял ЧЕЛОВЕК — мир молча взял его за существо. Вся лента боя писала
    счётчики ЧЕЛОВЕКА: его убийства как «УБИЛ», его смерти как «погиб». Счёт
    спарринга получился 48:3 «в пользу существа», тогда как на самом деле
    человек разнёс существо 48:4 — поймал это сам человек, глазами: «в основном
    убивал я, а не он». Прибор, который путает, ЧЬИ очки он считает, хуже
    отсутствующего.

    Теперь: если в мире есть IMYA_SUSHCHESTVA — берём его; если игрок один —
    берём его; если игроков несколько и среди них нет знакомого имени — лучше
    остановиться, чем молча угадать не того.
    """
    otvet = konsol.komanda("list")
    # «There are 1 of a max of 4 players online: Korgan»
    if ":" not in otvet:
        return None
    imena = [s.strip() for s in otvet.split(":", 1)[1].split(",") if s.strip()]
    if not imena:
        return None
    if IMYA_SUSHCHESTVA in imena:
        if len(imena) > 1:
            print(f"  в мире {len(imena)} игрока, существо = {IMYA_SUSHCHESTVA}, "
                  f"остальные: {[x for x in imena if x != IMYA_SUSHCHESTVA]}")
        return IMYA_SUSHCHESTVA
    if len(imena) == 1:
        return imena[0]
    raise SystemExit(
        f"В мире несколько игроков {imena}, и среди них нет «{IMYA_SUSHCHESTVA}». "
        "Не угадываю, кто из них существо: один раз такое угадывание уже "
        "перевернуло счёт спарринга. Поправь IMYA_SUSHCHESTVA в telo/arena.py.")


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
    zhizn = _chislo_iz_otveta(konsol.komanda(
        f"data get entity {igrok} Health"))
    sytost = _chislo_iz_otveta(konsol.komanda(
        f"data get entity {igrok} foodLevel"))
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
    pos_moba = _koordinaty(
        konsol, cel or f"@e[tag={METKA},limit=1,sort=nearest]")
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
