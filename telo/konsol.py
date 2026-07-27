# -*- coding: utf-8 -*-
"""
КОНСОЛЬ СЕРВЕРА (RCON): управляем миром и читаем точные числа игры.

Своя реализация протокола на голых сокетах — сторонних библиотек не нужно.

Зачем: это решает три вещи, из-за которых мы мучились с MineRL.
  * АРЕНА строится командами (/fill, /summon) — гибче кривого XML;
  * СБРОС боя одной командой вместо пересоздания мира (без семиминутных запусков);
  * НАГРАДА берётся из СОБСТВЕННЫХ счётчиков Minecraft — точный нанесённый урон
    и точные убийства, а не клиентская отсебятина, которая занижала урон вчетверо.

Протокол простой: длина (4 байта) + номер запроса (4) + тип (4) + текст + два нуля.
"""

import os
import socket
import struct

# Пароль консоли. Сервер слушает только 127.0.0.1, снаружи до него не достучаться,
# поэтому «killer» здесь безобиден. Но переопределить его можно, не трогая код:
#     set MC_RCON_PAROL=svoj_parol
PAROL = os.environ.get("MC_RCON_PAROL", "killer")

TIP_VHOD = 3        # представиться паролем
TIP_KOMANDA = 2     # выполнить команду


class Konsol:
    def __init__(self, host="127.0.0.1", port=25575, parol=None, timeout=5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.parol = parol or PAROL
        self._s = None
        self._nomer = 0

    # ── соединение ──
    def podklyuchit(self):
        self._s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._s.settimeout(self.timeout)
        nomer, _ = self._obmen(TIP_VHOD, self.parol)
        # при неверном пароле сервер отвечает номером -1
        if nomer == -1:
            raise SystemExit("Консоль отвергла пароль. Проверь rcon.password в server.properties")
        return self

    def close(self):
        if self._s is not None:
            try:
                self._s.close()
            finally:
                self._s = None

    # ── низкий уровень ──
    def _poslat(self, tip, telo):
        self._nomer += 1
        dannye = struct.pack("<ii", self._nomer, tip) + telo.encode("utf-8") + b"\x00\x00"
        self._s.sendall(struct.pack("<i", len(dannye)) + dannye)
        return self._nomer

    def _prochitat_rovno(self, n):
        buf = b""
        while len(buf) < n:
            kusok = self._s.recv(n - len(buf))
            if not kusok:
                raise ConnectionError("Консоль закрыла соединение")
            buf += kusok
        return buf

    def _prinyat(self):
        dlina = struct.unpack("<i", self._prochitat_rovno(4))[0]
        telo = self._prochitat_rovno(dlina)
        nomer, tip = struct.unpack("<ii", telo[:8])
        return nomer, tip, telo[8:-2].decode("utf-8", "replace")

    def _obmen(self, tip, telo):
        self._poslat(tip, telo)
        nomer, _, otvet = self._prinyat()
        return nomer, otvet

    # ── то, чем пользуемся ──
    def komanda(self, tekst):
        """Выполнить команду и вернуть ответ сервера текстом.

        При обрыве связи ОДИН раз переподключаемся и повторяем. Нужно потому, что
        долгая пауза в обучении может уронить соединение по таймауту, и тогда первая
        же команда после возврата свалила бы весь сеанс.
        """
        if self._s is None:
            self.podklyuchit()
        try:
            _, otvet = self._obmen(TIP_KOMANDA, tekst)
            return otvet
        except (ConnectionError, OSError, TimeoutError):
            self.close()
            self.podklyuchit()
            _, otvet = self._obmen(TIP_KOMANDA, tekst)
            return otvet

    def komandy(self, spisok):
        """Пачка команд подряд — так строится арена."""
        return [self.komanda(k) for k in spisok]

    def chislo_scoreboard(self, igrok, cel):
        """Точное значение счётчика игры, например нанесённый урон.

        Готовится один раз командой:
            scoreboard objectives add uron minecraft.custom:minecraft.damage_dealt
        и читается сюда. Это и есть замена той врущей кассы из Malmo.
        """
        otvet = self.komanda(f"scoreboard players get {igrok} {cel}")
        # ответ вида «Korgan has 137 [uron]»; если счётчика нет — текст без цифр
        for slovo in otvet.replace("[", " ").split():
            if slovo.lstrip("-").isdigit():
                return int(slovo)
        return None

