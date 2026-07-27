# -*- coding: utf-8 -*-
"""
ЗАПУСК ИГРЫ С НАШИМ МОДОМ — без лаунчера.

Зачем свой запускатель. В .minecraft лежит сборка на 55 модов (JoJo и прочее),
и профиль «Forge 1.16.5» из лаунчера тянет их все. Нам нужен чистый клиент, где
стоит ТОЛЬКО пуповина: иначе непонятно, чьё поведение мы наблюдаем, да и слабому
ноуту тяжело. Отдельная папка игры решает это, но настраивать её в лаунчере
руками неудобно и легко забыть.

Поэтому берём то, что лаунчер уже скачал (версию, 83 библиотеки, натив-длл), и
сами составляем команду запуска. Папка игры — наша klient\\, там один мод.

Тонкость про Java. В описании версии есть ключи вида --add-exports: они нужны
Java 9 и новее, а Forge 1.16.5 живёт на восьмёрке, и восьмёрка от такого ключа
падает сразу. Поэтому их отбрасываем.

Запуск: zapusk\\igra-s-modom.bat
"""

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

MINECRAFT = Path(os.environ["APPDATA"]) / ".minecraft"
VERSIYA = "Forge 1.16.5"
JAVA = Path.home() / "minecraft-ai" / "jdk8" / "bin" / "javaw.exe"
KLIENT = Path(__file__).resolve().parent / "klient"
IMYA = "Boec"
PAMYAT = "2G"


def podhodit(pravila):
    """Правила библиотеки: подходит ли она этой системе."""
    if not pravila:
        return True
    itog = False
    for p in pravila:
        os_p = p.get("os", {})
        sovpalo = True
        if "name" in os_p and os_p["name"] != "windows":
            sovpalo = False
        if "version" in os_p and not re.search(os_p["version"], platform.version()):
            sovpalo = False
        if sovpalo:
            itog = p.get("action") == "allow"
    return itog


def put_biblioteki(lib):
    skachka = lib.get("downloads", {}).get("artifact", {}).get("path")
    if skachka:
        return MINECRAFT / "libraries" / skachka
    gruppa, imya, versiya = lib["name"].split(":")[:3]
    hvost = ":".join(lib["name"].split(":")[3:])
    fajl = f"{imya}-{versiya}" + (f"-{hvost}" if hvost else "") + ".jar"
    return MINECRAFT / "libraries" / Path(*gruppa.split(".")) / imya / versiya / fajl


def sobrat_klassputi(opisanie, papka_versii):
    puti, net = [], []
    for lib in opisanie.get("libraries", []):
        if not podhodit(lib.get("rules")):
            continue
        p = put_biblioteki(lib)
        (puti if p.exists() else net).append(p)
    svoj = papka_versii / f"{VERSIYA}.jar"
    if svoj.exists():
        puti.append(svoj)
    return puti, net


def razvernut(znachenie, zameny):
    for klyuch, na in zameny.items():
        znachenie = znachenie.replace("${" + klyuch + "}", str(na))
    return znachenie


def sobrat_argumenty(spisok, zameny):
    gotovo = []
    for a in spisok:
        if isinstance(a, str):
            gotovo.append(razvernut(a, zameny))
            continue
        if not podhodit(a.get("rules")):
            continue
        znacheniya = a["values"]
        if isinstance(znacheniya, str):
            znacheniya = [znacheniya]
        for z in znacheniya:
            gotovo.append(razvernut(z, zameny))
    return gotovo


def main():
    papka = MINECRAFT / "versions" / VERSIYA
    opisanie_fajl = papka / f"{VERSIYA}.json"
    if not opisanie_fajl.exists():
        raise SystemExit(f"Нет описания версии: {opisanie_fajl}\n"
                         f"Поставь «{VERSIYA}» в лаунчере хотя бы один раз.")
    if not JAVA.exists():
        raise SystemExit(f"Нет Java 8: {JAVA}")

    opisanie = json.loads(opisanie_fajl.read_text(encoding="utf-8"))
    puti, net = sobrat_klassputi(opisanie, papka)
    if net:
        print(f"ВНИМАНИЕ: не нашёл {len(net)} библиотек, например {net[0].name}")
        print("Запусти «Forge 1.16.5» из лаунчера один раз, чтобы он их докачал.")
        raise SystemExit(1)

    KLIENT.mkdir(exist_ok=True)
    (KLIENT / "mods").mkdir(exist_ok=True)
    mody = list((KLIENT / "mods").glob("*.jar"))
    if not mody:
        raise SystemExit(f"В {KLIENT / 'mods'} нет ни одного мода. Собери: zapusk\\sobrat-mod.bat")

    zameny = {
        "auth_player_name": IMYA,
        "version_name": VERSIYA,
        "game_directory": str(KLIENT),
        "assets_root": str(MINECRAFT / "assets"),
        "assets_index_name": opisanie.get("assets", "1.16"),
        "auth_uuid": "00000000000000000000000000000001",
        "auth_access_token": "0",
        "clientid": "0",
        "auth_xuid": "0",
        "user_type": "legacy",
        "version_type": opisanie.get("type", "release"),
        "user_properties": "{}",
        "natives_directory": str(papka / "natives"),
        "launcher_name": "pupovina",
        "launcher_version": "1",
        "library_directory": str(MINECRAFT / "libraries"),
        "classpath_separator": os.pathsep,
        "classpath": os.pathsep.join(str(p) for p in puti),
    }

    argumenty = opisanie.get("arguments", {})
    jvm = sobrat_argumenty(argumenty.get("jvm", []), zameny)
    # Java 8 не знает модульных ключей и падает на них, не начав работу.
    jvm = [a for a in jvm if not a.startswith("--add-exports") and not a.startswith("--add-opens")]
    igra = sobrat_argumenty(argumenty.get("game", []), zameny)
    # Заходим на бойню сразу: 1.16.5 умеет --server, и меню можно не трогать.
    igra += ["--server", "127.0.0.1", "--port", "25565"]

    komanda = ([str(JAVA), f"-Xmx{PAMYAT}", "-Xms512M"] + jvm
               + [opisanie["mainClass"]] + igra)

    print(f"версия      : {VERSIYA}")
    print(f"папка игры  : {KLIENT}")
    print(f"модов       : {len(mody)} ({', '.join(m.name for m in mody)})")
    print(f"библиотек   : {len(puti)}")
    print(f"игрок       : {IMYA}")
    print("\nзапускаю. Окно игры откроется через полминуты-минуту.")
    print("Сервер «Bojnya (mod)» уже в списке — Сетевая игра -> двойной щелчок.\n")

    return subprocess.call(komanda, cwd=str(KLIENT))


if __name__ == "__main__":
    sys.exit(main())
