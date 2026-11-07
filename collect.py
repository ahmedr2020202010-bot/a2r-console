import os
import sys

# إجبار نظام ويندوز على إظهار أيقونة البرنامج المخصصة في شريط المهام (Taskbar)
if sys.platform == "win32":
    try:
        import ctypes
        app_id = "a2r.insurance.console.v41"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

# منع تشغيل أكثر من نسخة بشكل متوافق تماماً مع PyInstaller
_SINGLE_INSTANCE_MUTEX = None
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        _kernel32 = ctypes.windll.kernel32
        _user32 = ctypes.windll.user32
        MUTEX_NAME = "Local\\A2R_Insurance_Console_Mutex_v41_App"
        _SINGLE_INSTANCE_MUTEX = _kernel32.CreateMutexW(None, wintypes.BOOL(False), MUTEX_NAME)
        if _kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            hwnd = _user32.FindWindowW(None, "A2R Operations Console - Ahmed Ramadan")
            if hwnd:
                _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                _user32.SetForegroundWindow(hwnd)
            sys.exit(0)
    except Exception:
        pass

import glob
import re
import time
import json
import shutil
import sqlite3
import hashlib
import subprocess
import datetime
import unicodedata
import threading
import logging
import winsound
import webbrowser
import tempfile
import zlib
import html
from collections import Counter
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

PYSTRAY_IMPORT_ERROR = ""
try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except Exception as _tray_exc:
    PYSTRAY_AVAILABLE = False
    PYSTRAY_IMPORT_ERROR = repr(_tray_exc)

try:
    from PIL import ImageTk
except Exception:
    ImageTk = None

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import arabic_reshaper
    from bidi.algorithm import get_display
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

APP_VERSION = "v51"
APP_OWNER = "Ahmed Ramadan"

_SILENT_SEEN = {}

def _log_silent(ctx, e):
    """بديل `except Exception: pass`: بيسجّل الخطأ في app_log.txt بدل ما يخفيه، من غير ما يغيّر سلوك البرنامج.
    كل موضع بيتسجّل مرة كل 10 دقايق بس (السجل ميتملاش)، وأخطاء Tcl الخاصة بإغلاق النوافذ بتتجاهل."""
    try:
        if type(e).__name__ == "TclError":
            return
        if not logging.getLogger().handlers:      # السجل لسه متجهّزش (أثناء الاستيراد): متفعلش basicConfig بالغلط
            return
        key = (ctx, type(e).__name__)
        now = time.time()
        if now - _SILENT_SEEN.get(key, 0) < 600:
            return
        _SILENT_SEEN[key] = now
        logging.error(f"[silent:{ctx}] {type(e).__name__}: {e}")
    except Exception:
        pass



# ===== v51: أدوات المشرف (التقفيل + إيصالات الدفع) — مدمجة جوه collect.py =====
import types as _a2r_types

def _a2r_embed(_name, _src):
    _mod = _a2r_types.ModuleType(_name)
    try:
        _mod.__file__ = os.path.abspath(__file__)
    except Exception:
        _mod.__file__ = os.path.abspath(sys.argv[0])
    sys.modules[_name] = _mod
    try:
        exec(compile(_src, "<" + _name + ">", "exec"), _mod.__dict__)
    except Exception:
        sys.modules.pop(_name, None)
        raise
    return _mod

_A2R_POS_ENGINE_SRC = r'''# -*- coding: utf-8 -*-
"""
A2R POS Engine  (v4.50)
محرك قراءة وتحليل إيصالات ماكينات الدفع (التقفيل + إيصالات الدفع) لنسخة الويندوز.
- مفيش واتساب نهائياً: كل المصادر بتتحدد من المستخدم (مجلد أو ملفات صور/PDF) في كل مرة.
- الـ OCR: Tesseract (tesseract.exe) + تحسين صورة (OpenCV لو متاح) + قراءتين على الأقل ومطابقة المجاميع.
- PDF -> صور: pdftoppm.exe (من نفس حزمة poppler اللي فيها pdftotext.exe) أو pypdfium2 كبديل.
"""
import os
import sys
import re
import io
import json
import math
import shutil
import hashlib
import zipfile
import tempfile
import datetime
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageOps

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None
try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

ENGINE_VERSION = "4.50"

if getattr(sys, "frozen", False):
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = BUNDLE_DIR

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
_NOWIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class OcrUnavailable(Exception):
    pass


# ───────────────────────── جداول الماكينات والوحدات ─────────────────────────
class TerminalInfo:
    __slots__ = ("order", "row", "unit")

    def __init__(self, order, row, unit):
        self.order, self.row, self.unit = order, row, unit


TERMINALS = {
    "50335710": TerminalInfo(1, 2, "أبيس"),
    "50335993": TerminalInfo(2, 2, "أبيس"),
    "50335987": TerminalInfo(3, 2, "أبيس"),
    "50325716": TerminalInfo(4, 3, "برج العرب"),
    "50335998": TerminalInfo(5, 3, "برج العرب"),
    "50335994": TerminalInfo(6, 3, "برج العرب"),
    "50335711": TerminalInfo(7, 3, "برج العرب"),
    "50382298": TerminalInfo(8, 4, "المنتزه"),
    "50382315": TerminalInfo(9, 4, "المنتزه"),
    "50383712": TerminalInfo(10, 4, "المنتزه"),
    "50382306": TerminalInfo(11, 5, "محرم بك"),
    "50382316": TerminalInfo(12, 5, "محرم بك"),
    "50382308": TerminalInfo(13, 6, "العجمي"),
    "50383706": TerminalInfo(14, 6, "العجمي"),
    "50382300": TerminalInfo(15, 7, "القباري"),
    "50383702": TerminalInfo(16, 8, "مصطفى كامل"),
    "50382312": TerminalInfo(17, 9, "مديرية الأمن"),
    "50383699": TerminalInfo(18, 10, "ميناء الإسكندرية"),
    "50383700": TerminalInfo(19, 11, "خدمات مصر"),
}
NUM_TO_TID = {t.order: k for k, t in TERMINALS.items()}
TID_FIX = {
    "50336994": "50335994", "50336711": "50335711", "50336998": "50335998",
    "50302316": "50382316", "50382318": "50382315", "50330987": "50335987",
    "60382308": "50382308",
}
MERCHANT_CODE_MAP = {"22": 2, "23": 3, "24": 4, "25": 5, "26": 6,
                     "27": 7, "28": 8, "29": 9, "30": 10, "31": 11}
NAME_HINTS = [
    (["ABYSS", "ABIS"], 2), (["BURJ", "BORG"], 3), (["MONTZAH", "TOSUN"], 4),
    (["MUHRAM", "MOHARAM"], 5), (["AJAMI", "AGAMI"], 6), (["KABBARY", "KABARY"], 7),
    (["MUSTAFA", "KAMEL"], 8), (["MODRYT", "MODERYT"], 9),
    (["ALEXANDRIA PORT", "ESMAT"], 10), (["EC ESC", "ELZREA", "ESC ALEX", "KHADAMAT"], 11),
]
ROW_NAMES = {2: "أبيس", 3: "برج العرب", 4: "المنتزه", 5: "محرم بك", 6: "العجمي",
             7: "القباري", 8: "مصطفى كامل", 9: "مديرية الأمن", 10: "ميناء الإسكندرية",
             11: "خدمات مصر"}


def round2(v):
    return round(float(v) + 1e-9, 2)


def terminal_label(tid):
    t = TERMINALS.get(tid)
    return f"{t.order} - {t.unit} ({tid})" if t else (tid or "غير محدد")


def unit_label(tid, fallback=None):
    """اسم الوحدة مع رقمها لو الوحدة ليها أكتر من ماكينة (أبيس 1، أبيس 2، برج العرب 3 ...)."""
    t = TERMINALS.get(tid)
    if not t:
        return fallback or "غير محدد"
    same = sorted([x for x in TERMINALS.values() if x.row == t.row], key=lambda x: x.order)
    if len(same) > 1:
        return "%s %d" % (t.unit, [x.order for x in same].index(t.order) + 1)
    return t.unit


# ───────────────────────── أدوات خارجية (Tesseract / pdftoppm) ─────────────────────────
_TESS = None
_PPM = None


def _candidates(name, subs):
    out = []
    for base in (BUNDLE_DIR, BASE_DIR):
        for s in subs:
            out.append(os.path.join(base, s, name) if s else os.path.join(base, name))
    return out


def find_tesseract():
    global _TESS
    if _TESS and os.path.exists(_TESS):
        return _TESS
    exe = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    cands = _candidates(exe, ["tesseract", "Tesseract-OCR", ""])
    cands += [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
    for c in cands:
        if os.path.exists(c):
            _TESS = c
            break
    else:
        _TESS = shutil.which("tesseract")
    if _TESS:
        td = os.path.join(os.path.dirname(_TESS), "tessdata")
        if os.path.exists(os.path.join(td, "eng.traineddata")):
            os.environ["TESSDATA_PREFIX"] = td
    return _TESS


def find_pdftoppm():
    global _PPM
    if _PPM and os.path.exists(_PPM):
        return _PPM
    exe = "pdftoppm.exe" if sys.platform == "win32" else "pdftoppm"
    for c in _candidates(exe, ["", "poppler", "poppler/bin"]):
        if os.path.exists(c):
            _PPM = c
            return c
    _PPM = shutil.which("pdftoppm")
    return _PPM


def ocr_ready():
    """(ok, message)"""
    if not find_tesseract():
        return False, ("tesseract.exe مش موجود. حطّ فولدر tesseract (جواه tesseract.exe و tessdata\\eng.traineddata) "
                       "جنب البرنامج أو ضمّه في الـ exe.")
    return True, ""


def _tess_env():
    env = os.environ.copy()
    env["OMP_THREAD_LIMIT"] = "1"
    return env


# ───────────────────────── OCR ─────────────────────────
class OcrLine:
    __slots__ = ("text", "left", "right", "top", "bottom")

    def __init__(self, text, left, right, top, bottom):
        self.text, self.left, self.right, self.top, self.bottom = text, left, right, top, bottom

    @property
    def cy(self):
        return (self.top + self.bottom) / 2.0

    @property
    def h(self):
        return self.bottom - self.top


def tess_lines(img, psm=6):
    """يقرا صورة PIL (رمادي) ويرجّع سطور مع أماكنها (من TSV)."""
    exe = find_tesseract()
    if not exe:
        raise OcrUnavailable("Tesseract not found")
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(tmp)
        r = subprocess.run([exe, tmp, "stdout", "--psm", str(psm), "-l", "eng", "tsv"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                           creationflags=_NOWIN, env=_tess_env())
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    out = r.stdout.decode("utf-8", "ignore")
    groups = {}
    order = []
    for ln in out.splitlines()[1:]:
        p = ln.split("\t", 11)
        if len(p) < 12 or p[0] != "5":
            continue
        t = p[11].strip()
        if not t:
            continue
        key = (p[2], p[3], p[4])
        l, tp, w, h = int(p[6]), int(p[7]), int(p[8]), int(p[9])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((t, l, tp, l + w, tp + h))
    lines = []
    for k in order:
        ws = groups[k]
        lines.append(OcrLine(" ".join(w[0] for w in ws), min(w[1] for w in ws), max(w[3] for w in ws),
                             min(w[2] for w in ws), max(w[4] for w in ws)))
    return lines


def rows_text(lines):
    ls = sorted(lines, key=lambda l: l.cy)
    rows = []
    for l in ls:
        if rows:
            last = rows[-1]
            cy = sum(e.cy for e in last) / len(last)
            h = sum(e.h for e in last) / len(last)
            if abs(l.cy - cy) < h * 0.6:
                last.append(l)
                continue
        rows.append([l])
    return "\n".join("  ".join(e.text for e in sorted(r, key=lambda e: e.left)) for r in rows) + "\n"


def reading_text(lines):
    return "\n".join(l.text for l in lines)


# ───────────────────────── تحسين الصور ─────────────────────────
def load_image(path):
    im = Image.open(path)
    im.load()
    return ImageOps.exif_transpose(im).convert("RGB")


def prep_raw(pil):
    g = pil.convert("L")
    w = g.width
    if w < 1400:
        s = 1400.0 / w
        g = g.resize((int(g.width * s), int(g.height * s)), Image.LANCZOS)
    elif w > 2600:
        s = 2200.0 / w
        g = g.resize((int(g.width * s), int(g.height * s)), Image.LANCZOS)
    return g


def _paper_crop_cv(bgr):
    h, w = bgr.shape[:2]
    s = 1000.0 / max(h, w)
    sm = cv2.resize(bgr, None, fx=s, fy=s) if s < 1 else bgr.copy()
    s = sm.shape[0] / float(h)
    g = cv2.GaussianBlur(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), (7, 7), 0)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cs, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return bgr
    c = max(cs, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.08 * sm.shape[0] * sm.shape[1]:
        return bgr
    box = (cv2.boxPoints(cv2.minAreaRect(c)) / s).tolist()
    box.sort(key=lambda p: p[1])
    top = sorted(box[:2])
    bot = sorted(box[2:])
    tl, tr, bl, br = top[0], top[1], bot[0], bot[1]
    W = int(max(np.hypot(*(np.array(tr) - tl)), np.hypot(*(np.array(br) - bl))))
    H = int(max(np.hypot(*(np.array(bl) - tl)), np.hypot(*(np.array(br) - tr))))
    if W < 100 or H < 100:
        return bgr
    # الباتش ورقة طويلة: لو القص طلع عريض نسيب الصورة زي ما هي (يعني فيه أكتر من إيصال)
    if H < W * 1.6:
        return bgr
    M = cv2.getPerspectiveTransform(np.float32([tl, tr, bl, br]),
                                    np.float32([[0, 0], [W, 0], [0, H], [W, H]]))
    return cv2.warpPerspective(bgr, M, (W, H))


def scan_receipt(pil):
    """(نسخة ملونة مقصوصة للـ PDF، نسخة رمادية محسّنة للـ OCR)."""
    if cv2 is None or np is None:
        g = ImageOps.autocontrast(pil.convert("L"), cutoff=1)
        return pil, prep_raw(Image.merge("RGB", (g, g, g)))
    bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    try:
        crop = _paper_crop_cv(bgr)
    except Exception:
        crop = bgr
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, None, fx=0.25, fy=0.25)
    k = max(3, (min(small.shape) // 8) | 1)
    bg = cv2.resize(cv2.medianBlur(small, min(k, 31) | 1), (g.shape[1], g.shape[0]))
    norm = cv2.divide(g, bg, scale=255)
    if norm.shape[1] < 1600:
        norm = cv2.resize(norm, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
    elif norm.shape[1] > 2800:
        norm = cv2.resize(norm, None, fx=2200.0 / norm.shape[1], fy=2200.0 / norm.shape[1])
    color = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    return color, Image.fromarray(norm)


# ───────────────────────── PDF -> صور ─────────────────────────
def pdf_page_count(pdf):
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf).pages)
    except Exception:
        pass
    try:
        data = open(pdf, "rb").read()
        n = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", data))
        return n if n > 0 else None
    except Exception:
        return None


def pdf_to_images(pdf, outdir, dpi=200, first=None, last=None, max_side=3400):
    """يرجّع لستة مسارات PNG لصفحات الـ PDF. pdftoppm أولاً، وpypdfium2 بديل."""
    os.makedirs(outdir, exist_ok=True)
    base = hashlib.md5((os.path.abspath(pdf) + str(os.path.getsize(pdf))).encode()).hexdigest()[:10]
    prefix = os.path.join(outdir, base)
    ppm = find_pdftoppm()
    files = []
    if ppm:
        cmd = [ppm, "-r", str(dpi), "-png"]
        if first:
            cmd += ["-f", str(first)]
        if last:
            cmd += ["-l", str(last)]
        cmd += [pdf, prefix]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_NOWIN, timeout=600)
        files = sorted([os.path.join(outdir, f) for f in os.listdir(outdir)
                        if f.startswith(base + "-") and f.endswith(".png")])
    if not files:
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(pdf)
            n = len(doc)
            a = (first or 1) - 1
            b = min(n, last or n)
            for i in range(a, b):
                im = doc[i].render(scale=dpi / 72.0).to_pil().convert("RGB")
                p = f"{prefix}-{i + 1:03d}.png"
                im.save(p)
                files.append(p)
        except Exception:
            raise OcrUnavailable("مش قادر أحوّل PDF لصور: حطّ pdftoppm.exe جنب pdftotext.exe (أو pip install pypdfium2)")
    # تصغير الصفحات العملاقة (PDF ممسوح كبير) عشان الذاكرة
    for p in files:
        try:
            with Image.open(p) as im:
                s = max(im.size)
                if s > max_side:
                    r = max_side / float(s)
                    im2 = im.convert("RGB").resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
                    im2.save(p)
        except Exception:
            pass
    return files


# ───────────────────────── المبالغ والباتش (منقول من نسخة الموبايل) ─────────────────────────
_MARKERS = [re.compile(p, re.I) for p in (
    r"TERMINAL", r"GRAND|TOTALS?", r"NATIONAL\s*BANK|\bNBE\b", r"BATCH", r"MERCHANT",
    r"SUCCESSF|CLOSED", r"\bVISA\b|MASTER|MEZZA|MEEZA|MEEZ", r"THANK\s*YOU", r"NET\s*AMOUNT", r"\bSALE\b")]


def receipt_score(text):
    return sum(1 for r in _MARKERS if r.search(text))


_AMOUNT_RE = re.compile(r"(?<![\d,.])(\d{1,3}(?:,\d{3})*|\d+)[., ](\d{2})(?!\d)")
_BRAND_RE = re.compile(r"\b(VISA|MASTER(?:CARD)?|MEZZA|MEEZA|MEZA|MEZZ4|MEZZ)\b", re.I)
_TAIL_RE = re.compile(r"THANK\s*YOU|Hotline|App\s*Version", re.I)


def amounts_in(raw):
    text = re.sub(r"\bB(\d{2,3}[.,]\d{2})\b", lambda m: "8" + m.group(1), raw)
    out = []
    for m in _AMOUNT_RE.finditer(text):
        try:
            v = float(m.group(1).replace(",", "") + "." + m.group(2))
        except ValueError:
            continue
        if 0.5 <= v <= 5000000:
            out.append(round2(v))
    return out


def most_common(vals):
    if not vals:
        return None
    c = Counter(vals)
    best = None
    for v in vals:
        if best is None or c[v] > c[best]:
            best = v
    return best, c[best]


class Parsed:
    def __init__(self, grand, bsum, bvals):
        self.grand, self.bsum, self.bvals = grand, bsum, bvals


def parse_receipt(txt):
    t = _TAIL_RE.split(txt)[0]
    gm = re.search(r"GRAND|TOTALS", t, re.I)
    pre = t[:gm.start()] if gm else t
    post = t[gm.start():] if gm else ""
    bms = list(_BRAND_RE.finditer(pre))
    sections = []
    if bms:
        for i, m in enumerate(bms):
            end = bms[i + 1].start() if i + 1 < len(bms) else len(pre)
            sections.append(pre[m.end():end])
    else:
        sm = re.search(r"SUCCESSFULL?Y|CLOSED", pre, re.I)
        if sm:
            pre = pre[sm.end():]
        sections.append(pre)
    bvals = []
    for sec in sections:
        mc = most_common(amounts_in(sec))
        if mc:
            bvals.append(mc[0])
    grand = amounts_in(post)
    bsum = round2(sum(bvals)) if bvals else None
    return Parsed(grand, bsum, bvals)


def decide(results):
    for r in results:
        b = r.bsum
        if b and b > 0 and any(abs(g - b) < 0.005 for g in r.grand):
            return b, True
    for r in results:
        b = r.bsum
        if b and b > 0 and len(r.bvals) >= 2:
            for g in r.grand:
                sa, sb = "%.2f" % g, "%.2f" % b
                if len(sa) == len(sb) and sum(1 for x, y in zip(sa, sb) if x != y) == 1:
                    return b, True
    for r in results:
        c = most_common(r.grand)
        if c and c[1] >= 2 and r.bsum is None:
            return c[0], False
    pool = []
    for r in results:
        pool.extend(r.grand)
        if r.bsum and r.bsum > 0:
            pool.append(r.bsum)
    c = most_common(pool)
    if c:
        return c[0], False
    return 0.0, False


def classify_receipt(text):
    up = text.upper()
    pay = [r"R{1,2}N\W{0,3}\d{9,}", r"\d{4,6}\W{0,2}\*{3,}\W{0,2}\d{4}", r"APPROVED", r"AUTH\W{0,3}\d{6}",
           r"I\s*AUTHORI[SZ]E", r"MERCHANT\s*COPY", r"CLESS|CHIP\s*ONLINE"]
    batch = [r"BATCH\s*CLOS", r"SUCCESSF", r"GRAND\s*TOTAL", r"TOTAL\s*NET", r"THANK\s*YOU", r"NBE\s*NETWORK", r"HOTLINE"]
    p = sum(1 for r in pay if re.search(r, up))
    b = sum(1 for r in batch if re.search(r, up))
    if p >= 2 and b < 2:
        return "payment"
    if b >= 1:
        return "batch"
    return "other"


def sum_closure(texts):
    cnt = {}
    for t in texts:
        tt = _TAIL_RE.split(t)[0]
        local = Counter(amounts_in(tt))
        for k, v in local.items():
            if v > cnt.get(k, 0):
                cnt[k] = v
    c = sorted(k for k, v in cnt.items() if v >= 2)
    if len(c) < 3 or len(c) > 14:
        return None
    for gi in range(len(c) - 1, 1, -1):
        g = c[gi]
        others = c[:gi]
        n = len(others)
        for mask in range(1, 1 << n):
            bits, s = 0, 0.0
            for i in range(n):
                if mask & (1 << i):
                    bits += 1
                    s += others[i]
            if bits >= 2 and abs(s - g) < 0.005:
                return g
    return None


class PieceResult:
    def __init__(self, texts, val, ok):
        self.texts, self.val, self.ok = texts, val, ok


def ocr_piece(lines):
    texts = [rows_text(lines), reading_text(lines)]
    sc = sum_closure(texts)
    if sc is not None:
        return PieceResult(texts, sc, True)
    v, ok = decide([parse_receipt(t) for t in texts])
    return PieceResult(texts, v, ok)


def batch_no(texts):
    reg = re.compile(r"BATCH\s*NO\D{0,6}(\d{4,7})", re.I)
    allv = [m.group(1) for t in texts for m in reg.finditer(t)]
    mc = most_common(allv)
    return mc[0] if mc else None


def split_columns(lines):
    if len(lines) < 8:
        return [lines]
    minl = min(l.left for l in lines)
    maxr = max(l.right for l in lines)
    w = maxr - minl
    if w <= 0:
        return [lines]
    srt = sorted(lines, key=lambda l: l.left)
    for tol in (0.03, 0.02, 0.01):
        groups, cur_right = [], -1e9
        for l in srt:
            if not groups or l.left - cur_right > w * tol:
                groups.append([l])
                cur_right = l.right
            else:
                groups[-1].append(l)
                cur_right = max(cur_right, l.right)
        big = [g for g in groups
               if (max(e.right for e in g) - min(e.left for e in g)) >= w * 0.12 and len(g) >= 6]
        if 2 <= len(big) <= 4 and all(receipt_score(reading_text(g)) >= 3 for g in big):
            return big
    return [lines]


# ───────────────────────── الماكينة / الوحدة / التاريخ ─────────────────────────
def _tid_labeled(t):
    m = re.search(r"TERMINAL\s*(?:ID)?\D{0,15}?(\d[\d\s/]{6,9}\d)", t, re.I)
    if not m:
        return None
    raw = re.sub(r"\D", "", m.group(1).replace("/", "7"))
    if len(raw) < 8:
        return None
    d = raw[-8:]
    d = TID_FIX.get(d, d)
    return d if d in TERMINALS else None


def _tid_loose(t):
    for tid in TERMINALS:
        if tid in t:
            return tid
    for m in re.finditer(r"\b(503\d{5})\b", t):
        c = TID_FIX.get(m.group(1), m.group(1))
        if c in TERMINALS:
            return c
    return None


def find_terminal_in(texts):
    for t in texts:
        r = _tid_labeled(t)
        if r:
            return r
    for t in texts:
        r = _tid_loose(t)
        if r:
            return r
    return None


def find_terminal_fuzzy_in(texts, target_row):
    pool = [k for k, v in TERMINALS.items() if target_row is None or v.row == target_row]
    dist = {}
    for t in texts:
        for run in re.finditer(r"\d[\d /]{6,14}\d", t):
            digits = re.sub(r"\D", "", run.group(0).replace("/", "7"))
            for i in range(0, len(digits) - 7):
                cand = digits[i:i + 8]
                if not (cand.startswith("50") or cand.startswith("60")):
                    continue
                for tid in pool:
                    d = sum(1 for a, b in zip(cand, tid) if a != b)
                    if d < dist.get(tid, 99):
                        dist[tid] = d
    if not dist:
        return None
    best = min(dist.values())
    winners = [k for k, v in dist.items() if v == best]
    if best <= 1 and len(winners) == 1:
        return winners[0]
    return None


def find_unit_extra_in(texts):
    for t in texts:
        m = re.search(r"MERCHANT\s*(?:ID|10)\D{0,15}?(\d[\d\s/]{8,13}\d)", t, re.I)
        cands = []
        if m:
            cands.append(re.sub(r"\D", "", m.group(1).replace("/", "7")))
        cands.append(re.sub(r"\D", "", t))
        for d in cands:
            mm = re.search(r"11470?(2[2-9]|3[01])084", d)
            if mm and mm.group(1) in MERCHANT_CODE_MAP:
                return MERCHANT_CODE_MAP[mm.group(1)]
    for t in texts:
        up = t.upper()
        for words, row in NAME_HINTS:
            if any(w in up for w in words):
                return row
    return None


def find_date_in(texts):
    """التاريخ من سطر DATE: تصويت منفصل على الشهر واليوم بين كل القراءات
    (القراءة الغلط في رقم بتتعوّض بقراءة تانية)، وأي شهر/يوم مش منطقي بيتجاهل."""
    reg = re.compile(r"DATE\s*:?\s*(20\d{2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})", re.I)
    months, days = [], []
    for t in texts:
        for m in reg.finditer(t):
            mo, d = int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12:
                months.append(mo)
            if 1 <= d <= 31:
                days.append(d)
    mm, dd = most_common(months), most_common(days)
    return "%d.%d" % (dd[0], mm[0]) if mm and dd else None


class Analysis:
    def __init__(self, tid, how, row, unit, val, ok, batches, date):
        self.tid, self.how, self.row, self.unit = tid, how, row, unit
        self.val, self.ok, self.batches, self.date = val, ok, batches, date
        self.texts = []


def analyze_lines(all_lines):
    pieces = split_columns(all_lines)
    multi = len(pieces) > 1
    all_texts, batches, seen = [], [], set()
    all_ok = True
    for pc in pieces:
        r = ocr_piece(pc)
        all_texts.extend(r.texts)
        if r.val <= 0:
            all_ok = False
            continue
        b = batch_no(r.texts)
        key = (b, r.val)
        if b is not None and key in seen:
            continue
        seen.add(key)
        batches.append(r.val)
        all_ok = all_ok and r.ok
    total = round2(sum(batches))
    ok = all_ok and bool(batches)
    if multi and not ok:
        r = ocr_piece(all_lines)
        all_texts.extend(r.texts)
        if r.val > 0 and (r.ok or not batches):
            total, ok, batches = r.val, r.ok, [r.val]
    date = find_date_in(all_texts)
    tid = find_terminal_in(all_texts)
    how = "terminal"
    row = unit = None
    if tid is None:
        u0 = find_unit_extra_in(all_texts)
        tid = find_terminal_fuzzy_in(all_texts, u0)
        how = "fuzzy"
    if tid is not None:
        info = TERMINALS[tid]
        row, unit = info.row, info.unit
    else:
        how = "none"
        u = find_unit_extra_in(all_texts)
        if u is not None:
            row, unit, how = u, ROW_NAMES.get(u), "name/merchant"
    a = Analysis(tid, how, row, unit, total, ok, batches, date)
    a.texts = all_texts
    return a


def merge_second_read(a, b):
    """بيدمج القراءة التانية في الأولى. يرجّع قيمة تانية متعارضة (للمراجعة) أو None."""
    if a.tid is None and b.tid is not None:
        a.tid, a.row, a.unit, a.how = b.tid, b.row, b.unit, b.how
    elif a.row is None and b.row is not None:
        a.row, a.unit, a.how = b.row, b.unit, b.how
    if a.date is None:
        a.date = b.date
    if b.val <= 0:
        return None
    if a.val <= 0:
        a.val, a.ok, a.batches = b.val, b.ok, list(b.batches)
        return None
    if abs(a.val - b.val) < 0.005:
        a.ok = a.ok or b.ok
        return None
    if (not a.ok) and b.ok:
        a.val, a.ok, a.batches = b.val, True, list(b.batches)
        return None
    if a.ok and not b.ok:
        return None
    a.ok = False
    return b.val


def _looks_receipt(text):
    return receipt_score(text) >= 2 or find_terminal_in([text]) is not None


def analyze_image(pil, want_color_crop=False):
    """يحلل صورة واحدة. يرجّع dict: kind = batch | payment | other، و
    analysis, alt, image (الصورة بعد تصحيح الاتجاه)."""
    base = pil.convert("RGB")
    cur = base
    lines = tess_lines(prep_raw(cur), 6)
    text = reading_text(lines)
    is_r = _looks_receipt(text)
    if is_r and classify_receipt(text) == "payment":
        return {"kind": "payment", "image": cur}
    if not is_r:
        for deg in (90, 270, 180):
            rot = base.rotate(deg, expand=True)
            ln2 = tess_lines(prep_raw(rot), 6)
            t2 = reading_text(ln2)
            if _looks_receipt(t2):
                if classify_receipt(t2) == "payment":
                    return {"kind": "payment", "image": rot}
                cur, lines, text, is_r = rot, ln2, t2, True
                break
    if not is_r:
        return {"kind": "other", "image": cur}
    a = analyze_lines(lines)
    all_texts = list(a.texts)
    alt = None
    color, enh = scan_receipt(cur)
    for psm in (6, 4):
        if psm == 4 and a.ok and a.tid and a.row and a.val > 0:
            break
        ln2 = tess_lines(enh, psm)
        a2 = analyze_lines(ln2)
        r = merge_second_read(a, a2)
        if r is not None:
            alt = r
        all_texts.extend(a2.texts)
    # التاريخ: تصويت بين كل القراءات (كل قراءة ممكن تغلط في رقم مختلف)
    d = find_date_in(all_texts)
    if d:
        a.date = d
    return {"kind": "batch", "analysis": a, "alt": alt, "image": cur, "crop": color}


# ───────────────────────── عدّ إيصالات الدفع داخل PDF ─────────────────────────
_RRN1 = re.compile(r"R{1,2}N\W{0,3}([0-9OoDQlI|iSsBZzgb ]{9,16})", re.I)
_RRN2 = re.compile(r"(?<!\d)(63[\d ]{7,10})(?!\d)")
_FIX = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "l": "1", "I": "1", "|": "1", "i": "1",
                      "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2", "g": "9", "b": "6"})
_DATE_RE = re.compile(r"(20\d{2})[^\d\n]{1,3}(\d{2})[^\d\n]{1,3}(\d{2})")

_COUNT_PATS = {
    "ec": r"\bEC\b|MUSTAFA|KAMEL|MOGAMAA|KHADMAT|ELKWAT",
    "alex": r"ALEX\s*0?2F",
    "bank": r"NATIONAL|EGYPT",
    "sale": r"(MASTER|VISA|MEZZA|MEEZA)\s*-?\s*SALE",
    "auth": r"AUTHORI|DEBIT\s+THE|ABOVE\s+AMOUNT",
    "rrn": r"R{1,2}N\W{0,3}\d{6,}",
    "amount": r"AMOUNT\W{0,3}\d",
    "star": r"\d{4,6}\W{0,3}\*{4,}",
    "card": r"CLESS|CHIP\s*ONLINE",
}


def day_key(text):
    for m in _DATE_RE.finditer(text):
        mo, d = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return "%d.%d" % (d, mo)
    return None


def rrn_of(line):
    m = _RRN1.search(line)
    s = m.group(1).translate(_FIX) if m else None
    if s is None:
        m2 = _RRN2.search(line)
        s = m2.group(1) if m2 else None
    if not s:
        return None
    d = re.sub(r"\D", "", s)
    if len(d) < 9:
        return None
    d = d[:12]
    return d if (len(d) == 12 and d.startswith("63")) else "P"


def _dedupe(pts, tol):
    out = []
    for l, r, cy in sorted(pts, key=lambda p: p[2]):
        for o in out:
            if o[0] < r and l < o[1] and abs(o[2] - cy) < tol:
                break
        else:
            out.append([l, r, cy])
    return out


def _ocr_tiles(img_path, cols=5, rows=3, threads=None):
    """يقسّم الصفحة لبلاط (5 أعمدة × 3 صفوف بتداخل) ويقراه بالتوازي. يرجّع (w, h, [(text,l,r,cy)])."""
    im = Image.open(img_path).convert("L")
    w, h = im.size
    cw, rh = w / float(cols), h / float(rows)
    jobs = []
    for i in range(cols):
        for j in range(rows):
            x0 = max(0, int(i * cw - cw * 0.12))
            x1 = min(w, int((i + 1) * cw + cw * 0.12))
            y0 = max(0, int(j * rh - rh * 0.08))
            y1 = min(h, int((j + 1) * rh + rh * 0.08))
            jobs.append((x0, y0, im.crop((x0, y0, x1, y1))))

    def run(job):
        x0, y0, tile = job
        return [(l.text, x0 + l.left, x0 + l.right, y0 + l.cy) for l in tess_lines(tile, 6)]

    n = threads or max(1, min(8, os.cpu_count() or 2))
    out = []
    with ThreadPoolExecutor(max_workers=n) as ex:
        for part in ex.map(run, jobs):
            out.extend(part)
    return w, h, out


def count_page(w, h, L):
    """عدد الإيصالات في الصفحة = مجموع (أعلى عدد علامات من أي نوع) في كل عمود."""
    per = {}
    for k, pt in _COUNT_PATS.items():
        pts = [(l, r, cy) for t, l, r, cy in L if re.search(pt, t.upper())]
        per[k] = _dedupe(pts, h * 0.012)
    total = 0
    for ci in range(5):
        lo, hi = ci * w / 5.0, (ci + 1) * w / 5.0
        total += max((len([a for a in v if lo <= (a[0] + a[1]) / 2.0 < hi]) for v in per.values()), default=0)
    # RRN كامل (نقاط ارتكاز) بالتسلسل
    rr = {}
    for t, l, r, cy in L:
        a = rrn_of(t)
        if a and a != "P":
            rr[a] = day_key(t)
    return total, rr


def tid_votes(text):
    v = {}
    lab = _tid_labeled(text)
    if lab:
        v[lab] = v.get(lab, 0) + 3
    for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", text):
        c0 = m.group(1)
        c = TID_FIX.get(c0, c0)
        if c in TERMINALS:
            v[c] = v.get(c, 0) + 1
    if not v:
        f = find_terminal_fuzzy_in([text], None)
        if f:
            v[f] = 0.5
    return v


def machine_new_name(info, day, month):
    same = sorted([t for t in TERMINALS.values() if t.row == info.row], key=lambda t: t.order)
    unit = re.sub(r"\s+", ".", info.unit.strip())
    k = [t.order for t in same].index(info.order) + 1
    parts = [str(info.order), unit]
    if len(same) > 1:
        parts.append(str(k))
    parts += ["يوم", str(day), str(month)]
    return ".".join(parts)


class PayResult:
    def __init__(self, src):
        self.src = src
        self.name = os.path.basename(src)
        self.pages = 0
        self.count = 0
        self.tid = None
        self.votes = {}
        self.day = self.month = None
        self.new_name = None
        self.out_path = None
        self.seq_min = self.seq_max = None
        self.seq_missing = []
        self.other_day = []
        self.notes = []
        self.ok = True
        # المرحلة 2 (العد): تفصيل الصفحات
        self.counted = False
        self.n15 = self.n10 = self.last = None
        self.page_counts = []
        self.id_notes = []
        self.id_ok = True

    @property
    def order(self):
        return TERMINALS[self.tid].order if self.tid in TERMINALS else 99

    def snapshot_identity(self):
        self.id_notes, self.id_ok = list(self.notes), self.ok


def scan_payment_pdf(pdf, workdir, progress=None, stop=lambda: False, max_pages=60):
    r = PayResult(pdf)
    imgs = pdf_to_images(pdf, workdir, dpi=300, last=max_pages, max_side=3700)
    r.pages = len(imgs)
    votes, days, rrn_day, total = {}, {}, {}, 0
    texts = []
    for i, p in enumerate(imgs):
        if stop():
            break
        if progress:
            progress("صفحة %d من %d" % (i + 1, len(imgs)))
        w, h, L = _ocr_tiles(p)
        c, rr = count_page(w, h, L)
        total += c
        rrn_day.update(rr)
        page_text = "\n".join(t for t, *_ in L)
        texts.append(page_text)
        for k, v in tid_votes(page_text).items():
            votes[k] = votes.get(k, 0) + v
        for m in _DATE_RE.finditer(page_text):
            k = day_key(m.group(0))
            if k:
                days[k] = days.get(k, 0) + 1
        try:
            os.remove(p)
        except OSError:
            pass
    r.count, r.votes = total, votes
    allt = "\n".join(texts)
    if votes:
        r.tid = max(votes.items(), key=lambda e: e[1])[0]
    else:
        row = find_unit_extra_in([allt])
        same = [k for k, v in TERMINALS.items() if v.row == row] if row else []
        if len(same) == 1:
            r.tid = same[0]
            r.notes.append("Terminal ID مش واضح، الوحدة اتحددت من Merchant ID/الاسم - راجع")
            r.ok = False
    top = max(votes.values()) if votes else 0
    if days:
        best = max(days.items(), key=lambda e: e[1])[0]
        r.day, r.month = best.split(".")
        for rrn, d in rrn_day.items():
            if d and d != best:
                r.other_day.append("إيصال %s بتاريخ %s" % (rrn[6:], d))
    if r.tid is None:
        r.ok = False
        r.notes.append("مش قادر أعرف الماكينة من الـ PDF")
    elif top < 2 and not r.notes:
        r.ok = False
        r.notes.append("قراءة ضعيفة للـ Terminal ID - راجع")
    if r.day is None:
        r.ok = False
        r.notes.append("مش قادر أعرف التاريخ من الـ PDF")
    # تسلسل أرقام الإيصالات (آخر 6 أرقام من RRN)
    nums = sorted(int(k[6:]) for k in rrn_day)
    if len(nums) >= 2:
        best_start, best_len, start = 0, 1, 0
        for i in range(1, len(nums) + 1):
            if i == len(nums) or nums[i] - nums[i - 1] > 15:
                if i - start > best_len:
                    best_len, best_start = i - start, start
                start = i
        cl = nums[best_start:best_start + best_len]
        r.seq_min, r.seq_max = cl[0], cl[-1]
        have = set(cl)
        r.seq_missing = [n for n in range(cl[0], cl[-1] + 1) if n not in have]
        span = r.seq_max - r.seq_min + 1
        if span != r.count and span <= r.count + 15:
            miss = "، ".join("%06d" % n for n in r.seq_missing[:12])
            r.notes.append("العدد المقدّر %d بينما التسلسل من %06d إلى %06d (%d رقم). أرقام مش لاقيها: %s%s "
                           "(ممكن إيصالات ناقصة فعلاً أو أرقام ما اتقرتش، راجع الملف)" % (
                               r.count, r.seq_min, r.seq_max, span, miss, " ..." if len(r.seq_missing) > 12 else ""))
    if r.other_day:
        r.ok = False
        r.notes.append("إيصالات بتاريخ مختلف: " + " ، ".join(r.other_day[:6]))
    return r


def apply_payment_name(results, r, dest_dir):
    """يسمّي ويكوّب الملف باسم الماكينة. لو اسم مكرر من ملف تاني بيزوّد _2."""
    r.new_name = r.out_path = None
    if r.tid not in TERMINALS or not r.day or not r.month:
        return
    base = machine_new_name(TERMINALS[r.tid], r.day, r.month)
    final, k = base, 2
    while any(x is not r and x.new_name == final for x in results):
        final = "%s_%d" % (base, k)
        k += 1
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, final + ".pdf")
    if os.path.abspath(dst) != os.path.abspath(r.src):
        shutil.copy2(r.src, dst)
    r.new_name, r.out_path = final, dst



# ───────────────────────── إيصالات الدفع: مرحلتين (1 تعريف + إعادة تسمية / 2 عد) ─────────────────────────
def _pdf_page_count(pdf):
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf).pages)
    except Exception:
        pass
    try:
        import pypdfium2 as pdfium
        return len(pdfium.PdfDocument(pdf))
    except Exception:
        return 0


def _finish_identity(r, votes, days, allt):
    """يحدد الماكينة واليوم من الأصوات."""
    if votes:
        r.tid = max(votes.items(), key=lambda e: e[1])[0]
    else:
        row = find_unit_extra_in([allt])
        same = [k for k, v in TERMINALS.items() if v.row == row] if row else []
        if len(same) == 1:
            r.tid = same[0]
            r.notes.append("Terminal ID مش واضح، الوحدة اتحددت من Merchant ID/الاسم - راجع")
            r.ok = False
    top = max(votes.values()) if votes else 0
    if days:
        best = max(days.items(), key=lambda e: e[1])[0]
        r.day, r.month = best.split(".")
    if r.tid is None:
        r.ok = False
        r.notes.append("مش قادر أعرف الماكينة من الـ PDF")
    elif top < 2 and not r.notes:
        r.ok = False
        r.notes.append("قراءة ضعيفة للـ Terminal ID - راجع")
    if r.day is None:
        r.ok = False
        r.notes.append("مش قادر أعرف التاريخ من الـ PDF")


def identify_payment_pdf(pdf, workdir, progress=None, stop=lambda: False, max_probe=4):
    """المرحلة 1: يعرّف الماكينة (Terminal ID) واليوم من أول صفحات الملف بس، من غير عدّ."""
    r = PayResult(pdf)
    r.pages = _pdf_page_count(pdf)
    votes, days, texts = {}, {}, []
    limit = min(max_probe, r.pages) if r.pages else max_probe
    for pg in range(1, limit + 1):
        if stop():
            break
        if progress:
            progress("قراءة رقم الماكينة من صفحة %d" % pg)
        for p in pdf_to_images(pdf, workdir, dpi=300, first=pg, last=pg, max_side=3700):
            try:
                w, h, L = _ocr_tiles(p)
                page_text = "\n".join(t for t, *_ in L)
                texts.append(page_text)
                for k, v in tid_votes(page_text).items():
                    votes[k] = votes.get(k, 0) + v
                for m in _DATE_RE.finditer(page_text):
                    k = day_key(m.group(0))
                    if k:
                        days[k] = days.get(k, 0) + 1
            finally:
                try:
                    os.remove(p)
                except OSError:
                    pass
        if votes and max(votes.values()) >= 3 and days:
            break
    _finish_identity(r, votes, days, "\n".join(texts))
    return r


def _snap_page(raw):
    """صفحة كاملة لازم تكون 15 أو 10. يرجّع أقرب قيمة (فرق أقصاه 2) أو None."""
    best = min((10, 15), key=lambda k: abs(raw - k))
    return best if abs(raw - best) <= 2 else None


def count_payment_pdf(r, workdir, progress=None, stop=lambda: False, max_pages=80):
    """المرحلة 2: يعدّ كل صفحة. الصفحات الكاملة = 15 أو 10 (بنقرّب لأقرب قيمة)، وآخر صفحة بتتعد زي ما هي."""
    pdf = r.src
    total_pages = r.pages or _pdf_page_count(pdf)
    r.pages = total_pages
    n_loop = min(total_pages, max_pages) if total_pages else max_pages
    raws, rrn_day, votes, days = [], {}, {}, {}
    for pg in range(1, n_loop + 1):
        if stop():
            return False
        if progress:
            progress("عدّ صفحة %d من %s" % (pg, total_pages or "؟"))
        imgs = pdf_to_images(pdf, workdir, dpi=300, first=pg, last=pg, max_side=3700)
        if not imgs:
            break
        p = imgs[0]
        try:
            w, h, L = _ocr_tiles(p)
            c, rr = count_page(w, h, L)
            raws.append(c)
            rrn_day.update(rr)
            page_text = "\n".join(t for t, *_ in L)
            for k, v in tid_votes(page_text).items():
                votes[k] = votes.get(k, 0) + v
            for m in _DATE_RE.finditer(page_text):
                k = day_key(m.group(0))
                if k:
                    days[k] = days.get(k, 0) + 1
        finally:
            for q in imgs:
                try:
                    os.remove(q)
                except OSError:
                    pass
    r.notes = list(r.id_notes)
    r.ok = r.id_ok
    if not raws:
        r.ok = False
        r.notes.append("مفيش صفحات اتقرت من الملف")
        return True
    if r.tid is None and votes:
        r.tid = max(votes.items(), key=lambda e: e[1])[0]
    if r.day is None and days:
        r.day, r.month = max(days.items(), key=lambda e: e[1])[0].split(".")
    r.n15 = r.n10 = 0
    r.last = None
    total = 0
    r.page_counts = []
    fixes, odd = [], []
    last_i = len(raws) - 1
    for i, raw in enumerate(raws):
        if i == last_i:
            cnt, kind = raw, "last"
            r.last = raw
        else:
            k = _snap_page(raw)
            if k is None:
                cnt, kind = raw, "?"
                odd.append("ص%d (اتقرت %d)" % (i + 1, raw))
            else:
                cnt, kind = k, k
                if k == 15:
                    r.n15 += 1
                else:
                    r.n10 += 1
                if raw != k:
                    fixes.append("ص%d اتقرت %d واتصنفت %d" % (i + 1, raw, k))
        total += cnt
        r.page_counts.append((i + 1, raw, cnt, kind))
    r.count = total
    r.counted = True
    detail = "  ".join(("آخر ص%d:%d" if kind == "last" else "ص%d:%d") % (n, cnt) for n, raw, cnt, kind in r.page_counts)
    r.notes.append("عدد الصفحات %d | صفحات 15 = %d | صفحات 10 = %d | آخر صفحة = %s" % (
        len(raws), r.n15, r.n10, r.last if r.last is not None else "—"))
    r.notes.append("تفصيل الصفحات: " + detail)
    if fixes:
        r.notes.append("تصحيح تلقائي لصفحات كاملة: " + " ، ".join(fixes))
    if odd:
        r.ok = False
        r.notes.append("صفحات مش 15 ولا 10 وهي مش الأخيرة (راجعها): " + " ، ".join(odd))
    if total_pages and len(raws) < total_pages:
        r.ok = False
        r.notes.append("اتقرى %d صفحة بس من %d (حد أقصى %d)" % (len(raws), total_pages, max_pages))
    # مقارنة مع تسلسل أرقام الـ RRN
    r.other_day = []
    if r.day:
        for rrn, d in rrn_day.items():
            if d and d != "%s.%s" % (r.day, r.month):
                r.other_day.append("إيصال %s بتاريخ %s" % (rrn[6:], d))
    nums = sorted(int(k[6:]) for k in rrn_day)
    if len(nums) >= 2:
        best_start, best_len, start = 0, 1, 0
        for i in range(1, len(nums) + 1):
            if i == len(nums) or nums[i] - nums[i - 1] > 15:
                if i - start > best_len:
                    best_len, best_start = i - start, start
                start = i
        cl = nums[best_start:best_start + best_len]
        r.seq_min, r.seq_max = cl[0], cl[-1]
        have = set(cl)
        r.seq_missing = [n for n in range(cl[0], cl[-1] + 1) if n not in have]
        span = r.seq_max - r.seq_min + 1
        if span != total and span <= total + 15:
            miss = "، ".join("%06d" % n for n in r.seq_missing[:12])
            r.notes.append("العدد %d بينما التسلسل من %06d إلى %06d (%d رقم). أرقام مش لاقيها: %s%s" % (
                total, r.seq_min, r.seq_max, span, miss, " ..." if len(r.seq_missing) > 12 else ""))
    if r.other_day:
        r.ok = False
        r.notes.append("إيصالات بتاريخ مختلف: " + " ، ".join(r.other_day[:6]))
    return True


# ───────────────────────── التقفيل: عناصر + ترقيم + مخرجات ─────────────────────────
class Item:
    def __init__(self, label, image):
        self.label = label          # اسم العرض (ملف / ملف pdf صفحة n)
        self.image = image          # PIL بعد تصحيح الاتجاه
        self.crop = None
        self.tid = None
        self.order = None
        self.row = None
        self.unit = None
        self.amount = 0.0
        self.date = None
        self.ok = False
        self.how = "none"
        self.batches = []
        self.suffix = None
        self.orig_tid = None
        self.conflict = False
        self.skip = False
        self.alt = None
        self.key = ""
        self.path = None

    @property
    def needs_review(self):
        return (self.amount <= 0 or self.row is None or not self.ok or self.alt is not None
                or self.how in ("auto-number", "conflict"))


def _item_reset(self):
    self.tid, self.order, self.row, self.unit, self.how = self.det
    self.suffix = self.orig_tid = None
    self.conflict = self.skip = False


Item.reset = _item_reset
Item.det = (None, None, None, None, "none")


def renumber(raw_items):
    """يعيد الترقيم والتكرار بعد أي تعديل يدوي. يرجّع (kept, warnings)."""
    for r in raw_items:
        r.reset()
    warns = []
    return assign_numbers(raw_items, warns), warns


def flag_payment_duplicates(results):
    """لو ملفين اتعرفوا على نفس الماكينة (بنفس اليوم) نعلّم الاتنين للمراجعة."""
    tag = "اتعرفت على نفس الماكينة"
    for r in results:
        r.notes = [n for n in r.notes if not n.startswith(tag)]
    groups = {}
    for r in results:
        if r.tid and r.new_name:
            groups.setdefault((r.tid, r.day, r.month), []).append(r)
    for (tid, _d, _m), lst in groups.items():
        if len(lst) < 2:
            continue
        for r in lst:
            others = " ، ".join(x.name for x in lst if x is not r)
            r.ok = False
            r.notes.append("%s (%s) كمان في: %s - راجع" % (tag, terminal_label(tid), others))


def same_day(a, b):
    return a.date is None or b.date is None or a.date == b.date


def assign_numbers(raw, warnings):
    """المرحلة 2: التكرار وترقيم الماكينات (منقولة من نسخة الموبايل)."""
    prio = {"manual": 0, "terminal": 0, "fuzzy": 1}
    with_tid = [r for r in raw if r.tid is not None]
    with_tid.sort(key=lambda r: (prio.get(r.how, 3), raw.index(r)))
    taken = {}
    for r in with_tid:
        n = r.order
        prev = taken.get(n)
        if prev is None:
            taken[n] = r
        elif r.amount > 0 and abs(prev.amount - r.amount) < 0.005 and same_day(prev, r):
            r.skip = True
            warnings.append("%s: نفس الماكينة %s ونفس المبلغ %.2f (إيصال مكرر) - تم استبعاده" % (r.label, n, r.amount))
        else:
            r.orig_tid, r.tid, r.conflict = r.tid, None, True
    used = set()

    def give_suffix(r):
        k = 2
        while (r.orig_tid, k) in used:
            k += 1
        used.add((r.orig_tid, k))
        r.tid, r.suffix, r.how = r.orig_tid, k, "extra-batch"

    for r in raw:
        if r.skip or r.tid is not None or r.row is None:
            continue
        if r.conflict and r.how in ("terminal", "fuzzy"):
            give_suffix(r)
            continue
        free = [n for n in range(1, 20) if TERMINALS[NUM_TO_TID[n]].row == r.row and n not in taken]
        if free:
            n = free[0]
            t = NUM_TO_TID[n]
            r.tid, r.order, r.unit = t, n, TERMINALS[t].unit
            taken[n] = r
            r.how = "conflict" if r.conflict else "auto-number"
        elif r.orig_tid is not None:
            give_suffix(r)
    kept = [r for r in raw if not r.skip]
    votes = Counter(r.date for r in kept if r.date)
    main = votes.most_common(1)[0][0] if votes else None
    for r in kept:
        nm = r.label
        if main and r.date and r.date != main:
            warnings.append("%s: تاريخ الإيصال %s بينما أغلب الإيصالات %s" % (nm, r.date, main))
        if r.row is not None and r.amount > 0:
            if not r.ok:
                warnings.append("%s: %s = %.2f (راجع المبلغ يدوياً)" % (nm, r.unit, r.amount))
            if r.alt is not None:
                warnings.append("%s: القراءة التانية للمبلغ %.2f مختلفة عن %.2f - راجع الصورة" % (nm, r.alt, r.amount))
            if r.how == "extra-batch":
                warnings.append("%s: الماكينة %s ظهرت بمبلغ مختلف - اتحسبت كباتش إضافي %s" % (nm, r.order, r.suffix))
            elif r.how in ("auto-number", "conflict"):
                warnings.append("%s: رقم الماكينة اتحدد تلقائياً (%s) - اتأكد منه" % (nm, r.order))
            elif r.how not in ("terminal", "fuzzy", "manual"):
                warnings.append("%s: الوحدة اتحددت بالاسم/الميرشانت فقط" % nm)
        else:
            warnings.append("%s: مش قادر أقرا المبلغ أو الوحدة - اضغط تعديل" % nm)
    return kept


def main_date_of(items):
    c = Counter(r.date for r in items if r.date)
    return c.most_common(1)[0][0] if c else datetime.date.today().strftime("%d.%m")


# ───────────── ملء قالب الإكسيل مباشرة في XML (من غير ما نبوّظ التنسيق) ─────────────
_CELL_RE = re.compile(r"<c\b[^>]*?/>|<c\b[^>]*?>.*?</c>", re.S)


def _col_num(c):
    n = 0
    for ch in c:
        n = n * 26 + (ord(ch) - 64)
    return n


def _find_row(xml, row):
    return re.search(r'<row\b[^>]*\br="%d"[^>]*?(?:/>|>.*?</row>)' % row, xml, re.S)


def _read_num(xml, col, row):
    rm = _find_row(xml, row)
    if not rm:
        return 0.0
    for m in _CELL_RE.finditer(rm.group(0)):
        cell = m.group(0)
        op = re.search(r"<c\b[^>]*?>", cell).group(0)
        r = re.search(r'\br="([A-Z]+)\d+"', op)
        if not r or r.group(1) != col:
            continue
        t = re.search(r'\bt="([^"]+)"', op)
        if t and t.group(1) != "n":
            return 0.0
        v = re.search(r"<v>([^<]*)</v>", cell)
        try:
            return float(v.group(1)) if v else 0.0
        except ValueError:
            return 0.0
    return 0.0


def _set_cell(xml, col, row, build):
    rm = _find_row(xml, row)
    if not rm:
        raise Exception("row %d missing" % row)
    row_xml = rm.group(0)
    ref = "%s%d" % (col, row)
    target = _col_num(col)
    existing = before = None
    for m in _CELL_RE.finditer(row_xml):
        cell = m.group(0)
        op = re.search(r"<c\b[^>]*?>", cell).group(0)
        r = re.search(r'\br="([A-Z]+)\d+"', op)
        if not r:
            continue
        cn = _col_num(r.group(1))
        if cn == target:
            existing = m
            break
        if cn > target and before is None:
            before = m
    style = formula = None
    if existing:
        cell = existing.group(0)
        op = re.search(r"<c\b[^>]*?>", cell).group(0)
        s = re.search(r'\bs="(\d+)"', op)
        style = s.group(1) if s else None
        f = re.search(r"<f\b[^>]*?(?:/>|>.*?</f>)", cell, re.S)
        formula = f.group(0) if f else None
    new_cell = build(ref, style, formula)
    if existing:
        row_xml = row_xml[:existing.start()] + new_cell + row_xml[existing.end():]
    elif before:
        row_xml = row_xml[:before.start()] + new_cell + row_xml[before.start():]
    elif row_xml.endswith("/>"):
        row_xml = row_xml[:-2] + ">" + new_cell + "</row>"
    else:
        i = row_xml.rfind("</row>")
        row_xml = row_xml[:i] + new_cell + row_xml[i:]
    return xml[:rm.start()] + row_xml + xml[rm.end():]


def _first_sheet_path(z):
    names = z.namelist()
    try:
        wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
        rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")
        sm = re.search(r'<sheet\b[^>]*?r:id="([^"]+)"', wb)
        if sm:
            for m in re.finditer(r"<Relationship\b[^>]*>", rels):
                tag = m.group(0)
                if 'Id="%s"' % sm.group(1) in tag:
                    t = re.search(r'Target="([^"]+)"', tag)
                    if t:
                        tg = t.group(1)
                        return tg[1:] if tg.startswith("/") else "xl/" + tg
    except KeyError:
        pass
    return "xl/worksheets/sheet1.xml" if "xl/worksheets/sheet1.xml" in names else names[0]


def fill_template(template_path, out_path, totals):
    with zipfile.ZipFile(template_path) as zin:
        sheet = _first_sheet_path(zin)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
            found = False
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == sheet:
                    found = True
                    xml = data.decode("utf-8", "ignore")
                    for r in range(2, 12):
                        tot = round2(totals.get(r, 0.0))
                        xml = _set_cell(xml, "D", r, lambda ref, st, f0, tot=tot:
                                        '<c r="%s"%s><v>%s</v></c>' % (ref, ' s="%s"' % st if st else "", tot))
                        cash = _read_num(xml, "E", r)
                        total = round2(tot + cash)
                        xml = _set_cell(xml, "F", r, lambda ref, st, f0, r=r, total=total:
                                        '<c r="%s"%s>%s<v>%s</v></c>' % (
                                            ref, ' s="%s"' % st if st else "",
                                            f0 or "<f>D%d+IF(ISBLANK(E%d),0,E%d)</f>" % (r, r, r), total))
                    data = xml.encode("utf-8")
                zout.writestr(info, data)
            if not found:
                raise Exception("sheet not found: " + sheet)


def simple_workbook(out_path, totals):
    """لو مفيش قالب: إكسيل بسيط بنفس ترتيب الصفوف (A اسم الوحدة، D المبلغ، E كاش، F الإجمالي)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.sheet_view.rightToLeft = True
    for c, h in zip("ABCDEF", ["الوحدة", "", "", "مبلغ الماكينات", "كاش", "الإجمالي"]):
        ws[c + "1"] = h
    for r in range(2, 12):
        ws["A%d" % r] = ROW_NAMES.get(r, "")
        ws["D%d" % r] = round2(totals.get(r, 0.0))
        ws["F%d" % r] = "=D%d+IF(ISBLANK(E%d),0,E%d)" % (r, r, r)
    ws["A12"] = "الإجمالي"
    ws["D12"] = "=SUM(D2:D11)"
    ws["E12"] = "=SUM(E2:E11)"
    ws["F12"] = "=SUM(F2:F11)"
    wb.save(out_path)


def find_template(extra_dirs=()):
    """قالب الإكسيل: الاسم المضبوط 'الاسكندريه 00.xlsx' الأول، وبعده أي ملف اسمه بينتهي بـ 00.xlsx."""
    dirs = [d for d in list(extra_dirs) + [BASE_DIR, BUNDLE_DIR] if d and os.path.isdir(d)]
    for d in dirs:
        exact = os.path.join(d, "الاسكندريه 00.xlsx")
        if os.path.exists(exact):
            return exact
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except Exception:
            continue
        for f in names:
            if f.lower().endswith("00.xlsx") and not f.startswith(("~", ".")):
                return os.path.join(d, f)
    return None


def build_closing_outputs(items, out_dir, template=None, report_date=None, progress=None):
    """يكتب: raw_images/N.jpg، PDF مجمّع لكل يوم، الإكسيل، وتقرير نصي. يرجّع dict بالمسارات."""
    os.makedirs(out_dir, exist_ok=True)
    raw_dir = os.path.join(out_dir, "raw_images")
    shutil.rmtree(raw_dir, ignore_errors=True)
    os.makedirs(raw_dir, exist_ok=True)
    report_date = report_date or main_date_of(items)
    items = sorted([i for i in items if not i.skip],
                   key=lambda r: ((r.order or 99), (r.suffix or 1)))
    for r in items:
        if r.order is None:
            nm = "x_%s" % re.sub(r"[^\w\-]+", "_", r.label)[:40]
        else:
            nm = "%d%s" % (r.order, "_%d" % r.suffix if r.suffix else "")
        r.path = os.path.join(raw_dir, nm + ".jpg")
        r.image.save(r.path, quality=92)
    main_items = [r for r in items if r.date is None or r.date == report_date]
    other = {}
    for r in items:
        if r.date is not None and r.date != report_date:
            other.setdefault(r.date, []).append(r)

    def build_pdf(lst, path):
        pages = []
        for r in lst:
            try:
                crop = r.crop if r.crop is not None else scan_receipt(r.image)[0]
            except Exception:
                crop = r.image
            r.crop = crop
            W, H = 1240, 1754
            page = Image.new("RGB", (W, H), "white")
            c = crop.copy()
            c.thumbnail((W - 80, H - 80))
            page.paste(c, ((W - c.width) // 2, (H - c.height) // 2))
            pages.append(page)
        if not pages:
            return False
        pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
        return True

    res = {"report_date": report_date, "pdf": None, "extra_pdfs": [], "xlsx": None, "report": None}
    rd = report_date.replace(".", ".")
    pdf_path = os.path.join(out_dir, "الاسكندريه %s.pdf" % rd)
    if build_pdf(main_items, pdf_path):
        res["pdf"] = pdf_path
    for d, lst in other.items():
        p = os.path.join(out_dir, "الاسكندريه %s.pdf" % d)
        if build_pdf(lst, p):
            res["extra_pdfs"].append(p)
    totals = {r: 0.0 for r in range(2, 12)}
    for r in main_items:
        if r.row is not None and r.amount > 0:
            totals[r.row] = totals.get(r.row, 0.0) + r.amount
    xlsx = os.path.join(out_dir, "الاسكندريه %s.xlsx" % rd)
    try:
        if template and os.path.exists(template):
            fill_template(template, xlsx, totals)
        else:
            simple_workbook(xlsx, totals)
        res["xlsx"] = xlsx
    except Exception as e:  # pragma: no cover
        res["xlsx_error"] = str(e)
    found = {r.order for r in main_items if r.amount > 0 and r.order}
    res["missing"] = [i for i in range(1, 20) if i not in found]
    res["totals"] = totals
    lines = ["تقرير التقفيل - %s" % rd, "=" * 40]
    for r in main_items:
        lines.append("%s | %s | %s | %.2f %s" % (
            r.order or "-", unit_label(r.tid, r.unit), r.label, r.amount, "" if r.ok else "(راجع)"))
    lines.append("-" * 40)
    for row in range(2, 12):
        lines.append("%s: %.2f" % (ROW_NAMES[row], totals.get(row, 0.0)))
    lines.append("الإجمالي: %.2f" % sum(totals.values()))
    if res["missing"]:
        lines.append("ماكينات ما ظهرش لها باتش: " + "، ".join(str(i) for i in res["missing"]))
    rp = os.path.join(out_dir, "تقرير التقفيل %s.txt" % rd)
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    res["report"] = rp
    return res


def expand_sources(paths, recursive=False):
    """أي مجموعة مسارات (ملفات أو مجلدات) -> (صور، PDFs). من غير أي افتراض عن الأسماء أو الترتيب."""
    imgs, pdfs = [], []

    def add(p):
        low = p.lower()
        if os.path.basename(p).startswith(("."," ")):
            return
        if low.endswith(".pdf"):
            pdfs.append(p)
        elif low.endswith(IMG_EXT):
            imgs.append(p)

    for p in paths:
        if os.path.isdir(p):
            if recursive:
                for dp, _dn, fns in os.walk(p):
                    for f in fns:
                        add(os.path.join(dp, f))
            else:
                for f in os.listdir(p):
                    fp = os.path.join(p, f)
                    if os.path.isfile(fp):
                        add(fp)
        elif os.path.isfile(p):
            add(p)
    return sorted(set(imgs)), sorted(set(pdfs))


def process_closing(img_paths, pdf_paths, workdir, progress=None, stop=lambda: False, fixes=None):
    """يقرا كل الصور وصفحات الـ PDF ويرجّع (items, excluded_payment, warnings)."""
    fixes = fixes or {}
    ok, msg = ocr_ready()
    if not ok:
        raise OcrUnavailable(msg)
    todo = []     # (label, key, loader)
    for p in img_paths:
        todo.append(("%s" % os.path.basename(p), "%s:%d" % (os.path.basename(p), os.path.getsize(p)),
                     (lambda p=p: load_image(p))))
    for pdf in pdf_paths:
        if stop():
            break
        if progress:
            progress(0.0, "تحويل صفحات: %s" % os.path.basename(pdf))
        pages = pdf_to_images(pdf, os.path.join(workdir, "pdf"), dpi=220)
        for i, pg in enumerate(pages, 1):
            todo.append(("%s (ص%d)" % (os.path.basename(pdf), i), "%s:p%d:%d" % (
                os.path.basename(pdf), i, os.path.getsize(pdf)), (lambda pg=pg: load_image(pg))))
    raw, excluded, warnings = [], [], []
    for n, (label, key, loader) in enumerate(todo):
        if stop():
            break
        if progress:
            progress(n / float(max(1, len(todo))) * 0.9, "قراءة %d من %d: %s" % (n + 1, len(todo), label))
        try:
            res = analyze_image(loader())
        except OcrUnavailable:
            raise
        except Exception as e:
            warnings.append("%s: فشلت القراءة (%s)" % (label, e))
            continue
        if res["kind"] == "payment":
            excluded.append(label)
            continue
        if res["kind"] != "batch":
            continue
        a = res["analysis"]
        it = Item(label, res["image"])
        it.crop = res.get("crop")
        it.key = key
        it.tid, it.row, it.unit, it.how = a.tid, a.row, a.unit, a.how
        it.order = TERMINALS[a.tid].order if a.tid else None
        it.amount, it.date, it.ok, it.batches, it.alt = a.val, a.date, a.ok, a.batches, res["alt"]
        fx = fixes.get(key)
        if isinstance(fx, dict):
            v, ft = fx.get("val"), fx.get("tid")
            if isinstance(v, (int, float)) and v > 0:
                it.amount, it.batches = round2(v), [round2(v)]
            if ft in TERMINALS:
                info = TERMINALS[ft]
                it.tid, it.order, it.row, it.unit = ft, info.order, info.row, info.unit
            it.ok, it.alt, it.how = True, None, "manual"
        it.det = (it.tid, it.order, it.row, it.unit, it.how)
        raw.append(it)
    if excluded:
        warnings.append("اتجاهلت %d صورة إيصال دفع أو مستند (مش باتش كلوز): %s%s" % (
            len(excluded), "، ".join(excluded[:8]), " ..." if len(excluded) > 8 else ""))
    kept = assign_numbers(raw, warnings) if raw else []
    return kept, excluded, warnings, raw


# ───────────────────────── تشغيل من سطر الأوامر للاختبار ─────────────────────────
if __name__ == "__main__":  # pragma: no cover
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "closing":
        imgs, pdfs = expand_sources(sys.argv[2:])
        wd = tempfile.mkdtemp()
        items, ex, warns, _raw = process_closing(imgs, pdfs, wd, progress=lambda f, m: print("..", m))
        for r in items:
            print(r.label, "| tid", r.tid, "| order", r.order, "| amount", r.amount, "| ok", r.ok,
                  "| alt", r.alt, "| how", r.how, "| date", r.date, "| batches", r.batches)
        print("excluded:", ex)
        print("warnings:", warns)
    elif cmd == "payments":
        wd = tempfile.mkdtemp()
        for p in sys.argv[2:]:
            r = scan_payment_pdf(p, wd, progress=lambda m: print("..", m))
            print(r.name, "pages", r.pages, "count", r.count, "tid", r.tid, "votes", r.votes, "day", r.day, r.month,
                  "seq", r.seq_min, r.seq_max, "missing", len(r.seq_missing), "ok", r.ok)
            if r.tid:
                print("name:", machine_new_name(TERMINALS[r.tid], r.day or "?", r.month or "?"))
            print("notes:", r.notes)
'''

_A2R_POS_TOOLS_SRC = r'''# -*- coding: utf-8 -*-
"""
A2R POS Tools  (v4.50)
زرّين للمشرف فقط: "التقفيل" و"إيصالات الدفع".
- كل زر بيطلب باسورد مستقل (مختلف عن باسورد المشرف) في كل مرة.
- مفيش واتساب: كل مرة بتختار مجلد أو ملفات (صور / PDF) مرتبة أو مش مرتبة.
"""
import os
import sys
import re
import json
import time
import hmac
import queue
import shutil
import hashlib
import logging
import tempfile
import threading
import datetime
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk

import a2r_pos_engine as E

TOOLS_VERSION = "v4.50"

# باسورد الفكرتين: مخزّن كـ PBKDF2-SHA256 (200 ألف دورة) مع salt، مش نص صريح، ومنفصل تماماً عن باسورد المشرف.
_PW_SALT = "684cb086e29d8d07046fc249108085fc"
_PW_HASH = "0e8d736a1037c8dc5297dd2be3bba6af0793f7a98ebe0cabc578d8d6ce89fe48"
_PW_ITER = 200000

_FAILS = 0
_LOCKS = 0
_LOCKED_UNTIL = 0.0


def verify_pos_password(pw):
    """حساس لحالة الحروف (من غير lower/strip)."""
    h = hashlib.pbkdf2_hmac("sha256", (pw or "").encode("utf-8"), _PW_SALT.encode("utf-8"), _PW_ITER).hex()
    return hmac.compare_digest(h, _PW_HASH)


def _lock_remaining():
    return max(0, int(_LOCKED_UNTIL - time.time() + 0.999))


def _register_fail():
    global _FAILS, _LOCKS, _LOCKED_UNTIL
    _FAILS += 1
    try:
        logging.warning("POS tools: wrong password attempt #%d", _FAILS)
    except Exception:
        pass
    if _FAILS >= 3:
        _FAILS = 0
        _LOCKS += 1
        _LOCKED_UNTIL = time.time() + min(600, 30 * (2 ** (_LOCKS - 1)))


def _register_ok():
    global _FAILS, _LOCKS, _LOCKED_UNTIL
    _FAILS = _LOCKS = 0
    _LOCKED_UNTIL = 0.0


# ───────────────────────── ثيم وأدوات مساعدة ─────────────────────────
_DEFAULT = {"bg": "#080E17", "card": "#121E2E", "border": "#1E2E42", "input": "#0A131F", "text": "#FFFFFF",
            "muted": "#8FA3B8", "primary": "#0284C7", "hover": "#0369A1", "success": "#10B981",
            "danger": "#EF4444", "warning": "#F59E0B", "accent": "#38BDF8"}


def _theme(parent):
    t = dict(_DEFAULT)
    try:
        main = sys.modules.get("__main__")
        themes = getattr(main, "THEMES", None)
        cur = themes.get(getattr(parent, "current_theme_name", ""), None) if themes else None
        if cur:
            t.update({"bg": cur["bg"], "card": cur["card"], "border": cur["border"], "input": cur["input"],
                      "text": cur["text"], "muted": cur["text_muted"], "primary": cur["primary"],
                      "hover": cur["primary_hover"], "success": cur["success"], "danger": cur["danger"],
                      "warning": cur["warning"], "accent": cur["accent"]})
    except Exception:
        pass
    return t


def _font():
    return getattr(sys.modules.get("__main__"), "FONT_FAMILY", "Segoe UI")


# ألوان الأزرار: غامقة عشان الكتابة البيضا تبان (الأخضر الفسفوري كان بيخفي الكلام)
_GREEN, _GREEN_H = "#15803D", "#166534"
_AMBER, _AMBER_H = "#B45309", "#92400E"
_SLATE, _SLATE_H = "#334155", "#1E293B"


def _icon(win):
    try:
        f = getattr(sys.modules.get("__main__"), "set_window_icon_safe", None)
        if f:
            f(win)
    except Exception:
        pass


def _documents_dir():
    d = getattr(sys.modules.get("__main__"), "DOCUMENTS_DIR", None)
    if not d:
        d = os.path.join(os.path.expanduser("~"), "Documents", "A2R_Reports")
    os.makedirs(d, exist_ok=True)
    return d


def _appdata_dir():
    d = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "A2R")
    os.makedirs(d, exist_ok=True)
    return d


def _open_path(p):
    try:
        if not p or not os.path.exists(p):
            messagebox.showinfo("A2R", "الملف أو المكان ده مش موجود.")
            return
        if sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except Exception as e:
        messagebox.showerror("A2R", str(e))


def _lang():
    return getattr(sys.modules.get("__main__"), "CURRENT_LANG", "en")


def _L(ar, en):
    return ar if _lang() == "ar" else en


def _settings_path():
    return os.path.join(_appdata_dir(), "pos_settings.json")


def _load_settings():
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_setting(k, v):
    try:
        d = _load_settings()
        d[k] = v
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _reveal(p):
    """يفتح مكان الملف في الإكسبلورر ويحدد الملف (أو يفتح الفولدر لو الملف مش موجود)."""
    try:
        if p and os.path.isfile(p) and sys.platform == "win32":
            subprocess.Popen(["explorer", "/select," + os.path.normpath(p)])
        elif p and os.path.isdir(p):
            _open_path(p)
        elif p and os.path.isdir(os.path.dirname(p)):
            _open_path(os.path.dirname(p))
        else:
            messagebox.showinfo("A2R", "المكان ده لسه مش موجود.")
    except Exception as e:
        messagebox.showerror("A2R", str(e))


def _newest(folder, ext):
    try:
        c = [os.path.join(folder, f) for f in os.listdir(folder)
             if f.lower().endswith(ext) and not f.startswith("~")]
        return max(c, key=os.path.getmtime) if c else None
    except Exception:
        return None


def _fixes_path():
    return os.path.join(_appdata_dir(), "pos_fixes.json")


def _load_fixes():
    try:
        with open(_fixes_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_fix(key, tid, val):
    if not key:
        return
    d = _load_fixes()
    d[key] = {"val": val, "tid": tid}
    try:
        with open(_fixes_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def _terminal_choices():
    return ["— غير محدد —"] + [E.terminal_label(k) for k, _ in sorted(E.TERMINALS.items(), key=lambda kv: kv[1].order)]


def _tid_from_choice(s):
    m = re.search(r"\((\d{8})\)", s or "")
    return m.group(1) if m else None


def _style_tree(theme):
    st = ttk.Style()
    name = "A2RPos.Treeview"
    st.configure(name, background=theme["card"], fieldbackground=theme["card"], foreground=theme["text"],
                 rowheight=26, borderwidth=0, font=(_font(), 10))
    st.configure(name + ".Heading", font=(_font(), 10, "bold"))
    st.map(name, background=[("selected", theme["primary"])], foreground=[("selected", "#FFFFFF")])
    return name


class _Modal(ctk.CTkToplevel):
    def __init__(self, parent, title, w, h):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        _icon(self)
        self.t = _theme(parent)
        self.configure(fg_color=self.t["bg"])
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))
        except Exception:
            pass
        try:
            self.transient(parent)
        except Exception:
            pass
        self.after(120, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass


# ───────────────────────── نافذة الباسورد ─────────────────────────
class PosPasswordDialog(_Modal):
    def __init__(self, parent, feature_title, on_success):
        super().__init__(parent, "A2R - صلاحية المشرف", 380, 230)
        self.on_success = on_success
        t, F = self.t, _font()
        ctk.CTkLabel(self, text="🔐 " + feature_title, font=(F, 15, "bold"), text_color=t["accent"]).pack(pady=(14, 2))
        ctk.CTkLabel(self, text="اكتب كلمة المرور الخاصة بالأدوات", font=(F, 10, "bold"),
                     text_color=t["muted"]).pack(pady=(0, 8))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=26)
        self.e = ctk.CTkEntry(row, show="•", justify="center", font=(F, 13, "bold"), fg_color=t["input"],
                              border_color=t["border"], text_color=t["text"])
        self.e.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.e.bind("<Return>", lambda ev: self.check())
        self._vis = False
        self.eye = ctk.CTkButton(row, text="👁️", width=36, fg_color=t["card"], text_color=t["text"],
                                 command=self.toggle)
        self.eye.pack(side="right")
        self.err = ctk.CTkLabel(self, text="", font=(F, 10, "bold"), text_color=t["danger"], wraplength=330)
        self.err.pack(pady=(6, 0))
        ctk.CTkButton(self, text="فتح", font=(F, 12, "bold"), fg_color=t["primary"], hover_color=t["hover"],
                      command=self.check).pack(fill="x", padx=26, pady=(8, 4))
        self.after(200, self.e.focus_set)
        self._tick()

    def toggle(self):
        self._vis = not self._vis
        self.e.configure(show="" if self._vis else "•")
        self.eye.configure(text="🙈" if self._vis else "👁️")

    def _tick(self):
        try:
            rem = _lock_remaining()
            if rem > 0:
                self.err.configure(text="تم القفل مؤقتاً بسبب محاولات خاطئة. حاول بعد %d ثانية." % rem)
                self.after(1000, self._tick)
        except tk.TclError:
            pass

    def check(self):
        rem = _lock_remaining()
        if rem > 0:
            self._tick()
            return
        if verify_pos_password(self.e.get()):
            _register_ok()
            cb = self.on_success
            self.destroy()
            cb()
            return
        _register_fail()
        self.e.delete(0, "end")
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass
        rem = _lock_remaining()
        self.err.configure(text=("كلمة المرور غير صحيحة. اتقفل مؤقتاً %d ثانية." % rem) if rem else
                           "كلمة المرور غير صحيحة!")
        if rem:
            self._tick()


# ───────────────────────── عامل خلفي ─────────────────────────
class _Job:
    def __init__(self, fn):
        self.q = queue.Queue()
        self.stop_ev = threading.Event()
        self.fn = fn
        self.th = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            self.q.put(("done", self.fn(self)))
        except E.OcrUnavailable as e:
            self.q.put(("error", str(e)))
        except Exception as e:
            logging.exception("pos job")
            self.q.put(("error", "%s: %s" % (type(e).__name__, e)))

    def progress(self, frac, text):
        self.q.put(("progress", frac, text))

    def start(self):
        self.th.start()


class _FeatureWindow(ctk.CTkToplevel):
    """أساس نافذتي الفكرتين: اختيار المصدر (مجلد أو ملفات) كل مرة، تقدّم، وجدول نتائج."""
    TITLE = ""

    def __init__(self, parent, w, h):
        super().__init__(parent)
        self.parent = parent
        self.t = _theme(parent)
        self.F = _font()
        self.title("A2R - %s  %s" % (self.TITLE, TOOLS_VERSION))
        _icon(self)
        self.configure(fg_color=self.t["bg"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(w, int(sw * 0.86)), min(h, int(sh * 0.80))
        self.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 4)))
        self.minsize(720, 460)
        self.sources = []
        self.recursive = tk.BooleanVar(value=False)
        self.job = None
        self.workdir = tempfile.mkdtemp(prefix="a2r_pos_")
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        if self.job:
            self.job.stop_ev.set()
        shutil.rmtree(self.workdir, ignore_errors=True)
        self.destroy()

    # --- عناصر مشتركة
    def _btn(self, parent, text, cmd, color=None, w=None, **kw):
        t = self.t
        col, hov = color or t["primary"], t["hover"]
        if col == t["success"]:          # الأخضر الفسفوري بيتبدل بأخضر غامق عشان الكتابة تبان
            col, hov = _GREEN, _GREEN_H
        elif col == t["warning"]:        # نفس الفكرة للأصفر/البرتقالي
            col, hov = _AMBER, _AMBER_H
        elif col == t["card"]:           # الأزرار العادية: رمادي-أزرق واضح على الخلفية
            col, hov = _SLATE, _SLATE_H
        kw.setdefault("height", 32)
        return ctk.CTkButton(parent, text=text, command=cmd, font=(self.F, 11, "bold"),
                             fg_color=col, hover_color=hov, text_color="#FFFFFF",
                             text_color_disabled="#CBD5E1", width=w or 120, **kw)

    def _build_source_bar(self, parent):
        t, F = self.t, self.F
        bar = ctk.CTkFrame(parent, fg_color=t["card"], border_color=t["border"], border_width=1)
        bar.pack(fill="x", padx=12, pady=(8, 4))
        r = ctk.CTkFrame(bar, fg_color="transparent")
        r.pack(fill="x", padx=8, pady=6)
        self._btn(r, "📁 اختيار مجلد", self.pick_folder, w=125).pack(side="right", padx=4)
        self._btn(r, "🗂️ اختيار ملفات", self.pick_files, w=125).pack(side="right", padx=4)
        ctk.CTkCheckBox(r, text="يشمل المجلدات الفرعية", variable=self.recursive, font=(F, 10),
                        text_color=t["text"]).pack(side="right", padx=10)
        self.lbl_src = ctk.CTkLabel(r, text="لم يتم اختيار مصدر بعد", font=(F, 11, "bold"),
                                    text_color=t["muted"], anchor="w", justify="left")
        self.lbl_src.pack(side="left", fill="x", expand=True)

    def _src_summary(self):
        imgs, pdfs = E.expand_sources(self.sources, self.recursive.get())
        self._imgs, self._pdfs = imgs, pdfs
        self.lbl_src.configure(
            text="%d صورة + %d ملف PDF" % (len(imgs), len(pdfs)) + ("" if (imgs or pdfs) else "  ⚠️ مفيش حاجة مناسبة"),
            text_color=self.t["success"] if (imgs or pdfs) else self.t["warning"])

    def pick_folder(self):
        d = filedialog.askdirectory(parent=self, title="اختار المجلد اللي فيه الصور أو ملفات PDF")
        if d:
            self.sources = [d]
            self._src_summary()

    def pick_files(self):
        fs = filedialog.askopenfilenames(
            parent=self, title="اختار صور أو ملفات PDF",
            filetypes=[("صور و PDF", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.pdf"),
                       ("صور", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("PDF", "*.pdf"),
                       ("كل الملفات", "*.*")])
        if fs:
            self.sources = list(fs)
            self._src_summary()

    def _build_progress(self, parent):
        t, F = self.t, self.F
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        fr.pack(fill="x", padx=12, pady=2)
        self.btn_start = self._btn(fr, "▶ بدء القراءة", self.start, color=t["success"], w=130)
        self.btn_start.pack(side="right", padx=4)
        self.btn_stop = self._btn(fr, "⏹ إيقاف", self.stop, color=t["danger"], w=85, state="disabled")
        self.btn_stop.pack(side="right", padx=4)
        self.bar = ctk.CTkProgressBar(fr, progress_color=t["accent"])
        self.bar.set(0)
        self.bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.lbl_status = ctk.CTkLabel(parent, text="", font=(F, 10, "bold"), text_color=t["muted"], anchor="w",
                                       justify="left", wraplength=700)
        self.lbl_status.pack(fill="x", padx=14, pady=(0, 2))

    def _tree(self, parent, columns, widths, height=10):
        name = _style_tree(self.t)
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        fr.pack(fill="both", expand=True, padx=12, pady=4)
        tv = ttk.Treeview(fr, columns=[c for c, _ in columns], show="headings", style=name, height=height,
                          selectmode="browse")
        for (cid, title), wd in zip(columns, widths):
            tv.heading(cid, text=title)
            tv.column(cid, width=wd, anchor="center", stretch=(cid in ("file", "status", "name")))
        sb = ttk.Scrollbar(fr, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tv.tag_configure("ok", foreground=self.t["success"])
        tv.tag_configure("warn", foreground=self.t["warning"])
        tv.tag_configure("skip", foreground=self.t["muted"])
        return tv

    def stop(self):
        if self.job:
            self.job.stop_ev.set()
            self.lbl_status.configure(text="جاري الإيقاف بعد العملية الحالية...")

    def _set_busy(self, busy):
        self.btn_start.configure(state="disabled" if busy else "normal")
        self.btn_stop.configure(state="normal" if busy else "disabled")

    def _run_job(self, fn, on_done):
        self._set_busy(True)
        self.bar.set(0)
        self.job = _Job(fn)
        self.job.start()
        self._poll(on_done)

    def _poll(self, on_done):
        job = self.job
        try:
            while True:
                m = job.q.get_nowait()
                if m[0] == "progress":
                    self.bar.set(max(0.0, min(1.0, m[1])))
                    self.lbl_status.configure(text=m[2], text_color=self.t["muted"])
                elif m[0] == "error":
                    self._set_busy(False)
                    self.lbl_status.configure(text="⚠️ " + m[1], text_color=self.t["danger"])
                    messagebox.showerror("A2R", m[1], parent=self)
                    return
                else:
                    self._set_busy(False)
                    self.bar.set(1)
                    on_done(m[1])
                    return
        except queue.Empty:
            pass
        except tk.TclError:
            return
        self.after(150, lambda: self._poll(on_done))

    def start(self):
        raise NotImplementedError


# ───────────────────────── التقفيل ─────────────────────────
class _ReceiptViewer(ctk.CTkToplevel):
    """نافذة واحدة: عرض الإيصال (زوم بالعجلة أو بالضغط على أي جزء) + تعديل الماكينة والمبلغ."""

    MIN_Z, MAX_Z = 0.1, 8.0

    def __init__(self, parent, item, on_save=None):
        super().__init__(parent)
        self.item, self.on_save = item, on_save
        from PIL import Image as _Img, ImageTk as _ImgTk
        self._Img, self._ImgTk = _Img, _ImgTk
        t, F = _theme(parent), _font()
        self.t = t
        self.title("A2R - %s" % item.label)
        _icon(self)
        self.configure(fg_color=t["bg"])
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        mw, mh = min(760, int(sw * 0.55)), int(sh * 0.86)
        self.geometry("%dx%d+%d+%d" % (mw, mh, max(0, sw - mw - 40), 30))
        self.minsize(420, 380)
        info = "%s  |  %s  |  المبلغ المقروء: %s" % (
            item.label, E.terminal_label(item.tid) if item.tid else "ماكينة غير محددة",
            "%.2f" % item.amount if item.amount else "—")
        info_lbl = ctk.CTkLabel(self, text=info, font=(F, 11, "bold"), text_color=t["accent"], wraplength=mw - 20)
        info_lbl.pack(pady=(6, 2))
        self._info_w = mw - 20

        # الصور المتاحة: الإيصال المقصوص + الصورة الكاملة (لو مختلفين)
        self._srcs = []
        try:
            if item.crop is not None:
                self._srcs.append(("الإيصال", item.crop.copy().convert("RGB")))
            if item.image is not None and (item.crop is None or item.image.size != item.crop.size):
                self._srcs.append(("الصورة الكاملة", item.image.copy().convert("RGB")))
        except Exception:
            pass
        self._src_i = 0
        self._zoom, self._fit, self._ox, self._oy, self._iw, self._ih = 1.0, True, 0, 0, 1, 1
        self._photo = None
        self._tot_w = self._tot_h = 1

        tb = ctk.CTkFrame(self, fg_color="transparent")
        tb.pack(fill="x", padx=8, pady=2)
        tb.grid_columnconfigure(tuple(range(6)), weight=1, uniform="v")

        def vb(col, text, cmd, color=_SLATE):
            b = ctk.CTkButton(tb, text=text, command=cmd, height=30, font=(F, 11, "bold"), fg_color=color,
                              hover_color=_SLATE_H, text_color="#FFFFFF")
            b.grid(row=0, column=col, padx=2, sticky="ew")
            return b

        vb(0, "➕ تكبير", lambda: self._step(1.25), "#0369A1")
        vb(1, "➖ تصغير", lambda: self._step(0.8), "#0369A1")
        vb(2, "⛶ مناسب", self.fit)
        vb(3, "1:1 أصلي", lambda: self._set_zoom(1.0))
        vb(4, "↻ تدوير", self.rotate)
        self.b_swap = vb(5, "🔀 " + (self._srcs[1][0] if len(self._srcs) > 1 else "—"), self.swap)
        if len(self._srcs) < 2:
            self.b_swap.configure(state="disabled")
        self.lbl_zoom = ctk.CTkLabel(self, text="", font=(F, 10, "bold"), text_color=t["muted"])
        self.lbl_zoom.pack()

        # --- التعديل (في نفس النافذة)
        self.lbl_info = info_lbl
        ed = ctk.CTkFrame(self, fg_color=t["card"], border_color=t["border"], border_width=1)
        ed.pack(fill="x", padx=8, pady=(2, 4))
        row = ctk.CTkFrame(ed, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(row, text="💾 حفظ", width=80, height=30, font=(F, 11, "bold"), fg_color=_GREEN,
                      hover_color=_GREEN_H, text_color="#FFFFFF", command=self._save).pack(side="left", padx=2)
        self.e_amt = ctk.CTkEntry(row, justify="center", width=100, font=(F, 12, "bold"))
        self.e_amt.pack(side="right", padx=4)
        self.e_amt.insert(0, "%.2f" % item.amount if item.amount else "")
        ctk.CTkLabel(row, text="المبلغ:", font=(F, 11, "bold"), text_color=t["text"]).pack(side="right", padx=2)
        self.cb = ttk.Combobox(row, values=_terminal_choices(), state="readonly", width=26, justify="right")
        self.cb.pack(side="right", padx=4)
        cur = E.terminal_label(item.tid) if item.tid else "— غير محدد —"
        self.cb.set(cur if cur in self.cb["values"] else "— غير محدد —")
        ctk.CTkLabel(row, text="الماكينة:", font=(F, 11, "bold"), text_color=t["text"]).pack(side="right", padx=2)
        self.e_amt.bind("<Return>", lambda e: self._save())
        self.lbl_msg = ctk.CTkLabel(ed, text="", font=(F, 10, "bold"), text_color=t["danger"])
        self.lbl_msg.pack(pady=(0, 4))

        fr = tk.Frame(self, bg=t["bg"])
        fr.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        fr.grid_rowconfigure(0, weight=1)
        fr.grid_columnconfigure(0, weight=1)
        self.cv = tk.Canvas(fr, bg="#0B1220", highlightthickness=0, cursor="fleur")
        vs = ttk.Scrollbar(fr, orient="vertical", command=self.cv.yview)
        hs = ttk.Scrollbar(fr, orient="horizontal", command=self.cv.xview)
        self.cv.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        self.cv.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self._img_id = self.cv.create_image(0, 0, anchor="nw")

        self.cv.bind("<Configure>", lambda e: self._on_resize())
        self._press = None
        self._moved = False
        self.cv.bind("<ButtonPress-1>", self._on_press)
        self.cv.bind("<B1-Motion>", self._on_drag)
        self.cv.bind("<ButtonRelease-1>", self._on_release)
        self.cv.bind("<Button-3>", lambda e: self._set_zoom(self._zoom / 1.6, e.x, e.y))
        self.cv.bind("<MouseWheel>", self._wheel_zoom)          # العجلة = زوم إن / أوت
        self.cv.bind("<Button-4>", self._wheel_zoom)            # لينكس
        self.cv.bind("<Button-5>", self._wheel_zoom)
        self.cv.bind("<Shift-MouseWheel>", lambda e: self.cv.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<KeyPress-plus>", lambda e: self._step(1.25))
        self.bind("<KeyPress-equal>", lambda e: self._step(1.25))
        self.bind("<KeyPress-minus>", lambda e: self._step(0.8))
        self.bind("<Control-Key-0>", lambda e: self.fit())
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass
        if not self._srcs:
            ctk.CTkLabel(self, text="مش قادر أعرض الصورة", text_color=t["danger"]).pack(pady=20)
        self.after(80, self.fit)

    # --- أدوات
    def _src(self):
        return self._srcs[self._src_i][1] if self._srcs else None

    def _max_z(self):
        im = self._src()
        if im is None:
            return self.MAX_Z
        return max(1.0, min(self.MAX_Z, (30e6 / max(1, im.width * im.height)) ** 0.5))

    def _cw(self):
        return max(50, self.cv.winfo_width())

    def _ch(self):
        return max(50, self.cv.winfo_height())

    def _on_resize(self):
        if self._fit:
            self.fit()
        else:
            self._render()

    def fit(self):
        im = self._src()
        if im is None:
            return
        z = min(self._cw() / im.width, self._ch() / im.height)
        self._fit = True
        self._zoom = max(self.MIN_Z, min(self._max_z(), z))
        self._render()

    def _step(self, f):
        self._set_zoom(self._zoom * f)

    def _set_zoom(self, z, ax=None, ay=None):
        im = self._src()
        if im is None:
            return
        z = max(self.MIN_Z, min(self._max_z(), z))
        ax = self._cw() / 2 if ax is None else ax
        ay = self._ch() / 2 if ay is None else ay
        fx = (self.cv.canvasx(ax) - self._ox) / max(1, self._iw)
        fy = (self.cv.canvasy(ay) - self._oy) / max(1, self._ih)
        self._fit = False
        self._zoom = z
        self._render()
        tw, th = self._tot_w, self._tot_h
        nx = self._ox + fx * self._iw - ax
        ny = self._oy + fy * self._ih - ay
        self.cv.xview_moveto(max(0.0, nx) / max(1, tw))
        self.cv.yview_moveto(max(0.0, ny) / max(1, th))

    def _render(self):
        im = self._src()
        if im is None:
            return
        w, h = max(1, int(im.width * self._zoom)), max(1, int(im.height * self._zoom))
        try:
            res = self._Img.LANCZOS if self._zoom < 1 else self._Img.BICUBIC
            disp = im.resize((w, h), res)
            self._photo = self._ImgTk.PhotoImage(disp)
        except Exception:
            return
        self._iw, self._ih = w, h
        self._tot_w, self._tot_h = max(w, self._cw()), max(h, self._ch())
        self._ox, self._oy = (self._tot_w - w) // 2, (self._tot_h - h) // 2
        self.cv.itemconfigure(self._img_id, image=self._photo)
        self.cv.coords(self._img_id, self._ox, self._oy)
        self.cv.configure(scrollregion=(0, 0, self._tot_w, self._tot_h))
        self.lbl_zoom.configure(text="التكبير: %d%%   (عجلة الماوس = زوم • اضغط على أي جزء لتكبيره • كليك يمين = تصغير • اسحب للتحريك)"
                                % round(self._zoom * 100))

    def _on_press(self, e):
        self._press, self._moved = (e.x, e.y), False
        self.cv.scan_mark(e.x, e.y)

    def _on_drag(self, e):
        if self._press and (abs(e.x - self._press[0]) > 4 or abs(e.y - self._press[1]) > 4):
            self._moved = True
        if self._moved:
            self.cv.scan_dragto(e.x, e.y, gain=1)

    def _on_release(self, e):
        # ضغطة من غير سحب = تكبير الجزء اللي اتضغط عليه
        if self._press and not self._moved:
            self._set_zoom(self._zoom * 1.6, e.x, e.y)
        self._press = None

    def _wheel_zoom(self, e):
        up = (getattr(e, "delta", 0) > 0) or getattr(e, "num", 0) == 4
        self._set_zoom(self._zoom * (1.15 if up else 1 / 1.15), e.x, e.y)
        return "break"

    def _save(self):
        tid = _tid_from_choice(self.cb.get())
        try:
            amt = float(self.e_amt.get().replace(",", "").strip())
            if amt <= 0:
                raise ValueError
        except ValueError:
            self.lbl_msg.configure(text="اكتب مبلغ صحيح أكبر من صفر", text_color=self.t["danger"])
            return
        amt = E.round2(amt)
        if self.on_save:
            self.on_save(self.item, tid, amt)
        it = self.item
        self.lbl_info.configure(text="%s  |  %s  |  المبلغ المقروء: %s" % (
            it.label, E.terminal_label(it.tid) if it.tid else "ماكينة غير محددة",
            "%.2f" % it.amount if it.amount else "—"))
        self.lbl_msg.configure(text="✓ تم الحفظ", text_color=self.t["success"])

    def rotate(self):
        if not self._srcs:
            return
        nm, im = self._srcs[self._src_i]
        self._srcs[self._src_i] = (nm, im.rotate(-90, expand=True))
        self.fit()

    def swap(self):
        if len(self._srcs) > 1:
            self._src_i = (self._src_i + 1) % len(self._srcs)
            self.b_swap.configure(text="🔀 " + self._srcs[(self._src_i + 1) % len(self._srcs)][0])
            self.fit()


class ClosingWindow(_FeatureWindow):
    TITLE = "التقفيل"

    def __init__(self, parent):
        super().__init__(parent, 780, 520)
        self.minsize(700, 440)
        t, F = self.t, self.F
        self.raw_all, self.kept, self.warnings, self.outputs = [], [], [], None
        _st = _load_settings()
        self.out_dir = _st.get("closing_out") or os.path.join(_documents_dir(), "Closing")
        self.template = _st.get("closing_template") if os.path.exists(_st.get("closing_template") or "") else None
        ctk.CTkLabel(self, text="📑 التقفيل - قراءة باتشات الماكينات", font=(F, 15, "bold"),
                     text_color=t["accent"]).pack(pady=(8, 0))
        self._build_source_bar(self)
        # سطر معلومات بس (الناتج + القالب) - الأزرار بتاعتهم اتشالت، وفتح مكان الملفات من الشريط اللي تحت
        self.lbl_out = ctk.CTkLabel(self, text="", font=(F, 9), text_color=t["muted"], anchor="w", justify="left",
                                    wraplength=720)
        self.lbl_out.pack(fill="x", padx=16, pady=(0, 2))
        self._refresh_out_label()
        self._build_progress(self)
        # الشريط السفلي والملاحظات الأول (side=bottom) عشان الأزرار ماتختفيش في الشاشات الصغيرة
        bt = ctk.CTkFrame(self, fg_color="transparent")
        bt.pack(side="bottom", fill="x", padx=12, pady=(2, 10))
        self.txt = ctk.CTkTextbox(self, height=70, font=(F, 10), fg_color=t["input"], text_color=t["text"])
        self.txt.pack(side="bottom", fill="x", padx=12, pady=4)
        self.txt.configure(state="disabled")
        cols = [("n", "م"), ("file", "الملف"), ("tid", "الماكينة"), ("unit", "الوحدة"), ("amount", "المبلغ"),
                ("status", "الحالة")]
        self.tv = self._tree(self, cols, [40, 190, 90, 110, 85, 230], height=6)
        self.tv.bind("<Double-1>", lambda e: self.view_selected())
        # أي صف محتاج تأكيد يدوي يظهر بالأحمر (خلفية حمرا فاتحة + كتابة حمرا غامقة)
        self.tv.tag_configure("err", foreground="#B91C1C", background="#FDE2E2")
        self.b_view = self._btn(bt, "🔍 عرض وتعديل", self.view_selected, color=t["warning"], w=10)
        self.b_rebuild = self._btn(bt, "🔄 إعادة بناء", self.rebuild, w=10)
        self.b_folder = self._btn(bt, "📂 مكان الملفات", self.show_folder, color=t["card"], w=10)
        self.b_pdf = self._btn(bt, "📄 فتح الـ PDF", lambda: self._open_out("pdf"), color=t["success"], w=10)
        self.b_xlsx = self._btn(bt, "📊 فتح الإكسيل", lambda: self._open_out("xlsx"), color=t["success"], w=10)
        # صف واحد، أعمدة متساوية، مرتبين من اليمين لليسار
        bt.grid_columnconfigure(tuple(range(5)), weight=1, uniform="cb")
        for i, b in enumerate((self.b_view, self.b_rebuild, self.b_folder, self.b_pdf, self.b_xlsx)):
            b.grid(row=0, column=4 - i, padx=3, sticky="ew")

    def _refresh_out_label(self):
        tpl = self.template or E.find_template([self.out_dir])
        self._tpl_eff = tpl
        self.lbl_out.configure(text="الناتج: %s   |   القالب: %s" % (
            self.out_dir, tpl if tpl else "مش موجود - هيتعمل إكسيل بسيط بنفس الترتيب"))

    def pick_out(self):
        d = filedialog.askdirectory(parent=self, title="اختار مكان حفظ الناتج")
        if d:
            self.out_dir = d
            _save_setting("closing_out", d)
            self._refresh_out_label()

    def pick_template(self):
        f = filedialog.askopenfilename(parent=self, title="اختار قالب الإكسيل (الاسكندريه 00.xlsx)",
                                       filetypes=[("Excel", "*.xlsx")])
        if f:
            self.template = f
            _save_setting("closing_template", f)
            self._refresh_out_label()

    def _out_file(self, kind):
        p = (self.outputs or {}).get(kind)
        if p and os.path.exists(p):
            return p
        return _newest(self.out_dir, ".pdf" if kind == "pdf" else ".xlsx")

    def _open_out(self, kind):
        p = self._out_file(kind)
        if not p:
            messagebox.showinfo("A2R", "لسه ما اتعملش ملف. اضغط «بدء القراءة» الأول.", parent=self)
            return
        _open_path(p)

    def show_folder(self):
        """بيفتح فولدر الملفات اللي اتغيّر اسمها بعد التسمية (raw_images: رقم الماكينة.jpg)."""
        raw = os.path.join(self.out_dir, "raw_images")
        if os.path.isdir(raw):
            _open_path(raw)
        else:
            messagebox.showinfo("A2R", "لسه ما فيش ملفات متسمّاة. اضغط «بدء القراءة» الأول.", parent=self)

    def view_selected(self):
        sel = self.tv.selection()
        item = self._iid.get(sel[0]) if sel and getattr(self, "_iid", None) else None
        if item is None:
            messagebox.showinfo("A2R", "اختار صف الأول.", parent=self)
            return
        try:
            if getattr(self, "_viewer", None) is not None and self._viewer.winfo_exists():
                self._viewer.destroy()
        except Exception:
            pass
        self._viewer = _ReceiptViewer(self, item, on_save=self.apply_edit)

    # --- التشغيل
    def start(self):
        self._src_summary()
        if not (self._imgs or self._pdfs):
            messagebox.showwarning("A2R", "اختار مجلد أو ملفات صور / PDF الأول.", parent=self)
            return
        ok, msg = E.ocr_ready()
        if not ok:
            messagebox.showerror("A2R", msg, parent=self)
            return
        imgs, pdfs, out_dir, tpl = self._imgs, self._pdfs, self.out_dir, self._tpl_eff
        fixes = _load_fixes()
        wd = self.workdir

        def job(j):
            kept, excl, warns, raw = E.process_closing(
                imgs, pdfs, wd, progress=lambda f, m: j.progress(f, m), stop=j.stop_ev.is_set, fixes=fixes)
            outs = None
            if kept and not j.stop_ev.is_set():
                j.progress(0.93, "بناء ملفات الـ PDF والإكسيل...")
                outs = E.build_closing_out
