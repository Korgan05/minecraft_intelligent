# -*- coding: utf-8 -*-
"""
ГЛАЗА: снимаем окно Minecraft напрямую, без MineRL и без сторонних библиотек.

Только ctypes (Windows) + numpy + cv2 — ничего нового ставить не нужно.

Почему снимаем ОБЛАСТЬ ЭКРАНА, а не окно через PrintWindow: Minecraft рисует
через OpenGL, и содержимое такого окна обычными способами часто отдаётся чёрным
прямоугольником. Снимок экрана в координатах окна работает всегда — ценой того,
что окно должно быть видимым и не перекрытым.

Отдаём кадр 64x64 RGB — ровно тот формат, который наше существо уже понимает,
поэтому его нынешний мозг переносится сюда без переучивания зрения.
"""

import ctypes
import ctypes.wintypes as wt

import cv2
import numpy as np

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()          # иначе на масштабировании экрана координаты врут

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
RAZMER = 64                          # сторона кадра, который видит существо


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def najti_okno(chast_zagolovka):
    """Найти окно по части заголовка. Возвращает (hwnd, полный заголовок)."""
    najdeno = []
    igla = chast_zagolovka.lower()

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def perebor(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        dlina = user32.GetWindowTextLengthW(hwnd)
        if dlina == 0:
            return True
        buf = ctypes.create_unicode_buffer(dlina + 1)
        user32.GetWindowTextW(hwnd, buf, dlina + 1)
        if igla in buf.value.lower():
            najdeno.append((hwnd, buf.value))
        return True

    user32.EnumWindows(perebor, 0)
    return najdeno[0] if najdeno else (None, None)


def oblast_okna(hwnd):
    """Координаты КЛИЕНТСКОЙ области окна на экране: (x, y, ширина, высота).

    Берём именно клиентскую часть, без рамки и заголовка — иначе в кадр существа
    попадала бы полоска Windows, и оно училось бы на мусоре.
    """
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    levyj_verh = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(levyj_verh))
    return levyj_verh.x, levyj_verh.y, r.right - r.left, r.bottom - r.top


class Glaza:
    """Снимок области экрана. Ресурсы Windows создаём один раз, не на каждый кадр."""

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self._dc_ekrana = user32.GetDC(0)
        self._dc_pamyati = gdi32.CreateCompatibleDC(self._dc_ekrana)
        self._bitmap = gdi32.CreateCompatibleBitmap(self._dc_ekrana, w, h)
        gdi32.SelectObject(self._dc_pamyati, self._bitmap)
        self._info = BITMAPINFO()
        self._info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self._info.bmiHeader.biWidth = w
        self._info.bmiHeader.biHeight = -h      # минус = сверху вниз, иначе кадр вверх ногами
        self._info.bmiHeader.biPlanes = 1
        self._info.bmiHeader.biBitCount = 32
        self._info.bmiHeader.biCompression = 0
        self._buf = ctypes.create_string_buffer(w * h * 4)

    def kadr_polnyj(self):
        """Сырой снимок области целиком, BGR (как любит cv2)."""
        gdi32.BitBlt(self._dc_pamyati, 0, 0, self.w, self.h,
                     self._dc_ekrana, self.x, self.y, SRCCOPY)
        gdi32.GetDIBits(self._dc_pamyati, self._bitmap, 0, self.h,
                        self._buf, ctypes.byref(self._info), DIB_RGB_COLORS)
        kadr = np.frombuffer(self._buf, dtype=np.uint8).reshape(self.h, self.w, 4)
        return kadr[:, :, :3]

    def kadr_sushchestva(self):
        """То, что видит существо: 64x64 RGB uint8 — формат его нынешнего мозга."""
        bgr = cv2.resize(self.kadr_polnyj(), (RAZMER, RAZMER), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def close(self):
        gdi32.DeleteObject(self._bitmap)
        gdi32.DeleteDC(self._dc_pamyati)
        user32.ReleaseDC(0, self._dc_ekrana)


def glaza_na_okno(chast_zagolovka):
    """Готовые глаза, наведённые на окно по части заголовка."""
    hwnd, zagolovok = najti_okno(chast_zagolovka)
    if hwnd is None:
        raise SystemExit(f"Окно с «{chast_zagolovka}» в заголовке не найдено. "
                         f"Запусти игру и не сворачивай её.")
    x, y, w, h = oblast_okna(hwnd)
    if w < 50 or h < 50:
        raise SystemExit(f"Окно «{zagolovok}» свёрнуто или крошечное ({w}x{h}).")
    return Glaza(x, y, w, h), zagolovok, (x, y, w, h)
