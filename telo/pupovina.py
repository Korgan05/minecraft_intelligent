# -*- coding: utf-8 -*-
"""
ПУПОВИНА со стороны питона: разговор с нашим модом напрямую, без Windows.

Что меняется по сравнению со старым телом (glaza.py + ruki.py):
  * окно игры больше НЕ обязано быть впереди — можно работать за компьютером;
  * поворот задаётся В ГРАДУСАХ, а не в единицах мыши: 5.0 — это ровно пять
    градусов, а не «пять умножить на чувствительность и надеяться»;
  * кадр приходит уже 64x64 из самой игры — не снимок рабочего стола, где
    могло оказаться чужое окно;
  * здоровье и сытость приходят вместе с кадром, без запроса к серверу.

Чего мы НАРОЧНО не берём, хотя мод мог бы: положения зомби, расстояний,
списка сущностей. Существо видит то же, что человек, — иначе это не обучение,
а подсказка.

Разговор устроен просто. Каждое сообщение — четыре байта длины, потом само
сообщение. Мы посылаем строку, мод отвечает: либо кадром с приборами, либо
текстом. На один шаг существа приходится ровно один обмен.
"""

import socket
import struct
import time

import numpy as np

PORT = 25580
ZAGOLOVOK = struct.Struct(">4sBHHfffffI")   # метка, флаги, ширина, высота, приборы, длина
METKA = b"PUP\x01"

FLAG_IGROK = 1        # игрок есть в мире
FLAG_PAUZA = 2        # человек попросил паузу клавишей мода
FLAG_FOKUS = 4        # окно игры сейчас впереди
# Открыт любой экран — меню Escape, инвентарь, чат. Игра в этом состоянии не
# разбирает клавиши, поэтому существо не ходит и не бьёт, что бы мы ни просили.
FLAG_MENYU = 8
# БЕЖИТ ли игрок. Спрашиваем игру, а не клавишу: человек часто разгоняется
# двойным W, и по клавише бега такой разбег не был бы виден вовсе.
FLAG_BEG = 16


class NetSvyazi(RuntimeError):
    """Мод не отвечает: игра закрыта, мод не встал или порт занят."""


class Pupovina:
    def __init__(self, port=PORT, host="127.0.0.1", zhdat=30.0):
        self.adres = (host, port)
        self.s = None
        self.podklyuchit(zhdat)

    # ── связь ──
    def podklyuchit(self, zhdat=30.0):
        konec = time.perf_counter() + zhdat
        posledn = None
        while time.perf_counter() < konec:
            try:
                s = socket.create_connection(self.adres, timeout=5.0)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.s = s
                return self
            except OSError as e:
                posledn = e
                time.sleep(1.0)
        raise NetSvyazi(
            f"мод не отвечает на {self.adres[0]}:{self.adres[1]} ({posledn}).\n"
            "Проверь: игра запущена профилем Forge 1.16.5, и pupovina.jar лежит в mods.")

    def _poslat(self, tekst):
        data = tekst.encode("utf-8")
        self.s.sendall(struct.pack(">I", len(data)) + data)

    def _prinyat(self):
        n = struct.unpack(">I", self._rovno(4))[0]
        return self._rovno(n)

    def _rovno(self, n):
        """Читаем РОВНО n байт. Обычный recv возвращает сколько успел, и кадр
        на 12 килобайт приходил бы кусками — первая версия так и ломалась."""
        chasti, ostalos = [], n
        while ostalos:
            try:
                kusok = self.s.recv(ostalos)
            except socket.timeout:
                # Самая частая причина — ВТОРОЕ соединение. Мод обслуживает одного
                # собеседника, остальные молча висят в очереди и ответа не ждут.
                # Первый запуск обучения упал именно так, и по слову «timed out»
                # понять это было невозможно.
                raise NetSvyazi(
                    "мод не ответил за отведённое время.\n"
                    "Чаще всего это ВТОРОЕ соединение: мод разговаривает только с "
                    "одним, остальные ждут молча.\n"
                    "Реже — игра свёрнута и потому не рисует кадры.")
            if not kusok:
                raise NetSvyazi("мод оборвал связь (игру закрыли?)")
            chasti.append(kusok)
            ostalos -= len(kusok)
        return b"".join(chasti)

    # ── обмен ──
    def ping(self):
        self._poslat("PING")
        return self._prinyat().decode("utf-8", "replace")

    def razmer_kadra(self, shirina, vysota):
        self._poslat(f"RAZMER {shirina} {vysota}")
        return self._prinyat().decode("utf-8", "replace")

    def skazat(self, tekst):
        """Показать надпись человеку В ИГРЕ, над хотбаром.

        Нужна для записи показа: обратный отсчёт в консоли человек не видит,
        он смотрит в игру. Ввод при этом не трогается.
        """
        self._poslat("SKAZAT " + str(tekst))
        return self._prinyat().decode("utf-8", "replace")

    def diag(self):
        """Что игра думает прямо сейчас: экран, фокус, прицел, нажатые клавиши."""
        self._poslat("DIAG")
        return self._prinyat().decode("utf-8", "replace")

    def otpustit_vse(self):
        self._poslat("OTPUSTIT")
        return self._prinyat().decode("utf-8", "replace")

    def sostoyanie(self):
        """Только посмотреть: кадр и приборы, ничего не нажимая.

        Отличие от shag важное: shag берёт власть над клавиатурой на секунду,
        а это значит, что во время паузы человек не смог бы ходить. Здесь мод
        не трогает ввод вообще.
        """
        self._poslat("SOSTOYANIE")
        return self._razobrat(self._prinyat())

    def shag(self, vpered=0, nazad=0, vlevo=0, vpravo=0, pryzhok=0,
             prisest=0, bezhat=0, udar=0, dyaw=0.0, dpitch=0.0):
        """Одно действие существа: нажать что нужно, повернуть голову, получить кадр.

        Повороты — в ГРАДУСАХ. Возвращает всё, что существо имеет право знать.
        """
        self._poslat(
            "SHAG %d %d %d %d %d %d %d %d %.4f %.4f"
            % (int(vpered), int(nazad), int(vlevo), int(vpravo), int(pryzhok),
               int(prisest), int(bezhat), int(udar), float(dyaw), float(dpitch)))
        return self._razobrat(self._prinyat())

    def _razobrat(self, telo):
        if not telo.startswith(METKA):
            raise NetSvyazi(f"мод ответил непонятным: {telo[:40]!r}")
        (_, flagi, w, h, zhizn, max_zhizn, sytost, yaw, pitch,
         dlina) = ZAGOLOVOK.unpack_from(telo, 0)
        piksely = telo[ZAGOLOVOK.size:ZAGOLOVOK.size + dlina]
        if len(piksely) != dlina:
            raise NetSvyazi(f"кадр пришёл обрезанным: {len(piksely)} из {dlina}")
        kadr = (np.frombuffer(piksely, dtype=np.uint8).reshape(h, w, 3)
                if dlina else np.zeros((h, w, 3), np.uint8))
        return {
            "kadr": kadr,
            "zhizn": zhizn,
            "max_zhizn": max_zhizn,
            "sytost": sytost,
            "yaw": yaw,
            "pitch": pitch,
            "v_mire": bool(flagi & FLAG_IGROK),
            "pauza": bool(flagi & FLAG_PAUZA),
            "fokus": bool(flagi & FLAG_FOKUS),
            "menyu": bool(flagi & FLAG_MENYU),
            "bezhit": bool(flagi & FLAG_BEG),
        }

    def close(self):
        if self.s is not None:
            try:
                self.otpustit_vse()
            except Exception:
                pass
            try:
                self.s.close()
            except Exception:
                pass
            self.s = None
