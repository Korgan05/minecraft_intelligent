# -*- coding: utf-8 -*-
"""
РУКИ: нажатия клавиш и движения мыши через системный ввод Windows (SendInput).

Только ctypes — ничего ставить не нужно. Для Minecraft это неотличимо от человека:
игра читает обычный ввод операционной системы, а не какой-то особый канал.

Клавиши посылаем ПО СКАН-КОДУ, а не по букве. Причина та же, что укусила нас в
записи показа: при русской раскладке буква «W» превращается в «ц», и игра получает
не то, что нужно. Скан-код — это номер физической клавиши, раскладке он не подвластен.
"""

import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32

INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0002, 0x0008
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010

# ДВЕ РАЗНЫЕ ТАБЛИЦЫ, и путать их нельзя:
#   SKAN — скан-коды физических клавиш, ими мы ПОСЫЛАЕМ нажатия через SendInput;
#   VK   — виртуальные коды, ими Windows отвечает на вопрос «зажата ли клавиша».
# Оба набора не зависят от раскладки: и там и там речь о физической клавише.
VK = {
    "W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
    "SPACE": 0x20, "SHIFT": 0x10, "CTRL": 0x11, "TAB": 0x09,
    "E": 0x45, "Q": 0x51, "T": 0x54, "ENTER": 0x0D, "ESC": 0x1B,
    "MYSH_LEVAYA": 0x01, "MYSH_PRAVAYA": 0x02,
}


def zazhata(imya):
    """Зажата ли клавиша ПРЯМО СЕЙЧАС."""
    return bool(user32.GetAsyncKeyState(VK[imya]) & 0x8000)


def nazhimalas(imya):
    """Зажата СЕЙЧАС или нажималась С ПРОШЛОЙ ПРОВЕРКИ.

    Обязательно для чтения игры человека: щелчок мышью длится миллисекунд
    пятьдесят, а мы опрашиваем раз в 200 мс — мгновенным срезом теряется почти
    каждый удар. Из-за этого запись подписывала попадания как «стоял» и «отходил».
    Младший бит как раз означает «нажималась между опросами» и обнуляется чтением.
    """
    s = user32.GetAsyncKeyState(VK[imya])
    return bool(s & 0x8000) or bool(s & 0x0001)


# Скан-коды физических клавиш (набор 1). Раскладка на них не влияет.
SKAN = {
    "W": 0x11, "A": 0x1E, "S": 0x1F, "D": 0x20,
    "SPACE": 0x39, "SHIFT": 0x2A, "CTRL": 0x1D, "TAB": 0x0F,
    "E": 0x12, "Q": 0x10, "T": 0x14, "ENTER": 0x1C, "ESC": 0x01,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "F3": 0x3D, "SLASH": 0x35,
}


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _VVOD(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _VVOD)]


def _poslat(*sobytiya):
    n = len(sobytiya)
    massiv = (INPUT * n)(*sobytiya)
    otpravleno = user32.SendInput(n, ctypes.byref(massiv), ctypes.sizeof(INPUT))
    return otpravleno == n


def _klavisha(skan, otpustit):
    flagi = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if otpustit else 0)
    return INPUT(type=INPUT_KEYBOARD,
                 u=_VVOD(ki=_KEYBDINPUT(wVk=0, wScan=skan, dwFlags=flagi,
                                        time=0, dwExtraInfo=None)))


def nazhat(imya):
    """Зажать клавишу и НЕ отпускать (ходьба удержанием, как у человека)."""
    return _poslat(_klavisha(SKAN[imya], False))


def otpustit(imya):
    return _poslat(_klavisha(SKAN[imya], True))


def otpustit_vse():
    """Снять все зажатые клавиши — обязательно при сбросе, иначе существо
    останется бежать вперёд в новом бою и мы не поймём, почему оно «тупит»."""
    return all(otpustit(k) for k in ("W", "A", "S", "D", "SPACE", "SHIFT", "CTRL", "E"))



def myshka(dx, dy):
    """ОТНОСИТЕЛЬНОЕ движение мыши — именно так игра вращает обзор.

    В Minecraft курсор захвачен, поэтому абсолютные координаты бесполезны:
    игра слушает приращения. Это и даёт существу ПЛАВНУЮ камеру вместо
    наших рывков по 15 градусов.
    """
    return _poslat(INPUT(type=INPUT_MOUSE,
                         u=_VVOD(mi=_MOUSEINPUT(dx=int(dx), dy=int(dy), mouseData=0,
                                                dwFlags=MOUSEEVENTF_MOVE, time=0,
                                                dwExtraInfo=None))))


def myshka_kursorom(dx, dy):
    """Запасной способ: двигаем сам курсор Windows.

    Нужен потому, что Minecraft 1.16 умеет читать мышь напрямую с устройства
    («ввод без обработки»), и тогда наши приращения через SendInput игра не видит:
    кнопки доходят, а повороты нет. Если сырой ввод в настройках выключен, игра
    следит за курсором, и этот способ срабатывает.
    """
    x, y = polozhenie_kursora()
    return bool(user32.SetCursorPos(int(x + dx), int(y + dy)))


def myshka_staraya(dx, dy):
    """Ещё один запасной: устаревший вызов mouse_event. Иногда проходит там,
    где SendInput отфильтрован как «искусственный»."""
    user32.mouse_event(MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
    return True


def udar():
    """Один щелчок левой кнопкой = один взмах."""
    return _poslat(
        INPUT(type=INPUT_MOUSE, u=_VVOD(mi=_MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, None))),
        INPUT(type=INPUT_MOUSE, u=_VVOD(mi=_MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, None))))



def polozhenie_kursora():
    t = wt.POINT()
    user32.GetCursorPos(ctypes.byref(t))
    return t.x, t.y


def okno_vperedi(hwnd):
    """Наше ли окно активно. Без фокуса ввод уйдёт не туда — например в браузер."""
    return user32.GetForegroundWindow() == hwnd


