#!/usr/bin/env python3
# Таблица — мини-Эксель на Python (Tkinter). Сборка 1.7.
# 52 функции пяти категорий. Подсказка функций после =, шаблон аргументов
# внутри скобок, вставка адресов кликом, Ctrl+H — скрыть формулы,
# Ctrl+S/Ctrl+O — сохранить/открыть .csv, F1 — справка.

import csv
import datetime
import math
import random
import re
import statistics
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BUILD = "1.8"
BG, PANEL, ACCENT, TEXT, MUTED, BORDER, HOVER = (
    "#f5f6fa", "#ffffff", "#4a69bd", "#2f3542", "#808e9b", "#dfe4ec", "#3b559e")
REF_HL = "#fff3bf"
ERR_FG = "#b3261e"

RANGE_RE = re.compile(r"([A-Za-z]+)(\d+)\s*:\s*([A-Za-z]+)(\d+)")
REF_RE = re.compile(r"[A-Za-z]+\d+")
IGNORE_KEYS = {"Up", "Down", "Left", "Right", "Return", "Tab", "Escape",
               "ISO_Left_Tab", "Shift_L", "Shift_R", "Control_L",
               "Control_R", "Alt_L", "Alt_R", "Home", "End", "Prior",
               "Next", "Insert", "Caps_Lock", "Num_Lock", "Menu",
               "KP_Up", "KP_Down", "KP_Left", "KP_Right", "KP_Enter",
               "KP_Home", "KP_End", "F1"}


# ---------- значения формул ----------

def col_letters(idx):
    s = ""
    idx += 1
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def num(value):
    s = str(value).strip()
    if s == "":
        return 0.0
    try:
        return float(s.replace(",", "."))
    except ValueError:
        raise ValueError(f"не число: «{s}»")


def fmt_num(x):
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e12:
            return str(int(x))
        return f"{x:.8f}".rstrip("0").rstrip(".")
    return str(x)


def to_display(v):
    if isinstance(v, bool):
        return "ИСТИНА" if v else "ЛОЖЬ"
    if isinstance(v, float):
        return fmt_num(v)
    return str(v)


def to_num(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, float):
        return v
    return num(v)


def truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        return v != 0
    if isinstance(v, str):
        s = v.strip().upper()
        if s in ("ИСТИНА", "TRUE"):
            return True
        if s in ("ЛОЖЬ", "FALSE"):
            return False
        raise ValueError(f"не логическое значение: «{v}»")
    raise ValueError("не логическое значение")


def compare(op, a, b):
    if isinstance(a, (float, bool)) and isinstance(b, (float, bool)):
        ka, kb = to_num(a), to_num(b)
    elif isinstance(a, str) and isinstance(b, str):
        ka, kb = a.casefold(), b.casefold()
    else:
        ka = 0 if isinstance(a, (float, bool)) else 1
        kb = 0 if isinstance(b, (float, bool)) else 1
    if op == "=":
        return ka == kb
    if op == "<>":
        return ka != kb
    if op == "<":
        return ka < kb
    if op == ">":
        return ka > kb
    if op == "<=":
        return ka <= kb
    if op == ">=":
        return ka >= kb
    raise ValueError(f"неизвестное сравнение: {op}")


def ref_index(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", str(ref).strip().upper())
    if not m:
        raise ValueError(f"ссылка: {ref} (буквы — латинские)")
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return int(m.group(2)) - 1, col - 1


def split_formula(cell):
    s = str(cell).strip()
    if s.startswith("="):
        return "", s
    return s, None


# ---------- библиотека функций ----------

def _flatten(args):
    out = []
    for a in args:
        if isinstance(a, list):
            out.extend(a)
        else:
            out.append(a)
    return out


def _collect_nums(args):
    out = []
    for a in args:
        if isinstance(a, list):
            out.extend(v for v in a if isinstance(v, float))
        elif isinstance(a, bool):
            out.append(1.0 if a else 0.0)
        elif isinstance(a, float):
            out.append(a)
        else:
            out.append(to_num(a))
    return out


def _scalar(args, idx):
    if idx >= len(args):
        raise ValueError(f"нужен аргумент №{idx + 1}")
    v = args[idx]
    if isinstance(v, list):
        v = v[0] if v else ""
    return v


def _scalar_num(args, idx):
    return to_num(_scalar(args, idx))


def _nonempty(args):
    vals = []
    for a in args:
        if isinstance(a, list):
            vals.extend(v for v in a if v != "")
        else:
            vals.append(a)
    return vals


def _round_impl(x, d, mode):
    m = 10.0 ** d
    y = abs(x) * m
    if mode == "half":
        y = math.floor(y + 0.5)
    elif mode == "up":
        y = math.ceil(y - 1e-9)
    else:
        y = math.floor(y + 1e-9)
    y = y / m
    return y if x >= 0 else -y


def _date_parts(v):
    s = to_display(v).strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if not m:
        raise ValueError("нужна дата вида ДД.ММ.ГГГГ")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def f_sum(args):
    return float(sum(_collect_nums(args)))


def f_product(args):
    p = 1.0
    for v in _collect_nums(args):
        p *= v
    return p


def f_abs(args):
    return abs(_scalar_num(args, 0))


def f_power(args):
    x, y = _scalar_num(args, 0), _scalar_num(args, 1)
    try:
        r = x ** y
    except Exception:
        raise ValueError("не удаётся возвести в степень")
    if isinstance(r, complex):
        raise ValueError("отрицательное число в дробной степени")
    return float(r)


def f_sqrt(args):
    x = _scalar_num(args, 0)
    if x < 0:
        raise ValueError("корень из отрицательного числа")
    return math.sqrt(x)


def f_int(args):
    return float(math.floor(_scalar_num(args, 0)))


def f_round(args):
    d = int(_scalar_num(args, 1)) if len(args) > 1 else 0
    return _round_impl(_scalar_num(args, 0), d, "half")


def f_roundup(args):
    d = int(_scalar_num(args, 1)) if len(args) > 1 else 0
    return _round_impl(_scalar_num(args, 0), d, "up")


def f_rounddown(args):
    d = int(_scalar_num(args, 1)) if len(args) > 1 else 0
    return _round_impl(_scalar_num(args, 0), d, "down")


def f_ceiling(args):
    x, sig = _scalar_num(args, 0), _scalar_num(args, 1)
    if sig <= 0:
        raise ValueError("кратное должно быть больше нуля")
    return math.ceil(x / sig - 1e-9) * sig


def f_floor(args):
    x, sig = _scalar_num(args, 0), _scalar_num(args, 1)
    if sig <= 0:
        raise ValueError("кратное должно быть больше нуля")
    return math.floor(x / sig + 1e-9) * sig


def f_mod(args):
    a, b = _scalar_num(args, 0), _scalar_num(args, 1)
    if b == 0:
        raise ValueError("деление на ноль")
    return a - b * math.floor(a / b)


def f_sign(args):
    x = _scalar_num(args, 0)
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def f_pi(args):
    return math.pi


def f_rand(args):
    return random.random()


def f_randbetween(args):
    a, b = _scalar_num(args, 0), _scalar_num(args, 1)
    if a > b:
        raise ValueError("первое число должно быть не больше второго")
    return float(random.randint(math.ceil(a), math.floor(b)))


def f_average(args):
    nums = _collect_nums(args)
    if not nums:
        raise ValueError("нет чисел для среднего")
    return sum(nums) / len(nums)


def f_min(args):
    nums = _collect_nums(args)
    if not nums:
        raise ValueError("нет чисел")
    return min(nums)


def f_max(args):
    nums = _collect_nums(args)
    if not nums:
        raise ValueError("нет чисел")
    return max(nums)


def f_count(args):
    n = 0
    for a in args:
        if isinstance(a, list):
            n += sum(1 for v in a if isinstance(v, (float, bool)))
        elif isinstance(a, (float, bool)):
            n += 1
    return float(n)


def f_counta(args):
    n = 0
    for a in args:
        if isinstance(a, list):
            n += sum(1 for v in a if v != "")
        elif a != "":
            n += 1
    return float(n)


def f_median(args):
    nums = _collect_nums(args)
    if not nums:
        raise ValueError("нет чисел")
    return statistics.median(nums)


def f_stdev(args):
    nums = _collect_nums(args)
    if len(nums) < 2:
        raise ValueError("нужно хотя бы два числа")
    return statistics.stdev(nums)


def f_stdevp(args):
    nums = _collect_nums(args)
    if not nums:
        raise ValueError("нет чисел")
    return statistics.pstdev(nums)


def f_var(args):
    nums = _collect_nums(args)
    if len(nums) < 2:
        raise ValueError("нужно хотя бы два числа")
    return statistics.variance(nums)


def f_varp(args):
    nums = _collect_nums(args)
    if not nums:
        raise ValueError("нет чисел")
    return statistics.pvariance(nums)


def f_large(args):
    nums = _collect_nums(args[:1])
    k = int(_scalar_num(args, 1))
    if k < 1 or k > len(nums):
        raise ValueError("k вне диапазона")
    return sorted(nums, reverse=True)[k - 1]


def f_small(args):
    nums = _collect_nums(args[:1])
    k = int(_scalar_num(args, 1))
    if k < 1 or k > len(nums):
        raise ValueError("k вне диапазона")
    return sorted(nums)[k - 1]


def f_if(args):
    cond = truthy(_scalar(args, 0))
    if len(args) >= 3:
        return args[1] if cond else args[2]
    if cond:
        return args[1]
    return False


def f_and(args):
    vals = _nonempty(args)
    if not vals:
        raise ValueError("нет аргументов")
    return all(truthy(v) for v in vals)


def f_or(args):
    vals = _nonempty(args)
    if not vals:
        raise ValueError("нет аргументов")
    return any(truthy(v) for v in vals)


def f_not(args):
    return not truthy(_scalar(args, 0))


def f_true(args):
    return True


def f_false(args):
    return False


def f_isnumber(args):
    return isinstance(_scalar(args, 0), float)


def f_istext(args):
    v = _scalar(args, 0)
    return isinstance(v, str) and v != ""


def f_isblank(args):
    return _scalar(args, 0) == ""


def f_len(args):
    return float(len(to_display(_scalar(args, 0))))


def f_left(args):
    s = to_display(_scalar(args, 0))
    n = int(_scalar_num(args, 1)) if len(args) > 1 else 1
    if n < 0:
        raise ValueError("количество символов не может быть отрицательным")
    return s[:n]


def f_right(args):
    s = to_display(_scalar(args, 0))
    n = int(_scalar_num(args, 1)) if len(args) > 1 else 1
    if n < 0:
        raise ValueError("количество символов не может быть отрицательным")
    return s[-n:] if n > 0 else ""


def f_mid(args):
    s = to_display(_scalar(args, 0))
    start = int(_scalar_num(args, 1))
    n = int(_scalar_num(args, 2))
    if start < 1:
        raise ValueError("позиция начинается с 1")
    if n < 0:
        raise ValueError("длина не может быть отрицательной")
    return s[start - 1:start - 1 + n]


def f_upper(args):
    return to_display(_scalar(args, 0)).upper()


def f_lower(args):
    return to_display(_scalar(args, 0)).lower()


def f_concat(args):
    return "".join(to_display(v) for v in _flatten(args))


def f_trim(args):
    return " ".join(to_display(_scalar(args, 0)).split())


def f_replace(args):
    old = to_display(_scalar(args, 0))
    start = int(_scalar_num(args, 1))
    n = int(_scalar_num(args, 2))
    new = to_display(_scalar(args, 3))
    if start < 1:
        raise ValueError("позиция начинается с 1")
    if n < 0:
        raise ValueError("длина не может быть отрицательной")
    return old[:start - 1] + new + old[start - 1 + n:]


def f_find(args):
    needle = to_display(_scalar(args, 0))
    hay = to_display(_scalar(args, 1))
    start = int(_scalar_num(args, 2)) if len(args) > 2 else 1
    if start < 1:
        raise ValueError("позиция начинается с 1")
    i = hay.find(needle, start - 1)
    if i < 0:
        raise ValueError("подстрока не найдена")
    return float(i + 1)


def f_rept(args):
    s = to_display(_scalar(args, 0))
    n = int(_scalar_num(args, 1))
    if n < 0:
        raise ValueError("количество не может быть отрицательным")
    if n * max(1, len(s)) > 32767:
        raise ValueError("слишком длинный результат")
    return s * n


def f_today(args):
    d = datetime.date.today()
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def f_year(args):
    return float(_date_parts(_scalar(args, 0))[2])


def f_month(args):
    return float(_date_parts(_scalar(args, 0))[1])


def f_day(args):
    return float(_date_parts(_scalar(args, 0))[0])


# --- каталог функций: (имя, синонимы, описание, категория) ---

FUNC_INFO = [
    ("СУММ", ("SUM",), "сумма чисел", "математика"),
    ("ПРОИЗВ", ("PRODUCT",), "произведение чисел", "математика"),
    ("ABS", (), "модуль числа", "математика"),
    ("СТЕПЕНЬ", ("POWER",), "возведение в степень", "математика"),
    ("КОРЕНЬ", ("SQRT",), "квадратный корень", "математика"),
    ("ЦЕЛОЕ", ("INT",), "целая часть числа", "математика"),
    ("ОКРУГЛ", ("ROUND",), "округление до знаков", "математика"),
    ("ОКРУГЛВВЕРХ", ("ROUNDUP",), "округление вверх", "математика"),
    ("ОКРУГЛВНИЗ", ("ROUNDDOWN",), "округление вниз", "математика"),
    ("ОКРВВЕРХ", ("CEILING",), "округление вверх до кратного", "математика"),
    ("ОКРВНИЗ", ("FLOOR",), "округление вниз до кратного", "математика"),
    ("ОСТАТ", ("MOD",), "остаток от деления", "математика"),
    ("ЗНАК", ("SIGN",), "знак числа", "математика"),
    ("ПИ", ("PI",), "число Пи", "математика"),
    ("СЛЧИС", ("RAND",), "случайное число от 0 до 1", "математика"),
    ("СЛУЧМЕЖДУ", ("RANDBETWEEN",), "случайное целое между двумя",
     "математика"),
    ("СРЗНАЧ", ("AVERAGE",), "среднее арифметическое", "статистика"),
    ("МИН", ("MIN",), "наименьшее значение", "статистика"),
    ("МАКС", ("MAX",), "наибольшее значение", "статистика"),
    ("СЧЁТ", ("COUNT",), "сколько чисел в диапазоне", "статистика"),
    ("СЧЁТЗ", ("COUNTA",), "сколько непустых ячеек", "статистика"),
    ("МЕДИАНА", ("MEDIAN",), "медиана чисел", "статистика"),
    ("СТАНДОТКЛОН", ("STDEV",), "стандартное отклонение (выборка)",
     "статистика"),
    ("СТАНДОТКЛОНП", ("STDEVP",), "стандартное отклонение (общая)",
     "статистика"),
    ("ДИСП", ("VAR",), "дисперсия (выборка)", "статистика"),
    ("ДИСПР", ("VARP",), "дисперсия (общая)", "статистика"),
    ("НАИБОЛЬШИЙ", ("LARGE",), "k-е наибольшее значение", "статистика"),
    ("НАИМЕНЬШИЙ", ("SMALL",), "k-е наименьшее значение", "статистика"),
    ("ЕСЛИ", ("IF",), "условие: ЕСЛИ(условие; то; иначе)", "логика"),
    ("И", ("AND",), "истина, если все условия истинны", "логика"),
    ("ИЛИ", ("OR",), "истина, если хоть одно истинно", "логика"),
    ("НЕ", ("NOT",), "меняет истину на ложь и наоборот", "логика"),
    ("ИСТИНА", ("TRUE",), "логическое значение истина", "логика"),
    ("ЛОЖЬ", ("FALSE",), "логическое значение ложь", "логика"),
    ("ЕЧИСЛО", ("ISNUMBER",), "истина, если число", "логика"),
    ("ЕТЕКСТ", ("ISTEXT",), "истина, если текст", "логика"),
    ("ЕПУСТО", ("ISBLANK",), "истина, если ячейка пуста", "логика"),
    ("ДЛСТР", ("LEN",), "длина текста", "текст"),
    ("ЛЕВСИМВ", ("LEFT",), "первые символы текста", "текст"),
    ("ПРАВСИМВ", ("RIGHT",), "последние символы текста", "текст"),
    ("ПСТР", ("MID",), "часть текста с позиции", "текст"),
    ("ПРОПИСН", ("UPPER",), "текст прописными", "текст"),
    ("СТРОЧН", ("LOWER",), "текст строчными", "текст"),
    ("СЦЕПИТЬ", ("CONCATENATE",), "склеивает тексты", "текст"),
    ("СЖПРОБЕЛЫ", ("TRIM",), "убирает лишние пробелы", "текст"),
    ("ЗАМЕНИТЬ", ("REPLACE",), "заменяет часть текста", "текст"),
    ("НАЙТИ", ("FIND",), "ищет подстроку, возвращает позицию", "текст"),
    ("ПОВТОР", ("REPT",), "повторяет текст", "текст"),
    ("СЕГОДНЯ", ("TODAY",), "сегодняшняя дата", "дата и время"),
    ("ГОД", ("YEAR",), "год из даты ДД.ММ.ГГГГ", "дата и время"),
    ("МЕСЯЦ", ("MONTH",), "месяц из даты ДД.ММ.ГГГГ", "дата и время"),
    ("ДЕНЬ", ("DAY",), "день из даты ДД.ММ.ГГГГ", "дата и время"),
]

IMPL = {
    "СУММ": f_sum, "ПРОИЗВ": f_product, "ABS": f_abs, "СТЕПЕНЬ": f_power,
    "КОРЕНЬ": f_sqrt, "ЦЕЛОЕ": f_int, "ОКРУГЛ": f_round,
    "ОКРУГЛВВЕРХ": f_roundup, "ОКРУГЛВНИЗ": f_rounddown,
    "ОКРВВЕРХ": f_ceiling, "ОКРВНИЗ": f_floor, "ОСТАТ": f_mod,
    "ЗНАК": f_sign, "ПИ": f_pi, "СЛЧИС": f_rand,
    "СЛУЧМЕЖДУ": f_randbetween,
    "СРЗНАЧ": f_average, "МИН": f_min, "МАКС": f_max, "СЧЁТ": f_count,
    "СЧЁТЗ": f_counta, "МЕДИАНА": f_median, "СТАНДОТКЛОН": f_stdev,
    "СТАНДОТКЛОНП": f_stdevp, "ДИСП": f_var, "ДИСПР": f_varp,
    "НАИБОЛЬШИЙ": f_large, "НАИМЕНЬШИЙ": f_small,
    "ЕСЛИ": f_if, "И": f_and, "ИЛИ": f_or, "НЕ": f_not,
    "ИСТИНА": f_true, "ЛОЖЬ": f_false, "ЕЧИСЛО": f_isnumber,
    "ЕТЕКСТ": f_istext, "ЕПУСТО": f_isblank,
    "ДЛСТР": f_len, "ЛЕВСИМВ": f_left, "ПРАВСИМВ": f_right,
    "ПСТР": f_mid, "ПРОПИСН": f_upper, "СТРОЧН": f_lower,
    "СЦЕПИТЬ": f_concat, "СЖПРОБЕЛЫ": f_trim, "ЗАМЕНИТЬ": f_replace,
    "НАЙТИ": f_find, "ПОВТОР": f_rept,
    "СЕГОДНЯ": f_today, "ГОД": f_year, "МЕСЯЦ": f_month, "ДЕНЬ": f_day,
}

FUNC_IMPL = {}
for _main, _syns, _desc, _cat in FUNC_INFO:
    FUNC_IMPL[_main] = IMPL[_main]
    for _s in _syns:
        FUNC_IMPL[_s] = IMPL[_main]

ARG_HINTS = {
    "СУММ": ["число; число; …"], "ПРОИЗВ": ["число; число; …"],
    "ABS": ["число"], "СТЕПЕНЬ": ["число", "степень"],
    "КОРЕНЬ": ["число"], "ЦЕЛОЕ": ["число"],
    "ОКРУГЛ": ["число", "знаков"], "ОКРУГЛВВЕРХ": ["число", "знаков"],
    "ОКРУГЛВНИЗ": ["число", "знаков"], "ОКРВВЕРХ": ["число", "кратное"],
    "ОКРВНИЗ": ["число", "кратное"], "ОСТАТ": ["число", "делитель"],
    "ЗНАК": ["число"], "ПИ": [], "СЛЧИС": [],
    "СЛУЧМЕЖДУ": ["от", "до"],
    "СРЗНАЧ": ["число; число; …"], "МИН": ["число; число; …"],
    "МАКС": ["число; число; …"], "СЧЁТ": ["значение; …"],
    "СЧЁТЗ": ["значение; …"], "МЕДИАНА": ["число; …"],
    "СТАНДОТКЛОН": ["число; …"], "СТАНДОТКЛОНП": ["число; …"],
    "ДИСП": ["число; …"], "ДИСПР": ["число; …"],
    "НАИБОЛЬШИЙ": ["диапазон", "k"], "НАИМЕНЬШИЙ": ["диапазон", "k"],
    "ЕСЛИ": ["условие", "если_истина", "если_ложь"],
    "И": ["условие; …"], "ИЛИ": ["условие; …"], "НЕ": ["значение"],
    "ИСТИНА": [], "ЛОЖЬ": [],
    "ЕЧИСЛО": ["значение"], "ЕТЕКСТ": ["значение"], "ЕПУСТО": ["ячейка"],
    "ДЛСТР": ["текст"], "ЛЕВСИМВ": ["текст", "сколько"],
    "ПРАВСИМВ": ["текст", "сколько"],
    "ПСТР": ["текст", "с_какого", "сколько"],
    "ПРОПИСН": ["текст"], "СТРОЧН": ["текст"],
    "СЦЕПИТЬ": ["текст; …"], "СЖПРОБЕЛЫ": ["текст"],
    "ЗАМЕНИТЬ": ["текст", "с_какого", "сколько", "новый"],
    "НАЙТИ": ["что_искать", "где", "с_какого"],
    "ПОВТОР": ["текст", "сколько"],
    "СЕГОДНЯ": [], "ГОД": ["дата"], "МЕСЯЦ": ["дата"], "ДЕНЬ": ["дата"],
}

MAIN_NAME = {}
FUNC_DESC_BY = {}
for _f in FUNC_INFO:
    MAIN_NAME[_f[0]] = _f[0]
    FUNC_DESC_BY[_f[0]] = _f[2]
    for _s in _f[1]:
        MAIN_NAME[_s] = _f[0]


def eval_formula(expr, get_raw, resolving=None):
    if resolving is None:
        resolving = set()

    def value_at(r, c):
        key = (r, c)
        if key in resolving:
            raise ValueError("циклическая ссылка")
        raw = str(get_raw(r, c)).strip()
        v, f = split_formula(raw)
        if f is None:
            if v == "":
                return ""
            try:
                return float(v.replace(",", "."))
            except ValueError:
                return v
        resolving.add(key)
        try:
            return eval_formula(f, get_raw, resolving)
        finally:
            resolving.discard(key)

    s = str(expr).strip()
    while s.startswith("="):
        s = s[1:].strip()
    if not s:
        raise ValueError("пустая формула")
    need = s.count("(") - s.count(")")
    if need > 0:
        s = s + ")" * need

    tokens = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            j = s.find('"', i + 1)
            if j == -1:
                raise ValueError("незакрытая кавычка в тексте")
            tokens.append(("str", s[i + 1:j]))
            i = j + 1
            continue
        if ch.isdigit():
            m = re.match(r"\d+(?:[.,]\d+)?", s[i:])
            tokens.append(("num", float(m.group(0).replace(",", "."))))
            i += len(m.group(0))
            continue
        if re.match(r"[A-Za-zА-Яа-яЁё]", ch):
            m = re.match(r"[A-Za-zА-Яа-яЁё]+\d*", s[i:])
            body = re.match(r"([A-Za-zА-Яа-яЁё]+)(\d*)", m.group(0))
            if body.group(2):
                tokens.append(("ref", (body.group(1) + body.group(2)).upper()))
            else:
                tokens.append(("name", body.group(1)))
            i += len(m.group(0))
            continue
        if ch in "<>=":
            two = s[i:i + 2]
            if two in ("<=", ">=", "<>"):
                tokens.append(("op", two))
                i += 2
                continue
            tokens.append(("op", ch))
            i += 1
            continue
        if ch in "+-*/():,;&^":
            tokens.append(("op", ch))
            i += 1
            continue
        raise ValueError(f"непонятный символ: «{ch}»")

    pos = 0

    def peek(k=0):
        j = pos + k
        return tokens[j] if j < len(tokens) else None

    def eat():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def expect(op):
        tok = peek()
        if tok is None or tok[0] != "op" or tok[1] != op:
            raise ValueError(f"ожидался знак «{op}»")
        return eat()

    def parse_cmp():
        val = parse_concat()
        while (peek() and peek()[0] == "op"
               and peek()[1] in ("<", ">", "<=", ">=", "<>")):
            tok = eat()
            rhs = parse_concat()
            val = compare(tok[1], val, rhs)
        return val

    def parse_concat():
        val = parse_add()
        while peek() and peek()[0] == "op" and peek()[1] == "&":
            eat()
            rhs = parse_add()
            val = to_display(val) + to_display(rhs)
        return val

    def parse_add():
        val = parse_mul()
        while True:
            tok = peek()
            if tok and tok[0] == "op" and tok[1] in "+-":
                eat()
                rhs = parse_mul()
                if tok[1] == "+":
                    val = to_num(val) + to_num(rhs)
                else:
                    val = to_num(val) - to_num(rhs)
            else:
                return val

    def parse_mul():
        val = parse_pow()
        while True:
            tok = peek()
            if tok and tok[0] == "op" and tok[1] in "*/":
                eat()
                rhs = parse_pow()
                x, y = to_num(val), to_num(rhs)
                if tok[1] == "*":
                    val = x * y
                else:
                    if y == 0:
                        raise ValueError("деление на ноль")
                    val = x / y
            else:
                return val

    def parse_pow():
        val = parse_unary()
        if peek() and peek()[0] == "op" and peek()[1] == "^":
            eat()
            exp = parse_pow()
            x, y = to_num(val), to_num(exp)
            try:
                r = x ** y
            except Exception:
                raise ValueError("не удаётся возвести в степень")
            if isinstance(r, complex):
                raise ValueError("отрицательное число в дробной степени")
            return float(r)
        return val

    def parse_unary():
        tok = peek()
        if tok and tok[0] == "op":
            if tok[1] == "-":
                eat()
                return -to_num(parse_unary())
            if tok[1] == "+":
                eat()
                return parse_unary()
        return parse_primary()

    def parse_primary():
        tok = peek()
        if tok is None:
            raise ValueError("неожиданный конец формулы")
        if tok[0] == "op":
            if tok[1] == "(":
                eat()
                v = parse_cmp()
                expect(")")
                return v
            raise ValueError(f"неожиданный знак «{tok[1]}»")
        if tok[0] == "num":
            eat()
            return tok[1]
        if tok[0] == "str":
            eat()
            return tok[1]
        if tok[0] == "ref":
            eat()
            return value_at(*ref_index(tok[1]))
        if tok[0] == "name":
            fname = tok[1]
            eat()
            up = fname.upper()
            nxt = peek()
            no_paren = not (nxt and nxt[0] == "op" and nxt[1] == "(")
            if up in ("ИСТИНА", "TRUE") and no_paren:
                return True
            if up in ("ЛОЖЬ", "FALSE") and no_paren:
                return False
            expect("(")
            args = []
            nxt = peek()
            if nxt and not (nxt[0] == "op" and nxt[1] == ")"):
                args.append(parse_arg())
                while (peek() and peek()[0] == "op"
                       and peek()[1] in (",", ";")):
                    eat()
                    args.append(parse_arg())
            expect(")")
            if up not in FUNC_IMPL:
                raise ValueError(f"неизвестная функция: {fname}")
            try:
                return FUNC_IMPL[up](args)
            except ValueError:
                raise
            except Exception as ex:
                raise ValueError(str(ex))
        raise ValueError(f"непонятное: {tok[1]}")

    def parse_arg():
        t0 = peek()
        if (t0 and t0[0] == "ref" and peek(1)
                and peek(1)[0] == "op" and peek(1)[1] == ":"):
            eat()
            eat()
            t2 = peek()
            if not (t2 and t2[0] == "ref"):
                raise ValueError("в диапазоне должно быть два адреса ячеек")
            eat()
            r1, c1 = ref_index(t0[1])
            r2, c2 = ref_index(t2[1])
            r1, r2 = min(r1, r2), max(r1, r2)
            c1, c2 = min(c1, c2), max(c1, c2)
            return [value_at(r, c)
                    for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
        return parse_cmp()

    return parse_cmp()


def compute_cell(raw, get_raw):
    s = str(raw).strip()
    if not s:
        return ""
    v, f = split_formula(s)
    if f is None:
        return v
    try:
        return to_display(eval_formula(f, get_raw))
    except Exception as ex:
        return f"#ОШИБКА: {ex}"


SELF_TESTS = [
    ("=СУММ(B1+C1)", {(0, 1): "4", (0, 2): "5"}, "9"),
    ("=СУММ(B1:C1)", {(0, 1): "4", (0, 2): "5"}, "9"),
    ("=B1*2", {(0, 1): "4"}, "8"),
    ("=СРЗНАЧ(B1:C1)", {(0, 1): "4", (0, 2): "5"}, "4.5"),
    ("=(B1+C1)/2", {(0, 1): "4", (0, 2): "5"}, "4.5"),
    ("=-B1+2", {(0, 1): "4"}, "-2"),
    ("=МИН(A1:C1)", {(0, 0): "7", (0, 1): "3", (0, 2): "9"}, "3"),
    ("=МАКС(A1:C1)", {(0, 0): "7", (0, 1): "3", (0, 2): "9"}, "9"),
    ("=A1+1", {(0, 0): "=A1+1"}, None),
    ("=ЕСЛИ(B1>3;1;2)", {(0, 1): "4"}, "1"),
    ("=ЕСЛИ(B1>5;\"да\";\"нет\")", {(0, 1): "4"}, "нет"),
    ("=ОКРУГЛ(2,5;0)", {}, "3"),
    ("=ОКРУГЛ(-2,5;0)", {}, "-3"),
    ("=КОРЕНЬ(9)", {}, "3"),
    ("=СТЕПЕНЬ(2;10)", {}, "1024"),
    ("=A1&B1", {(0, 0): "3", (0, 1): "4"}, "34"),
    ("=СЦЕПИТЬ(\"а\";1)", {}, "а1"),
    ("=ДЛСТР(\"привет\")", {}, "6"),
    ("=ЛЕВСИМВ(\"привет\";3)", {}, "при"),
    ("=ПСТР(\"привет\";2;3)", {}, "рив"),
    ("=И(1<2;3>2)", {}, "ИСТИНА"),
    ("=ИЛИ(1>2;3>2)", {}, "ИСТИНА"),
    ("=НЕ(1>2)", {}, "ИСТИНА"),
    ("=1<2", {}, "ИСТИНА"),
    ("=СРЗНАЧ(A1:C1)", {(0, 0): "1", (0, 1): "текст", (0, 2): "3"}, "2"),
    ("=СЧЁТ(A1:C1)", {(0, 0): "1", (0, 1): "текст", (0, 2): "3"}, "2"),
    ("=СЧЁТЗ(A1:C1)", {(0, 0): "1", (0, 1): "текст", (0, 2): "3"}, "3"),
    ("=ГОД(\"05.11.2026\")", {}, "2026"),
    ("=МЕСЯЦ(\"05.11.2026\")", {}, "11"),
    ("=НАИБОЛЬШИЙ(A1:C1;1)", {(0, 0): "7", (0, 1): "3", (0, 2): "9"}, "9"),
    ("=ОСТАТ(10;3)", {}, "1"),
    ("=ЕПУСТО(A1)", {}, "ИСТИНА"),
    ("=ПРОИЗВ(A1:B1)", {(0, 0): "2", (0, 1): "5"}, "10"),
]


def self_test():
    errs = []
    for expr, cells, want in SELF_TESTS:
        try:
            got = compute_cell(
                expr, lambda r, c, cells=cells: cells.get((r, c), ""))
        except Exception as ex:
            got = f"#ОШИБКА: {ex}"
        if want is None:
            if not got.startswith("#ОШИБКА"):
                errs.append(f"{expr} → {got}, ожидалась ошибка")
        elif got != want:
            errs.append(f"{expr} → {got}, ожидалось {want}")
    return errs


class SheetApp:
    DEF_ROWS, DEF_COLS = 25, 12
    MAX_ROWS, MAX_COLS = 100, 26

    def __init__(self, root):
        self.root = root
        root.title("Таблица — без имени")
        root.geometry("1080x680")
        root.minsize(760, 420)
        root.configure(bg=BG)
        self.rows, self.cols = self.DEF_ROWS, self.DEF_COLS
        self.CELLS = {}
        self.display = {}
        self.entries = {}
        self.selected = (0, 0)
        self.dirty = False
        self.file_path = None
        self.show_formulas = True
        self._fpop = None
        self._fpop_lb = None
        self._fpop_items = None
        self._fpop_accept = None
        self._ahpop = None
        self._ref_click_pending = False
        self._edit_in_fbar = False
        self._build_fbar()
        self._build_grid()
        self._build_status()
        self._bind()
        self.recalc()

    def _build_fbar(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill=tk.X, padx=10, pady=(8, 2))
        self.fbar_addr = tk.Label(bar, text="A1", width=8, bg=PANEL,
                                  fg=ACCENT, anchor="w",
                                  font=("Courier New", 10, "bold"),
                                  relief=tk.FLAT, padx=6)
        self.fbar_addr.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4), ipady=3)
        tk.Label(bar, text="fx", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10, "italic")).pack(
            side=tk.LEFT, padx=(0, 4))
        self.fbar_entry = tk.Entry(bar, font=("Courier New", 10),
                                   relief=tk.FLAT, highlightthickness=1,
                                   highlightbackground=BORDER,
                                   highlightcolor=ACCENT)
        self.fbar_entry.pack(side=tk.LEFT, fill=tk.X, expand=True,
                             pady=2, ipady=2)
        self.btn_show_formulas = tk.Button(
            bar, text="👁 Формулы", command=self.toggle_show_formulas,
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0,
            cursor="hand2", padx=10, pady=4, bg=ACCENT, fg="#ffffff",
            activebackground=HOVER, activeforeground="#ffffff")
        self.btn_show_formulas.pack(side=tk.LEFT, padx=(6, 0))
        self._update_formula_button()
        self.fbar_entry.bind("<FocusIn>", self.on_fbar_focus_in)
        self.fbar_entry.bind("<KeyRelease>", self.on_fbar_key)
        self.fbar_entry.bind("<Escape>", self.on_fbar_escape)
        for seq in ("<Return>", "<Down>", "<Up>", "<Tab>"):
            self.fbar_entry.bind(seq, self.on_fbar_navkey)

    def _build_grid(self):
        outer = tk.Frame(self.root, bg=BORDER)
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 2))
        self.grid_frame = tk.Frame(outer, bg=PANEL)
        self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self._make_grid_widgets()

    def _make_grid_widgets(self):
        self._fpop_hide()
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.entries.clear()
        tk.Label(self.grid_frame, text="", bg=ACCENT, width=4,
                 relief=tk.FLAT).grid(row=0, column=0, sticky="nsew")
        for j in range(self.cols):
            tk.Label(self.grid_frame, text=col_letters(j), bg=ACCENT,
                     fg="#ffffff", font=("Segoe UI", 9, "bold"),
                     width=12, relief=tk.FLAT).grid(
                row=0, column=j + 1, sticky="nsew", padx=1, pady=(0, 1))
        for i in range(self.rows):
            tk.Label(self.grid_frame, text=str(i + 1), bg=ACCENT,
                     fg="#ffffff", font=("Segoe UI", 9, "bold"),
                     width=4, relief=tk.FLAT).grid(
                row=i + 1, column=0, sticky="nsew", padx=(0, 1))
            for j in range(self.cols):
                e = tk.Entry(self.grid_frame, width=12,
                             font=("Courier New", 10), justify="left",
                             relief=tk.FLAT, highlightthickness=1,
                             highlightbackground=BORDER,
                             highlightcolor=ACCENT, bg="#ffffff", fg=TEXT)
                e.grid(row=i + 1, column=j + 1, padx=1, pady=1, sticky="nsew")
                e.bind("<FocusIn>",
                       lambda ev, r=i, c=j: self.on_focus_in(r, c))
                e.bind("<KeyRelease>",
                       lambda ev, r=i, c=j: self.on_key(r, c, ev))
                e.bind("<Return>", lambda ev, r=i, c=j: self.on_enter(r, c))
                e.bind("<Tab>", lambda ev, r=i, c=j: self.on_tab(r, c))
                e.bind("<ISO_Left_Tab>",
                       lambda ev, r=i, c=j: self.on_tab(r, c))
                e.bind("<Escape>",
                       lambda ev, r=i, c=j: self.on_escape(r, c))
                e.bind("<Up>",
                       lambda ev, r=i, c=j: self.on_arrow(r, c, -1, 0, "Up"))
                e.bind("<Down>",
                       lambda ev, r=i, c=j: self.on_arrow(r, c, 1, 0, "Down"))
                e.bind("<Left>",
                       lambda ev, r=i, c=j: self.on_arrow(r, c, 0, -1,
                                                          "Left"))
                e.bind("<Right>",
                       lambda ev, r=i, c=j: self.on_arrow(r, c, 0, 1,
                                                          "Right"))
                e.bind("<Delete>",
                       lambda ev, r=i, c=j: self.on_delete(r, c))
                e.bind("<Button-3>", self.on_right_click)
                self.entries[(i, j)] = e

    def _build_status(self):
        self.status = tk.Label(self.root, anchor="w", bg=BG, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(fill=tk.X, padx=10, pady=(2, 8))

    def _bind(self):
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-h>", lambda e: self.toggle_show_formulas())
        self.root.bind("<F1>", lambda e: self.help_dialog())

    def _get_raw(self, r, c):
        return self.CELLS.get((r, c), "")

    def _edit_content(self, r, c):
        raw = self._get_raw(r, c)
        if not self.show_formulas and raw.strip().startswith("="):
            return self.display.get((r, c), "")
        return raw

    def recalc(self):
        for (r, c) in list(self.entries):
            val = compute_cell(self._get_raw(r, c), self._get_raw)
            self.display[(r, c)] = val
            e = self.entries[(r, c)]
            e.configure(fg=ERR_FG if val.startswith("#ОШИБКА") else TEXT)
            if (r, c) == self.selected and self.dirty:
                continue
            if e.get() != val:
                e.delete(0, tk.END)
                e.insert(0, val)
        self.fbar_sync()

    def fbar_sync(self):
        r, c = self.selected
        addr = f"{col_letters(c)}{r + 1}"
        if self.fbar_addr.cget("text") != addr:
            self.fbar_addr.config(text=addr)
        if self.dirty:
            return
        content = self._edit_content(r, c)
        if self.fbar_entry.get() != content:
            self.fbar_entry.delete(0, tk.END)
            self.fbar_entry.insert(0, content)

    def current_edit_text(self):
        try:
            if self.root.focus_get() is self.fbar_entry:
                return self.fbar_entry.get()
        except Exception:
            pass
        return self.entries[self.selected].get()

    def _update_formula_button(self):
        if self.show_formulas:
            self.btn_show_formulas.config(bg=ACCENT, fg="#ffffff")
        else:
            self.btn_show_formulas.config(bg=BORDER, fg=TEXT)

    def toggle_show_formulas(self):
        self.show_formulas = not self.show_formulas
        self._update_formula_button()
        if not self.dirty:
            r, c = self.selected
            e = self.entries[(r, c)]
            content = self._edit_content(r, c)
            if e.get() != content:
                e.delete(0, tk.END)
                e.insert(0, content)
        self.fbar_sync()
        if self.show_formulas:
            self.status.config(text="Формулы снова видны.")
        else:
            self.status.config(
                text="Формулы скрыты: видны только результаты. Формулы "
                     "сохранены, продолжают считаться и в файл пишутся "
                     "всегда (вернуть — Ctrl+H).")

    def is_editing_formula(self):
        return self.current_edit_text().lstrip().startswith("=")

    def on_focus_in(self, r, c):
        if self._ref_click_pending:
            self._ref_click_pending = False
            self.highlight_refs()
            self.update_status()
            return
        prev = self.selected
        if self.dirty and (r, c) != prev and self.is_editing_formula():
            self._edit_in_fbar = False
            self._insert_cell_ref(f"{col_letters(c)}{r + 1}")
            return
        if self.dirty and (r, c) != prev:
            self.commit_cell(prev[0], prev[1])
        if (r, c) != prev and not self.dirty:
            # из ячейки ушли без правки: вернуть ей результат,
            # чтобы сырой текст формулы не застревал на экране
            e_prev = self.entries[prev]
            val = self.display.get(prev, "")
            if e_prev.get() != val:
                e_prev.delete(0, tk.END)
                e_prev.insert(0, val)
        self.selected = (r, c)
        self.dirty = False
        self._edit_in_fbar = False
        self._fpop_hide()
        self.clear_highlights()
        e = self.entries[(r, c)]
        e.delete(0, tk.END)
        e.insert(0, self._edit_content(r, c))
        self.fbar_sync()
        self.update_status()

    def _insert_cell_ref(self, addr):
        if self._edit_in_fbar:
            ent = self.fbar_entry
        else:
            ent = self.entries[self.selected]
        try:
            upto = ent.get()[:ent.index(tk.INSERT)]
        except Exception:
            upto = ent.get()
        if upto.upper().endswith(addr):
            self._ref_click_pending = True
            self.root.after_idle(ent.focus_set)
            return
        ent.insert(tk.INSERT, addr)
        text = ent.get()
        e = self.entries[self.selected]
        if e.get() != text:
            e.delete(0, tk.END)
            e.insert(0, text)
        self.fbar_entry.delete(0, tk.END)
        self.fbar_entry.insert(0, text)
        self.dirty = True
        self._ref_click_pending = True
        self.root.after_idle(ent.focus_set)
        self.highlight_refs()
        self._fpop_check_entry(ent)
        self._arghint_check(ent)
        self.update_status()

    def on_key(self, r, c, event):
        if event.keysym in IGNORE_KEYS:
            return
        text = self.entries[(r, c)].get()
        self.dirty = text != self._edit_content(r, c)
        self.fbar_entry.delete(0, tk.END)
        self.fbar_entry.insert(0, text)
        if self.dirty:
            self.highlight_refs()
            self._fpop_check_entry(self.entries[(r, c)])
            self._arghint_check(self.entries[(r, c)])
        self.update_status()

    def commit_cell(self, r, c, text=None):
        if text is None:
            text = self.entries[(r, c)].get()
        s = str(text).strip()
        if s:
            self.CELLS[(r, c)] = s
        else:
            self.CELLS.pop((r, c), None)
        self.dirty = False
        self._edit_in_fbar = False
        self._fpop_hide()
        self.clear_highlights()
        self.recalc()

    def on_enter(self, r, c):
        if self._fpop is not None:
            return self._fpop_key_event(self.entries[(r, c)], "Return")
        self.commit_cell(r, c)
        self.move(r + 1, c)
        return "break"

    def on_tab(self, r, c):
        if self._fpop is not None:
            return self._fpop_key_event(self.entries[(r, c)], "Tab")
        self.commit_cell(r, c)
        self.move(r, c + 1)
        return "break"

    def on_escape(self, r, c):
        if self._fpop is not None:
            self._fpop_hide()
            return "break"
        self.dirty = False
        self._edit_in_fbar = False
        self.clear_highlights()
        self.recalc()
        self.update_status()
        return "break"

    def on_delete(self, r, c):
        if not self.dirty:
            self.CELLS.pop((r, c), None)
            self.recalc()
            return "break"
        return None

    def on_arrow(self, r, c, dr, dc, keysym):
        if self._fpop is not None and keysym in ("Up", "Down"):
            return self._fpop_key_event(self.entries[(r, c)], keysym)
        if self.dirty:
            return None
        self.move(r + dr, c + dc)
        return "break"

    def move(self, r, c):
        r = max(0, min(self.rows - 1, r))
        c = max(0, min(self.cols - 1, c))
        self.entries[(r, c)].focus_set()

    def on_fbar_focus_in(self, event):
        if self.dirty:
            return
        r, c = self.selected
        self.fbar_entry.delete(0, tk.END)
        self.fbar_entry.insert(0, self._edit_content(r, c))

    def on_fbar_navkey(self, event):
        if self._fpop is not None:
            return self._fpop_key_event(self.fbar_entry, event.keysym)
        if event.keysym == "Return":
            r, c = self.selected
            self.commit_cell(r, c, text=self.fbar_entry.get())
            self.move(r + 1, c)
            return "break"
        if event.keysym == "Tab":
            r, c = self.selected
            self.commit_cell(r, c, text=self.fbar_entry.get())
            self.move(r, c + 1)
            return "break"
        return None

    def on_fbar_escape(self, event):
        if self._fpop is not None:
            self._fpop_hide()
            return "break"
        self.dirty = False
        self._edit_in_fbar = False
        self.clear_highlights()
        self.recalc()
        return "break"

    def on_fbar_key(self, event):
        if event.keysym in IGNORE_KEYS:
            return
        self._edit_in_fbar = True
        r, c = self.selected
        text = self.fbar_entry.get()
        self.dirty = text != self._edit_content(r, c)
        e = self.entries[(r, c)]
        if e.get() != text:
            e.delete(0, tk.END)
            e.insert(0, text)
        self.highlight_refs()
        self._fpop_check_entry(self.fbar_entry)
        self._arghint_check(self.fbar_entry)
        self.update_status()

    def _place_below(self, anchor, pop, w, h, extra_offset=0):
        """Ставит панель под якорным полем поверх всего окна, чтобы её
        не перекрывали ячейки сетки."""
        try:
            x = anchor.winfo_rootx() - self.root.winfo_rootx()
            y = (anchor.winfo_rooty() - self.root.winfo_rooty()
                 + anchor.winfo_height())
        except Exception:
            x, y = 0, 0
        x = max(0, min(x, max(0, self.root.winfo_width() - w - 8)))
        pop.place(in_=self.root, x=x, y=y + extra_offset, width=w, height=h)
        pop.lift()

    def _fpop_hide(self):
        if self._fpop is not None:
            try:
                self._fpop.destroy()
            except Exception:
                pass
            self._fpop = None
            self._fpop_lb = None
            self._fpop_items = None
            self._fpop_accept = None
        if self._ahpop is not None:
            try:
                self._ahpop.destroy()
            except Exception:
                pass
            self._ahpop = None

    def _fpop_show(self, anchor_widget, items, accept):
        self._fpop_hide()
        if not items:
            return
        h = min(len(items), 10) * 19 + 6
        pop = tk.Frame(self.root, bg=BORDER, bd=1)
        lb = tk.Listbox(pop, font=("Segoe UI", 9), bd=0,
                        highlightthickness=0, activestyle="none",
                        exportselection=False)
        for _, display in items:
            lb.insert(tk.END, display)
        lb.selection_set(0)
        lb.see(0)

        def on_lb_click(event):
            i = lb.nearest(event.y)
            if 0 <= i < lb.size():
                lb.selection_clear(0, tk.END)
                lb.selection_set(i)
                self._fpop_accept_current()

        lb.bind("<Button-1>", on_lb_click)
        lb.pack(fill=tk.BOTH, expand=True)
        tk.Label(pop, text="↑↓ — выбор · Tab/Enter — вставить · Esc",
                 font=("Segoe UI", 7), bg=PANEL, fg=MUTED,
                 anchor="w", padx=6).pack(fill=tk.X)
        self._place_below(anchor_widget, pop,
                          min(320, max(200, anchor_widget.winfo_width())),
                          h + 20)
        self._fpop = pop
        self._fpop_lb = lb
        self._fpop_items = items
        self._fpop_accept = accept

    def _fpop_move(self, delta):
        if self._fpop_lb is None:
            return
        n = self._fpop_lb.size()
        if not n:
            return
        sel = self._fpop_lb.curselection()
        i = (sel[0] + delta) % n if sel else 0
        self._fpop_lb.selection_clear(0, tk.END)
        self._fpop_lb.selection_set(i)
        self._fpop_lb.see(i)

    def _fpop_accept_current(self):
        if self._fpop_lb is None or self._fpop_accept is None:
            return
        sel = self._fpop_lb.curselection()
        if not sel:
            return
        name = self._fpop_items[sel[0]][0]
        self._fpop_accept(name)

    def _fpop_key_event(self, ent, keysym):
        if self._fpop is None:
            return None
        if keysym == "Down":
            self._fpop_move(1)
            return "break"
        if keysym == "Up":
            self._fpop_move(-1)
            return "break"
        if keysym in ("Return", "Tab"):
            self._fpop_accept_current()
            return "break"
        if keysym == "Escape":
            self._fpop_hide()
            return "break"
        return None

    def _formula_partial(self, before_cursor):
        p = before_cursor.rfind("=")
        if p == -1:
            return None
        after = before_cursor[p + 1:]
        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё]*", after):
            return None
        return p, after

    def _fpop_suggestions(self, partial):
        part = partial.upper()
        out = []
        for main_name, syns, desc, _cat in FUNC_INFO:
            if main_name.upper().startswith(part) or any(
                    s.upper().startswith(part) for s in syns):
                out.append((main_name, f"{main_name} — {desc}"))
        return out

    def _fpop_check_entry(self, ent):
        try:
            upto = ent.get()[:ent.index(tk.INSERT)]
        except Exception:
            upto = ent.get()
        parsed = self._formula_partial(upto)
        if parsed is None:
            self._fpop_hide()
            return
        _, partial = parsed
        items = self._fpop_suggestions(partial)
        if not items:
            self._fpop_hide()
            return

        def accept(main_name):
            text = ent.get()
            cursor = ent.index(tk.INSERT)
            p, old_partial = self._formula_partial(text[:cursor])
            if p is None:
                return
            start = cursor - len(old_partial)
            ent.delete(start, cursor)
            ent.insert(start, main_name + "(")
            ent.icursor(start + len(main_name) + 1)
            self._fpop_hide()
            self._after_edit(ent)

        self._fpop_show(ent, items, accept)

    def _after_edit(self, ent):
        if ent is self.fbar_entry:
            e = self.entries[self.selected]
            if e.get() != self.fbar_entry.get():
                e.delete(0, tk.END)
                e.insert(0, self.fbar_entry.get())
        else:
            self.fbar_entry.delete(0, tk.END)
            self.fbar_entry.insert(0, ent.get())
        self.dirty = True
        self.highlight_refs()
        self.update_status()

    def _arg_index(self, between):
        idx, depth, i = 0, 0, 0
        n = len(between)
        while i < n:
            ch = between[i]
            if ch == '"':
                j = between.find('"', i + 1)
                if j == -1:
                    break
                i = j + 1
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    return None
                depth -= 1
            elif depth == 0 and ch in ";,":
                idx += 1
            i += 1
        return idx

    def _arg_context(self, upto):
        stack = []
        i, n = 0, len(upto)
        while i < n:
            ch = upto[i]
            if ch == '"':
                j = upto.find('"', i + 1)
                if j == -1:
                    break
                i = j + 1
                continue
            if ch == "(":
                m = re.search(r"([A-Za-zА-Яа-яЁё]+)$", upto[:i])
                stack.append((m.group(1).upper() if m else None, i))
            elif ch == ")":
                if stack:
                    stack.pop()
            i += 1
        if not stack or stack[-1][0] is None:
            return None
        fname, popen = stack[-1]
        idx = self._arg_index(upto[popen + 1:])
        if idx is None:
            return None
        return fname, idx

    def _arghint_hide(self):
        if self._ahpop is not None:
            try:
                self._ahpop.destroy()
            except Exception:
                pass
            self._ahpop = None

    def _arghint_check(self, ent):
        try:
            upto = ent.get()[:ent.index(tk.INSERT)]
        except Exception:
            upto = ent.get()
        ctx = self._arg_context(upto)
        if ctx is None:
            self._arghint_hide()
            return
        fname, idx = ctx
        main = MAIN_NAME.get(fname, fname)
        sig = ARG_HINTS.get(main)
        desc = FUNC_DESC_BY.get(main)
        if sig is None and desc is None:
            self._arghint_hide()
            return
        self._arghint_show(ent, main, sig, desc, idx)

    def _arghint_show(self, anchor, fname, sig, desc, idx):
        self._arghint_hide()
        pop = tk.Frame(self.root, bg=BORDER, bd=1)
        if sig:
            row = tk.Frame(pop, bg=PANEL)
            row.pack(fill=tk.X, padx=6, pady=(4, 1))
            tk.Label(row, text=fname + "(", font=("Segoe UI", 9, "bold"),
                     bg=PANEL, fg=TEXT).pack(side=tk.LEFT)
            for k, a in enumerate(sig):
                if k:
                    tk.Label(row, text=";", font=("Segoe UI", 9),
                             bg=PANEL, fg=MUTED).pack(side=tk.LEFT)
                is_cur = (k == min(idx, len(sig) - 1))
                tk.Label(row, text=a,
                         font=("Segoe UI", 9, "bold" if is_cur else "normal"),
                         bg=ACCENT if is_cur else PANEL,
                         fg="#ffffff" if is_cur else TEXT).pack(side=tk.LEFT)
            tk.Label(row, text=")", font=("Segoe UI", 9, "bold"),
                     bg=PANEL, fg=TEXT).pack(side=tk.LEFT)
        if sig:
            if idx >= len(sig):
                line = "лишний аргумент — проверьте формулу"
            else:
                line = f"{idx + 1}-й аргумент: {sig[idx]}"
        else:
            line = "без аргументов"
        if desc:
            line += f" · {desc}"
        tk.Label(pop, text=line, font=("Segoe UI", 8), bg=PANEL, fg=MUTED,
                 anchor="w", padx=6).pack(fill=tk.X, pady=(0, 3))
        w = min(360, max(240, anchor.winfo_width()))
        extra = 0
        if self._fpop is not None:
            try:
                extra = self._fpop.winfo_height()
            except Exception:
                pass
        self._place_below(anchor, pop, w, 48 if sig else 32,
                          extra_offset=extra)
        self._ahpop = pop

    def clear_highlights(self):
        for e in self.entries.values():
            if e.cget("bg") != "#ffffff":
                e.configure(bg="#ffffff")

    def highlight_refs(self):
        self.clear_highlights()
        if not self.dirty:
            return
        text = self.current_edit_text()
        if not text.lstrip().startswith("="):
            return
        covered = set()
        try:
            for m in RANGE_RE.finditer(text):
                r1, c1 = ref_index(m.group(1) + m.group(2))
                r2, c2 = ref_index(m.group(3) + m.group(4))
                r1, r2 = min(r1, r2), max(r1, r2)
                c1, c2 = min(c1, c2), max(c1, c2)
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        covered.add((r, c))
            rest = RANGE_RE.sub(" ", text)
            for tok in REF_RE.findall(rest):
                covered.add(ref_index(tok))
        except ValueError:
            return
        parts = []
        for r, c in sorted(covered):
            if 0 <= r < self.rows and 0 <= c < self.cols:
                self.entries[(r, c)].configure(bg=REF_HL)
                val = self.display.get((r, c), "") or "∅"
                parts.append(f"{col_letters(c)}{r + 1}={val}")
        if parts:
            self.status.config(text="Значения: " + "  |  ".join(parts))

    def update_status(self):
        r, c = self.selected
        addr = f"{col_letters(c)}{r + 1}"
        note = ""
        if self._fpop is not None:
            note = " | ⬆ Подсказка: ↑↓ — выбор, Tab/Enter — вставить"
        elif self._ahpop is not None:
            note = " | ⬆ Шаблон аргументов"
        elif self.dirty and self.is_editing_formula():
            note = (" | 🖊 РЕЖИМ ФОРМУЛЫ: щёлкай по ячейкам — адреса "
                    "встанут в формулу; Enter — посчитать")
        elif not self.show_formulas:
            note = " | 👁 Формулы скрыты (Ctrl+H — вернуть)"
        self.status.config(
            text=f"Ячейка {addr}{note} | Ctrl+S — сохранить, Ctrl+O — "
                 f"открыть, F1 — справка"
                 + (f" | файл: {self.file_path}" if self.file_path else ""))

    def on_right_click(self, event):
        self._fpop_hide()
        menu = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 9))
        menu.add_command(label="✕ Очистить ячейку",
                         command=self.clear_cell)
        menu.add_command(label="📐 Размер сетки…",
                         command=self.resize_dialog)
        menu.add_command(label="👁 Показать/скрыть формулы (Ctrl+H)",
                         command=self.toggle_show_formulas)
        menu.add_separator()
        menu.add_command(label="💾 Сохранить… (Ctrl+S)",
                         command=self.save_file)
        menu.add_command(label="📂 Открыть… (Ctrl+O)",
                         command=self.open_file)
        menu.add_command(label="❓ Справка (F1)", command=self.help_dialog)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def clear_cell(self):
        r, c = self.selected
        self.CELLS.pop((r, c), None)
        self.dirty = False
        self._edit_in_fbar = False
        self._fpop_hide()
        self.recalc()

    def resize_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Размер сетки")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()
        tk.Label(dialog, text="Строк:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10)).grid(row=0, column=0, padx=(16, 4),
                                             pady=(16, 4), sticky="w")
        cb_r = ttk.Combobox(dialog, values=[str(n) for n in
                                            range(5, self.MAX_ROWS + 1)],
                            width=5, state="readonly")
        cb_r.set(str(self.rows))
        cb_r.grid(row=0, column=1, pady=(16, 4), sticky="w")
        tk.Label(dialog, text="Столбцов:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10)).grid(row=1, column=0, padx=(16, 4),
                                             pady=(4, 4), sticky="w")
        cb_c = ttk.Combobox(dialog, values=[str(n) for n in
                                            range(1, self.MAX_COLS + 1)],
                            width=5, state="readonly")
        cb_c.set(str(self.cols))
        cb_c.grid(row=1, column=1, pady=(4, 4), sticky="w")

        def on_ok():
            self.rows = int(cb_r.get())
            self.cols = int(cb_c.get())
            dialog.destroy()
            self._make_grid_widgets()
            self.selected = (0, 0)
            self.dirty = False
            self.recalc()
            self.status.config(text=f"✔ Сетка: {self.rows} × {self.cols}. "
                                    "Данные сохранены.")

        row = tk.Frame(dialog, bg=PANEL)
        row.grid(row=2, column=0, columnspan=2, pady=(8, 14))
        tk.Button(row, text="ОК", command=on_ok,
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT, bg=ACCENT,
                  fg="#ffffff", cursor="hand2", padx=16, pady=4).pack(
            side=tk.LEFT, padx=6)
        tk.Button(row, text="Отмена", command=dialog.destroy,
                  font=("Segoe UI", 10), relief=tk.FLAT, bg=BORDER, fg=TEXT,
                  cursor="hand2", padx=16, pady=4).pack(side=tk.LEFT)
        dialog.wait_window()

    def save_file(self):
        path = filedialog.asksaveasfilename(
            title="Сохранить таблицу",
            defaultextension=".csv",
            initialfile="таблица.csv",
            filetypes=[("Таблица CSV (*.csv)", "*.csv")])
        if not path:
            return
        maxr = max([r for (r, c) in self.CELLS] + [0])
        maxc = max([c for (r, c) in self.CELLS] + [0])
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                for r in range(maxr + 1):
                    w.writerow([self._get_raw(r, c) for c in range(maxc + 1)])
        except Exception as ex:
            messagebox.showerror("Сохранить", f"Не удалось сохранить:\n{ex}")
            return
        self.file_path = path
        self.root.title(f"Таблица — {path}")
        self.status.config(text=f"✔ Сохранено: {path} (формулы внутри)")

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Открыть таблицу",
            filetypes=[("Таблица CSV (*.csv)", "*.csv"),
                       ("Все файлы", "*.*")])
        if not path:
            return
        rows = []
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                sample = fh.read(4096)
                fh.seek(0)
                delim = ";" if sample.count(";") >= sample.count(",") else ","
                for row in csv.reader(fh, delimiter=delim):
                    rows.append(row)
        except Exception as ex:
            messagebox.showerror("Открыть", f"Не удалось открыть:\n{ex}")
            return
        self._fpop_hide()
        self.CELLS = {}
        need_r = max(len(rows), 1)
        need_c = max((len(r) for r in rows), default=1)
        self.rows = max(self.rows, min(need_r, self.MAX_ROWS))
        self.cols = max(self.cols, min(need_c, self.MAX_COLS))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                if str(val).strip():
                    self.CELLS[(r, c)] = str(val).strip()
        self.file_path = path
        self.root.title(f"Таблица — {path}")
        self._make_grid_widgets()
        self.selected = (0, 0)
        self.dirty = False
        self._edit_in_fbar = False
        self.recalc()
        self.status.config(text=f"Открыт файл: {path}")

    def help_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Справка: Таблица")
        dialog.geometry("620x560")
        dialog.configure(bg=PANEL)
        dialog.grab_set()
        frame = tk.Frame(dialog, bg=PANEL)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        content = tk.Text(frame, wrap="word", bg=PANEL, fg=TEXT,
                          relief=tk.FLAT, bd=0, highlightthickness=0,
                          font=("Segoe UI", 10))
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=content.yview)
        content.configure(yscrollcommand=vsb.set)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        text = (
            "Формулы начинаются со знака =. Ссылки — латинскими буквами: "
            "A1, B2, C10.\n\n"
            "Внутри формул работают: текст в кавычках (\"да\"), сравнения "
            "(=, <>, <, >, <=, >=), склейка текстов через &, степень через "
            "^, логические ИСТИНА и ЛОЖЬ. Разделитель аргументов — точка "
            "с запятой ; (принимается и запятая).\n\n"
            "Примеры: =ЕСЛИ(B2>=4;\"сдано\";\"нет\") · =ОКРУГЛ(A1;2) · "
            "=СРЗНАЧ(B2:B9) · =НАИБОЛЬШИЙ(A1:A10;1) · "
            "=ЕСЛИ(И(A1>0;B1>0);A1*B1;0) · =СЦЕПИТЬ(A1;\" \";B1) · "
            "=ГОД(СЕГОДНЯ())\n\n"
            "Подсказка: набрал = и букву — всплывает список функций; "
            "↑↓ — выбор, Tab/Enter — вставить, Esc — спрятать. Курсор "
            "внутри скобок функции — всплывает шаблон с подсветкой "
            "текущего аргумента (учитывает кавычки и вложенность).\n\n"
            "Режим формулы: щёлкай по ячейкам — адреса сами встанут "
            "в формулу (без повторов), ссылки подсветятся жёлтым.\n\n"
            "Скрытие формул: «👁 Формулы» (Ctrl+H) прячет формулы — видны "
            "только результаты. Формулы не теряются: продолжают считаться "
            "и в файл пишутся всегда.\n\n"
            "Ctrl+S — сохранить (.csv, формулы внутри), Ctrl+O — открыть. "
            "«Размер сетки…» — правый клик мыши.\n\n"
            "Функции по категориям:\n"
            "  математика: СУММ, ПРОИЗВ, ABS, СТЕПЕНЬ, КОРЕНЬ, ЦЕЛОЕ, "
            "ОКРУГЛ, ОКРУГЛВВЕРХ, ОКРУГЛВНИЗ, ОКРВВЕРХ, ОКРВНИЗ, ОСТАТ, "
            "ЗНАК, ПИ, СЛЧИС, СЛУЧМЕЖДУ\n"
            "  статистика: СРЗНАЧ, МИН, МАКС, СЧЁТ, СЧЁТЗ, МЕДИАНА, "
            "СТАНДОТКЛОН, СТАНДОТКЛОНП, ДИСП, ДИСПР, НАИБОЛЬШИЙ, "
            "НАИМЕНЬШИЙ\n"
            "  логика: ЕСЛИ, И, ИЛИ, НЕ, ИСТИНА, ЛОЖЬ, ЕЧИСЛО, ЕТЕКСТ, "
            "ЕПУСТО\n"
            "  текст: ДЛСТР, ЛЕВСИМВ, ПРАВСИМВ, ПСТР, ПРОПИСН, СТРОЧН, "
            "СЦЕПИТЬ, СЖПРОБЕЛЫ, ЗАМЕНИТЬ, НАЙТИ, ПОВТОР\n"
            "  дата и время: СЕГОДНЯ, ГОД, МЕСЯЦ, ДЕНЬ\n\n"
            "Ошибки видны в ячейке как #ОШИБКА: и причина. Частые "
            "причины: русская буква вместо латинской (С1 вместо C1), "
            "ссылка за пределами сетки, циклическая ссылка, незакрытая "
            "кавычка в тексте.\n"
        )
        content.insert("1.0", text)
        content.configure(state="disabled")
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def on_close(self):
        self.root.destroy()


def main():
    print(f"Таблица: сборка {BUILD}")
    errs = self_test()
    if errs:
        print("Самопроверка движка нашла проблемы:")
        for e in errs:
            print("  -", e)
    else:
        print("Самопроверка движка: OK")
    root = tk.Tk()
    SheetApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
