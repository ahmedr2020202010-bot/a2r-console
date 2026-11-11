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
import queue
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

APP_VERSION = "v60"
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
import threading
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

ENGINE_VERSION = "60"

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
        self.txn = None     # عدد معاملات الباتش (من إيصال الإقفال)


def analyze_lines(all_lines):
    pieces = split_columns(all_lines)
    multi = len(pieces) > 1
    all_texts, batches, seen = [], [], set()
    txns = []
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
        txns.append(batch_txn_of(r.texts))
        all_ok = all_ok and r.ok
    total = round2(sum(batches))
    ok = all_ok and bool(batches)
    if multi and not ok:
        r = ocr_piece(all_lines)
        all_texts.extend(r.texts)
        if r.val > 0 and (r.ok or not batches):
            total, ok, batches = r.val, r.ok, [r.val]
            txns = [batch_txn_of(r.texts)]
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
    a.txn = sum(txns) if (txns and all(t is not None for t in txns)) else None
    return a


def merge_second_read(a, b):
    """بيدمج القراءة التانية في الأولى. يرجّع قيمة تانية متعارضة (للمراجعة) أو None."""
    if a.tid is None and b.tid is not None:
        a.tid, a.row, a.unit, a.how = b.tid, b.row, b.unit, b.how
    elif a.row is None and b.row is not None:
        a.row, a.unit, a.how = b.row, b.unit, b.how
    if a.date is None:
        a.date = b.date
    if a.txn is None:
        a.txn = b.txn
    if b.val <= 0:
        return None
    if a.val <= 0:
        a.val, a.ok, a.batches = b.val, b.ok, list(b.batches)
        a.txn = b.txn if b.txn is not None else a.txn
        return None
    if abs(a.val - b.val) < 0.005:
        a.ok = a.ok or b.ok
        return None
    if (not a.ok) and b.ok:
        a.val, a.ok, a.batches = b.val, True, list(b.batches)
        a.txn = b.txn if b.txn is not None else a.txn
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


# ───────────────────────── إيصالات الدفع: نفس طريقة تطبيق الموبايل ─────────────────────────
# الفكرة (منقولة من التطبيق):
#  1) كل صفحة بتتقرا مرة واحدة (الصورة الأصلية جوه الـ PDF الممسوح من غير تحويل) على شرائح مضبوطة.
#  2) العدد = عدّ بالهيكل (لوجو + TERMINAL + RRN + AMOUNT + APPROVED) في كل عمود.
#  3) أوراق التعريف الصغيرة (اسم + TID + تاريخ) بتتجاهل، وإيصالات الإقفال/الملخص مش بتتعد.
#  4) مراجعة بتسلسل أرقام RRN + تاريخ كل إيصال + مقارنة بعدد معاملات الباتش من التقفيل.

CLOSING_TXN = {}   # رقم الماكينة -> عدد معاملات الباتش (من إيصالات الإقفال في التقفيل)


def publish_closing_txn(items):
    """بيحفظ عدد معاملات الباتش لكل ماكينة (من التقفيل) علشان إيصالات الدفع تقارنه بالعدد الفعلي."""
    sums, bad = {}, set()
    for it in items:
        if getattr(it, "skip", False):
            continue
        n = getattr(it, "order", None) or (TERMINALS[it.tid].order if getattr(it, "tid", None) in TERMINALS else None)
        if n is None:
            continue
        t = getattr(it, "txn", None)
        if t is None:
            bad.add(n)
            continue
        sums[n] = sums.get(n, 0) + t
    for n in bad:
        sums.pop(n, None)
    CLOSING_TXN.clear()
    CLOSING_TXN.update(sums)
    return sums


def _txn_num(s):
    t = s.strip().replace("O", "0").replace("o", "0")
    t = re.sub(r"[Il|]", "1", t)
    try:
        return int(t)
    except ValueError:
        return None


def batch_txn_of(texts):
    """عدد معاملات الباتش من إيصال الإقفال: GRAND TOTALS / Sale (010) (ولو مجموع الكروت بيتطابق معاه)."""
    grand_re = re.compile(r"GRAND|TOTALS", re.I)
    paren = re.compile(r"\(\s*([0-9OoIl|]{1,5})\s*\)")
    tot_re = re.compile(r"TOTAL(?!\s*NET)[^()\n]{0,12}\(\s*([0-9OoIl|]{1,5})\s*\)", re.I)
    grands, sums = [], []
    for raw in texts:
        gm = grand_re.search(raw)
        if gm:
            m = paren.search(raw[gm.start():])
            v = _txn_num(m.group(1)) if m else None
            if v is not None and 0 < v < 100000:
                grands.append(v)
        pre = raw[:gm.start()] if gm else raw
        s, n = 0, 0
        for m in tot_re.finditer(pre):
            v = _txn_num(m.group(1))
            if v is not None:
                s += v
                n += 1
        if n > 0 and s > 0:
            sums.append(s)
    g = most_common(grands)[0] if grands else None
    s = most_common(sums)[0] if sums else None
    if g is not None and s is not None and g != s:
        return None          # القراءتين متعارضتين: الأفضل تتكتب بإيدك
    return g if g is not None else s


# ───────────── قراءة الصفحة (RapidOCR أولاً، Tesseract بديل) ─────────────
_RAPID = {"eng": None, "tried": False}
_RAPID_LOCK = threading.Lock()
_TILE_MAX = 1900     # RapidOCR بيصغّر أي صورة أكبر من ~2000 بكسل، فالصفحة بتتقسم بلاطات أصغر من كده


def _rapid():
    if not _RAPID["tried"]:
        _RAPID["tried"] = True
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID["eng"] = RapidOCR()
        except Exception:
            _RAPID["eng"] = None
    return _RAPID["eng"]


def pay_ocr_ready():
    """(ok, message): إيصالات الدفع بتشتغل بـ RapidOCR أو Tesseract (أي واحد منهم)."""
    if _rapid() is not None or find_tesseract():
        return True, ""
    return False, "مفيش محرك OCR: لا RapidOCR ولا Tesseract. اتأكد إن البرنامج اتبنى بالمكتبات كاملة."


def _ocr_image_lines(im, scale=1.0, dx=0.0, dy=0.0):
    """OCR لصورة واحدة -> OcrLine بإحداثيات الصفحة الأصلية."""
    out = []
    eng = _rapid()
    if eng is not None and np is not None:
        with _RAPID_LOCK:
            res = eng(np.array(im.convert("RGB")))
        items = (res[0] if isinstance(res, (tuple, list)) else None) or []
        for box, txt, _sc in items:
            t = str(txt).strip()
            if not t:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            out.append(OcrLine(t, dx + min(xs) / scale, dx + max(xs) / scale,
                               dy + min(ys) / scale, dy + max(ys) / scale))
        return out
    for l in tess_lines(im.convert("L"), 6):
        out.append(OcrLine(l.text, dx + l.left / scale, dx + l.right / scale,
                           dy + l.top / scale, dy + l.bottom / scale))
    return out


def _tile_boxes(w, h, cols=5, max_tile=_TILE_MAX):
    cw = w / float(cols)
    rows = max(1, int(math.ceil(h / float(max_tile))))
    rh = h / float(rows)
    boxes = []
    for i in range(cols):
        x0 = max(0, int(i * cw - cw * 0.12))
        x1 = min(w, int((i + 1) * cw + cw * 0.12))
        for j in range(rows):
            y0 = max(0, int(j * rh - rh * 0.06))
            y1 = min(h, int((j + 1) * rh + rh * 0.06))
            boxes.append((x0, y0, x1, y1))
    return boxes


def _merge_lines(lines):
    """نفس السطر اتقرا من بلاطتين متداخلتين: يفضل مرة واحدة (الأطول)."""
    out = []
    for l in sorted(lines, key=lambda x: (x.cy, x.left)):
        dup = None
        for k in range(len(out) - 1, max(-1, len(out) - 80), -1):
            o = out[k]
            if abs(o.cy - l.cy) > max(o.h, l.h, 1.0) * 0.7:
                break
            ov = min(o.right, l.right) - max(o.left, l.left)
            if ov > 0 and ov >= 0.6 * min(o.right - o.left, l.right - l.left):
                dup = k
                break
        if dup is None:
            out.append(l)
        elif len(l.text) > len(out[dup].text):
            out[dup] = l
    return out


def read_page(im, mode="fast"):
    """يرجّع (w, h, lines). fast = بلاطات بالدقة الأصلية. accurate = الصفحة كلها + بلاطات مكبّرة 1.5x."""
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    lines = []
    f = 1.5 if mode == "accurate" else 1.0
    if mode == "accurate":
        s = min(1.0, float(_TILE_MAX) / max(w, h))
        small = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS) if s < 1.0 else im
        lines += _ocr_image_lines(small, s)
    for (x0, y0, x1, y1) in _tile_boxes(w, h, max_tile=_TILE_MAX / f):
        tile = im.crop((x0, y0, x1, y1))
        if f != 1.0:
            tile = tile.resize((int(tile.width * f), int(tile.height * f)), Image.LANCZOS)
        lines += _ocr_image_lines(tile, f, x0, y0)
    return w, h, _merge_lines(lines)


def _page_text(lines, w):
    """نص الصفحة مرتب عمود عمود (كل عمود = إيصالات فوق بعض)."""
    cw = max(1.0, w / 5.0)
    ls = sorted(lines, key=lambda l: (int(((l.left + l.right) / 2.0) / cw), l.cy))
    return "\n".join(l.text for l in ls)


# ───────────── أوراق التعريف + العد بالهيكل ─────────────
_SLIP_PAY = re.compile(r"TERMINAL|RRN|AMOUNT|APPROVED|NATIONAL|BANK\s*OF\s*EGYPT|BATCH|TOTAL|SALE|GRAND|CARD|REPRINT")


def is_id_slip(lines):
    """ورقة تعريف صغيرة (اسم + وحدة + TID + تاريخ) جوه الملف: مش إيصال دفع فمتتعدّش."""
    if not lines or len(lines) > 16:
        return False
    allt = "\n".join(l.text.upper() for l in lines)
    if _SLIP_PAY.search(allt):
        return False
    if re.search(r"(?<!\d)\d{12}(?!\d)", re.sub(r"[ \t]", "", allt)):
        return False
    if re.search(r"\bT\s?[I1L|]\s?D\b\W{0,4}[\dOo]{7,9}", allt) or re.search(r"\bT\s?[I1L|]\s?D\b", allt):
        return True
    has_date = re.search(r"\d{2}\s?[/.\-]\s?\d{2}\s?[/.\-]\s?20\d{2}", allt)
    return bool(has_date) and len(lines) <= 8 and find_terminal_in([allt]) is not None


_S_NAME = re.compile(r"NATIONAL|BANK\s*OF\s*EGYPT")
_S_RRN = re.compile(r"(?<![A-Z])R{1,2}N\W{0,3}\d")
_S_AMT = re.compile(r"^\s*AMOUNT\b")
_S_AMT_BAD = re.compile(r"FROM|ACCOUNT|CONFIRM|DEBIT|\bMY\b")


def struct_count(lines):
    """عدّ الإيصالات بالهيكل: كل إيصال له لوجو + Terminal + RRN + AMOUNT + Approved (مرة واحدة).
    بنقسم العلامات أعمدة، وفي كل عمود أكتر علامة متكررة = عدد الإيصالات.
    يرجّع dict: sm (عدد الأعمدة)، mx (أكبر نوع علامة)، h."""
    out = {"sm": 0, "mx": 0, "h": 3000.0, "types": {}}
    if not lines:
        return out
    h = max(l.bottom for l in lines)
    w = max(l.right for l in lines)
    out["h"] = h
    marks = []
    for l in lines:
        u = l.text.upper()
        cx = (l.left + l.right) / 2.0
        kinds = []
        if _S_NAME.search(u):
            kinds.append("logo")
        if "TERMINAL" in u:
            kinds.append("term")
        if _S_RRN.search(u):
            kinds.append("rrn")
        if _S_AMT.search(u) and not _S_AMT_BAD.search(u):
            kinds.append("amount")
        if "APPROVED" in u:
            kinds.append("appr")
        for k in kinds:
            marks.append((k, cx, l.cy, l.left, l.right))
    ded = []
    for m in marks:
        dup = False
        for o in ded:
            if o[0] == m[0] and o[3] < m[4] and m[3] < o[4] and abs(o[2] - m[2]) < h * 0.02:
                dup = True
                break
        if not dup:
            ded.append(m)
    for m in ded:
        out["types"][m[0]] = out["types"].get(m[0], 0) + 1
    if not ded:
        return out
    out["mx"] = max(out["types"].values())
    ded.sort(key=lambda m: m[1])
    cols, cur = [], [ded[0]]
    for m in ded[1:]:
        if m[1] - cur[-1][1] > w * 0.07:
            cols.append(cur)
            cur = []
        cur.append(m)
    cols.append(cur)
    n = 0
    for c in cols:
        cnt = {}
        for m in c:
            cnt[m[0]] = cnt.get(m[0], 0) + 1
        n += max(cnt.values())
    out["sm"] = n
    return out


# ───────────── نقاط الارتكاز (RRN) والتسلسل ─────────────
class ScanSummary:
    def __init__(self):
        self.full = 0
        self.partial = 0
        self.rrn_day = {}
        self.non_payment = False
        self.tid = None
        self.day = self.month = None
        self.other_day = []
        self.seq_min = self.seq_max = None
        self.seq_missing = []

    @property
    def count(self):
        return self.full + self.partial

    @property
    def range_len(self):
        return None if self.seq_min is None else self.seq_max - self.seq_min + 1

    @property
    def agree(self):
        return self.range_len is None or self.count == self.range_len

    @property
    def range_text(self):
        if self.seq_min is None:
            return ""
        return " • التسلسل %06d-%06d (%d)" % (self.seq_min, self.seq_max, self.range_len)

    def missing_text(self, k=10):
        miss = "، ".join("%06d" % n for n in self.seq_missing[:k])
        return (" - أرقام مش لاقيها: %s%s" % (miss, " ..." if len(self.seq_missing) > k else "")) if self.seq_missing else ""


class PayCollector:
    def __init__(self):
        self.pages = []
        self.slips = 0
        self.texts = []
        self.page_h = 3000.0

    def new_page(self, h):
        self.pages.append([])
        self.page_h = float(h) if h else 3000.0

    def _add(self, rrn, day, l, r, cy):
        for a in self.pages[-1]:
            if a["l"] < r and l < a["r"] and abs(a["cy"] - cy) < self.page_h * 0.012:
                a["rrn"] = a["rrn"] or rrn
                a["day"] = a["day"] or day
                return
        self.pages[-1].append({"rrn": rrn, "day": day, "l": l, "r": r, "cy": cy})

    def collect(self, lines):
        if not self.pages:
            self.new_page(3000.0)
        self.texts.append("\n".join(l.text for l in lines))
        dates = [l for l in lines if day_key(l.text)]
        for l in lines:
            a = rrn_of(l.text)
            if a is None:
                continue
            day = day_key(l.text)
            if day is None:
                best, bd = None, 1e18
                for d in dates:
                    dy = abs(d.cy - l.cy)
                    if dy > l.h * 5:
                        continue
                    if not (d.left < l.right + 60 and l.left < d.right + 60):
                        continue
                    if dy < bd:
                        bd, best = dy, d
                if best is not None:
                    day = day_key(best.text)
            self._add(None if a == "P" else a, day, l.left, l.right, l.cy)

    def finish(self):
        r = ScanSummary()
        seen, days, partial_days = set(), {}, []
        for a in (x for p in self.pages for x in p):
            if a["rrn"]:
                if a["rrn"] not in seen:
                    seen.add(a["rrn"])
                    r.full += 1
                    r.rrn_day[a["rrn"]] = a["day"]
                    if a["day"]:
                        days[a["day"]] = days.get(a["day"], 0) + 1
            else:
                r.partial += 1
                if a["day"]:
                    partial_days.append(a["day"])
                    days[a["day"]] = days.get(a["day"], 0) + 1
        allt = "\n".join(self.texts)
        r.non_payment = bool(re.search(
            r"GRAND\s*TOTAL|TOTAL\s*NET\s*AMOUNT|BATCH\s*CLOS|SUMMARY|REPRINT|DUPLICATE|SUCCESSF", allt, re.I))
        r.tid = _tid_of_text(allt)
        if not days:
            for m in _DATE_RE.finditer(allt):
                k = day_key(m.group(0))
                if k:
                    days[k] = days.get(k, 0) + 1
        if days:
            best = max(days.items(), key=lambda e: e[1])[0]
            r.day, r.month = best.split(".")
            for rrn, d in r.rrn_day.items():
                if d and d != best:
                    r.other_day.append("إيصال %s بتاريخ %s" % (rrn[6:], d))
            for d in partial_days:
                if d != best:
                    r.other_day.append("إيصال (رقمه مش واضح) بتاريخ %s" % d)
        nums = sorted(int(k[6:]) for k in r.rrn_day)
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
        return r


def _tid_of_text(text):
    """الماكينة: أكتر Terminal ID معروف متكرر في النص."""
    tc = {}
    for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", text):
        c = TID_FIX.get(m.group(1), m.group(1))
        if c in TERMINALS:
            tc[c] = tc.get(c, 0) + 1
    if tc:
        return max(tc.items(), key=lambda e: e[1])[0]
    return find_terminal_in([text]) or find_terminal_fuzzy_in([text], None)


def _day_of_text(text):
    days = {}
    for m in _DATE_RE.finditer(text):
        k = day_key(m.group(0))
        if k:
            days[k] = days.get(k, 0) + 1
    if not days:
        return None, None
    best = max(days.items(), key=lambda e: e[1])[0]
    d, mo = best.split(".")
    return d, mo


def plausible_day(d, m):
    """تاريخ إيصال في المستقبل = قراءة غلط."""
    if not d or not m:
        return True
    try:
        di, mi = int(d), int(m)
    except ValueError:
        return False
    today = datetime.date.today()
    for y in (today.year, today.year - 1):
        try:
            dt = datetime.date(y, mi, di)
        except ValueError:
            continue
        if dt <= today + datetime.timedelta(days=1):
            if y == today.year or (today - dt).days <= 90:
                return True
    return False


# ───────────── مصدر صفحات الـ PDF ─────────────
def pdf_jpeg_pages(path):
    """صور الصفحات الأصلية (JPEG) من PDF ممسوح (CamScanner وغيره): من غير تحويل ولا رسم."""
    try:
        with open(path, "rb") as f:
            b = f.read()
    except OSError:
        return []
    out, pos = [], 0
    while True:
        i = b.find(b"/DCTDecode", pos)
        if i < 0:
            break
        s = b.find(b"stream", i)
        if s < 0:
            break
        st = s + 6
        if b[st:st + 2] == b"\r\n":
            st += 2
        elif b[st:st + 1] in (b"\n", b"\r"):
            st += 1
        e = b.find(b"endstream", st)
        if e < 0:
            break
        en = e
        while en > st and b[en - 1] in (10, 13, 32):
            en -= 1
        if en - st > 20000 and b[st:st + 2] == b"\xff\xd8" and b[en - 2:en] == b"\xff\xd9":
            out.append(b[st:en])
        pos = e + 9
    return out


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


class PageSource:
    """صفحات PDF واحدة واحدة: صورة JPEG الأصلية لو ممسوح، وإلا رسم الصفحة (pdftoppm / pypdfium2)."""

    def __init__(self, pdf, workdir, fast=True, dpi=200):
        self.pdf, self.wd, self.dpi = pdf, workdir, dpi
        self.jpegs = pdf_jpeg_pages(pdf) if fast else []
        self.scanned = bool(self.jpegs)
        self.n = len(self.jpegs) if self.scanned else (_pdf_page_count(pdf) or 0)

    def get(self, i):
        if self.scanned:
            if i >= len(self.jpegs):
                return None
            with Image.open(io.BytesIO(self.jpegs[i])) as t:
                return t.convert("RGB")
        imgs = pdf_to_images(self.pdf, self.wd, dpi=self.dpi, first=i + 1, last=i + 1, max_side=3400)
        if not imgs:
            return None
        try:
            with Image.open(imgs[0]) as t:
                return t.convert("RGB")
        finally:
            for q in imgs:
                try:
                    os.remove(q)
                except OSError:
                    pass


# ───────────── نتيجة ملف إيصالات ─────────────
class PayResult:
    def __init__(self, src):
        self.src = src
        self.name = os.path.basename(src)
        try:
            self.size = os.path.getsize(src)
        except OSError:
            self.size = 0
        self.pages = 0
        self.count = -1             # -1 = لسه ما اتعدّش
        self.tid = None
        self.votes = {}
        self.alt_tids = []
        self.day = self.month = None
        self.new_name = None
        self.out_path = None
        self.seq_min = self.seq_max = None
        self.seq_missing = []
        self.other_day = []
        self.id_notes = []
        self.cnt_notes = []
        self.id_ok = True
        self.cnt_ok = True
        self.detail = ""
        self.verdict = 0            # 0 = لسه ما اتراجعش، 1 = صح، -1 = غلط (مستبعد)
        self.expected = None        # "الصح" بإيدك (عدد الباتش)
        self.n15 = self.n10 = self.last = None
        self.page_counts = []

    key = property(lambda self: "%s:%d" % (self.name, self.size))
    excluded = property(lambda self: self.verdict < 0)
    pending = property(lambda self: self.count < 0 and self.verdict >= 0)
    counted = property(lambda self: self.count >= 0)
    ok = property(lambda self: self.verdict != 0 or (self.id_ok and self.cnt_ok))
    notes = property(lambda self: list(self.id_notes) + list(self.cnt_notes))

    @property
    def order(self):
        return TERMINALS[self.tid].order if self.tid in TERMINALS else 99


def apply_payment_name(results, r, dest_dir):
    """يسمّي ويكوّب الملف باسم الماكينة. لو اسم مكرر من ملف تاني بيزوّد _2."""
    old = r.out_path
    try:
        if (old and os.path.exists(old) and os.path.abspath(old) != os.path.abspath(r.src)
                and os.path.abspath(old).startswith(os.path.abspath(dest_dir))):
            os.remove(old)
    except OSError:
        pass
    r.new_name = r.out_path = None
    miss_t, miss_d = "مش قادر أعرف الماكينة من الـ PDF", "مش قادر أعرف التاريخ من الـ PDF"
    r.id_notes = [n for n in r.id_notes if n not in (miss_t, miss_d)]
    if r.tid not in TERMINALS:
        r.id_ok = False
        r.id_notes.append(miss_t)
        return
    if not r.day or not r.month:
        r.id_ok = False
        r.id_notes.append(miss_d)
        return
    base = machine_new_name(TERMINALS[r.tid], r.day, r.month)
    final, k = base, 2
    while any(x is not r and not x.excluded and x.new_name == final for x in results):
        final = "%s_%d" % (base, k)
        k += 1
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, final + ".pdf")
    if os.path.abspath(dst) != os.path.abspath(r.src):
        shutil.copy2(r.src, dst)
    r.new_name, r.out_path = final, dst


# ───────────── المرحلة 1: تعريف الماكينة واليوم ─────────────
def identify_payment_pdf(pdf, workdir, progress=None, stop=lambda: False, max_probe=25, fast=True):
    """بيقرا صفحات الملف (لحد 6، ولو مفيش ماكينة يكمّل لحد 25) ويصوّت على Terminal ID."""
    r = PayResult(pdf)
    src = PageSource(pdf, workdir, fast)
    r.pages = src.n
    votes, texts = {}, []
    limit = min(max_probe, src.n) if src.n else max_probe
    pi = 0
    while pi < limit:
        if stop():
            break
        if pi >= 6 and votes:
            break
        if progress:
            progress("قراءة رقم الماكينة من صفحة %d" % (pi + 1))
        im = src.get(pi)
        if im is None:
            break
        w, h, lines = read_page(im, "fast")
        txt = _page_text(lines, w)
        texts.append(txt)
        for k, v in tid_votes(txt).items():
            votes[k] = votes.get(k, 0) + v
        pi += 1
        d, _m = _day_of_text("\n".join(texts))
        rk = sorted(votes.items(), key=lambda e: -e[1])
        # وقف بدري لو الماكينة واضحة (Terminal ID مقروء بوضوح) واليوم معروف
        if d and rk and rk[0][1] >= 3 and (len(rk) < 2 or rk[0][1] >= rk[1][1] * 2):
            break
    allt = "\n".join(texts)
    rk = sorted(votes.items(), key=lambda e: -e[1])
    r.alt_tids, r.votes = [k for k, _ in rk], votes
    tid = rk[0][0] if rk else _tid_of_text(allt)
    from_unit = False
    if tid is None:
        row = find_unit_extra_in([allt])
        same = [k for k, v in TERMINALS.items() if v.row == row] if row else []
        if len(same) == 1:
            tid, from_unit = same[0], True
    day, month = _day_of_text(allt)
    top = rk[0][1] if rk else 0.0
    weak = tid is not None and ((not from_unit and top < 2) or not plausible_day(day, month))
    if weak:
        # مش واضح إنه إيصال ماكينة (توكيل / ملف تاني): للمراجعة، من غير تسمية ولا عد
        r.tid = None
        r.day, r.month = day, month
        r.id_ok = False
        r.id_notes.append("الملف ده مش واضح إنه إيصال ماكينة (قراءة ضعيفة للـ Terminal ID)، راجعه")
        r.count = 0
        r.detail = "للمراجعة (مش معدود)"
        return r
    r.tid, r.day, r.month = tid, day, month
    if from_unit:
        r.id_ok = False
        r.id_notes.append("Terminal ID مش واضح، الوحدة اتحددت من Merchant ID/الاسم جوه الـ PDF، راجع")
    return r


def resolve_payment_duplicates(results, dest_dir):
    """لو ملفين اتعرفوا على نفس الماكينة: الأقوى (أكتر أصوات) يفضل، والتاني ياخد مرشحه التاني لو قراءته واضحة."""
    groups = {}
    for r in results:
        if r.tid and r.new_name and not r.excluded:
            groups.setdefault(r.tid, []).append(r)
    for tid, g in groups.items():
        if len(g) < 2:
            continue
        g.sort(key=lambda x: -x.votes.get(tid, 0))
        for r in g[1:]:
            if not os.path.exists(r.src):
                continue
            claimed = set(x.tid for x in results if x.tid)
            alt = None
            for c in r.alt_tids:
                if c == tid or c in claimed:
                    continue
                if r.votes.get(c, 0) >= 1:
                    alt = c
                    break
            if alt is None:
                continue
            r.tid = alt
            apply_payment_name(results, r, dest_dir)
            if r.new_name:
                r.id_ok = False
                r.id_notes.append("الـ PDF اتعرّف على نفس ماكينة ملف تاني، اتسمّى ماكينة %d (المرشح التاني من قراءة الـ PDF)، راجع"
                                  % TERMINALS[alt].order)


def flag_payment_duplicates(results):
    """بيعلّم الملفات اللي لسه واخدة نفس الماكينة (مفيش حل تلقائي)."""
    tag = "نفس الماكينة"
    for r in results:
        had = any(n.startswith(tag) for n in r.id_notes)
        r.id_notes = [n for n in r.id_notes if not n.startswith(tag)]
        if had and not r.id_notes and r.new_name:
            r.id_ok = True
    groups = {}
    for r in results:
        if r.tid and r.new_name and not r.excluded:
            groups.setdefault((r.tid, r.day, r.month), []).append(r)
    for (tid, _d, _m), lst in groups.items():
        if len(lst) < 2:
            continue
        info = TERMINALS.get(tid)
        for r in lst:
            others = " ، ".join(x.name for x in lst if x is not r)
            r.id_ok = False
            r.id_notes.append("%s (%s %s) اتعرفت كمان في: %s — راجع" % (
                tag, info.order if info else "", info.unit if info else "", others))


# ───────────── المرحلة 2: العد ─────────────
def _scan_notes(r, sc, total, slips):
    """ملاحظات المقارنة بين العدد وتسلسل الـ RRN واليوم (نفس رسايل التطبيق)."""
    if sc.range_len is not None and sc.full >= total * 0.8 and total != sc.range_len:
        r.cnt_ok = False
        r.cnt_notes.append("العدد %d بس التسلسل %d%s" % (total, sc.range_len, sc.missing_text()))
    r.seq_min, r.seq_max, r.seq_missing = sc.seq_min, sc.seq_max, list(sc.seq_missing)
    r.other_day = list(sc.other_day)
    if len(sc.other_day) >= 3 and len(sc.other_day) >= total * 0.1:
        r.cnt_ok = False
        r.cnt_notes.append("مش تبع نفس اليوم: " + " ، ".join(sc.other_day[:5]))
    if sc.non_payment:
        r.cnt_notes.append("فيه إيصال إقفال/ملخص/إعادة طباعة (اتجاهل ومش معدود)")
    if r.new_name is None and sc.tid:
        # التعريف فشل: نسمّي من نتيجة العد (الاسم بيتعمل في apply_payment_name)
        r.tid, r.day, r.month = sc.tid, sc.day or r.day, sc.month or r.month
        r.id_ok, r.id_notes = True, []
    elif sc.tid in TERMINALS and r.tid in TERMINALS and TERMINALS[sc.tid].order != TERMINALS[r.tid].order:
        r.cnt_ok = False
        r.cnt_notes.append("العد لقى ماكينة %d بس التسمية ماكينة %d، راجع" % (
            TERMINALS[sc.tid].order, TERMINALS[r.tid].order))


def _count_fast(r, workdir, progress, stop, max_pages):
    """العد السريع: كل صفحة تتقرا مرة واحدة + عدّ بالهيكل. بيرجّع None لو اتوقف، False لو مش نافع."""
    src = PageSource(r.src, workdir, True)
    r.pages = src.n
    col = PayCollector()
    total = total_mx = failed = slips = done = 0
    diff, empty = [], []
    n = min(src.n, max_pages) if src.n else max_pages
    for i in range(n):
        if stop():
            return None
        if progress:
            progress("عدّ صفحة %d من %s" % (i + 1, src.n or "؟"))
        try:
            im = src.get(i)
            if im is None:
                break
            w, h, lines = read_page(im, "fast")
        except OcrUnavailable:
            raise
        except Exception:
            failed += 1
            continue
        done += 1
        if is_id_slip(lines):
            slips += 1
            continue
        sp = struct_count(lines)
        total += sp["sm"]
        total_mx += sp["mx"]
        if sp["sm"] == 0:
            empty.append(i + 1)
        if abs(sp["sm"] - sp["mx"]) >= 2:
            diff.append("%d (%d أو %d)" % (i + 1, sp["sm"], sp["mx"]))
        col.new_page(sp["h"] or h)
        col.collect(lines)
    if total == 0 or done == 0:
        return False
    sc = col.finish()
    r.count = total
    r.detail = "عدّ سريع • %d صفحة • RRN مقروء %d%s%s" % (
        done + failed, sc.full, sc.range_text, (" • أوراق تعريف مُتجاهلة %d" % slips) if slips else "")
    if failed:
        r.cnt_ok = False
        r.cnt_notes.append("%d صفحة فشلت قراءتها، العدد ممكن يكون ناقص" % failed)
    if empty:
        r.cnt_notes.append("صفحات ما لقيتش فيها إيصالات: " + "، ".join(str(x) for x in empty))
    if diff:
        r.cnt_notes.append("صفحات الطريقتين اختلفوا فيها: %s (راجعها لو العدد مهم)" % "، ".join(diff))
    _scan_notes(r, sc, total, slips)
    return True


def _count_accurate(r, workdir, progress, stop, max_pages):
    """العد الدقيق (أبطأ): الصفحة كلها + بلاطات مكبّرة، والعدد = عدد نقاط الارتكاز (RRN)."""
    src = PageSource(r.src, workdir, True)
    r.pages = src.n
    col = PayCollector()
    done = failed = 0
    n = min(src.n, max_pages) if src.n else max_pages
    for i in range(n):
        if stop():
            return None
        if progress:
            progress("عدّ دقيق: صفحة %d من %s" % (i + 1, src.n or "؟"))
        try:
            im = src.get(i)
            if im is None:
                break
            w, h, lines = read_page(im, "accurate")
        except OcrUnavailable:
            raise
        except Exception:
            failed += 1
            continue
        done += 1
        if is_id_slip(lines):
            col.slips += 1
            continue
        col.new_page(max([l.bottom for l in lines] or [h]))
        col.collect(lines)
    if done == 0:
        r.count = 0
        r.cnt_ok = False
        r.cnt_notes.append("فشل العد")
        return True
    sc = col.finish()
    r.count = sc.count
    r.detail = "عدّ دقيق • RRN كامل %d • ناقص القراءة %d%s%s" % (
        sc.full, sc.partial, sc.range_text, (" • أوراق تعريف مُتجاهلة %d" % col.slips) if col.slips else "")
    if failed:
        r.cnt_ok = False
        r.cnt_notes.append("%d صفحة فشلت قراءتها، العدد ممكن يكون ناقص" % failed)
    if not sc.agree:
        r.cnt_ok = False
        r.cnt_notes.append("العدد %d بس التسلسل %d%s (ممكن إيصالات ناقصة أو مش اتقرت، راجع الملف)" % (
            sc.count, sc.range_len, sc.missing_text()))
    r.seq_min, r.seq_max, r.seq_missing = sc.seq_min, sc.seq_max, list(sc.seq_missing)
    r.other_day = list(sc.other_day)
    if sc.other_day:
        r.cnt_ok = False
        r.cnt_notes.append("مش تبع نفس اليوم: " + " ، ".join(sc.other_day))
    if sc.non_payment:
        r.cnt_notes.append("فيه إيصال إقفال/ملخص/إعادة طباعة (اتجاهل ومش معدود)")
    if r.new_name is None and sc.tid:
        r.tid, r.day, r.month = sc.tid, sc.day or r.day, sc.month or r.month
        r.id_ok, r.id_notes = True, []
    elif sc.tid in TERMINALS and r.tid in TERMINALS and TERMINALS[sc.tid].order != TERMINALS[r.tid].order:
        r.cnt_ok = False
        r.cnt_notes.append("العد لقى ماكينة %d بس التسمية ماكينة %d، راجع" % (
            TERMINALS[sc.tid].order, TERMINALS[r.tid].order))
    return True


def count_payment_pdf(r, workdir, progress=None, stop=lambda: False, fast=True, max_pages=400):
    """بيعدّ إيصالات الملف. يرجّع False لو اتوقف قبل ما يخلص."""
    r.cnt_notes, r.cnt_ok = [], True
    if not os.path.exists(r.src):
        r.count = 0
        r.cnt_ok = False
        r.cnt_notes.append("الملف الأصلي مش موجود")
        return True
    if fast:
        res = _count_fast(r, workdir, progress, stop, max_pages)
        if res is None:
            return False
        if res:
            return True
        r.cnt_notes, r.cnt_ok = [], True      # السريع ما نفعش: نكمّل بالدقيق
    res = _count_accurate(r, workdir, progress, stop, max_pages)
    return res is not None


# ───────────── مقارنة الباتش + حالة الملف + الملاحظات ─────────────
def batch_manual(r):
    try:
        return int(str(r.expected).strip())
    except (TypeError, ValueError):
        return None


def batch_auto(r):
    return CLOSING_TXN.get(r.order) if r.order != 99 else None


def batch_of(r):
    m = batch_manual(r)
    return m if m is not None else batch_auto(r)


def batch_diff(r):
    b = batch_of(r)
    if b is None or r.pending or r.excluded:
        return None
    return b - r.count


def batch_match(r):
    """True/False، أو None لو مفيش حاجة نقارنها. لو راجعته يدوي وعلّمته صح يتحسب مطابق."""
    if r.excluded or r.pending:
        return None
    if r.verdict > 0:
        return True
    d = batch_diff(r)
    return None if d is None else d == 0


def diff_text(d):
    return "مطابق ✓" if d == 0 else ("ناقص %d" % d if d > 0 else "زيادة %d" % (-d))


def pay_status(r):
    """(نص، tag للجدول)."""
    if r.excluded:
        return "مستبعد", "skip"
    if r.pending:
        return "لسه ما اتعدّش", "skip"
    if r.verdict > 0:
        return "اتراجع: صح", "ok"
    if r.ok:
        return "سليم", "ok"
    return "محتاج مراجعة", "warn"


def pay_summary(r):
    if r.excluded:
        return "مستبعد (علامة غلط)"
    if r.pending:
        return "لسه ما اتعدّش (دوس ② عدّ الإيصالات)"
    s = "عدد المعاملات: %d" % r.count
    b, d = batch_of(r), batch_diff(r)
    if b is not None and d is not None:
        tag = " (يدوي)" if batch_manual(r) is not None else " (من التقفيل)"
        res = "راجعته يدوي: صح ✓" if (r.verdict > 0 and d != 0) else diff_text(d)
        s += "\nالباتش: %d%s • الفعلي: %d • %s" % (b, tag, r.count, res)
    return s


def missing_machines(results):
    got = set(r.order for r in results if not r.excluded and r.order != 99)
    return ["%d %s" % (n, TERMINALS[NUM_TO_TID[n]].unit) for n in range(1, 20) if n not in got]


# (key, severity 2=لازم تراجع 1=انتبه 0=معلومة, عنوان، السبب، الحل)
NOTE_KINDS = [
    ("seq", 2, "العدد مش مطابق لتسلسل الإيصالات",
     "أرقام الإيصالات (RRN) متتالية، فالعدد المتوقع هو من أول رقم لآخر رقم. العدد اللي اتعدّ مختلف عنه، يعني غالباً فيه إيصال ناقص في الملف أو البرنامج ما قراش إيصال.",
     "افتح الملف وراجع الأرقام اللي مش لاقيها، وسجّل العدد الصح في خانة \"الصح\" لو اتأكدت."),
    ("otherday", 2, "فيه إيصالات من يوم تاني",
     "تاريخ بعض الإيصالات مختلف عن يوم باقي الملف، فممكن تكون اتضافت بالغلط أو الملف فيه أكتر من يوم.",
     "راجع التواريخ المذكورة، ولو الملف مش بتاع اليوم علّمه غلط ✗."),
    ("machconf", 2, "تعارض في رقم الماكينة",
     "اسم الملف اتحدد لماكينة، لكن الإيصالات جواه بتقول إنها ماكينة تانية.",
     "استخدم \"تحديد/تعديل\" واختار الماكينة الصح."),
    ("readfail", 2, "فشل في قراءة صفحات",
     "البرنامج ما قدرش يقرا صفحة أو أكتر، فالعدد ممكن يكون ناقص.",
     "اختار الملف ودوس \"إعادة عد\". لو اتكرر راجع الملف بنفسك."),
    ("emptypages", 1, "صفحات من غير إيصالات",
     "فيه صفحات في الملف البرنامج ما لقاش فيها أي إيصال (ممكن تكون صفحة فاضية أو صورة مش واضحة).",
     "افتح الصفحات المذكورة وتأكد إنها فعلاً فاضية."),
    ("methoddiff", 1, "تضارب بين طريقتين للعد",
     "البرنامج بيعد بطريقتين للتأكد، وفي صفحات معينة النتيجة اختلفت.",
     "راجع الصفحات المذكورة لو العدد مهم ليك."),
    ("nonpay", 0, "مستند إقفال أو ملخص",
     "الملف فيه إيصال إقفال أو ملخص أو إعادة طباعة. البرنامج تجاهله ومش محسوب في العدد.",
     "مفيش حاجة مطلوبة، ده طبيعي."),
    ("nofile", 2, "الملف الأصلي مش موجود",
     "الملف اتمسح أو اتنقل من مكانه، فالبرنامج مش قادر يعدّه.",
     "رجّع الملف مكانه أو اعمل فحص من جديد."),
    ("datefail", 1, "التاريخ مش واضح",
     "البرنامج ما قدرش يقرا تاريخ اليوم من الملف.",
     "افتح الملف وتأكد من التاريخ بنفسك."),
    ("namefail", 2, "فشلت التسمية",
     "البرنامج ما قدرش يتعرف على الماكينة فمسمّاش الملف.",
     "استخدم \"تحديد/تعديل\" واختار الماكينة."),
    ("idweak", 2, "الماكينة مش مؤكدة",
     "رقم الماكينة (Terminal ID) ما اتقراش بوضوح، فالبرنامج خمّن الماكينة من بيانات تانية أو لقاها في أكتر من ملف.",
     "اتأكد من الماكينة، ولو غلط استخدم \"تحديد/تعديل\"."),
    ("other", 1, "ملاحظة تانية", "ملاحظة من البرنامج مش متصنفة.", "اقراها وقرر لو محتاجة مراجعة."),
]
_NOTE_RULES = [
    (re.compile(r"^العدد \d+ بس التسلسل"), "seq"),
    (re.compile(r"مش تبع نفس اليوم"), "otherday"),
    (re.compile(r"العد لقى ماكينة"), "machconf"),
    (re.compile(r"صفحة فشلت قراءتها|فشل العد|العد وقف"), "readfail"),
    (re.compile(r"صفحات ما لقيتش فيها إيصالات"), "emptypages"),
    (re.compile(r"الطريقتين اختلفوا"), "methoddiff"),
    (re.compile(r"إقفال/ملخص"), "nonpay"),
    (re.compile(r"الملف الأصلي مش موجود"), "nofile"),
    (re.compile(r"مش قادر أعرف التاريخ"), "datefail"),
    (re.compile(r"فشل التسمية|فشل التعريف|فشل النسخ"), "namefail"),
    (re.compile(r"Terminal ID|مش واضح|مش قادر أعرف الماكينة|نفس الماكينة|اتعرفت كمان|الوحدة اتحددت|نفس ماكينة"), "idweak"),
]


def note_kind(n):
    """يرجّع (key, severity, عنوان, سبب, حل) للملاحظة."""
    for rx, key in _NOTE_RULES:
        if rx.search(n):
            return next(k for k in NOTE_KINDS if k[0] == key)
    return NOTE_KINDS[-1]


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
        self.txn = None             # عدد معاملات الباتش من إيصال الإقفال

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
    try:
        publish_closing_txn(kept)      # عدد معاملات الباتش لكل ماكينة (تقارنه إيصالات الدفع)
    except Exception:
        pass
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
        it.txn = getattr(a, "txn", None)
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
            r = identify_payment_pdf(p, wd, progress=lambda m: print("..", m))
            count_payment_pdf(r, wd, progress=lambda m: print("..", m))
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

TOOLS_VERSION = "v60"

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
                outs = E.build_closing_outputs(kept, out_dir, tpl)
            return kept, warns, raw, outs

        self._run_job(job, self._done)

    def _done(self, res):
        kept, warns, raw, outs = res
        self.raw_all, self.kept, self.warnings, self.outputs = raw, kept, warns, outs
        self._fill()
        if not raw:
            self.lbl_status.configure(text="مفيش باتشات اتقرت في المصدر ده.", text_color=self.t["warning"])
        else:
            self._status_after_build()

    def _status_after_build(self):
        o = self.outputs or {}
        total = sum((o.get("totals") or {}).values())
        bad = sum(1 for r in self.kept if r.needs_review)
        msg = "اكتمل: %d باتش" % len(self.kept)
        if o:
            msg += " | تقفيل يوم %s | الإجمالي %s ج.م" % (o.get("report_date"), format(total, ",.2f"))
        if bad:
            msg += " | ⚠️ %d محتاج مراجعة" % bad
        self.lbl_status.configure(text=msg, text_color=self.t["warning"] if bad else self.t["success"])

    def _status_text(self, r):
        if r.skip:
            return "مستبعد - مكرر"
        notes = []
        if r.amount <= 0:
            notes.append("المبلغ مش مقروء")
        elif not r.ok:
            notes.append("مبلغ غير مؤكد")
        if r.row is None:
            notes.append("الوحدة مش معروفة")
        if r.alt is not None:
            notes.append("قراءة تانية %.2f" % r.alt)
        if r.how == "extra-batch":
            notes.append("باتش إضافي %s" % r.suffix)
        elif r.how in ("auto-number", "conflict"):
            notes.append("رقم الماكينة تلقائي")
        elif r.how == "manual":
            return "✓ تعديل يدوي"
        return "⚠️ " + " ، ".join(notes) if notes else "✓ مؤكد"

    def _fill(self):
        self.tv.delete(*self.tv.get_children())
        order = sorted(self.raw_all, key=lambda r: ((r.order or 99), (r.suffix or 1), r.label))
        self._iid = {}
        for r in order:
            st = self._status_text(r)
            tag = "skip" if r.skip else ("err" if (st.startswith("⚠️") or r.needs_review) else "ok")
            sfx = "_%d" % r.suffix if r.suffix else ""
            iid = self.tv.insert("", "end", values=(
                "%s%s" % (r.order or "-", sfx), r.label, r.tid or "—", E.unit_label(r.tid, r.unit),
                "%.2f" % r.amount if r.amount else "—", st), tags=(tag,))
            self._iid[iid] = r
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        lines = list(self.warnings)
        o = self.outputs or {}
        if o.get("missing"):
            lines.append("ماكينات ما ظهرش لها باتش: " + "، ".join(str(i) for i in o["missing"]))
        if o.get("extra_pdfs"):
            lines.append("فيه إيصالات بتواريخ تانية: اتعمل لها PDF منفصل ومش داخلة في الإجمالي.")
        if o.get("xlsx_error"):
            lines.append("⚠️ فشل الإكسيل: " + o["xlsx_error"])
        tot = o.get("totals") or {}
        if tot:
            lines.insert(0, "الإجماليات: " + " | ".join(
                "%s %s" % (E.ROW_NAMES[r], format(v, ",.2f")) for r, v in sorted(tot.items()) if v))
        self.txt.insert("1.0", ("ملاحظات للمراجعة (%d):\n• " % len(lines) + "\n• ".join(lines)) if lines else "مفيش ملاحظات ✓")
        self.txt.configure(state="disabled")

    def apply_edit(self, item, tid, amt):
        if tid in E.TERMINALS:
            i = E.TERMINALS[tid]
            item.det = (tid, i.order, i.row, i.unit, "manual")
        else:
            item.det = (None, None, None, None, "manual")
        item.amount, item.batches, item.ok, item.alt, item.how = amt, [amt], True, None, "manual"
        _save_fix(item.key, tid, amt)
        self.kept, self.warnings = E.renumber(self.raw_all)
        self.outputs = dict(self.outputs or {})
        self._fill()
        self.lbl_status.configure(text="اتعدّل. اضغط «إعادة بناء» عشان الـ PDF والإكسيل يتحدّثوا.",
                                  text_color=self.t["warning"])

    def rebuild(self):
        if not self.kept:
            return
        kept, out_dir, tpl = self.kept, self.out_dir, self._tpl_eff

        def job(j):
            j.progress(0.3, "بناء ملفات الـ PDF والإكسيل...")
            return E.build_closing_outputs(kept, out_dir, tpl)

        def done(outs):
            self.outputs = outs
            self._fill()
            self._status_after_build()

        self._run_job(job, done)


# ───────────────────────── إيصالات الدفع ─────────────────────────
class _EditPayDialog(_Modal):
    """تحديد/تعديل ملف إيصالات: الماكينة واليوم والشهر والعدد + \"الصح\" (عدد الباتش) لو عايز تكتبه بإيدك."""

    def __init__(self, parent, r, on_ok):
        super().__init__(parent, "تحديد / تعديل ملف إيصالات", 500, 390)
        t, F = self.t, _font()
        self.on_ok = on_ok
        ctk.CTkLabel(self, text=r.name, font=(F, 11, "bold"), text_color=t["accent"], wraplength=460).pack(pady=(12, 6))
        fr = ctk.CTkFrame(self, fg_color="transparent")
        fr.pack(fill="x", padx=20)
        rows = [("الماكينة:", None), ("اليوم:", r.day), ("الشهر:", r.month),
                ("عدد الإيصالات:", r.count if r.count >= 0 else ""),
                ("الصح (عدد الباتش) - اختياري:", r.expected)]
        ctk.CTkLabel(fr, text=rows[0][0], font=(F, 11, "bold"), text_color=t["text"]).grid(row=0, column=1, sticky="e", pady=4)
        self.cb = ttk.Combobox(fr, values=_terminal_choices(), state="readonly", width=38, justify="right")
        self.cb.grid(row=0, column=0, padx=8, pady=4)
        cur = E.terminal_label(r.tid) if r.tid else "— غير محدد —"
        self.cb.set(cur if cur in self.cb["values"] else "— غير محدد —")
        self.ents = []
        for i, (lbl, val) in enumerate(rows[1:], 1):
            ctk.CTkLabel(fr, text=lbl, font=(F, 11, "bold"), text_color=t["text"]).grid(row=i, column=1, sticky="e", pady=4)
            e = ctk.CTkEntry(fr, justify="center", width=120, font=(F, 12, "bold"))
            e.grid(row=i, column=0, padx=8, pady=4, sticky="w")
            e.insert(0, "" if val is None else str(val))
            self.ents.append(e)
        ctk.CTkLabel(self, text="لو سيبت العدد فاضي هيتعدّ تاني بالقراءة الآلية.", font=(F, 10),
                     text_color=t["muted"]).pack()
        self.lbl = ctk.CTkLabel(self, text="", text_color=t["danger"], font=(F, 10, "bold"))
        self.lbl.pack()
        ctk.CTkButton(self, text="حفظ وإعادة التسمية", font=(F, 12, "bold"), fg_color=_GREEN, hover_color=_GREEN_H,
                      text_color="#FFFFFF", command=self.save).pack(fill="x", padx=20, pady=8)

    def save(self):
        tid = _tid_from_choice(self.cb.get())
        try:
            d, m = int(self.ents[0].get()), int(self.ents[1].get())
            c_raw = self.ents[2].get().strip()
            c = int(c_raw) if c_raw else None
            e_raw = self.ents[3].get().strip()
            ex = int(e_raw) if e_raw else None
            if not (1 <= d <= 31 and 1 <= m <= 12) or (c is not None and c < 0) or (ex is not None and ex < 0):
                raise ValueError
        except ValueError:
            self.lbl.configure(text="اليوم 1-31 والشهر 1-12 والأعداد أرقام صحيحة")
            return
        if tid not in E.TERMINALS:
            self.lbl.configure(text="اختار الماكينة")
            return
        cb = self.on_ok
        self.destroy()
        cb(tid, str(d), str(m), c, ex)


# ───────────── حفظ حالة إيصالات الدفع (علشان لو البرنامج اتقفل يكمّل من مكانه) ─────────────
_PAY_KEYS = ("src", "size", "name", "pages", "count", "tid", "day", "month", "new_name", "out_path",
             "id_notes", "cnt_notes", "id_ok", "cnt_ok", "detail", "verdict", "expected", "votes",
             "alt_tids", "seq_min", "seq_max", "seq_missing", "other_day")


def _pay_state_path():
    return os.path.join(_appdata_dir(), "pos_payments_state.json")


def _pay_save(results):
    try:
        data = [{k: getattr(r, k) for k in _PAY_KEYS} for r in list(results)]
        tmp = _pay_state_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, _pay_state_path())
    except Exception:
        logging.exception("pay state save")


def _pay_load():
    out = []
    try:
        with open(_pay_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return out
    for d in data if isinstance(data, list) else []:
        try:
            if not isinstance(d, dict) or not d.get("src"):
                continue
            r = E.PayResult(d["src"])
            for k in _PAY_KEYS:
                if k in d:
                    setattr(r, k, d[k])
            out.append(r)
        except Exception:
            continue
    return out


class _PayOverview(_Modal):
    """ملخص الماكينات: كل ماكينة (1-19) جاب ليها ملف ولا لأ، وعددها مقارنة بالباتش."""

    def __init__(self, parent, results):
        super().__init__(parent, "ملخص ماكينات إيصالات الدفع", 820, 560)
        t, F = self.t, _font()
        self.resizable(True, True)
        by = {}
        for r in results:
            if not r.excluded and r.order != 99:
                by.setdefault(r.order, []).append(r)
        miss = [n for n in range(1, 20) if n not in by]
        total = sum(r.count for rs in by.values() for r in rs if r.count > 0)
        pend = sum(1 for rs in by.values() for r in rs if r.pending)
        bad = sum(1 for rs in by.values() for r in rs if r.count >= 0 and not r.ok)
        ctk.CTkLabel(self, text="📊 ملخص الماكينات", font=(F, 15, "bold"), text_color=t["accent"]).pack(pady=(10, 2))
        ctk.CTkLabel(self, text="إجمالي الإيصالات: %d  |  ماكينات ناقصة: %d  |  لسه ما اتعدّتش: %d  |  محتاج مراجعة: %d"
                     % (total, len(miss), pend, bad), font=(F, 11, "bold"),
                     text_color=t["warning"] if (miss or pend or bad) else t["success"]).pack(pady=2)
        name = _style_tree(t)
        fr = ctk.CTkFrame(self, fg_color="transparent")
        fr.pack(fill="both", expand=True, padx=12, pady=6)
        cols = ("n", "unit", "file", "count", "batch", "diff", "status")
        heads = ("م", "الوحدة", "الملف", "العدد", "الباتش", "الفرق", "الحالة")
        wid = (40, 150, 200, 70, 70, 90, 150)
        tv = ttk.Treeview(fr, columns=cols, show="headings", style=name, height=19, selectmode="browse")
        for c, h, w in zip(cols, heads, wid):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="center", stretch=(c in ("file", "status")))
        sb = ttk.Scrollbar(fr, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tv.tag_configure("ok", foreground=t["success"])
        tv.tag_configure("warn", foreground=t["warning"])
        tv.tag_configure("bad", foreground=t["danger"])
        dash = "—"
        for n in range(1, 20):
            info = E.TERMINALS[E.NUM_TO_TID[n]]
            rs = sorted(by.get(n, []), key=lambda x: x.new_name or x.name)
            if not rs:
                tv.insert("", "end", values=(n, E.unit_label(E.NUM_TO_TID[n]), dash, dash, dash, dash, "ناقصة - مفيش ملف"),
                          tags=("bad",))
                continue
            for r in rs:
                b, d = E.batch_of(r), E.batch_diff(r)
                st, tag = E.pay_status(r)
                if tag == "ok" and E.batch_match(r) is False:
                    tag = "warn"
                tv.insert("", "end", values=(n, E.unit_label(E.NUM_TO_TID[n]), r.new_name or r.name,
                                             r.count if r.count >= 0 else dash, b if b is not None else dash,
                                             E.diff_text(d) if d is not None else dash, st), tags=(tag,))


class PaymentsWindow(_FeatureWindow):
    TITLE = "إيصالات الدفع"

    def __init__(self, parent):
        super().__init__(parent, 1120, 720)
        t, F = self.t, self.F
        st = _load_settings()
        self.dest = st.get("pay_dest") or os.path.join(_documents_dir(), "وحدات")
        self.fast = tk.BooleanVar(value=bool(st.get("pay_fast", True)))
        self.skip_done = tk.BooleanVar(value=bool(st.get("pay_skip_done", True)))
        self.results = _pay_load()
        self._iid = {}
        ctk.CTkLabel(self, text="🧾 إيصالات الدفع", font=(F, 16, "bold"), text_color=t["accent"]).pack(pady=(10, 0))
        self._build_source_bar(self)
        fr = ctk.CTkFrame(self, fg_color="transparent")
        fr.pack(fill="x", padx=12, pady=2)
        self._btn(fr, "📂 فتح فولدر الملفات المسمّاة", self.open_dest, color=t["card"], w=230).pack(side="right", padx=4)
        self._btn(fr, "✏️ تغيير المكان", self.pick_dest, color=t["card"], w=130).pack(side="right", padx=4)
        self.lbl_dest = ctk.CTkLabel(fr, text="الناتج: " + self.dest, font=(F, 10), text_color=t["muted"], anchor="w")
        self.lbl_dest.pack(side="left", fill="x", expand=True)
        self._build_progress(self)
        # خطّين: ① إعادة التسمية  ② العد
        self.btn_start.configure(text="① فحص وإعادة تسمية", width=160)
        self.btn_count = self._btn(self.btn_start.master, "② عدّ الإيصالات", self.start_count, color=t["warning"], w=150,
                                   state="disabled")
        self.btn_count.pack(side="right", padx=4)
        opt = ctk.CTkFrame(self, fg_color="transparent")
        opt.pack(fill="x", padx=12, pady=(0, 2))
        ctk.CTkCheckBox(opt, text="عدّ سريع (قراءة كل صفحة مرة واحدة من الصورة الأصلية)", variable=self.fast, font=(F, 10),
                        text_color=t["text"], command=lambda: _save_setting("pay_fast", bool(self.fast.get()))
                        ).pack(side="right", padx=8)
        ctk.CTkCheckBox(opt, text="تخطّي الملفات اللي اتفحصت قبل كده", variable=self.skip_done, font=(F, 10),
                        text_color=t["text"], command=lambda: _save_setting("pay_skip_done", bool(self.skip_done.get()))
                        ).pack(side="right", padx=8)
        cols = [("n", "م"), ("file", "الملف الأصلي"), ("unit", "الماكينة"), ("pages", "صفحات"), ("count", "العدد"),
                ("batch", "الباتش"), ("diff", "الفرق"), ("day", "اليوم"), ("name", "الاسم الجديد"), ("status", "الحالة")]
        self.tv = self._tree(self, cols, [34, 160, 150, 55, 60, 60, 80, 55, 190, 110], height=10)
        self.tv.tag_configure("bad", foreground=t["danger"])
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._show_notes())
        self.tv.bind("<Double-1>", lambda e: self.open_selected())   # دبل كليك = فتح الـ PDF
        self.txt = ctk.CTkTextbox(self, height=130, font=(F, 10), fg_color=t["input"], text_color=t["text"], wrap="word")
        self.txt.pack(fill="x", padx=12, pady=4)
        self.txt.configure(state="disabled")
        self.lbl_total = ctk.CTkLabel(self, text="", font=(F, 11, "bold"), text_color=t["text"])
        self.lbl_total.pack(fill="x", padx=14)
        bt = ctk.CTkFrame(self, fg_color="transparent")
        bt.pack(fill="x", padx=12, pady=(2, 10))
        for txt, cmd, col, w in (("🗑 مسح الكل", self.clear_all, t["danger"], 100),
                                 ("💾 تقرير TXT", self.save_report, t["card"], 110),
                                 ("📊 ملخص الماكينات", self.open_overview, t["card"], 140),
                                 ("↻ إعادة عدّ", self.recount_selected, t["card"], 105),
                                 ("✏️ تحديد/تعديل", self.edit_selected, t["warning"], 120),
                                 ("الباقي صح", self.mark_rest_ok, t["card"], 95),
                                 ("✗ غلط", lambda: self.set_verdict(-1), t["danger"], 80),
                                 ("✓ صح", lambda: self.set_verdict(1), t["success"], 80)):
            self._btn(bt, txt, cmd, color=col, w=w).pack(side="right", padx=3)
        if self.results:
            self._fill()
            pend = sum(1 for r in self.results if r.pending)
            self.lbl_status.configure(
                text=("فيه %d ملف لسه ما اتعدّش. دوس \"② عدّ الإيصالات\" لما تحب." % pend) if pend
                else "آخر نتيجة: %d ملف." % len(self.results), text_color=self.t["muted"])
            self.btn_count.configure(state="normal")

    # ---------- عام ----------
    def _set_busy(self, busy):
        super()._set_busy(busy)
        self.btn_count.configure(state="disabled" if (busy or not self.results) else "normal")

    def job_running(self):
        return str(self.btn_stop.cget("state")) == "normal"

    def open_dest(self):
        """بيفتح الفولدر اللي فيه الملفات المسمّاة (مش نافذة اختيار)."""
        try:
            os.makedirs(self.dest, exist_ok=True)
        except OSError:
            pass
        _open_path(self.dest)

    def pick_dest(self):
        d = filedialog.askdirectory(parent=self, title="اختار مكان حفظ الملفات المسمّاة", initialdir=self.dest)
        if d:
            self.dest = d
            _save_setting("pay_dest", d)
            self.lbl_dest.configure(text="الناتج: " + self.dest)

    def _selected(self):
        sel = self.tv.selection()
        return self._iid.get(sel[0]) if sel else None

    def _sort(self):
        self.results.sort(key=lambda x: (x.order, x.new_name or x.name))

    # ---------- ① التعريف وإعادة التسمية ----------
    def start(self):
        self._src_summary()
        if not self._pdfs:
            messagebox.showwarning("A2R", "اختار مجلد أو ملفات PDF الأول (الصور مش بتتحسب في الفكرة دي).", parent=self)
            return
        ok, msg = E.pay_ocr_ready()
        if not ok:
            messagebox.showerror("A2R", msg, parent=self)
            return
        existing = list(self.results)
        have = set(r.key for r in existing)
        todo, skipped = [], 0
        for p in self._pdfs:
            try:
                k = "%s:%d" % (os.path.basename(p), os.path.getsize(p))
            except OSError:
                continue
            if self.skip_done.get() and k in have:
                skipped += 1
                continue
            todo.append(p)
        if not todo:
            messagebox.showinfo("A2R", "كل الملفات في المصدر ده اتفحصت قبل كده (%d ملف)." % skipped, parent=self)
            return
        fast = bool(self.fast.get())
        dest, wd, ignored = self.dest, self.workdir, len(self._imgs)

        def job(j):
            newkeys = set("%s:%d" % (os.path.basename(p), os.path.getsize(p)) for p in todo)
            kept = []
            for r in existing:
                if r.key in newkeys:       # بنعيد فحصه: نمسح نسخته المسمّاة القديمة (الأصلي مش بيتمس)
                    try:
                        if (r.out_path and os.path.exists(r.out_path) and os.path.abspath(r.out_path) != os.path.abspath(r.src)
                                and os.path.abspath(r.out_path).startswith(os.path.abspath(dest))):
                            os.remove(r.out_path)
                    except OSError:
                        pass
                else:
                    kept.append(r)
            res = []
            for i, p in enumerate(todo):
                if j.stop_ev.is_set():
                    break
                base = i / float(len(todo))
                name = os.path.basename(p)
                try:
                    r = E.identify_payment_pdf(
                        p, wd, progress=lambda m, base=base, i=i, name=name: j.progress(
                            base, "① ملف %d من %d: %s — %s" % (i + 1, len(todo), name, m)),
                        stop=j.stop_ev.is_set, fast=fast)
                except E.OcrUnavailable:
                    raise
                except Exception as e:
                    logging.exception("identify")
                    r = E.PayResult(p)
                    r.id_ok = False
                    r.id_notes.append("فشل التعريف: %s" % str(e).split("\n")[0])
                res.append(r)
            allres = kept + res
            for r in res:
                if r.pending:               # الملفات الضعيفة (مش إيصال ماكينة) مش بتتسمّى
                    try:
                        E.apply_payment_name(allres, r, dest)
                    except Exception as e:
                        r.id_ok = False
                        r.id_notes.append("فشل التسمية: %s" % e)
            E.resolve_payment_duplicates(allres, dest)
            E.flag_payment_duplicates(allres)
            _pay_save(allres)
            return allres, ignored, skipped

        self._run_job(job, self._done_rename)

    def _done_rename(self, payload):
        allres, ignored, skipped = payload
        self.results = allres
        self._sort()
        self._fill()
        named = sum(1 for r in self.results if r.new_name and not r.excluded)
        bad = sum(1 for r in self.results if not r.ok)
        msg = "① اكتمل الفحص: %d ملف، %d اتسمّى" % (len(self.results), named)
        if bad:
            msg += " | ⚠️ %d محتاج مراجعة" % bad
        if skipped:
            msg += " | (اتخطّيت %d اتفحصوا قبل كده)" % skipped
        if ignored:
            msg += " | (اتجاهلت %d صورة)" % ignored
        pend = sum(1 for r in self.results if r.pending)
        if pend:
            msg += "  —  دوس \"② عدّ الإيصالات\" لعدّ %d ملف." % pend
        self.lbl_status.configure(text=msg, text_color=self.t["warning"] if bad else self.t["success"])
        self.btn_count.configure(state="normal" if self.results else "disabled")

    # ---------- ② العد ----------
    def start_count(self):
        todo = [r for r in self.results if r.pending]
        if not todo:
            messagebox.showinfo("A2R", "كل الملفات اتعدّت. اختار ملف ودوس \"↻ إعادة عدّ\" لو عايز تعيد.", parent=self)
            return
        ok, msg = E.pay_ocr_ready()
        if not ok:
            messagebox.showerror("A2R", msg, parent=self)
            return
        fast, dest, wd = bool(self.fast.get()), self.dest, self.workdir

        def job(j):
            for i, r in enumerate(todo):
                if j.stop_ev.is_set():
                    break
                if r.excluded:
                    continue
                base = i / float(len(todo))
                name = r.new_name or r.name
                try:
                    done = E.count_payment_pdf(
                        r, wd, progress=lambda m, base=base, i=i, name=name: j.progress(
                            base, "② ملف %d من %d: %s — %s" % (i + 1, len(todo), name, m)),
                        stop=j.stop_ev.is_set, fast=fast)
                    if done and r.new_name is None and r.tid and r.day and r.month:
                        E.apply_payment_name(self.results, r, dest)    # التعريف فشل: نسمّي من نتيجة العد
                except E.OcrUnavailable:
                    raise
                except Exception:
                    logging.exception("count")
                    r.count = 0
                    r.cnt_ok = False
                    r.cnt_notes.append("فشل العد")
                _pay_save(self.results)
            E.flag_payment_duplicates(self.results)
            _pay_save(self.results)
            return todo

        self._run_job(job, self._done_count)

    def _done_count(self, _items):
        self._sort()
        self._fill()
        done = [r for r in self.results if r.counted and not r.excluded]
        n = sum(r.count for r in done)
        bad = sum(1 for r in self.results if r.counted and not r.ok)
        pend = sum(1 for r in self.results if r.pending)
        msg = "② اكتمل العد: %d ملف | إجمالي الإيصالات %d" % (len(done), n)
        if pend:
            msg += " | فاضل %d لسه (اتوقف) - دوس ② تاني يكمّل من مكانه" % pend
        if bad:
            msg += " | ⚠️ %d محتاج مراجعة" % bad
        self.lbl_status.configure(text=msg, text_color=self.t["warning"] if (bad or pend) else self.t["success"])

    def recount_selected(self):
        r = self._selected()
        if not r:
            messagebox.showinfo("A2R", "اختار صف الأول.", parent=self)
            return
        if self.job_running():
            return
        r.count, r.cnt_notes, r.cnt_ok, r.detail = -1, [], True, ""
        _pay_save(self.results)
        self._fill()
        self.start_count()

    # ---------- العرض ----------
    def _fill(self):
        keep = None
        r0 = self._selected()
        if r0 is not None:
            keep = r0
        self.tv.delete(*self.tv.get_children())
        self._iid = {}
        dash = "—"
        sel_iid = None
        for r in self.results:
            b, d = E.batch_of(r), E.batch_diff(r)
            stt, tag = E.pay_status(r)
            if tag == "ok" and E.batch_match(r) is False:
                tag = "warn"
            if r.counted and not r.excluded and E.batch_match(r) is False and r.verdict == 0 and tag != "skip":
                tag = "warn"
            iid = self.tv.insert("", "end", values=(
                r.order if r.order != 99 else "-", r.name, E.terminal_label(r.tid) if r.tid else "غير محدد",
                r.pages or dash, r.count if r.count >= 0 else dash, b if b is not None else dash,
                E.diff_text(d) if d is not None else dash, ("%s/%s" % (r.day, r.month)) if r.day else dash,
                r.new_name or dash, stt), tags=(tag,))
            self._iid[iid] = r
            if r is keep:
                sel_iid = iid
        if sel_iid:
            self.tv.selection_set(sel_iid)
        counted = [r for r in self.results if r.counted and not r.excluded]
        miss = E.missing_machines(self.results) if self.results else []
        self.lbl_total.configure(text="إجمالي الإيصالات: %d  |  الملفات: %d  |  اتعدّت: %d  |  لسه: %d  |  محتاج مراجعة: %d  |  ماكينات ناقصة: %d" % (
            sum(r.count for r in counted), len(self.results), len(counted),
            sum(1 for r in self.results if r.pending), sum(1 for r in counted if not r.ok), len(miss)))
        self.btn_count.configure(state="normal" if (self.results and not self.job_running()) else "disabled")
        self._show_notes()

    def _show_notes(self):
        r = self._selected()
        out = []
        if r:
            st, _tag = E.pay_status(r)
            out.append("[%s]  %s" % (st, E.pay_summary(r).replace("\n", "  |  ")))
            if r.detail:
                out.append("التفاصيل: " + r.detail)
            seen = set()
            for n in r.notes:
                k = E.note_kind(n)
                out.append("")
                out.append("%s %s" % ("🔴" if k[1] == 2 else ("🟠" if k[1] == 1 else "ℹ️"), k[2]))
                out.append("   • " + n)
                if k[0] not in seen:
                    seen.add(k[0])
                    out.append("   لماذا: " + k[3])
                    out.append("   الحل: " + k[4])
            if not r.notes:
                out.append("\nمفيش ملاحظات ✓")
        else:
            lines = []
            for x in self.results:
                for n in x.notes:
                    lines.append("• %s: %s" % (x.name, n))
            miss = E.missing_machines(self.results) if self.results else []
            if miss:
                lines.append("• ماكينات ملهاش ملف: " + " ، ".join(miss))
            out.append("\n".join(lines) if lines else "اختار ملف لعرض ملاحظاته.")
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(out))
        self.txt.configure(state="disabled")

    def open_selected(self):
        r = self._selected()
        if r:
            p = r.out_path if (r.out_path and os.path.exists(r.out_path)) else r.src
            _open_path(p)

    def open_overview(self):
        if not self.results:
            messagebox.showinfo("A2R", "مفيش نتايج لسه.", parent=self)
            return
        _PayOverview(self, self.results)

    # ---------- المراجعة: صح / غلط / تعديل ----------
    def set_verdict(self, v):
        """صح = يفضل مع ملفات اليوم، غلط = يتشال من العد والفولدر. الضغط تاني بيلغي الاختيار."""
        r = self._selected()
        if not r:
            messagebox.showinfo("A2R", "اختار صف الأول.", parent=self)
            return
        if self.job_running():
            return
        nv = 0 if r.verdict == v else v
        was_ex = r.excluded
        r.verdict = nv
        try:
            op = r.out_path
            inside = bool(op) and os.path.abspath(op).startswith(os.path.abspath(self.dest)) \
                and os.path.abspath(op) != os.path.abspath(r.src)
            if nv < 0 and not was_ex:
                if inside and os.path.exists(op):
                    os.remove(op)        # النسخة المسمّاة بس (مش الأصلي أبداً)
            elif nv >= 0 and was_ex and inside and os.path.exists(r.src) and not os.path.exists(op):
                os.makedirs(os.path.dirname(op), exist_ok=True)
                shutil.copy2(r.src, op)
        except OSError:
            logging.exception("verdict file")
        E.flag_payment_duplicates(self.results)
        _pay_save(self.results)
        self._fill()
        # علّمته صح بس البرنامج مش عارف ماكينته: اسأل عليها
        if nv > 0 and not r.tid:
            self.edit_selected()

    def mark_rest_ok(self):
        lst = [r for r in self.results if not r.ok]
        if not lst:
            messagebox.showinfo("A2R", "مفيش حاجة محتاجة مراجعة.", parent=self)
            return
        if not messagebox.askyesno("A2R", "هتعلّم %d ملف على إنهم صح؟" % len(lst), parent=self):
            return
        for r in lst:
            r.verdict = 1
        _pay_save(self.results)
        self._fill()

    def edit_selected(self):
        r = self._selected()
        if not r:
            messagebox.showinfo("A2R", "اختار صف الأول.", parent=self)
            return
        if self.job_running():
            return

        def ok(tid, d, m, c, ex):
            r.tid, r.day, r.month = tid, d, m
            r.expected = ex
            r.id_ok, r.id_notes = True, []
            r.verdict = 1
            if c is None:
                r.count, r.cnt_notes, r.cnt_ok, r.detail = -1, [], True, ""
            else:
                r.count, r.cnt_notes, r.cnt_ok, r.detail = c, [], True, "تعديل يدوي"
            try:
                E.apply_payment_name(self.results, r, self.dest)
            except Exception as e:
                r.id_ok = False
                r.id_notes.append("فشل التسمية: %s" % e)
            E.flag_payment_duplicates(self.results)
            self._sort()
            _pay_save(self.results)
            self._fill()
            if c is None:
                self.lbl_status.configure(text="اتسمّى. دوس \"② عدّ الإيصالات\" لعدّ إيصالاته.", text_color=self.t["warning"])

        _EditPayDialog(self, r, ok)

    def clear_all(self):
        if not self.results:
            return
        mine = [r for r in self.results if r.out_path]
        if not messagebox.askyesno(
                "A2R", "هيتمسح %d ملف مسمّى من:\n%s\n\nوهتتمسح نتيجة الفحص.\n(ملفاتك الأصلية مش هتتمس)" % (len(mine), self.dest),
                parent=self):
            return
        for r in mine:
            try:
                p = os.path.abspath(r.out_path)
                if p.startswith(os.path.abspath(self.dest)) and p != os.path.abspath(r.src) and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        self.results = []
        _pay_save(self.results)
        self._fill()
        self.lbl_status.configure(text="تم المسح. اختار مصدر وابدأ يوم جديد.", text_color=self.t["muted"])

    def save_report(self):
        if not self.results:
            return
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".txt", filetypes=[("Text", "*.txt")],
                                         initialfile="تقرير إيصالات الدفع %s.txt" % datetime.date.today().strftime("%d-%m-%Y"))
        if not p:
            return
        lines = ["تقرير إيصالات الدفع", "=" * 44]
        for r in self.results:
            st, _t = E.pay_status(r)
            lines.append("%s | %s | العدد %s | %s | %s" % (
                E.terminal_label(r.tid) if r.tid else "غير محدد", r.name, r.count if r.count >= 0 else "—",
                r.new_name or "بدون اسم", st))
            b, d = E.batch_of(r), E.batch_diff(r)
            if b is not None and d is not None:
                lines.append("    الباتش: %d • الفعلي: %d • %s" % (b, r.count, E.diff_text(d)))
            if r.detail:
                lines.append("    " + r.detail)
            lines += ["    - " + n for n in r.notes]
        miss = E.missing_machines(self.results)
        if miss:
            lines += ["-" * 44, "ماكينات ملهاش ملف: " + " ، ".join(miss)]
        lines.append("-" * 44)
        lines.append("إجمالي الإيصالات: %d" % sum(r.count for r in self.results if r.count > 0 and not r.excluded))
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        _open_path(p)


# ───────────────────────── النافذة الرئيسية للأدوات + نقطة الدخول ─────────────────────────
class PosToolsHub(_Modal):
    def __init__(self, app):
        super().__init__(app, _L("A2R - أدوات المشرف", "A2R - Supervisor"), 440, 300)
        self.app = app
        t, F = self.t, _font()
        self._wins = {}
        ctk.CTkLabel(self, text=_L("🛠️ المشرف", "🛠️ Supervisor"), font=(F, 17, "bold"),
                     text_color=t["accent"]).pack(pady=(14, 2))
        ctk.CTkLabel(self, text=_L("كل صلاحيات المشرف في مكان واحد", "All supervisor tools in one place"),
                     font=(F, 10, "bold"), text_color=t["muted"]).pack(pady=(0, 8))
        g = ctk.CTkFrame(self, fg_color="transparent")
        g.pack(fill="both", expand=True, padx=20, pady=4)
        g.grid_columnconfigure((0, 1), weight=1, uniform="a")

        def mk(r, c, text, cmd, color):
            ctk.CTkButton(g, text=text, height=64, font=(F, 12, "bold"), fg_color=color, hover_color=t["hover"],
                          command=cmd).grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

        mk(0, 0, _L("📑 التقفيل 🔐", "📑 Closing 🔐"), lambda: self.ask("التقفيل", ClosingWindow), t["primary"])
        mk(0, 1, _L("🧾 إيصالات الدفع 🔐", "🧾 Payment receipts 🔐"),
           lambda: self.ask("إيصالات الدفع", PaymentsWindow), t["primary"])
        mk(1, 0, _L("📊 فتح الإكسيل", "📊 Open Excel"), lambda: self.run_app("open_excel"), "#059669")
        mk(1, 1, _L("🗂️ سجل الأرشيف", "🗂️ Archive history"), lambda: self.run_app("open_archive_history"), "#7C3AED")
        ctk.CTkLabel(self, text="A2R %s" % TOOLS_VERSION, font=(F, 9, "bold"), text_color="#64748B").pack(pady=(4, 8))

    def run_app(self, name):
        fn = getattr(self.app, name, None)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if fn:
            try:
                fn()
            except Exception as e:
                messagebox.showerror("A2R", str(e))

    def ask(self, title, cls):
        w = self._wins.get(title)
        try:
            if w is not None and w.winfo_exists():
                w.deiconify()
                w.lift()
                return
        except Exception:
            pass

        def go():
            win = cls(self.app)
            self._wins[title] = win

        try:
            self.grab_release()
        except Exception:
            pass
        PosPasswordDialog(self, title, go)


_HUB = None


def open_pos_tools(app):
    """بيتنادى من زر المشرف. لو المستخدم مش مشرف بيترفض."""
    global _HUB
    if not getattr(app, "is_supervisor", False):
        messagebox.showwarning("A2R", "هذه الصلاحية متاحة للمشرف فقط!")
        return
    try:
        if _HUB is not None and _HUB.winfo_exists():
            _HUB.deiconify()
            _HUB.lift()
            return
    except Exception:
        pass
    _HUB = PosToolsHub(app)


def pos_tools_button_text():
    return _L("🛠️ المشرف", "🛠️ Supervisor")


def refresh_pos_tools_button(app):
    b = getattr(app, "btn_pos_tools", None)
    if b is not None:
        try:
            b.configure(text=pos_tools_button_text())
        except Exception:
            pass


def make_pos_tools_button(app, parent, **kw):
    """بيعمل الزر (من غير ما يحطه). الاسم بيتغير مع لغة البرنامج."""
    t = _theme(app)
    btn = ctk.CTkButton(parent, text=pos_tools_button_text(), font=(_font(), 11, "bold"), fg_color=t["primary"],
                        hover_color=t["hover"], command=lambda: open_pos_tools(app), **kw)
    app.btn_pos_tools = btn
    return btn
'''

POS_TOOLS_ERROR = ""
try:
    _a2r_embed("a2r_pos_engine", _A2R_POS_ENGINE_SRC)
    _a2r_embed("a2r_pos_tools", _A2R_POS_TOOLS_SRC)
    from a2r_pos_tools import open_pos_tools, make_pos_tools_button, refresh_pos_tools_button
    POS_TOOLS_AVAILABLE = True
except Exception as _pos_exc:
    POS_TOOLS_AVAILABLE = False
    POS_TOOLS_ERROR = repr(_pos_exc)
    try:
        logging.error("POS tools failed to load: %s", POS_TOOLS_ERROR)
    except Exception as _e:
        _log_silent("module#1", _e)
ctk.set_appearance_mode("Dark")

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = BUNDLE_DIR

PDFTOTEXT_EXE = os.path.join(BUNDLE_DIR, "pdftotext.exe")
if not os.path.exists(PDFTOTEXT_EXE):
    PDFTOTEXT_EXE = os.path.join(BASE_DIR, "pdftotext.exe")

def get_app_icon_path():
    candidates = [
        os.path.join(BUNDLE_DIR, "app.ico"),
        os.path.join(BASE_DIR, "app.ico"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico") if "__file__" in globals() else ""
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None
def set_window_icon_safe(window):
    ico_path = get_app_icon_path()
    if not ico_path:
        return

    def _apply():
        try:
            window.iconbitmap(ico_path)
        except Exception:
            try:
                if ImageTk is not None:
                    img = Image.open(ico_path)
                    photo = ImageTk.PhotoImage(img)
                    window._a2r_icon_ref = photo
                    window.wm_iconphoto(True, photo)
            except Exception as _e:
                _log_silent("_apply#1", _e)

    _apply()
    try:
        # customtkinter يعيد وضع أيقونته الافتراضية بعد لحظات، فنعيد تطبيق أيقونتنا
        window.after(300, _apply)
        window.after(1000, _apply)
    except Exception as _e:
        _log_silent("set_window_icon_safe#1", _e)
def setup_windows_autostart():
    if not WINREG_AVAILABLE or sys.platform != "win32":
        return
    try:
        exe_path = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)
        if not exe_path.lower().endswith(".exe"):
            return
        cmd = f'"{exe_path}" --autostart'
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "A2R_Console", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
    except Exception as _e:
        _log_silent("setup_windows_autostart#1", _e)
def configure_printer_57x90_silent():
    if sys.platform != "win32":
        return False, "Windows required"
    ps_cmd = (
        "$p = Get-CimInstance Win32_Printer | Where-Object { $_.Default -eq $true }; "
        "if ($p) { "
        "  $n = $p.Name; "
        "  try { "
        "    Set-PrintConfiguration -PrinterName $n -PaperSize Custom -ErrorAction SilentlyContinue; "
        "  } catch {} "
        "} "
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            timeout=8
        )
        return True, "Success"
    except Exception as e:
        return False, str(e)

DEFAULT_RECEIPTS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
DOCUMENTS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "A2R_Reports")
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "A2R")
os.makedirs(APPDATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")

DB_FILE = os.path.join(DOCUMENTS_DIR, "a2r_vault.db")
LOG_FILE = os.path.join(DOCUMENTS_DIR, "app_log.txt")

ARCHIVE_DIRNAME = "_Receipts_Archive_"
UNSPEC = "وحدة غير محددة"
PRINT_TEMP_DIR = os.path.join(tempfile.gettempdir(), "A2R_Print")
_PRINT_LOCK = threading.Lock()   # طباعة واحدة في الوقت (الملفات المؤقتة بنفس الاسم)
MANUAL_NAME_RE = re.compile(r"^[_]?\d+(?:\.\d{2})?_\d{6}\.pdf$", re.IGNORECASE)

SOUND_MUTED = True

from logging.handlers import RotatingFileHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")],
)

def log_exception(context, exc):
    try: logging.error(f"[{context}] {exc}")
    except Exception as _e: _log_silent("log_exception#1", _e)

def db_connect():
    """اتصال موحّد بقاعدة البيانات: مهلة انتظار 15 ثانية بدل الفشل الفوري لو القاعدة مشغولة (database is locked)."""
    conn = sqlite3.connect(DB_FILE, timeout=15)
    try:
        conn.execute("PRAGMA busy_timeout=15000")
    except Exception as e:
        log_exception("db_connect", e)
    return conn

def init_local_database():
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS manual_tx (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit TEXT,
                plate TEXT,
                insured TEXT,
                amount REAL,
                created_at TEXT,
                file_name TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS void_tx (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit TEXT,
                plate TEXT,
                insured TEXT,
                amount REAL,
                created_at TEXT,
                file_name TEXT,
                reason TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS voids (
                file_key TEXT PRIMARY KEY,
                amount REAL,
                plate TEXT,
                reason TEXT,
                voided_at TEXT,
                voided_by TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_meta (
                meta_key TEXT PRIMARY KEY,
                meta_value TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        log_exception("init_db", e)

init_local_database()

_VOID_KEYS = {}

def void_key(path_or_name):
    return os.path.basename(path_or_name or "").lstrip("_")

def load_void_map():
    global _VOID_KEYS
    mp = {}
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT file_key, reason, voided_at, voided_by FROM voids")
        for k, r, at, by in c.fetchall():
            mp[k] = {"reason": r or "", "at": at or "", "by": by or ""}
        conn.close()
    except Exception as e:
        log_exception("load_void_map", e)
    _VOID_KEYS = mp
    return mp

def add_void(file_key, amount, plate, reason):
    by = os.environ.get("USERNAME") or os.environ.get("USER") or "-"
    at = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    conn = db_connect()
    try:
        conn.execute("INSERT OR REPLACE INTO voids (file_key, amount, plate, reason, voided_at, voided_by) VALUES (?,?,?,?,?,?)",
                     (file_key, float(amount), plate or "-", reason or "", at, by))
        conn.commit()
    finally:
        conn.close()
    _VOID_KEYS[file_key] = {"reason": reason or "", "at": at, "by": by}

def remove_void(file_key):
    conn = db_connect()
    try:
        conn.execute("DELETE FROM voids WHERE file_key = ?", (file_key,))
        conn.commit()
    finally:
        conn.close()
    _VOID_KEYS.pop(file_key, None)

def refresh_void_flag(rec):
    bname = os.path.basename(rec.get("path", "") or rec.get("file", ""))
    key = bname.lstrip("_")
    legacy = bname.startswith("_")
    info = _VOID_KEYS.get(key)
    rec["is_void"] = bool(legacy or info)
    rec["legacy_void"] = legacy
    rec["void_reason"] = (info or {}).get("reason", "")
    return rec

def ensure_archive_root(folder_path):
    root = os.path.join(folder_path, ARCHIVE_DIRNAME)
    os.makedirs(root, exist_ok=True)
    return root

def archive_day_dir(folder_path, d):
    return os.path.join(folder_path, ARCHIVE_DIRNAME, str(d.year),
                        f"{d.month:02d}-{d.strftime('%B')}", f"{d.day:02d}")

THEMES = {
    "Aero Dark": {
        "mode": "Dark",
        "bg": "#080E17", "card": "#121E2E", "sub_card": "#0F1926",
        "border": "#1E2E42", "input": "#0A131F", "text": "#FFFFFF",
        "text_muted": "#8FA3B8", "primary": "#0284C7", "primary_hover": "#0369A1",
        "success": "#10B981", "danger": "#EF4444", "warning": "#F59E0B", "accent": "#38BDF8"
    },
    "Light Modern": {
        "mode": "Light",
        "bg": "#F1F5F9", "card": "#FFFFFF", "sub_card": "#E2E8F0",
        "border": "#CBD5E1", "input": "#F8FAFC", "text": "#0F172A",
        "text_muted": "#64748B", "primary": "#0284C7", "primary_hover": "#0369A1",
        "success": "#059669", "danger": "#DC2626", "warning": "#D97706", "accent": "#0284C7"
    },
    "Cyber Amber": {
        "mode": "Dark",
        "bg": "#0B0B0D", "card": "#17171C", "sub_card": "#111114",
        "border": "#282832", "input": "#0E0E12", "text": "#FFFFFF",
        "text_muted": "#9CA3AF", "primary": "#D97706", "primary_hover": "#B45309",
        "success": "#10B981", "danger": "#EF4444", "warning": "#F59E0B", "accent": "#FBBF24"
    },
    "Emerald Glass": {
        "mode": "Dark",
        "bg": "#04120D", "card": "#0A291E", "sub_card": "#061F17",
        "border": "#123829", "input": "#051811", "text": "#FFFFFF",
        "text_muted": "#86EFAC", "primary": "#059669", "primary_hover": "#047857",
        "success": "#10B981", "danger": "#F43F5E", "warning": "#F59E0B", "accent": "#34D399"
    },
    "Royal Purple": {
        "mode": "Dark",
        "bg": "#0E0717", "card": "#1E1033", "sub_card": "#170C28",
        "border": "#2C1B4D", "input": "#110920", "text": "#FFFFFF",
        "text_muted": "#A8A29E", "primary": "#7C3AED", "primary_hover": "#6D28D9",
        "success": "#10B981", "danger": "#EF4444", "warning": "#F59E0B", "accent": "#C084FC"
    }
}
THEME_KEYS = list(THEMES.keys())

# تباين النص الأبيض على اللون الأساسي كان أقل من 4.5:1 في أربع ثيمات (القراءة صعبة)؛ ده تغميق بسيط بيحقق المعيار.
THEMES["Aero Dark"].update(primary="#0369A1", primary_hover="#075985")
THEMES["Light Modern"].update(primary="#0369A1", primary_hover="#075985")
THEMES["Cyber Amber"].update(primary="#B45309", primary_hover="#92400E")
THEMES["Emerald Glass"].update(primary="#047857", primary_hover="#065F46")

# ألوان الأزرار بحسب الدور: (لون, لون الـ hover). كل الأزرار من نفس الدور بقت بنفس اللون، وتتغيّر مع الثيم.
#  primary = الإجراء الأساسي | success_btn = إنشاء/إضافة | tool = تقارير وأرشيف | warn_btn = طباعة ودفع
#  secondary = أزرار محايدة | danger_btn = خطر/صلاحيات
_ROLE_BTN = {
    "Aero Dark": {
        "secondary": ("#334155", "#475569"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Light Modern": {
        "secondary": ("#475569", "#334155"), "success_btn": ("#047857", "#065F46"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Cyber Amber": {
        "secondary": ("#3F3F46", "#52525B"), "success_btn": ("#047857", "#065F46"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#9A3412", "#7C2D12"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Emerald Glass": {
        "secondary": ("#1E3A34", "#2A4D45"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#BE123C", "#9F1239")},
    "Royal Purple": {
        "secondary": ("#3B2A5A", "#4C3A73"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#1D4ED8", "#1E40AF"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
}
for _n, _roles in _ROLE_BTN.items():
    for _k, (_c, _h) in _roles.items():
        THEMES[_n][_k] = _c
        THEMES[_n][_k + "_hover"] = _h

# أي زر في أي دور (أسماء الـ attributes في النافذة الرئيسية)
BUTTON_ROLES = {
    "primary": ["btn_run", "btn_pos_check", "btn_browse", "btn_today", "btn_view_rec"],
    "success_btn": ["btn_manual", "btn_cash", "btn_open_f", "btn_excel", "btn_pos_close"],
    "tool": ["btn_summary_reopen", "btn_archive_downloads", "btn_arch_hist", "btn_mini_archive", "btn_chrome"],
    "warn_btn": ["btn_print_slip", "btn_pos_pay", "btn_fix_printer"],
    "secondary": ["btn_yesterday", "btn_mute", "btn_back_to_mini", "btn_pdf_export"],
    "danger_btn": ["btn_elevate"],
}

TAG_COLORS = {
    "Dark": {
        "dup": ("#7F1D1D", "#FECACA"), "wrong": ("#7C2D12", "#FED7AA"),
        "missing": ("#713F12", "#FEF08A"), "manual": ("#1E3A5F", "#BFDBFE"),
        "void": ("#374151", "#9CA3AF")
    },
    "Light": {
        "dup": ("#FFC7CE", "#9C0006"), "wrong": ("#F8CBAD", "#833C0B"),
        "missing": ("#FFEB9C", "#7F6000"), "manual": ("#DDEBF7", "#1F3864"),
        "void": ("#E5E7EB", "#4B5563")
    },
}

FONT_FAMILY = "Segoe UI"
FONT_TITLE_LOGO = (FONT_FAMILY, 16, "bold")
FONT_SECTION_LBL = (FONT_FAMILY, 10, "bold")
FONT_REGULAR_BOLD = (FONT_FAMILY, 11, "bold")
FONT_KPI_VAL = (FONT_FAMILY, 16, "bold")
FONT_BTN_MAIN = (FONT_FAMILY, 12, "bold")
FONT_BTN_SUB = (FONT_FAMILY, 11, "bold")
FONT_ENTRY = (FONT_FAMILY, 11, "bold")

LANGUAGES = {
    "en": {
        "toggle_btn": "🌐 عربي", "dir_path": "DIRECTORY PATH", "browse": "Browse", "open": "Open",
        "date_lbl": "REPORT DATE", "today": "Today", "yesterday": "Yesterday",
        "start": "⚡ START EXTRACTION", "reset": "Reset",
        "manual": "➕ Manual", "summary_btn": "📊 Summary", "print_slip": "🖨️ Photocopy", "arch_hist_btn": "📚 Archive History", "pos_close_btn": "🧾 POS Closing", "pos_pay_btn": "💳 Payments", "view_records": "🔍 Records Viewer",
        "export_pdf": "📄 PDF Summary", "kpi1": "OPERATIONS", "kpi2": "TOTAL SUM",
        "open_excel": "📊 Open Excel", "currency": "EGP", "open_chrome": "🌐 Traffic Portal",
        "cash_btn": "💵 Cash", "clean_downloads": "📦 Archive", "autosync_on": "Auto Sync ON", "autosync_off": "Auto Sync OFF",
        "autoprint_on": "Auto Print ON", "autoprint_off": "Auto Print OFF", "invalid_date": "Invalid Date selected!",
        "dir_missing": "Receipts directory not found!", "pdf_missing": "pdftotext.exe not found in directory:\n",
        "summary_title": "Daily Inspection Summary", "unit_name_lbl": "Unit :", "period_lbl": "Date :",
        "total_ops_lbl": "Operations :", "pdf_lbl": "Electronic PDFs :", "txt_lbl": "Manual Receipts :",
        "void_ops_lbl": "Voided Receipts :", "duplicates_lbl": "Duplicates :", "wrong_lbl": "Other Unit :", "missing_lbl": "Incomplete :",
        "total_amt_lbl": "Total Sum :", "unspecified_unit": "Unspecified Unit",
        "records_viewer_title": "Transactions Viewer & Audit", "no_records_yet": "No records available yet. Run extraction first!",
        "no_summary_yet": "Please run extraction first to view summary!", "search_placeholder": "Search name, plate, chassis, motor...",
        "amt_filter_placeholder": "Amount...", "col_idx": "#", "col_unit": "Unit", "col_plate": "Plate No",
        "col_insured": "Insured Name", "col_amount": "Amount", "col_time": "Time", "col_make": "Make",
        "col_model": "Model", "col_chassis": "Chassis", "col_motor": "Motor", "col_period": "Period",
        "col_file": "File", "col_status": "Status", "pos_box_title": "POS / CASH RECONCILIATION",
        "pos_check_btn": "Match", "pos_matched": "✓ Matched", "pos_shortage": "⚠️ Short: ", "pos_excess": "⚠️ Extra: ",
        "slip_dialog_title": "Print Photocopy Receipt Slip", "slip_name_lbl": "Employee / Client Name :",
        "slip_unit_lbl": "Traffic Unit / Counter (Optional) :", "slip_date_lbl": "Date :", "slip_btn_print": "Print Now",
        "open_pdf_btn": "Open Selected File", "confirm_reset": "Are you sure you want to clear current operations and reset dashboard?",
        "btn_void_sel": "❌ Void Selected", "btn_restore_sel": "↩️ Restore Selected",
        "records_stats": "Shown: {shown} | Net Total: {net:,.2f} EGP | Grand System Sum: {total:,.2f} EGP",
        "legend_text": "🟥 Duplicate   ⬛ Voided (Deducted)",
        "menu_open_file": "Open Receipt File", "menu_void_tx": "❌ Void this Transaction", "menu_restore_tx": "↩️ Restore this Transaction",
        "void_confirm_title": "Confirm Void", "void_confirm_msg": "Are you sure you want to void record #{idx} with amount {amt:.2f} EGP?",
        "void_reason_title": "Void Reason", "void_reason_prompt": "Enter void reason (optional):",
        "void_already": "This transaction is already voided!", "restore_already": "This transaction is not voided!",
        "restore_confirm_title": "Confirm Restore", "restore_confirm_msg": "Do you want to restore record #{idx} with amount {amt:.2f} EGP?",
        "arch_title": "Smart Downloads Archiver & Reports", "arch_subtitle": "Automatically moves receipts and creates a daily summary PDF",
        "arch_dir_lbl": "Directory to Archive:", "arch_btn_browse": "Browse...",
        "arch_open_day_title": "Open Archived Daily Summary", "arch_btn_open_day": "📄 Open Daily Summary",
        "arch_btn_prev": "📁 Archive Previous Days & Build Summary PDFs", "arch_btn_all": "🗄️ Archive All Files & Build Summary PDFs",
        "arch_btn_open_folder": "📂 Open Archive Root Folder", "arch_ready": "Ready to archive...",
        "cash_win_title": "Cash & POS Reconciliation - A2R", "cash_hdr": "💵 Cash & POS Settlement",
        "cash_manual_lbl": "Manual Cash Amount:", "cash_pos_lbl": "Total POS (Cards):", "cash_denom_lbl": "{d} EGP Note:",
        "cash_tot_lbl": "Total Cash: {sum:,.2f} EGP", "cash_comb_lbl": "Combined Total (Cash + POS): {sum:,.2f} EGP",
        "cash_matched_lbl": "✓ Perfectly Matched with Insurance System", "cash_short_lbl": "Shortage: -{val:,.2f} EGP", "cash_extra_lbl": "Excess: +{val:,.2f} EGP",
        "cash_apply_btn": "Transfer Total to Matcher (Enter)", "manual_win_title": "Add Manual Receipt (PDF)",
        "manual_amt_lbl": "Amount (EGP)*:", "manual_name_lbl": "Insured Name (Optional):", "manual_plate_lbl": "Plate No (Optional):",
        "manual_unit_lbl": "Traffic Unit (Optional):", "manual_generate_btn": "Generate Manual Receipt PDF",
        "cut": "Cut", "copy": "Copy", "paste": "Paste", "select_all": "Select All",
        "restricted_admin": "This feature is restricted to administrator only!", "done": "Done",
        "status_void": "Voided ❌", "status_dup": "Duplicate ×{n} ⚠️", "status_wrong": "Other Unit", "status_missing": "Missing: ", "status_manual": "Manual Receipt", "status_ok": "Valid Receipt",
        "btn_full_console": "🖥️ Full Console", "btn_back_mini": "⚡ Mini Mode",
        "login_prompt": "🔒 Enter Password to Access Full Console", "access_denied": "Incorrect password. Access denied!",
        "mini_station_title": "A2R Mini Station", "mini_status_active": "● Instant Thermal Auto-Print Active",
        "mini_printed_count": "🖨️ Auto-Printed Today: {count} Receipts",
        "tray_open": "Open", "tray_console": "Full Console", "tray_exit": "Exit Application",
        "btn_reprint": "🖨️ Reprint", "menu_reprint": "🖨️ Reprint Receipt", "reprint_success": "Receipt sent to printer!",
        "btn_fix_printer": "⚙️ 57x90", "fix_printer_ok": "Default printer paper set to 57x90 mm!"
    },
    "ar": {
        "toggle_btn": "🌐 English", "dir_path": "مسار مجلد الإيصالات", "browse": "تحديد", "open": "فتح",
        "date_lbl": "تاريخ التقرير", "today": "اليوم", "yesterday": "أمس",
        "start": "⚡ بدء استخراج ومعالجة البيانات", "reset": "تصفير",
        "manual": "➕ إضافة يدوي", "summary_btn": "📊 ملخص الفحص", "print_slip": "🖨️ إيصال تصوير", "arch_hist_btn": "📚 سجل الأرشيف", "pos_close_btn": "🧾 تقفيل POS", "pos_pay_btn": "💳 إيصالات الدفع", "view_records": "🔍 عرض السجلات",
        "export_pdf": "📄 تقرير PDF", "kpi1": "عدد العمليات", "kpi2": "إجمالي مبالغ السيستم",
        "open_excel": "📊 فتح الإكسيل", "currency": "ج.م", "open_chrome": "🌐 بوابة المرور",
        "cash_btn": "💵 حاسبة الكاش", "clean_downloads": "📦 أرشفة", "autosync_on": "مزامنة تلقائية: مفعل", "autosync_off": "مزامنة تلقائية: معطل",
        "autoprint_on": "طباعة فورية: مفعل", "autoprint_off": "طباعة فورية: معطل", "invalid_date": "التاريخ المحدد غير صحيح!",
        "dir_missing": "مجلد الإيصالات المحدد غير موجود!",
        "pdf_missing": "ملف pdftotext.exe غير موجود في المجلد:\n",
        "summary_title": "ملخص فحص الوحدة", "unit_name_lbl": "وحدة المرور :", "period_lbl": "التاريخ :",
        "total_ops_lbl": "إجمالي العمليات :", "pdf_lbl": "إيصالات إلكترونية :", "txt_lbl": "معاملات يدوية :",
        "void_ops_lbl": "معاملات ملغية :", "duplicates_lbl": "عدد المكرر :", "wrong_lbl": "وحدة مختلفة :", "missing_lbl": "ناقص :",
        "total_amt_lbl": "إجمالي المبلغ :", "unspecified_unit": "وحدة غير محددة",
        "records_viewer_title": "عرض السجلات ومطابقتها", "no_records_yet": "لا توجد سجلات بعد. يرجى تشغيل المعالجة أولاً.",
        "no_summary_yet": "يرجى تشغيل عملية الاستخراج أولاً لعرض ملخص الفحص!", "search_placeholder": "بحث بالاسم، اللوحة، الشاسيه، الموتور...",
        "amt_filter_placeholder": "المبلغ...", "col_idx": "م", "col_unit": "الوحدة", "col_plate": "رقم اللوحة",
        "col_insured": "اسم المؤمن له", "col_amount": "المبلغ", "col_time": "الوقت", "col_make": "الماركة",
        "col_model": "الموديل", "col_chassis": "الشاسيه", "col_motor": "الموتور", "col_period": "المدة",
        "col_file": "الملف", "col_status": "الحالة", "pos_box_title": "مطابقة الخزينة (POS + كاش)",
        "pos_check_btn": "مطابقة", "pos_matched": "✓ مطابق", "pos_shortage": "⚠️ عجز: ", "pos_excess": "⚠️ زيادة: ",
        "slip_dialog_title": "طباعة إيصال التصوير", "slip_name_lbl": "اسم الموظف / العميل :",
        "slip_unit_lbl": "الوحدة / المنفذ (اختياري) :", "slip_date_lbl": "التاريخ :", "slip_btn_print": "طباعة الآن",
        "open_pdf_btn": "فتح الملف المحدد", "confirm_reset": "هل أنت متأكد من رغبتك في تصفير الشاشة والبيانات الحالية؟",
        "btn_void_sel": "❌ إلغاء المحددة", "btn_restore_sel": "↩️ استرجاع الملغية",
        "records_stats": "المعروض: {shown} | الصافي: {net:,.2f} ج.م | الإجمالي العام: {total:,.2f} ج.م",
        "legend_text": "🟥 مكرر   ⬛ ملغي (مخصوم)",
        "menu_open_file": "فتح ملف المعاملة", "menu_void_tx": "❌ إلغاء هذه المعاملة (تسجيل في قاعدة البيانات)", "menu_restore_tx": "↩️ استرجاع هذه المعاملة كمعاملة سليمة",
        "void_confirm_title": "تأكيد الإلغاء", "void_confirm_msg": "هل أنت متأكد من إلغاء المعاملة رقم {idx} بمبلغ {amt:.2f} ج.م وخصمها من الإجمالي؟",
        "void_reason_title": "سبب الإلغاء", "void_reason_prompt": "اكتب سبب الإلغاء (اختياري):",
        "void_already": "هذه المعاملة ملغية بالفعل!", "restore_already": "هذه المعاملة غير ملغية لتتم استعادتها!",
        "restore_confirm_title": "تأكيد الاسترجاع", "restore_confirm_msg": "هل تريد استرجاع المعاملة رقم {idx} بمبلغ {amt:.2f} ج.م وإلغاء خصمها؟",
        "arch_title": "📦 أرشفة مجلد الإيصالات وإدارة التقارير", "arch_subtitle": "يتم نقل الملفات مع توليد ملخص لكل يوم مؤرشف تلقائياً",
        "arch_dir_lbl": "المجلد المراد أرشفته:", "arch_btn_browse": "تحديد...",
        "arch_open_day_title": "فتح ملخص الفحص لأي يوم مؤرشف", "arch_btn_open_day": "📄 فتح ملخص اليوم",
        "arch_btn_prev": "📁 أرشفة الأيام السابقة وتوليد ملفات سامري PDF", "arch_btn_all": "🗄️ أرشفة كل الملفات القديمة وتوليد سامري PDF",
        "arch_btn_open_folder": "📂 فتح مجلد الأرشيف للمسار المختار", "arch_ready": "جاهز للأرشفة...",
        "cash_win_title": "تسوية النقدية والـ POS - A2R", "cash_hdr": "💵 تسوية الخزينة (كاش + POS)",
        "cash_manual_lbl": "المبلغ كاش (يدوي):", "cash_pos_lbl": "إجمالي الـ POS (فيزا):", "cash_denom_lbl": "فئة {d} ج:",
        "cash_tot_lbl": "إجمالي الكاش: {sum:,.2f} ج.م", "cash_comb_lbl": "المجموع الإجمالي (كاش + POS): {sum:,.2f} ج.م",
        "cash_matched_lbl": "✓ مطابق لسيستم التأمين تماماً", "cash_short_lbl": "عجز: -{val:,.2f} ج.م", "cash_extra_lbl": "زيادة: +{val:,.2f} ج.م",
        "cash_apply_btn": "ترحيل الإجمالي وإغلاق (Enter)", "manual_win_title": "إضافة معاملة يدوية (PDF)",
        "manual_amt_lbl": "المبلغ (جنيه)*:", "manual_name_lbl": "اسم المؤمن له (اختياري):", "manual_plate_lbl": "رقم اللوحة (اختياري):",
        "manual_unit_lbl": "وحدة المرور (اختياري):", "manual_generate_btn": "توليد إيصال تحصيل يدوي PDF",
        "cut": "قص", "copy": "نسخ", "paste": "لصق", "select_all": "تحديد الكل",
        "restricted_admin": "هذه الصلاحية متاحة للمشرف فقط!", "done": "تم",
        "status_void": "ملغي ❌", "status_dup": "مكرر ×{n} ⚠️", "status_wrong": "وحدة مختلفة", "status_missing": "ناقص: ", "status_manual": "معاملة يدوية", "status_ok": "إيصال سليم",
        "btn_full_console": "🖥️ النسخة الكاملة", "btn_back_mini": "⚡ وضع الميني",
        "login_prompt": "🔒 أدخل كلمة المرور لفتح النسخة الكاملة", "access_denied": "كلمة المرور غير صحيحة!",
        "mini_station_title": "A2R Mini Station", "mini_status_active": "● محرك الطباعة الفورية يعمل بنشاط",
        "mini_printed_count": "🖨️ المطبوع اليوم تلقائياً: {count} إيصال",
        "tray_open": "فتح البرنامج", "tray_console": "النسخة الكاملة", "tray_exit": "إغلاق البرنامج نهائياً",
        "btn_reprint": "🖨️ إعادة طباعة", "menu_reprint": "🖨️ إعادة طباعة هذا الإيصال", "reprint_success": "تم إرسال الإيصال للطابعة الحرارية!",
        "btn_fix_printer": "⚙️ 57x90", "fix_printer_ok": "تم ضبط مقاس الطابعة الافتراضية 57x90 مم بنجاح!"
    }
}

CURRENT_LANG = "en"

def tr(key, **kwargs):
    text = LANGUAGES.get(CURRENT_LANG, LANGUAGES["en"]).get(key, key)
    if kwargs:
        try: return text.format(**kwargs)
        except Exception as _e: _log_silent("tr#1", _e)
    return text

def format_arabic_for_dropdown(text):
    if not text: return ""
    if REPORTLAB_AVAILABLE and re.search(r"[\u0621-\u064A]", text):
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception as _e:
            _log_silent("format_arabic_for_dropdown#1", _e)
    return text

MANUAL_MAX_AMOUNT = 10_000_000

def parse_manual_amount(raw):
    """نص المبلغ → رقم صالح أو None. بيرفض nan/inf والصفر والسالب والمبلغ الضخم جدًا (غالبًا غلطة كتابة).
    '521,57' = فاصلة عشرية، و'1,500' = فاصل آلاف. والمبلغ بيتقرّب لخانتين عشان الملف والقاعدة يتطابقوا."""
    s = str(raw or "").strip().replace("٫", ".")
    if not s:
        return None
    if re.fullmatch(r"\d+,\d{1,2}", s):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    if not _math.isfinite(v) or v <= 0 or v > MANUAL_MAX_AMOUNT:
        return None
    return round(v, 2)

def unique_manual_filename(dest, amt, now_dt):
    """اسم الملف amount_HHMMSS.pdf. لو موجود (نفس المبلغ في نفس الثانية) بنزوّد ثانية عشان ميتكتبش فوق إيصال موجود."""
    for _ in range(60):
        base = f"{amt:.2f}_{now_dt.strftime('%H%M%S')}.pdf"
        if not os.path.exists(os.path.join(dest, base)) and not os.path.exists(os.path.join(dest, "_" + base)):
            return base, now_dt
        now_dt += datetime.timedelta(seconds=1)
    return base, now_dt

class SafeArabicComboBox(ctk.CTkComboBox):
    def __init__(self, master, values=None, command=None, **kwargs):
        self._user_command = command
        self._raw_values = list(values) if values else []
        self._val_map = {}
        display_vals = []
        for v in self._raw_values:
            disp = format_arabic_for_dropdown(v)
            self._val_map[disp] = v
            display_vals.append(disp)

        super().__init__(master, values=display_vals, command=self._internal_command, **kwargs)

    def _internal_command(self, choice):
        raw_choice = self._val_map.get(choice, choice)
        if self._user_command:
            self._user_command(raw_choice)

    def get(self):
        val = super().get()
        return self._val_map.get(val, val)

    def set(self, value):
        disp = format_arabic_for_dropdown(value)
        self._val_map[disp] = value
        super().set(disp)

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._raw_values = list(kwargs["values"])
            self._val_map = {}
            display_vals = []
            for v in self._raw_values:
                disp = format_arabic_for_dropdown(v)
                self._val_map[disp] = v
                display_vals.append(disp)
            kwargs["values"] = display_vals
        super().configure(**kwargs)

def play_sound_matched():
    if SOUND_MUTED: return
    def _tone():
        try:
            winsound.Beep(987, 100)
            winsound.Beep(1318, 120)
            winsound.Beep(1760, 160)
        except Exception as _e: _log_silent("_tone#1", _e)
    threading.Thread(target=_tone, daemon=True).start()

def play_sound_diff():
    if SOUND_MUTED: return
    def _tone():
        try:
            winsound.Beep(520, 150)
            winsound.Beep(440, 200)
        except Exception as _e: _log_silent("_tone#2", _e)
    threading.Thread(target=_tone, daemon=True).start()

def _entry_widget(widget):
    return widget._entry if hasattr(widget, "_entry") else widget

def _entry_editable(t):
    try: return str(t.cget("state")) == "normal"
    except Exception: return True

def _clip_copy(t, cut=False):
    try:
        if not t.selection_present(): return
        a, b = t.index("sel.first"), t.index("sel.last")
        txt = t.get()[a:b]
    except tk.TclError: return
    try:
        t.clipboard_clear()
        t.clipboard_append(txt)
    except tk.TclError: return
    if cut and _entry_editable(t):
        try: t.delete(a, b)
        except tk.TclError: pass

def _clip_paste(t):
    if not _entry_editable(t): return
    try: text = t.clipboard_get()
    except tk.TclError: return
    text = text.replace("\r", "").replace("\n", " ")
    try:
        if t.selection_present():
            t.delete("sel.first", "sel.last")
    except tk.TclError: pass
    try: t.insert("insert", text)
    except tk.TclError: pass

def _clip_select_all(t):
    try:
        t.select_range(0, "end")
        t.icursor("end")
    except tk.TclError: pass

def attach_context_menu(widget):
    target = _entry_widget(widget)
    menu = tk.Menu(target, tearoff=0)
    menu.add_command(label=tr("cut"), command=lambda: _clip_copy(target, cut=True))
    menu.add_command(label=tr("copy"), command=lambda: _clip_copy(target))
    menu.add_command(label=tr("paste"), command=lambda: _clip_paste(target))
    menu.add_separator()
    menu.add_command(label=tr("select_all"), command=lambda: _clip_select_all(target))

    def show_menu(event):
        menu.entryconfigure(0, label=tr("cut"))
        menu.entryconfigure(1, label=tr("copy"))
        menu.entryconfigure(2, label=tr("paste"))
        menu.entryconfigure(4, label=tr("select_all"))
        target.focus_set()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    target.bind("<Button-3>", show_menu)

def install_clipboard_shortcuts(root):
    def handler(event):
        w = event.widget
        try: cls = w.winfo_class()
        except Exception: return None
        if cls not in ("Entry", "TEntry"): return None
        kc = event.keycode
        ks = (event.keysym or "").lower()
        if kc == 65:
            _clip_select_all(w)
        elif kc in (67, 86, 88) and ks not in ("c", "v", "x"):
            if kc == 67: _clip_copy(w)
            elif kc == 88: _clip_copy(w, cut=True)
            else: _clip_paste(w)
        else:
            return None
        return "break"
    root.bind_all("<Control-KeyPress>", handler)

def center_window_relative(win, parent, width, height):
    win.update_idletasks()
    set_window_icon_safe(win)
    try: parent_hidden = (parent.state() == "withdrawn")
    except Exception: parent_hidden = False
    if parent_hidden:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")
        return
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    x = px + (pw - width) // 2
    y = py + (ph - height) // 2
    win.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
    win.transient(parent)

def clean_arabic(text):
    bidi_chars = ['\u202a', '\u202b', '\u202c', '\u202d', '\u202e', '\u200e', '\u200f', '\u061c', '\u2066', '\u2067', '\u2068', '\u2069', 'ـ']
    for c in bidi_chars: text = text.replace(c, '')
    return unicodedata.normalize('NFKC', text)

UNITS_LIST = [
    "ابيس 1", "ابيس 2", "ابيس 3",
    "برج العرب 1", "برج العرب 2", "برج العرب 3", "برج العرب 4",
    "المنتزة 1", "المنتزة 2", "المنتزة 3",
    "محرم بك 1", "محرم بك 2",
    "العجمي 1", "العجمي 2",
    "القبارى", "مصطفى كامل", "مديرية الأمن", "ميناء الإسكندرية", "مجمع خدمات مصر"
]

# قاعدة بيانات: الوحدة -> رقم الماكينة (Terminal ID)
UNIT_TERMINALS = {
    "ابيس 1": "50335710",
    "ابيس 2": "50335993",
    "ابيس 3": "50335987",
    "برج العرب 1": "50325716",
    "برج العرب 2": "50335998",
    "برج العرب 3": "50335994",
    "برج العرب 4": "50335711",
    "المنتزة 1": "50382298",
    "المنتزة 2": "50382315",
    "المنتزة 3": "50383712",
    "محرم بك 1": "50382306",
    "محرم بك 2": "50382316",
    "العجمي 1": "50382308",
    "العجمي 2": "50383706",
    "القبارى": "50382300",
    "مصطفى كامل": "50383702",
    "مديرية الأمن": "50382312",
    "ميناء الإسكندرية": "50383699",
    "مجمع خدمات مصر": "50383700",
}

EMPLOYEES_LIST = [
    "خالد محمد", "محمد السيد", "محمد زكريا", "احمد مصطفى", "زياد أحمد",
    "مصطفى محمد", "ادهم ماهر", "احمد وليد", "عبدالله محمد", "محمد مجدى",
    "سماح جمال", "امير حسين", "احمد سعيد", "كريم صبرى", "احمد مجدى",
    "عمر فتحى", "محمد احمد", "احمد جابر", "باسم محمد", "باسم مصطفى", "احمد رمضان"
]

STRICT_UNITS = [
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*ابيس", "وحدة مرور ابيس"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*برج\s+العرب", "وحدة مرور برج العرب"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*المنتز[ةه]", "وحدة مرور المنتزة"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*محرم\s+بك", "وحدة مرور محرم بك"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*العجم[ىي]", "وحدة مرور العجمي"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*القبار[ىي]", "وحدة مرور القبارى"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*مصطف[ىي]\s+كامل", "وحدة مرور مصطفى كامل"),
    (r"(?:وحدة\s+مرور|مرور|وحدة)?\s*مديري[ةه]\s+الأمن", "وحدة مرور مديرية الأمن"),
    (r"(?:منفذ|ميناء)\s+الإسكندري[ةه]|ميناء\s+اسكندري[ةه]", "منفذ ميناء الإسكندرية"),
    (r"مجمع\s+خدمات\s+مصر", "مجمع خدمات مصر")
]
UNIT_NAMES = [v for _, v in STRICT_UNITS]

def detect_unit_from_text(text):
    if not text: return None
    cleaned = clean_arabic(text)
    for pattern, mapped_val in STRICT_UNITS:
        if re.search(pattern, cleaned): return mapped_val
    return None

def parse_print_time(time_str):
    time_str = time_str.strip()
    patterns = [
        ("%H:%M %d-%m-%Y", r"^\d{2}:\d{2}\s+\d{2}-\d{2}-\d{4}$"),
        ("%d-%m-%Y %H:%M", r"^\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}$"),
        ("%Y-%m-%d %H:%M", r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$"),
        ("%d/%m/%Y %H:%M", r"^\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}$"),
        ("%H:%M %d/%m/%Y", r"^\d{2}:\d{2}\s+\d{2}/\d{2}/\d{4}$")
    ]
    for fmt, pat in patterns:
        if re.match(pat, time_str):
            try: return datetime.datetime.strptime(time_str, fmt)
            except Exception as _e: _log_silent("parse_print_time#1", _e)
    return None

def extract_date_from_text(txt):
    if not txt: return None
    time_m = re.search(r"(\d{2}:\d{2}\s+\d{2}[-/]\d{2}[-/]\d{4})|(\d{2}[-/]\d{2}[-/]\d{4}\s+\d{2}:\d{2})|(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})", txt)
    if time_m:
        raw_t = time_m.group(0).strip().replace("/", "-")
        dt_obj = parse_print_time(raw_t)
        if dt_obj: return dt_obj.date()
    dates = re.findall(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b|\b(\d{4}[-/]\d{2}[-/]\d{2})\b", txt)
    for d1, d2 in dates:
        d_str = (d1 or d2).replace("/", "-")
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(d_str, fmt).date()
            except Exception as _e: _log_silent("extract_date_from_text#1", _e)
    return None

def create_manual_receipt_pdf(filepath, unit_val, plate_val, name_val, amt_val, op_dt=None):
    if not REPORTLAB_AVAILABLE:
        raise Exception("ReportLab is not installed!")
    op_dt = op_dt or datetime.datetime.now()
    PAGE_W, PAGE_H = 160, 240
    c = canvas.Canvas(filepath, pagesize=(PAGE_W, PAGE_H))
    font_name = "Helvetica-Bold"
    for f_cand in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]:
        if os.path.exists(f_cand):
            try:
                pdfmetrics.registerFont(TTFont("ReceiptArabic", f_cand))
                font_name = "ReceiptArabic"
                break
            except Exception as _e: _log_silent("create_manual_receipt_pdf#1", _e)

    def _ar(t):
        try: return get_display(arabic_reshaper.reshape(str(t)))
        except Exception: return str(t)

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.2)
    c.rect(4, 4, PAGE_W - 8, PAGE_H - 8)

    c.setFont(font_name, 13)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 20, _ar("إيصال تحصيل يدوي"))

    c.setLineWidth(0.8)
    c.roundRect(PAGE_W / 2 - 55, PAGE_H - 36, 110, 14, 3, fill=False, stroke=True)
    c.setFont(font_name, 8.5)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 33, _ar("معاملة يدوية - للمراجعة"))

    c.line(10, PAGE_H - 42, PAGE_W - 10, PAGE_H - 42)

    y = PAGE_H - 58
    rows = [
        ("وحدة المرور", unit_val if unit_val != "-" else "وحدة غير محددة"),
        ("اسم المؤمن له", name_val),
        ("رقم اللوحة", plate_val),
        ("تاريخ العملية", op_dt.strftime("%d-%m-%Y")),
        ("وقت الطباعة", op_dt.strftime("%H:%M %d-%m-%Y")),
    ]

    for lbl, val in rows:
        c.setFont(font_name, 9)
        c.setFillColorRGB(0, 0, 0)
        c.drawRightString(PAGE_W - 10, y, _ar(lbl))
        c.drawString(10, y, _ar(val))
        c.setLineWidth(0.4)
        c.setDash(2, 2)
        c.line(8, y - 4, PAGE_W - 8, y - 4)
        c.setDash()
        y -= 20

    box_height = 68
    box_y = y - 56
    c.setLineWidth(1.2)
    c.rect(8, box_y, PAGE_W - 16, box_height, fill=False, stroke=True)

    c.setFont(font_name, 8.5)
    c.drawCentredString(PAGE_W / 2, box_y + box_height - 14, _ar("تنبيه: إيصال تحصيل يدوي مؤقت"))
    c.setFont(font_name, 7.5)
    c.drawCentredString(PAGE_W / 2, box_y + box_height - 24, _ar("(غير معتمد نهائياً - الدفع إلكتروني فيزا POS)"))

    c.setLineWidth(0.6)
    c.setDash(1, 2)
    c.line(12, box_y + 32, PAGE_W - 12, box_y + 32)
    c.setDash()

    c.setFont(font_name, 9)
    c.drawCentredString(PAGE_W / 2, box_y + 20, _ar("المبلغ المحصل:"))
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(PAGE_W / 2, box_y + 6, f"{amt_val:,.2f} EGP")

    c.save()

SLIP_SIZE_MM = 46        # مقاس البون المربع (مم) — صغّره/كبّره من هنا
SLIP_PAPER_W_MM = 57     # عرض الورقة
SLIP_PAPER_H_MM = 90     # طول الورقة
SLIP_DESIGN_MM = 70      # مقاس التصميم الأصلي (الخطوط والإطار بتتصغر بنفس النسبة)
SLIP_OFFSET_X_MM = 0     # لو الطابعة بتزحزح البون: + يمين / - شمال
SLIP_OFFSET_Y_MM = 0     # + لفوق / - لتحت
SLIP_FONT_CANDIDATES = [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]

def create_photocopy_slip_pdf(filepath, emp_name, unit_name, date_str, terminal_id=""):
    if not REPORTLAB_AVAILABLE:
        return False
    _pt = 72 / 25.4
    SHEET_W, SHEET_H = SLIP_PAPER_W_MM * _pt, SLIP_PAPER_H_MM * _pt   # الصفحة = مقاس الورقة (مفيش shrink يزحزح)
    box = SLIP_SIZE_MM * _pt
    S = SLIP_DESIGN_MM * _pt
    PAGE_W = PAGE_H = S
    c = canvas.Canvas(filepath, pagesize=(SHEET_W, SHEET_H))
    font_name = "Helvetica-Bold"
    for f_cand in SLIP_FONT_CANDIDATES:
        if os.path.exists(f_cand):
            try:
                pdfmetrics.registerFont(TTFont("SlipArabic", f_cand))
                font_name = "SlipArabic"
                break
            except Exception as _e: _log_silent("create_photocopy_slip_pdf#1", _e)

    def _ar(t):
        try: return get_display(arabic_reshaper.reshape(str(t)))
        except Exception: return str(t)

    # البون كله في نص الورقة (أفقي ورأسي)
    c.saveState()
    c.translate((SHEET_W - box) / 2 + SLIP_OFFSET_X_MM * _pt, (SHEET_H - box) / 2 + SLIP_OFFSET_Y_MM * _pt)
    c.scale(box / S, box / S)

    # الإطار
    margin = 7
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(2)
    c.roundRect(margin, margin, S - 2 * margin, S - 2 * margin, 9, stroke=1, fill=0)

    # الأسطر: الاسم الطويل بينزل لسطرين/تلاتة بدل ما يطلع بره الإطار، والخط بيصغر لو لزم
    inner_w = S - 2 * margin - 18

    def _fit_text(text, fn, base, min_single=16):
        sz = base
        while sz >= min_single:
            if pdfmetrics.stringWidth(_ar(text), fn, sz) <= inner_w:
                return [(_ar(text), fn, sz)]
            sz -= 1
        sz = min_single
        rows, cur = [], ""
        for w in str(text).split():
            cand = (cur + " " + w).strip()
            if cur and pdfmetrics.stringWidth(_ar(cand), fn, sz) > inner_w:
                rows.append(cur)
                cur = w
            else:
                cur = cand
        if cur:
            rows.append(cur)
        out = []
        for row in rows:
            s_, txt = sz, _ar(row)
            while s_ > 9 and pdfmetrics.stringWidth(txt, fn, s_) > inner_w:
                s_ -= 1
            out.append((txt, fn, s_))
        return out

    fitted = []
    if emp_name:
        fitted += _fit_text(emp_name, font_name, 25)
    if unit_name:
        fitted += _fit_text(unit_name, font_name, 21)
    if terminal_id:
        fitted += _fit_text(f"TID: {terminal_id}", "Helvetica-Bold", 18, min_single=10)
    fitted += _fit_text(str(date_str), "Helvetica-Bold", 19, min_single=10)

    gap = 10
    total_h = sum(sz for _, _, sz in fitted) + gap * (len(fitted) - 1)
    y_top = (PAGE_H + total_h) / 2
    c.setFillColorRGB(0, 0, 0)
    for txt, fn, sz in fitted:
        c.setFont(fn, sz)
        c.drawCentredString(PAGE_W / 2, y_top - sz * 0.8, txt)
        y_top -= sz + gap
    c.restoreState()
    c.save()
    return True

# ================= الوحدة المختارة في إيصال السمري (اجباري) + حفظها لليوم عشان تظهر في سمري الأرشيف =================
def _day_iso_from_label(label):
    """'11.11.2026' أو '11-11-2026' -> '2026-11-11' (أو None)."""
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", str(label or ""))
    if not m: return None
    try: return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except Exception: return None

def summary_unit_save(day_iso, unit, tid):
    try:
        conn = db_connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS system_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT)")
            conn.execute("INSERT OR REPLACE INTO system_meta (meta_key, meta_value) VALUES (?, ?)",
                         (f"summary_unit:{day_iso}", json.dumps({"unit": unit, "tid": tid}, ensure_ascii=False)))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        log_exception("summary_unit_save", e)

def summary_unit_load(day_iso):
    """بترجّع (اسم الوحدة، رقم الترمنل) المختارين لليوم ده، أو None لو مفيش."""
    if not day_iso: return None
    try:
        conn = db_connect()
        try:
            row = conn.execute("SELECT meta_value FROM system_meta WHERE meta_key = ?", (f"summary_unit:{day_iso}",)).fetchone()
        finally:
            conn.close()
        if not row: return None
        d = json.loads(row[0])
        if d.get("unit"): return d["unit"], d.get("tid", "")
    except Exception as e:
        _log_silent("summary_unit_load", e)
    return None

def _draw_summary_unit_block(c, font_name, ar, page_w, unit, tid, y0=58, h=114):
    """مربع منفصل (بعيد عن باقي بيانات الإيصال) فيه اسم الوحدة المختارة ورقم الترمنل."""
    if not unit: return
    x0, w = 12, page_w - 24
    c.saveState()
    c.setStrokeColorRGB(0.15, 0.35, 0.55)
    c.setLineWidth(1.2)
    c.setDash(3, 2)
    c.roundRect(x0, y0, w, h, 6, stroke=1, fill=0)
    c.setDash()
    c.setFont(font_name, 9)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawCentredString(page_w / 2, y0 + h - 16, ar("الوحدة المختارة"))
    txt, sz = ar(unit), 18
    while sz > 9 and pdfmetrics.stringWidth(txt, font_name, sz) > w - 20: sz -= 1
    c.setFont(font_name, sz)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(page_w / 2, y0 + h - 42, txt)
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.6)
    c.line(x0 + 10, y0 + h - 52, x0 + w - 10, y0 + h - 52)
    c.setFont(font_name, 9)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawCentredString(page_w / 2, y0 + h - 68, ar("رقم الترمنل"))
    c.setFont("Helvetica-Bold", 17)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(page_w / 2, y0 + h - 92, str(tid) if tid else "-")
    c.restoreState()


# ================= فهرس الأرشيف + النسخة الاحتياطية المخفية + البحث العام =================
ARCHIVE_BACKUP_DIR = os.path.join(DOCUMENTS_DIR, ".archive_backup")
_ARCHIVE_LOCK = threading.Lock()

def T2(ar, en):
    return ar if CURRENT_LANG == "ar" else en

def _hide_path(p):
    """إخفاء المجلد على ويندوز (Hidden) — الاسم نفسه يبدأ بنقطة كمان."""
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x02)
    except Exception as e:
        log_exception("hide_path", e)

def _ensure_archive_index():
    conn = db_connect()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS archive_index (
            path TEXT PRIMARY KEY, day TEXT, file TEXT, unit TEXT, plate TEXT,
            insured TEXT, amount REAL, rec_time TEXT, is_manual INTEGER,
            is_void INTEGER, is_receipt INTEGER, mtime REAL, size INTEGER
        )
    ''')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_arch_day ON archive_index(day)")
    conn.commit()
    return conn

def _archive_day_from_path(root, path):
    try:
        parts = os.path.relpath(path, root).split(os.sep)
        if len(parts) < 4: return None
        y, m, d = int(parts[0]), int(parts[1].split("-")[0]), int(parts[2])
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return None

def archive_index_update(folder_path, progress=None):
    """يفهرس إيصالات الأرشيف الجديدة فقط (الباقي يتخطاه) ويشيل المحذوف ويحدّث حالة الإلغاء."""
    root = os.path.join(folder_path, ARCHIVE_DIRNAME)
    if not os.path.isdir(root): return 0
    load_void_map()
    manual_map = load_manual_map()
    files = []
    for dp, _dn, fns in os.walk(root):
        for f in fns:
            if not f.lower().endswith((".pdf", ".txt")): continue
            if f.startswith("Samary_") or f.endswith("_cropped.pdf") or f.endswith("_Summary.pdf"): continue
            p = os.path.join(dp, f)
            day = _archive_day_from_path(root, p)
            if day: files.append((p, day))

    conn = _ensure_archive_index()
    done_new = 0
    try:
        existing = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT path, mtime, size FROM archive_index")}
        current = {p for p, _ in files}
        stale = [(p,) for p in existing if p not in current]
        if stale:
            conn.executemany("DELETE FROM archive_index WHERE path = ?", stale)

        todo = []
        for p, day in files:
            try: st = os.stat(p)
            except OSError: continue
            old = existing.get(p)
            if old and abs(old[0] - st.st_mtime) < 1 and old[1] == st.st_size: continue
            todo.append((p, day, st))

        total = len(todo)
        for i, (p, day, st) in enumerate(todo, 1):
            rec = None
            try:
                if p.lower().endswith(".txt"): rec = read_txt_record(p, datetime.date.fromisoformat(day))
                else: rec = read_pdf_record(p, manual_map)
            except Exception as e: log_exception(f"archive_index:{os.path.basename(p)}", e)
            fname = os.path.basename(p)
            if rec:
                row = (p, day, fname, rec["unit"], rec["plate"], rec["insured"], float(rec["amount"]),
                       rec["time"], int(bool(rec["is_manual"])), int(bool(rec["is_void"])), 1, st.st_mtime, st.st_size)
            else:
                row = (p, day, fname, "", "-", "-", 0.0, "-", 0, 0, 0, st.st_mtime, st.st_size)
            conn.execute("INSERT OR REPLACE INTO archive_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            done_new += 1
            if i % 40 == 0:
                conn.commit()
                if progress: progress(i, total)
        conn.commit()
        if progress and total: progress(total, total)

        # تحديث حالة الإلغاء (ممكن تتغير بعد الأرشفة)
        upd = []
        for p, fname, cur in conn.execute("SELECT path, file, is_void FROM archive_index WHERE is_receipt = 1").fetchall():
            v = int(fname.startswith("_") or fname.lstrip("_") in _VOID_KEYS)
            if v != cur: upd.append((v, p))
        if upd:
            conn.executemany("UPDATE archive_index SET is_void = ? WHERE path = ?", upd)
        conn.commit()
    finally:
        conn.close()
    return done_new

def _backup_db_safely(db_dir, keep_days=14):
    """نسخ القاعدة بأمان: فحص سلامة قبل النسخ، كتابة لملف مؤقت ثم استبدال ذري (النسخة السليمة القديمة
    متتمسحش لو النسخ فشل)، ونسخة مؤرخة لكل يوم مع الاحتفاظ بآخر keep_days يوم."""
    s_conn = db_connect()
    try:
        r = s_conn.execute("PRAGMA quick_check").fetchone()
        if not r or r[0] != "ok":
            log_exception("archive_backup_db", f"quick_check failed, backup skipped: {r}")
            return False
        latest = os.path.join(db_dir, "a2r_vault_backup.db")
        tmp = latest + ".tmp"
        if os.path.exists(tmp): os.remove(tmp)
        d_conn = sqlite3.connect(tmp)
        try: s_conn.backup(d_conn)
        finally: d_conn.close()
        os.replace(tmp, latest)
    finally:
        s_conn.close()
    day = datetime.datetime.now().strftime("%Y%m%d")
    dated = os.path.join(db_dir, f"a2r_vault_{day}.db")
    dtmp = dated + ".tmp"
    shutil.copy2(latest, dtmp)
    os.replace(dtmp, dated)
    olds = sorted(glob.glob(os.path.join(db_dir, "a2r_vault_????????.db")))
    for p in olds[:-keep_days]:
        try: os.remove(p)
        except Exception as e: log_exception("archive_backup_prune", e)
    return True

def archive_backup(folder_path):
    """نسخة احتياطية تراكمية للأرشيف في فولدر مخفي جوه فولدر تقارير البرنامج. مفيش حاجة بتتمسح من النسخة."""
    src = os.path.join(folder_path, ARCHIVE_DIRNAME)
    if not os.path.isdir(src): return 0
    os.makedirs(ARCHIVE_BACKUP_DIR, exist_ok=True)
    _hide_path(ARCHIVE_BACKUP_DIR)
    copied = 0
    for dp, _dn, fns in os.walk(src):
        rel = os.path.relpath(dp, src)
        dst_dir = ARCHIVE_BACKUP_DIR if rel == "." else os.path.join(ARCHIVE_BACKUP_DIR, rel)
        for f in fns:
            if f.startswith("~"): continue          # ملفات مؤقتة (إكسيل بيتكتب دلوقتي)
            s, d = os.path.join(dp, f), os.path.join(dst_dir, f)
            try:
                ss = os.stat(s)
                if os.path.exists(d):
                    ds = os.stat(d)
                    if ds.st_size == ss.st_size and abs(ds.st_mtime - ss.st_mtime) < 2: continue
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(s, d)
                copied += 1
            except Exception as e:
                log_exception(f"archive_backup:{f}", e)
    # نسخة من قاعدة البيانات (الإلغاءات/اليدوي/الفهرس) جنب الأرشيف
    try:
        db_dir = os.path.join(ARCHIVE_BACKUP_DIR, "_db")
        os.makedirs(db_dir, exist_ok=True)
        _backup_db_safely(db_dir)
    except Exception as e:
        log_exception("archive_backup_db", e)
    return copied

def archive_maintenance(folder_path, progress=None):
    """فهرسة + نسخ احتياطي. لو في عملية شغالة بالفعل بترجع None ومش بتتكرر."""
    if not _ARCHIVE_LOCK.acquire(blocking=False): return None
    try:
        n = archive_index_update(folder_path, progress)
        b = archive_backup(folder_path)
        try: _archive_search_rows()
        except Exception as e: log_exception("archive_search_warm", e)
        return n, b
    except Exception as e:
        log_exception("archive_maintenance", e)
        return None
    finally:
        _ARCHIVE_LOCK.release()

def archive_load_rows():
    conn = _ensure_archive_index()
    try:
        return conn.execute(
            "SELECT path, day, file, unit, plate, insured, amount, rec_time, is_manual, is_void "
            "FROM archive_index WHERE is_receipt = 1").fetchall()
    finally:
        conn.close()

def archive_day_folder_from_index(day_iso):
    """فولدر اليوم من الفهرس (لو اسم الشهر في الفولدر اتغير بسبب لغة الويندوز)."""
    try:
        conn = _ensure_archive_index()
        try:
            row = conn.execute("SELECT path FROM archive_index WHERE day = ? LIMIT 1", (day_iso,)).fetchone()
        finally:
            conn.close()
        if row: return os.path.dirname(row[0])
    except Exception as e:
        log_exception("archive_day_folder_from_index", e)
    return None

def archive_day_stats(rows):
    days = {}
    for path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void in rows:
        d = days.setdefault(day, {"day": day, "ops": 0, "total": 0.0, "manual": 0, "void": 0,
                                  "dup": 0, "missing": 0, "_keys": Counter()})
        if is_void:
            d["void"] += 1
            continue
        d["ops"] += 1
        d["total"] += amount
        if is_manual: d["manual"] += 1
        if amount <= 0 or (not is_manual and (plate in ("-", "") or unit in (UNSPEC, ""))):
            d["missing"] += 1
        if plate not in ("-", ""):
            d["_keys"][(plate, rtime, round(amount, 2))] += 1
    out = []
    for d in days.values():
        d["dup"] = sum(c - 1 for c in d["_keys"].values() if c > 1)
        d.pop("_keys", None)
        out.append(d)
    out.sort(key=lambda x: x["day"], reverse=True)
    return out

def _norm_search(s):
    s = clean_arabic(str(s or "")).lower()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        s = s.replace(a, b)
    return re.sub(r"[\s\-_]+", "", s)

_ARCH_SEARCH_CACHE = {"sig": None, "rows": []}
_ARCH_SEARCH_LOCK = threading.Lock()

def _archive_search_rows():
    """صفوف الأرشيف + النصوص المُطبَّعة (plate/insured/file) محسوبة مرة واحدة.
    بتتجدد بس لما الفهرس يتغيّر (بصمة: عدد الصفوف ومجاميع mtime/is_void/amount)."""
    conn = _ensure_archive_index()
    try:
        sig = conn.execute("SELECT COUNT(*), IFNULL(SUM(mtime),0), IFNULL(SUM(is_void),0), "
                           "IFNULL(SUM(amount),0) FROM archive_index").fetchone()
        with _ARCH_SEARCH_LOCK:
            if _ARCH_SEARCH_CACHE["sig"] == sig:
                return _ARCH_SEARCH_CACHE["rows"]
        rows = conn.execute(
            "SELECT path, day, file, unit, plate, insured, amount, rec_time, is_manual, is_void "
            "FROM archive_index WHERE is_receipt = 1").fetchall()
    finally:
        conn.close()
    prepared = [(r, _norm_search(r[4]), _norm_search(r[5]), _norm_search(r[2])) for r in rows]
    with _ARCH_SEARCH_LOCK:
        _ARCH_SEARCH_CACHE["sig"] = sig
        _ARCH_SEARCH_CACHE["rows"] = prepared
    return prepared

def archive_search(query, include_void=True, limit=3000):
    q = _norm_search(query)
    if not q: return []
    amt = None
    try: amt = float(str(query).strip().replace(",", ""))
    except Exception as _e: _log_silent("archive_search#1", _e)
    out = []
    for r, n_plate, n_insured, n_file in _archive_search_rows():
        path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void = r
        if is_void and not include_void: continue
        hit = q in n_plate or q in n_insured or q in n_file
        if not hit and amt is not None and abs(amount - amt) < 0.005: hit = True
        if hit: out.append(r)
    out.sort(key=lambda r: (r[1], r[7]), reverse=True)
    return out[:limit]

def parse_flex_date(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try: return datetime.datetime.strptime(s, fmt).date()
        except Exception as _e: _log_silent("parse_flex_date#1", _e)
    return None

# ================= كنس الأرشيف: أي ملف مش بتاع النهارده يتنقل للأرشيف =================
_SWEEP_CACHE = {}
_SWEEP_LOCK = threading.Lock()

_CACHE_LIMIT = 20000
_CACHE_LOCK = threading.Lock()

def _cache_put(cache, key, val):
    """تخزين مؤقت بحد أقصى: لما يعدّي الحد بنشيل أقدم نصف الإدخالات (القاموس بيحفظ ترتيب الإضافة).
    قبل كده الـ cache كان بيكبر مع كل ملف أُرشف طول عمر البرنامج."""
    with _CACHE_LOCK:
        cache[key] = val
        if len(cache) > _CACHE_LIMIT:
            for k in list(cache)[:_CACHE_LIMIT // 2]:
                cache.pop(k, None)

def _unique_dest(dest):
    """لو في ملف بنفس الاسم في الأرشيف (ويندوز بيرفض النقل) نضيف رقم بدل ما الملف يفضل برا."""
    if not os.path.exists(dest): return dest
    base, ext = os.path.splitext(dest)
    n = 1
    while os.path.exists(f"{base} ({n}){ext}"): n += 1
    return f"{base} ({n}){ext}"

def _sweep_file_date(path, fname, manual_map, mdate):
    if fname.lower().endswith(".txt"):
        rec = read_txt_record(path, mdate)
        return rec["actual_date"] if rec else None      # txt مش إيصال → نسيبه
    if MANUAL_NAME_RE.match(fname):
        row = manual_map.get(fname)
        if row:
            dt_m = parse_vault_dt(row[4])
            return dt_m.date() if dt_m else mdate
        return mdate
    raw = run_pdftotext(path)
    if is_receipt_text(raw):
        f = parse_receipt(path, raw)
        return f["dt"].date() if f["dt"] else mdate
    return extract_date_from_text(raw) or mdate

def archive_sweep(folder_path, progress=None):
    """ينقل كل ملف (PDF/TXT) تاريخه مش النهارده إلى الأرشيف، لأي سبب:
    تاريخ مستقبلي غلط ← بنستخدم تاريخ الملف، خطأ قراءة ← تاريخ الملف، اسم مكرر ← بنزود رقم.
    يرجّع (عدد المنقول، فولدرات الأيام اللي اتغيّرت)."""
    ensure_archive_root(folder_path)
    manual_map = load_manual_map()
    load_void_map()
    today = datetime.date.today()
    cands = [f for f in glob.glob(os.path.join(folder_path, "*.pdf"))
             if not f.endswith("_Summary.pdf") and not f.endswith("_cropped.pdf")]
    cands += [f for f in glob.glob(os.path.join(folder_path, "*.txt")) if os.path.basename(f) != "Copy_Slip.txt"]
    total, moved, touched = len(cands), 0, set()

    for idx, path in enumerate(cands, 1):
        fname = os.path.basename(path)
        if progress: progress(idx, total, fname)
        try: stt = os.stat(path)
        except OSError: continue
        mdate = datetime.date.fromtimestamp(stt.st_mtime)
        ck = (path, stt.st_mtime, stt.st_size)
        file_date = _SWEEP_CACHE.get(ck)
        if file_date is None:
            try: file_date = _sweep_file_date(path, fname, manual_map, mdate)
            except Exception as e:
                log_exception(f"sweep_date:{fname}", e)
                file_date = mdate
            if file_date is None: continue
            _cache_put(_SWEEP_CACHE, ck, file_date)
        if file_date > today:                  # تاريخ مستقبلي = غالبًا قراءة غلط
            file_date = mdate
        if file_date >= today: continue        # بتاع النهارده يفضل مكانه

        day_folder = archive_day_dir(folder_path, file_date)
        try:
            os.makedirs(day_folder, exist_ok=True)
            shutil.move(path, _unique_dest(os.path.join(day_folder, fname)))
            moved += 1
            touched.add(day_folder)
            if fname.lower().endswith(".pdf"):
                cropped = path[:-4] + "_cropped.pdf"
                if os.path.exists(cropped):
                    try: os.remove(cropped)
                    except Exception as _e: _log_silent("archive_sweep#1", _e)
        except Exception as e:
            log_exception(f"sweep_move:{fname}", e)   # هيتحاول تاني في الكنسة الجاية
    return moved, touched

def archive_day_records(day_folder):
    """كل سجلات اليوم من الفولدر نفسه (عشان الملخص يبقى لليوم كله مش للملفات الجديدة بس)."""
    manual_map = load_manual_map()
    load_void_map()
    recs = []
    for f in sorted(glob.glob(os.path.join(day_folder, "*.pdf"))):
        b = os.path.basename(f)
        if b.startswith("Samary_") or b.endswith("_cropped.pdf"): continue
        try: rec = read_pdf_record(f, manual_map)
        except Exception as e:
            log_exception(f"day_records:{b}", e); rec = None
        if rec: recs.append({"unit": rec["unit"], "amount": rec["amount"], "is_manual": rec["is_manual"], "is_void": rec["is_void"]})
    for f in sorted(glob.glob(os.path.join(day_folder, "*.txt"))):
        try: rec = read_txt_record(f, datetime.date.today())
        except Exception as e:
            log_exception(f"day_records_txt:{os.path.basename(f)}", e); rec = None
        if rec: recs.append({"unit": rec["unit"], "amount": rec["amount"], "is_manual": True, "is_void": rec["is_void"]})
    return recs

def load_archive_day_records(day_folder, day):
    """كل معاملات يوم من الأرشيف بكل التفاصيل (نفس شكل سجلات Records Viewer) ومعلّمة (مكرر/ملغي/ناقص...)."""
    manual_map = load_manual_map()
    load_void_map()
    recs = []
    for f in sorted(glob.glob(os.path.join(day_folder, "*.pdf"))):
        b = os.path.basename(f)
        if b.startswith("Samary_") or b.endswith("_cropped.pdf") or b.endswith("_Summary.pdf"): continue
        try: rec = read_pdf_record(f, manual_map)
        except Exception as e:
            log_exception(f"load_day_pdf:{b}", e); rec = None
        if rec: recs.append(refresh_void_flag(rec))
    for f in sorted(glob.glob(os.path.join(day_folder, "*.txt"))):
        try: rec = read_txt_record(f, day)
        except Exception as e:
            log_exception(f"load_day_txt:{os.path.basename(f)}", e); rec = None
        if rec: recs.append(refresh_void_flag(rec))
    recs.sort(key=lambda x: x["dt_key"])
    annotate_records(recs)
    return recs

# ================= إكسيل تفصيلي لكل يوم أرشيف (Details_DD-MM-YYYY.xlsx) =================
def archive_day_excel_path(day_folder, d):
    return os.path.join(day_folder, f"Details_{d.strftime('%d-%m-%Y')}.xlsx")

def archive_write_day_excel(day_folder, d, recs=None):
    """يعمل إكسيل بكل بيانات معاملات اليوم (نفس شكل Insurance_Report) جوه فولدر اليوم في الأرشيف.
    بيكتب في ملف مؤقت وبعدين يستبدل القديم، فلو الإكسيل مفتوح بيسيبه ويرجّع None (يتعاد لاحقًا)."""
    if not OPENPYXL_AVAILABLE: return None
    out = archive_day_excel_path(day_folder, d)
    tmp = os.path.join(day_folder, f"~tmp_Details_{d.strftime('%d-%m-%Y')}.xlsx")
    try:
        if recs is None: recs = load_archive_day_records(day_folder, d)
        if not recs: return None
        recs = sorted(recs, key=lambda r: r["dt_key"])
        write_report(recs, tmp)
        if not os.path.exists(tmp): return None
        os.replace(tmp, out)
        return out
    except PermissionError:
        _log_silent("archive_write_day_excel#locked", out)
        return None
    except Exception as e:
        log_exception(f"archive_write_day_excel:{out}", e)
        return None
    finally:
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except Exception as _e: _log_silent("archive_write_day_excel#cleanup", _e)

def archive_backfill_excels(folder_path, progress=None, force=False):
    """يعمل إكسيل لكل الأيام المؤرشفة اللي معندهاش واحد (أو الكل لو force). بيرجّع عدد اللي اتعمل."""
    root = os.path.join(folder_path, ARCHIVE_DIRNAME)
    if not os.path.isdir(root): return 0
    todo = []
    for dp, _dn, fns in os.walk(root):
        parts = os.path.relpath(dp, root).split(os.sep)
        if len(parts) != 3: continue
        try: d = datetime.date(int(parts[0]), int(parts[1].split("-")[0]), int(parts[2]))
        except Exception: continue
        if not any(f.lower().endswith((".pdf", ".txt")) and not f.startswith("Samary_") and not f.endswith("_cropped.pdf")
                   for f in fns): continue
        if not force and os.path.exists(archive_day_excel_path(dp, d)): continue
        todo.append((dp, d))
    made = 0
    todo.sort(key=lambda x: x[1])
    for i, (dp, d) in enumerate(todo, 1):
        if progress: progress(i, len(todo))
        if archive_write_day_excel(dp, d): made += 1
    return made

# ================= أدوات POS (التقفيل + إيصالات الدفع) — بدون واتساب =================
import hashlib as _hl, hmac as _hm
import math as _math

POS_TERMINALS = {  # tid: (orderNum, excelRow, unitName)
    "50335710": (1, 2, "أبيس"), "50335993": (2, 2, "أبيس"), "50335987": (3, 2, "أبيس"),
    "50325716": (4, 3, "برج العرب"), "50335998": (5, 3, "برج العرب"),
    "50335994": (6, 3, "برج العرب"), "50335711": (7, 3, "برج العرب"),
    "50382298": (8, 4, "المنتزه"), "50382315": (9, 4, "المنتزه"), "50383712": (10, 4, "المنتزه"),
    "50382306": (11, 5, "محرم بك"), "50382316": (12, 5, "محرم بك"),
    "50382308": (13, 6, "العجمي"), "50383706": (14, 6, "العجمي"),
    "50382300": (15, 7, "القباري"), "50383702": (16, 8, "مصطفى كامل"),
    "50382312": (17, 9, "مديرية الأمن"), "50383699": (18, 10, "ميناء الإسكندرية"),
    "50383700": (19, 11, "خدمات مصر"),
}
POS_NUM_TO_TID = {v[0]: k for k, v in POS_TERMINALS.items()}
POS_TID_FIX = {"50336994": "50335994", "50336711": "50335711", "50336998": "50335998",
               "50302316": "50382316", "50382318": "50382315", "50330987": "50335987",
               "60382308": "50382308"}
POS_MERCHANT_CODE = {"22": 2, "23": 3, "24": 4, "25": 5, "26": 6, "27": 7, "28": 8, "29": 9, "30": 10, "31": 11}
POS_NAME_HINTS = [
    (["ABYSS", "ABIS"], 2), (["BURJ", "BORG"], 3), (["MONTZAH", "TOSUN"], 4),
    (["MUHRAM", "MOHARAM"], 5), (["AJAMI", "AGAMI"], 6), (["KABBARY", "KABARY"], 7),
    (["MUSTAFA", "KAMEL"], 8), (["MODRYT", "MODERYT"], 9),
    (["ALEXANDRIA PORT", "ESMAT"], 10), (["EC ESC", "ELZREA", "ESC ALEX", "KHADAMAT"], 11),
]
POS_ROW_NAMES = {2: "أبيس", 3: "برج العرب", 4: "المنتزه", 5: "محرم بك", 6: "العجمي",
                 7: "القباري", 8: "مصطفى كامل", 9: "مديرية الأمن", 10: "ميناء الإسكندرية", 11: "خدمات مصر"}

# ---------- الباسورد الإضافي (محفوظ كـ PBKDF2 hash مش نص ظاهر) ----------
_POS_SALT = bytes.fromhex("a2b7c41d9e3f5a60718293a4b5c6d7e8")
_POS_HASH = "22c4833cb10419941ea6389532d40d9f4a6d11b07cfcc87dd6ea7a57cb2b3670"
_POS_STATE = {"until": 0.0, "fails": 0, "locked_until": 0.0}

def _pos_hash(pw):
    return _hl.pbkdf2_hmac("sha256", pw.encode("utf-8"), _POS_SALT, 200_000).hex()

def pos_check_password(pw):
    """يرجّع (ok, msg). 3 محاولات غلط = قفل 60 ثانية."""
    now = time.time()
    if now < _POS_STATE["locked_until"]:
        return False, T2(f"مقفول مؤقتًا. حاول بعد {int(_POS_STATE['locked_until'] - now)} ثانية.",
                         f"Locked. Try again in {int(_POS_STATE['locked_until'] - now)}s.")
    if _hm.compare_digest(_pos_hash(pw or ""), _POS_HASH):
        _POS_STATE["fails"] = 0
        _POS_STATE["until"] = now + 15 * 60
        return True, ""
    _POS_STATE["fails"] += 1
    if _POS_STATE["fails"] >= 3:
        _POS_STATE["fails"] = 0
        _POS_STATE["locked_until"] = now + 60
        return False, T2("3 محاولات غلط — اتقفل لمدة دقيقة.", "3 wrong attempts — locked for 1 minute.")
    return False, T2("الباسورد غلط.", "Wrong password.")

def pos_is_unlocked():
    return time.time() < _POS_STATE["until"]

# ---------- مساعدات الأرقام ----------
def _r2(v): return round(float(v) + 1e-9, 2)

def _most_common(vals):
    if not vals: return None
    counts = {}
    for v in vals: counts[v] = counts.get(v, 0) + 1
    best = None
    for k, c in counts.items():
        if best is None or c > best[1]: best = (k, c)
    return best

class OcrLine:
    __slots__ = ("text", "left", "right", "top", "bottom")
    def __init__(self, text, left, right, top, bottom):
        self.text, self.left, self.right, self.top, self.bottom = text, left, right, top, bottom
    @property
    def cy(self): return (self.top + self.bottom) / 2
    @property
    def h(self): return max(1.0, self.bottom - self.top)

def pos_rows_text(lines):
    ls = sorted(lines, key=lambda l: l.cy)
    rows = []
    for l in ls:
        if rows:
            last = rows[-1]
            cy = sum(e.cy for e in last) / len(last)
            h = sum(e.h for e in last) / len(last)
            if abs(l.cy - cy) < h * 0.6:
                last.append(l); continue
        rows.append([l])
    return "\n".join("  ".join(e.text for e in sorted(r, key=lambda e: e.left)) for r in rows) + "\n"

def pos_reading_text(lines): return "\n".join(l.text for l in lines)

_POS_MARKERS = [re.compile(p, re.I) for p in (
    r"TERMINAL", r"GRAND|TOTALS?", r"NATIONAL\s*BANK|\bNBE\b", r"BATCH", r"MERCHANT",
    r"SUCCESSF|CLOSED", r"\bVISA\b|MASTER|MEZZA|MEEZA|MEEZ", r"THANK\s*YOU", r"NET\s*AMOUNT", r"\bSALE\b")]
def pos_receipt_score(text): return sum(1 for r in _POS_MARKERS if r.search(text))

def pos_split_columns(lines):
    if len(lines) < 8: return [lines]
    min_l = min(l.left for l in lines); max_r = max(l.right for l in lines)
    w = max_r - min_l
    if w <= 0: return [lines]
    srt = sorted(lines, key=lambda l: l.left)
    for tol in (0.03, 0.02, 0.01):
        groups, cur_r = [], -1e18
        for l in srt:
            if not groups or l.left - cur_r > w * tol:
                groups.append([l]); cur_r = l.right
            else:
                groups[-1].append(l); cur_r = max(cur_r, l.right)
        big = [g for g in groups if (max(e.right for e in g) - min(e.left for e in g)) >= w * 0.12 and len(g) >= 6]
        if 2 <= len(big) <= 4 and all(pos_receipt_score(pos_reading_text(g)) >= 3 for g in big):
            return big
    return [lines]

_AMOUNT_RE = re.compile(r"(?<![\d,.])(\d{1,3}(?:,\d{3})*|\d+)[., ](\d{2})(?!\d)")
_BRAND_RE = re.compile(r"\b(VISA|MASTER(?:CARD)?|MEZZA|MEEZA|MEZA|MEZZ4|MEZZ)\b", re.I)
_CUT_RE = re.compile(r"THANK\s*YOU|Hotline|App\s*Version", re.I)

def pos_amounts_in(raw):
    text = re.sub(r"\bB(\d{2,3}[.,]\d{2})\b", lambda m: "8" + m.group(1), raw)
    out = []
    for m in _AMOUNT_RE.finditer(text):
        try: v = float(m.group(1).replace(",", "") + "." + m.group(2))
        except ValueError: continue
        if 0.5 <= v <= 5_000_000: out.append(_r2(v))
    return out

def pos_parse_receipt(txt):
    t = _CUT_RE.split(txt)[0]
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
        if sm: pre = pre[sm.end():]
        sections.append(pre)
    bvals = []
    for sec in sections:
        net = []
        for ln in sec.split("\n"):
            if re.search(r"NET\s*AMOUNT", ln, re.I): net += pos_amounts_in(ln)
        mc = _most_common(net) or _most_common(pos_amounts_in(sec))
        if mc: bvals.append(mc[0])
    grand = pos_amounts_in(post)
    bsum = _r2(sum(bvals)) if bvals else None
    return {"grand": grand, "bsum": bsum, "bvals": bvals}

def pos_decide(results):
    for r in results:
        b = r["bsum"]
        if b and b > 0 and any(abs(g - b) < 0.005 for g in r["grand"]): return b, True
    for r in results:
        b = r["bsum"]
        if b and b > 0 and len(r["bvals"]) >= 2:
            for g in r["grand"]:
                sa, sb = f"{g:.2f}", f"{b:.2f}"
                if len(sa) == len(sb) and sum(1 for x, y in zip(sa, sb) if x != y) == 1:
                    if r["grand"].count(g) >= 2: return g, True   # الإجمالي اتقرا أكتر من مرة بنفس القيمة = أوثق من مجموع الكروت
                    return b, True
    for r in results:
        c = _most_common(r["grand"])
        if c and c[1] >= 2 and r["bsum"] is None: return c[0], False
    pool = []
    for r in results:
        pool.extend(r["grand"])
        if r["bsum"] and r["bsum"] > 0: pool.append(r["bsum"])
    c = _most_common(pool)
    return (c[0], False) if c else (0.0, False)

def pos_sum_closure(texts):
    cnt = {}
    for t in texts:
        tt = _CUT_RE.split(t)[0]
        local = {}
        for a in pos_amounts_in(tt): local[a] = local.get(a, 0) + 1
        for k, v in local.items():
            if v > cnt.get(k, 0): cnt[k] = v
    c = sorted(k for k, v in cnt.items() if v >= 2)
    if len(c) < 3 or len(c) > 14: return None
    for gi in range(len(c) - 1, 1, -1):
        g, others = c[gi], c[:gi]
        n = len(others)
        for mask in range(1, 1 << n):
            bits = 0; s = 0.0
            for i in range(n):
                if mask & (1 << i): bits += 1; s += others[i]
            if bits >= 2 and abs(s - g) < 0.005: return g
    return None

def pos_ocr_piece(lines):
    texts = [pos_rows_text(lines), pos_reading_text(lines)]
    sc = pos_sum_closure(texts)
    if sc is not None: return texts, sc, True
    val, ok = pos_decide([pos_parse_receipt(t) for t in texts])
    return texts, val, ok

def pos_classify(text):
    up = text.upper()
    pay = sum(1 for p in (r"R{1,2}N\W{0,3}\d{9,}", r"\d{4,6}\W{0,2}\*{3,}\W{0,2}\d{4}", r"APPROVED",
                          r"AUTH\W{0,3}\d{6}", r"I\s*AUTHORI[SZ]E", r"MERCHANT\s*COPY", r"CLESS|CHIP\s*ONLINE")
              if re.search(p, up))
    batch = sum(1 for p in (r"BATCH\s*CLOS", r"SUCCESSF", r"GRAND\s*TOTAL", r"TOTAL\s*NET", r"THANK\s*YOU",
                            r"NBE\s*NETWORK", r"HOTLINE") if re.search(p, up))
    if pay >= 2 and batch < 2: return "payment"
    if batch >= 1: return "batch"
    return "other"

def pos_batch_no(texts):
    allv = []
    for t in texts:
        allv += [m.group(1) for m in re.finditer(r"BATCH\s*NO\D{0,6}(\d{4,7})", t, re.I)]
    mc = _most_common(allv)
    return mc[0] if mc else None

# ---------- الماكينة / الوحدة / التاريخ ----------
def _tid_labeled(t):
    m = re.search(r"TERMINAL\s*(?:ID)?\D{0,15}?(\d[\d\s/]{6,9}\d)", t, re.I)
    if not m: return None
    raw = re.sub(r"\D", "", m.group(1).replace("/", "7"))
    if len(raw) < 8: return None
    cands = [raw[-8:]] + [raw[i:i + 8] for i in range(len(raw) - 7)]
    if len(raw) == 9: cands += [raw[:i] + raw[i + 1:] for i in range(9)]   # خانة زيادة من الـ OCR
    for d in cands:
        d = POS_TID_FIX.get(d, d)
        if d in POS_TERMINALS: return d
    return None

def _tid_loose(t):
    for tid in POS_TERMINALS:
        if tid in t: return tid
    for m in re.finditer(r"\b(503\d{5})\b", t):
        c = POS_TID_FIX.get(m.group(1), m.group(1))
        if c in POS_TERMINALS: return c
    return None

def pos_find_terminal(texts):
    for t in texts:
        r = _tid_labeled(t)
        if r: return r
    for t in texts:
        r = _tid_loose(t)
        if r: return r
    return None

def pos_find_terminal_fuzzy(texts, target_row=None):
    pool = [k for k, v in POS_TERMINALS.items() if target_row is None or v[1] == target_row]
    dist = {}
    for t in texts:
        for run in re.finditer(r"\d[\d /]{6,14}\d", t):
            digits = re.sub(r"\D", "", run.group(0).replace("/", "7"))
            for i in range(0, len(digits) - 7):
                cand = digits[i:i + 8]
                if not (cand.startswith("50") or cand.startswith("60")): continue
                for tid in pool:
                    d = sum(1 for a, b in zip(cand, tid) if a != b)
                    if d < dist.get(tid, 99): dist[tid] = d
    if not dist: return None
    best = min(dist.values())
    winners = [k for k, v in dist.items() if v == best]
    return winners[0] if best <= 1 and len(winners) == 1 else None

def pos_find_unit_extra(texts):
    for t in texts:
        m = re.search(r"MERCHANT\s*(?:ID|10)\D{0,15}?(\d[\d\s/]{8,13}\d)", t, re.I)
        cands = []
        if m: cands.append(re.sub(r"\D", "", m.group(1).replace("/", "7")))
        cands.append(re.sub(r"\D", "", t))
        for d in cands:
            mm = re.search(r"11470?(2[2-9]|3[01])084", d)
            if mm and mm.group(1) in POS_MERCHANT_CODE: return POS_MERCHANT_CODE[mm.group(1)]
    for t in texts:
        up = t.upper()
        for words, row in POS_NAME_HINTS:
            if any(w in up for w in words): return row
    return None

def pos_find_date(texts):
    for t in texts:
        m = re.search(r"DATE\s*:?\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t, re.I)
        if m: return f"{int(m.group(3))}.{int(m.group(2))}"
    return None

def pos_analyze_lines(all_lines):
    pieces = pos_split_columns(all_lines)
    multi = len(pieces) > 1
    all_texts, batches, all_ok, seen = [], [], True, set()
    for pc in pieces:
        texts, val, ok = pos_ocr_piece(pc)
        all_texts += texts
        if val <= 0: all_ok = False; continue
        b = pos_batch_no(texts)
        key = (b, val)
        if b is not None and key in seen: continue
        seen.add(key); batches.append(val); all_ok = all_ok and ok
    total = _r2(sum(batches)); ok = all_ok and bool(batches)
    if multi and not ok:
        texts, val, o2 = pos_ocr_piece(all_lines)
        all_texts += texts
        if val > 0 and (o2 or not batches):
            total, ok, batches = val, o2, [val]
    date = pos_find_date(all_texts)
    tid = pos_find_terminal(all_texts); how = "terminal"; row = None; name = None
    if tid is None:
        u0 = pos_find_unit_extra(all_texts)
        tid = pos_find_terminal_fuzzy(all_texts, u0); how = "fuzzy"
    if tid is not None:
        info = POS_TERMINALS[tid]; row, name = info[1], info[2]
    else:
        how = "none"; u = pos_find_unit_extra(all_texts)
        if u is not None: row, name, how = u, POS_ROW_NAMES.get(u), "name/merchant"
    return {"tid": tid, "how": how, "row": row, "unit": name, "val": total, "ok": ok,
            "batches": batches, "date": date, "texts": all_texts}

def pos_merge_second(a, b):
    """يدمج القراءة التانية في الأولى. يرجّع قيمة تانية متعارضة (للمراجعة) أو None."""
    if a["tid"] is None and b["tid"] is not None:
        for k in ("tid", "row", "unit", "how"): a[k] = b[k]
    elif a["row"] is None and b["row"] is not None:
        for k in ("row", "unit", "how"): a[k] = b[k]
    if not a["date"]: a["date"] = b["date"]
    if b["val"] <= 0: return None
    if a["val"] <= 0:
        a["val"], a["ok"], a["batches"] = b["val"], b["ok"], list(b["batches"]); return None
    if abs(a["val"] - b["val"]) < 0.005: return None
    if not a["ok"] and b["ok"]:
        a["val"], a["ok"], a["batches"] = b["val"], True, list(b["batches"]); return None
    if a["ok"] and not b["ok"]: return None
    a["ok"] = False
    return b["val"]

# ---------- محرك OCR (RapidOCR ← Tesseract) ----------
_OCR = {"engine": None, "name": None, "tried": False, "err": ""}

def _find_tesseract():
    cands = []
    for base in (os.path.dirname(os.path.abspath(sys.argv[0])), getattr(sys, "_MEIPASS", "")):
        if base: cands += [os.path.join(base, "tesseract", "tesseract.exe"), os.path.join(base, "tesseract.exe")]
    w = shutil.which("tesseract")
    if w: cands.append(w)
    cands += [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
    for c in cands:
        if c and os.path.isfile(c): return c
    return None

def pos_ocr_init():
    """يجهّز أول محرك متاح. يرجّع اسمه أو None (والسبب في _OCR['err'])."""
    if _OCR["tried"] and _OCR["name"]: return _OCR["name"]
    _OCR["tried"] = True
    errs = []
    # import ثابت (مش __import__) علشان PyInstaller يشوفه ويضمّه في الـ exe
    try:
        from rapidocr_onnxruntime import RapidOCR as _R1
        _OCR["engine"], _OCR["name"], _OCR["err"] = _R1(), "rapidocr1", ""
        return "rapidocr1"
    except Exception as e:
        errs.append(f"rapidocr_onnxruntime: {type(e).__name__}: {e}")
    try:
        from rapidocr import RapidOCR as _R3
        _OCR["engine"], _OCR["name"], _OCR["err"] = _R3(), "rapidocr3", ""
        return "rapidocr3"
    except Exception as e:
        errs.append(f"rapidocr: {type(e).__name__}: {e}")
    try:
        import pytesseract
        exe = _find_tesseract()
        if exe:
            pytesseract.pytesseract.tesseract_cmd = exe
            pytesseract.get_tesseract_version()
            _OCR["engine"], _OCR["name"] = pytesseract, "tesseract"
            _OCR["err"] = ""
            return "tesseract"
        errs.append("tesseract.exe not found")
    except Exception as e:
        errs.append(f"pytesseract: {type(e).__name__}: {e}")
    _OCR["err"] = "\n".join(errs)
    try: log_exception("pos_ocr_init", Exception(_OCR["err"]))
    except Exception as _e: _log_silent("pos_ocr_init#1", _e)
    return None

def pos_prepare_image(img, enhance=False):
    from PIL import Image, ImageOps, ImageFilter
    img = ImageOps.exif_transpose(img).convert("L")
    w, h = img.size
    mx = max(w, h)
    if mx > 3200:
        s = 3200 / mx; img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    elif w < 1000 and not enhance:
        img = img.resize((w * 2, h * 2), Image.LANCZOS)
    if enhance:
        img = img.resize((int(img.width * 1.5), int(img.height * 1.5)), Image.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=2).filter(ImageFilter.UnsharpMask(2, 150, 3))
    else:
        img = ImageOps.autocontrast(img, cutoff=1)
    return img

def pos_ocr_lines(pil_img, enhance=False):
    """صورة PIL → قايمة OcrLine بمواقعها."""
    name = pos_ocr_init()
    if not name:
        raise RuntimeError(T2("مفيش محرك OCR. ثبّت: pip install rapidocr_onnxruntime (أو Tesseract).",
                              "No OCR engine. Install: pip install rapidocr_onnxruntime (or Tesseract)."))
    from PIL import ImageOps
    base = ImageOps.exif_transpose(pil_img)
    img = pos_prepare_image(base, enhance)
    sc = img.width / float(base.width)      # الإحداثيات بترجع بالنسبة للصورة الأصلية مش المكبّرة
    out = []
    if name.startswith("rapidocr"):
        import numpy as np
        arr = np.array(img.convert("RGB"))
        res = _OCR["engine"](arr)
        if name == "rapidocr1":
            items = res[0] or []
            for box, txt, _sc in items:
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                if str(txt).strip(): out.append(OcrLine(str(txt).strip(), min(xs) / sc, max(xs) / sc, min(ys) / sc, max(ys) / sc))
        else:
            boxes = getattr(res, "boxes", None); txts = getattr(res, "txts", None)
            if boxes is not None and txts is not None:
                for box, txt in zip(boxes, txts):
                    xs = [p[0] for p in box]; ys = [p[1] for p in box]
                    if str(txt).strip(): out.append(OcrLine(str(txt).strip(), min(xs) / sc, max(xs) / sc, min(ys) / sc, max(ys) / sc))
        return out
    # tesseract
    pt = _OCR["engine"]
    psm = 6 if img.height > img.width * 1.4 else 3
    d = pt.image_to_data(img, lang="eng", config=f"--oem 1 --psm {psm}", output_type=pt.Output.DICT)
    groups = {}
    for i, txt in enumerate(d["text"]):
        txt = (txt or "").strip()
        if not txt or float(d["conf"][i]) < 0: continue
        k = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        l, t, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        g = groups.setdefault(k, {"w": [], "l": l, "r": l + w, "t": t, "b": t + h})
        g["w"].append(txt); g["l"] = min(g["l"], l); g["r"] = max(g["r"], l + w)
        g["t"] = min(g["t"], t); g["b"] = max(g["b"], t + h)
    for g in groups.values():
        out.append(OcrLine(" ".join(g["w"]), g["l"] / sc, g["r"] / sc, g["t"] / sc, g["b"] / sc))
    return out

def pos_pdf_pages(pdf_path, dpi=200, max_pages=400):
    """صفحات PDF كصور PIL (pypdfium2)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise RuntimeError(T2("محتاج: pip install pypdfium2", "Need: pip install pypdfium2"))
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            w, h = page.get_size()
            scale = dpi / 72.0
            if max(w, h) * scale > 3000: scale = 3000 / max(w, h)
            yield page.render(scale=scale).to_pil().convert("RGB")
    finally:
        try: pdf.close()
        except Exception as _e: _log_silent("pos_pdf_pages#1", _e)

POS_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")

def pos_collect_files(paths, exts):
    """يقبل ملفات وفولدرات (مرتبة أو لأ). يرجّع قايمة ملفات."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _dn, fns in os.walk(p):
                for f in fns:
                    if f.lower().endswith(exts) and not f.startswith("."): out.append(os.path.join(dp, f))
        elif os.path.isfile(p) and p.lower().endswith(exts):
            out.append(p)
    seen, res = set(), []
    for f in sorted(out, key=lambda x: (os.path.dirname(x), os.path.basename(x).lower())):
        if f not in seen: seen.add(f); res.append(f)
    return res


# ================= إيصالات الدفع: عدّ + تعريف الماكينة + التسمية =================
_PDATE_RE = re.compile(r"(20\d{2})[^\d\n]{1,3}(\d{2})[^\d\n]{1,3}(\d{2})")

def _pos_day_key(text):
    for m in _PDATE_RE.finditer(text):
        mo, d = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31: return f"{d}.{mo}"
    return None

def _pos_anchor_of(t):
    """None = مفيش RRN | 12 رقم = RRN كامل | 'P' = RRN ناقص."""
    m = re.search(r"R{1,2}N\W{0,3}((?:\d\s?){9,12})", t, re.I) or re.search(r"(?<!\d)(63(?:\d\s?){7,10})(?!\d)", t)
    if not m: return None
    d = re.sub(r"\s", "", m.group(1))
    if len(d) < 9: return None
    if len(d) == 12 and d.startswith("63"): return d
    return "P"

class PosCollector:
    def __init__(self):
        self.pages, self.texts, self.page_h = [], [], 3000.0
    def new_page(self, page_h):
        self.pages.append([]); self.page_h = float(page_h)
    def add(self, rrn, day, l, r, cy):
        for a in self.pages[-1]:
            if a["l"] < r and l < a["r"] and abs(a["cy"] - cy) < self.page_h * 0.012:
                a["rrn"] = a["rrn"] or rrn; a["day"] = a["day"] or day; return
        self.pages[-1].append({"rrn": rrn, "day": day, "l": l, "r": r, "cy": cy})
    def collect(self, lines, x0=0.0, scale=1.0):
        self.texts.append(pos_reading_text(lines))
        dates = [l for l in lines if _pos_day_key(l.text)]
        for l in lines:
            a = _pos_anchor_of(l.text)
            if a is None: continue
            day = _pos_day_key(l.text)
            if day is None:
                best, bd = None, 1e18
                for d in dates:
                    dy = abs(d.cy - l.cy)
                    if dy > l.h * 5: continue
                    if not (d.left < l.right + 60 and l.left < d.right + 60): continue
                    if dy < bd: bd, best = dy, d
                if best: day = _pos_day_key(best.text)
            self.add(None if a == "P" else a, day, x0 + l.left / scale, x0 + l.right / scale, l.cy / scale)
    def finish(self):
        r = {"full": 0, "partial": 0, "rrn_day": {}, "non_payment": False, "tid": None, "day": None,
             "month": None, "other_day": [], "seq_min": None, "seq_max": None, "seq_missing": []}
        seen, days, partial_days = set(), {}, []
        for a in (x for p in self.pages for x in p):
            if a["rrn"]:
                if a["rrn"] not in seen:
                    seen.add(a["rrn"]); r["full"] += 1; r["rrn_day"][a["rrn"]] = a["day"]
                    if a["day"]: days[a["day"]] = days.get(a["day"], 0) + 1
            else:
                r["partial"] += 1
                if a["day"]: partial_days.append(a["day"]); days[a["day"]] = days.get(a["day"], 0) + 1
        allt = "\n".join(self.texts)
        r["non_payment"] = bool(re.search(r"GRAND\s*TOTAL|TOTAL\s*NET\s*AMOUNT|BATCH\s*CLOS|SUMMARY|REPRINT|DUPLICATE|SUCCESSF", allt, re.I))
        r["tid"] = pos_identify_tid(allt)
        if not days:
            for m in _PDATE_RE.finditer(allt):
                k = _pos_day_key(m.group(0))
                if k: days[k] = days.get(k, 0) + 1
        if days:
            best = max(days.items(), key=lambda kv: kv[1])[0]
            r["day"], r["month"] = best.split(".")
            for rrn, d in r["rrn_day"].items():
                if d and d != best: r["other_day"].append(f"إيصال {rrn[6:]} بتاريخ {d}")
            for d in partial_days:
                if d != best: r["other_day"].append(f"إيصال (رقمه مش واضح) بتاريخ {d}")
        nums = sorted(int(k[6:]) for k in r["rrn_day"])
        if len(nums) >= 2:
            best_start, best_len, start = 0, 1, 0
            for i in range(1, len(nums) + 1):
                if i == len(nums) or nums[i] - nums[i - 1] > 15:
                    if i - start > best_len: best_len, best_start = i - start, start
                    start = i
            cl = nums[best_start:best_start + best_len]
            r["seq_min"], r["seq_max"] = cl[0], cl[-1]
            have = set(cl)
            r["seq_missing"] = [n for n in range(cl[0], cl[-1] + 1) if n not in have]
        r["count"] = r["full"] + r["partial"]
        return r

def pos_identify_tid(text):
    votes = {}
    for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", text):
        c = POS_TID_FIX.get(m.group(1), m.group(1))
        if c in POS_TERMINALS: votes[c] = votes.get(c, 0) + 1
    if votes: return max(votes.items(), key=lambda kv: kv[1])[0]
    return pos_find_terminal([text]) or pos_find_terminal_fuzzy([text])

def pos_machine_new_name(tid, day, month):
    order, row, unit = POS_TERMINALS[tid]
    same = sorted((v[0] for v in POS_TERMINALS.values() if v[1] == row))
    k = same.index(order) + 1
    parts = [str(order), re.sub(r"\s+", ".", unit.strip())]
    if len(same) > 1: parts.append(str(k))
    parts += ["يوم", str(day), str(month)]
    return ".".join(parts)

def pos_count_pdf(pdf_path, progress=None, stop=None):
    """يعدّ إيصالات الدفع في PDF ويعرّف الماكينة واليوم. صفحة كاملة + 5 شرائح رأسية متداخلة."""
    from PIL import Image
    col = PosCollector()
    n_pages = 0
    for page in pos_pdf_pages(pdf_path):
        if stop and stop(): break
        n_pages += 1
        if progress: progress(f"صفحة {n_pages}")
        w, h = page.size
        col.new_page(h)
        col.collect(pos_ocr_lines(page), 0, 1.0)
        n = 5; cw = w / n
        for i in range(n):
            x0 = max(0, int(round(i * cw - cw * 0.12))); x1 = min(w, int(round((i + 1) * cw + cw * 0.12)))
            strip = page.crop((x0, 0, x1, h))
            strip = strip.resize((int(strip.width * 1.5), int(strip.height * 1.5)), Image.LANCZOS)
            col.collect(pos_ocr_lines(strip), x0, 1.5)
    res = col.finish()
    res["pages"] = n_pages
    return res

# ================= التقفيل: قراءة الصور → ترقيم → PDF + إكسيل =================
def _pos_same_day(a, b): return a.get("date") == b.get("date") or a.get("date") is None or b.get("date") is None

def pos_apply_tid(item, tid):
    info = POS_TERMINALS[tid]
    item["tid"], item["order"], item["row"], item["unit"] = tid, info[0], info[1], info[2]

def pos_closing_scan(files, auto_rotate=True, progress=None, stop=None, work_dir=None):
    """يقرا صور/صفحات PDF (من أي مكان وبأي ترتيب). يرجّع (items, warnings, excluded_names)."""
    from PIL import Image, ImageOps
    work_dir = work_dir or tempfile.mkdtemp(prefix="a2r_pos_")
    os.makedirs(work_dir, exist_ok=True)
    work = []
    for f in files:
        if f.lower().endswith(".pdf"):
            n = 0
            for pg in pos_pdf_pages(f):
                n += 1
                p = os.path.join(work_dir, f"src_{len(work)}_p{n}.png"); pg.save(p)
                work.append((p, f"{os.path.basename(f)} (ص{n})"))
        else:
            work.append((f, os.path.basename(f)))
    items, warnings, excluded = [], [], []
    for i, (path, label) in enumerate(work):
        if stop and stop(): break
        if progress: progress(i, len(work), label)
        try:
            img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
            lines = pos_ocr_lines(img); text = pos_reading_text(lines)
            is_rec = pos_receipt_score(text) >= 2 or pos_find_terminal([text]) is not None
            skip_pay = False
            if is_rec and pos_classify(text) == "payment": is_rec, skip_pay = False, True
            cur = img
            if not is_rec and not skip_pay and auto_rotate:
                for deg in (90, 270, 180):
                    im2 = img.rotate(deg, expand=True)
                    l2 = pos_ocr_lines(im2); t2 = pos_reading_text(l2)
                    if (pos_receipt_score(t2) >= 2 or pos_find_terminal([t2]) is not None) and pos_classify(t2) != "payment":
                        lines, cur, is_rec = l2, im2, True; break
            if not is_rec:
                if skip_pay: excluded.append(label)
                continue
            a = pos_analyze_lines(lines)
            alt = None
            if (not a["ok"]) or a["tid"] is None or a["row"] is None or a["val"] <= 0:
                try: alt = pos_merge_second(a, pos_analyze_lines(pos_ocr_lines(cur, enhance=True)))
                except Exception as e: log_exception("pos_second_read", e)
            if a["tid"] is None:                      # اسم الملف رقم الماكينة (1..19)؟
                stem = os.path.splitext(os.path.basename(path))[0]
                if stem.isdigit() and int(stem) in POS_NUM_TO_TID:
                    ft = POS_NUM_TO_TID[int(stem)]
                    if a["row"] is None or POS_TERMINALS[ft][1] == a["row"]:
                        a["tid"], a["how"] = ft, "file-number"
            outp = os.path.join(work_dir, f"rc_{len(items)}.jpg"); cur.save(outp, quality=92)
            it = {"path": outp, "label": label, "tid": None, "order": None, "row": a["row"], "unit": a["unit"],
                  "amount": a["val"], "date": a["date"], "ok": a["ok"], "how": a["how"], "alt": alt,
                  "batches": a["batches"], "skip": False, "suffix": None, "conflict": False, "orig_tid": None, "include": True}
            if a["tid"]: pos_apply_tid(it, a["tid"])
            items.append(it)
        except Exception as e:
            log_exception(f"pos_closing:{label}", e)
            warnings.append(f"{label}: فشلت القراءة")
    return items, warnings, excluded

def pos_closing_number(items, warnings):
    """تكرار + ترقيم الماكينات + تحذيرات (نفس منطق التطبيق)."""
    prio = {"manual": 0, "terminal": 0, "fuzzy": 1, "file-number": 2}
    with_tid = sorted([r for r in items if r["tid"]], key=lambda r: (prio.get(r["how"], 3), items.index(r)))
    taken = {}
    for r in with_tid:
        n = r["order"]; prev = taken.get(n)
        if prev is None: taken[n] = r
        elif r["amount"] > 0 and abs(prev["amount"] - r["amount"]) < 0.005 and _pos_same_day(prev, r):
            r["skip"] = True
            warnings.append(f"{r['label']}: نفس الماكينة {n} ونفس المبلغ {r['amount']:.2f} (إيصال مكرر) - تم استبعاده")
        else:
            r["orig_tid"], r["tid"], r["conflict"] = r["tid"], None, True
    used = set()
    def give_suffix(r):
        k = 2
        while (r["orig_tid"], k) in used: k += 1
        used.add((r["orig_tid"], k))
        pos_apply_tid(r, r["orig_tid"]); r["suffix"], r["how"] = k, "extra-batch"
    for r in items:
        if r["skip"] or r["tid"] or r["row"] is None: continue
        if r["conflict"] and r["how"] in ("terminal", "fuzzy"): give_suffix(r); continue
        free = [n for n in range(1, 20) if POS_TERMINALS[POS_NUM_TO_TID[n]][1] == r["row"] and n not in taken]
        if free:
            n = free[0]; pos_apply_tid(r, POS_NUM_TO_TID[n]); taken[n] = r
            r["how"] = "conflict" if r["conflict"] else "auto-number"
        elif r["orig_tid"]: give_suffix(r)
    kept = [r for r in items if not r["skip"]]
    votes = [r["date"] for r in kept if r["date"]]
    main_date = _most_common(votes)[0] if votes else None
    for r in kept:
        nm = r["label"]
        if main_date and r["date"] and r["date"] != main_date:
            warnings.append(f"{nm}: تاريخ الإيصال {r['date']} بينما أغلب الإيصالات {main_date}")
        if r["row"] is not None and r["amount"] > 0:
            if not r["ok"]: warnings.append(f"{nm}: {r['unit']} = {r['amount']:.2f} (راجع المبلغ يدويًا)")
            if r["alt"] is not None: warnings.append(f"{nm}: القراءة التانية للمبلغ {r['alt']:.2f} مختلفة عن {r['amount']:.2f} - راجع الصورة")
            if r["how"] == "extra-batch": warnings.append(f"{nm}: الماكينة {r['order']} ظهرت بمبلغ مختلف - اتحسبت كباتش إضافي {r['suffix']}")
            elif r["how"] in ("auto-number", "conflict"): warnings.append(f"{nm}: رقم الماكينة اتحدد تلقائيًا ({r['order']}) - اتأكد منه")
            elif r["how"] not in ("terminal", "fuzzy", "manual"): warnings.append(f"{nm}: الوحدة اتحددت بالاسم/الميرشانت فقط")
        else:
            warnings.append(f"{nm}: مش قادر أقرا المبلغ أو الوحدة - اضغط تعديل")
    return items

def _pos_find_template(extra_dirs=()):
    names = ("الاسكندريه 00.xlsx", "الاسكندريه_00.xlsx", "template.xlsx")
    dirs = [os.path.dirname(os.path.abspath(sys.argv[0])), getattr(sys, "_MEIPASS", ""), DOCUMENTS_DIR, *extra_dirs]
    for d in dirs:
        for n in names:
            if d and os.path.isfile(os.path.join(d, n)): return os.path.join(d, n)
    return None

def _pos_images_to_pdf(paths, out_pdf):
    from PIL import Image
    W, H, M = 1240, 1754, 60       # A4 @150dpi
    pages = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            s = min((W - 2 * M) / im.width, (H - 2 * M) / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            pg = Image.new("RGB", (W, H), "white"); pg.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
            pages.append(pg)
        except Exception as e: log_exception(f"pos_pdf_page:{p}", e)
    if not pages: return False
    pages[0].save(out_pdf, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return True

def pos_closing_build(items, out_dir, template_path=None):
    """يطلع: PDF مجمّع + صور مرقّمة + إكسيل من القالب. يرجّع dict بالنتايج."""
    os.makedirs(out_dir, exist_ok=True)
    kept = [r for r in items if not r["skip"] and r.get("include", True)]
    cnt = {}
    for r in kept:
        if r["date"]: cnt[r["date"]] = cnt.get(r["date"], 0) + 1
    report_date = max(cnt.items(), key=lambda kv: kv[1])[0] if cnt else "اليوم"
    kept.sort(key=lambda r: (r["order"] if r["order"] is not None else 99, r["suffix"] or 1))
    main = [r for r in kept if r["date"] is None or r["date"] == report_date]
    others = {}
    for r in kept:
        if r["date"] and r["date"] != report_date: others.setdefault(r["date"], []).append(r)
    res = {"report_date": report_date, "pdfs": [], "xlsx": None, "images_dir": None, "totals": {}, "notes": []}
    img_dir = os.path.join(out_dir, "صور الإيصالات"); os.makedirs(img_dir, exist_ok=True)
    res["images_dir"] = img_dir
    used_names = set()
    for r in kept:
        if r["order"] is None: continue
        sfx = f"_{r['suffix']}" if r["suffix"] else ""
        nm, k = f"{r['order']}{sfx}", 2
        while nm in used_names: nm = f"{r['order']}{sfx}_{k}"; k += 1     # تعديل يدوي ممكن يعمل نفس الرقم مرتين
        used_names.add(nm)
        dst = os.path.join(img_dir, nm + ".jpg")
        try: shutil.copy2(r["path"], dst)
        except Exception as e: log_exception("pos_copy_img", e)
    main_pdf = os.path.join(out_dir, f"الاسكندريه {report_date}.pdf")
    if _pos_images_to_pdf([r["path"] for r in main], main_pdf): res["pdfs"].append(main_pdf)
    for d, lst in others.items():
        f = os.path.join(out_dir, f"الاسكندريه {d}.pdf")
        if _pos_images_to_pdf([r["path"] for r in lst], f): res["pdfs"].append(f)
    totals = {r: 0.0 for r in range(2, 12)}
    for r in main:
        if r["row"] is not None and r["amount"] > 0: totals[r["row"]] += r["amount"]
    res["totals"] = {k: _r2(v) for k, v in totals.items()}
    tpl = template_path or _pos_find_template()
    if not tpl or not os.path.isfile(tpl):
        res["notes"].append("قالب الإكسيل (الاسكندريه 00.xlsx) مش موجود — الإكسيل متعملش.")
    elif not OPENPYXL_AVAILABLE:
        res["notes"].append("openpyxl مش متثبتة — الإكسيل متعملش.")
    else:
        try:
            wb = openpyxl.load_workbook(tpl); ws = wb.worksheets[0]
            for rw in range(2, 12):
                ws[f"D{rw}"] = res["totals"][rw]
                ws[f"F{rw}"] = f"=D{rw}+IF(ISBLANK(E{rw}),0,E{rw})"
            try: wb.calculation.fullCalcOnLoad = True
            except Exception as _e: _log_silent("pos_closing_build#1", _e)
            xf = os.path.join(out_dir, f"الاسكندريه {report_date}.xlsx"); wb.save(xf); res["xlsx"] = xf
        except Exception as e:
            log_exception("pos_fill_template", e); res["notes"].append(f"فشل ملء القالب: {e}")
    return res

def pos_make_tree(parent, t, columns, headers, widths):
    style = ttk.Style()
    try: style.theme_use("clam")
    except Exception as _e: _log_silent("pos_make_tree#1", _e)
    style.configure("A2R.Treeview", background=t["input"], foreground=t["text"], fieldbackground=t["input"],
                    font=(FONT_FAMILY, 10, "bold"), rowheight=28)
    style.configure("A2R.Treeview.Heading", background=t["card"], foreground=t["accent"], font=(FONT_FAMILY, 11, "bold"), relief="flat")
    style.map("A2R.Treeview", background=[("selected", t["primary"])], foreground=[("selected", "#FFFFFF")])
    fr = ctk.CTkFrame(parent, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
    fr.pack(fill="both", expand=True, padx=12, pady=(4, 2))
    tree = ttk.Treeview(fr, columns=columns, show="headings", style="A2R.Treeview")
    for c in columns:
        tree.heading(c, text=headers[c]); tree.column(c, width=widths.get(c, 90), anchor="center")
    for kind, (bg, fg) in TAG_COLORS[t["mode"]].items():
        tree.tag_configure(kind, background=bg, foreground=fg)
    vsb = ttk.Scrollbar(fr, orient="vertical", command=tree.yview); vsb.pack(side="right", fill="y", padx=2, pady=2)
    tree.configure(yscrollcommand=vsb.set); tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
    return tree

# باسورد المشرف: مخزّن كـ PBKDF2-SHA256 (200 ألف دورة) مع salt، مفيش نص صريح في الكود.
# لتغييره: شغّل make_admin_hash.py والصق السطرين الناتجين مكان _SUP_SALT و _SUP_HASH.
_SUP_SALT = bytes.fromhex("4d5883eb3e96982fb29d76b5ae8d46d7")
_SUP_HASH = "8696da1f0380fb81ab0e79ce8ba22766d54115016d5b75846e42862b44394173"
_SUP_ITER = 200_000
_SUP_STATE = {"fails": 0, "locks": 0, "locked_until": 0.0}

def _sup_hash(val):
    return _hl.pbkdf2_hmac("sha256", val.encode("utf-8"), _SUP_SALT, _SUP_ITER).hex()

def sup_lock_remaining():
    return max(0, int(_SUP_STATE["locked_until"] - time.time() + 0.999))

def is_supervisor_password(raw):
    """مقارنة ثابتة الزمن. نفس التطبيع القديم (strip + lower) عشان السلوك ميتغيرش. مفيش عدّ فشل هنا."""
    return _hm.compare_digest(_sup_hash((raw or "").strip().lower()), _SUP_HASH)

def sup_register_fail():
    """5 محاولات فاشلة متتالية = قفل 30 ثانية (يتضاعف لحد 10 دقايق). النجاح بيصفّر العدّاد."""
    _SUP_STATE["fails"] += 1
    try: logging.warning("Supervisor gate: failed attempt #%d", _SUP_STATE["fails"])
    except Exception as _e: _log_silent("sup_register_fail#1", _e)
    if _SUP_STATE["fails"] >= 5:
        _SUP_STATE["fails"] = 0
        _SUP_STATE["locks"] += 1
        _SUP_STATE["locked_until"] = time.time() + min(600, 30 * (2 ** (_SUP_STATE["locks"] - 1)))

def sup_register_success():
    _SUP_STATE["fails"] = 0
    _SUP_STATE["locks"] = 0
EMPLOYEE_PASSWORDS = [
    "ahmedramadan", "a2r", "ahmed.r",
    "1531", "20262", "2026", "16061993", "1558", "1964",
    "2212", "1672", "30881999", "1990", "27121996", "1012",
    "160388", "505022", "20272", "0100elkok", "12345", "8110"
]
EMPLOYEE_HASHES = {hashlib.sha256(p.encode('utf-8')).hexdigest() for p in EMPLOYEE_PASSWORDS}

COMPANY_WORDS_RE = re.compile(r"مجمع|التأمين|التامين|الإلزامي|الالزامي|^للمركبات$|^المركبات$")
TIME_RE = re.compile(
    r"(\d{2}:\d{2}\s+\d{2}[-/]\d{2}[-/]\d{4})|(\d{2}[-/]\d{2}[-/]\d{4}\s+\d{2}:\d{2})|"
    r"(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2})")
FLOAT_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b|\b\d+\.\d{2}\b")

LABEL_PATTERNS = [
    ("insured", r"اسم\s+المؤمن\s+له"),
    ("company", r"اسم\s+المؤمن"),
    ("plate", r"رقم\s+اللوح[ةه]"),
    ("unit", r"وحدة\s+المرور"),
    ("chassis", r"رقم\s+الشاسي[ةه]?"),
    ("motor", r"رقم\s+الموتور"),
    ("make", r"الماركة|الماركه"),
    ("model", r"الطراز"),
    ("period", r"المدة\s+الت[اأ]مينية"),
    ("premium", r"[اأإ]جمالي\s+القسط"),
    ("total", r"ال[اأإ]جمالي\s+العام"),
    ("printed", r"تمت\s+الطباعة(?:\s+في)?"),
]

def split_label(line):
    for key, pat in LABEL_PATTERNS:
        m = re.search(pat + r"\s*[:：]?", line)
        if m:
            rest = line[:m.start()] + " " + line[m.end():]
            rest = re.sub(r"\s+", " ", rest).strip(" :：\t")
            return key, rest
    return None, line.strip()

def fix_plate(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if not s:
        return "-"
    digits = re.findall(r"\d+", s)
    letters = re.findall(r"[\u0621-\u064A]+", s)
    if digits and letters:
        return f"{' '.join(letters)} - {''.join(digits)}"
    return s.strip(" -") or "-"

def is_receipt_text(txt):
    return bool(re.search(r"رقم\s+اللوح[ةه]|سداد\s+قسط", txt or ""))

NOISE_LINE_RE = re.compile(r"إيصال|ايصال|سداد|قسط|على\s+المركبات|^المركبات$|^للمركبات$|مجمع|التأمين|التامين|الإلزامي|الالزامي|وحدة\s+مرور|^وحدة\b|للاطلاع|رمز\s+الاستجابة")

def _is_noise_line(line):
    return bool(NOISE_LINE_RE.search(line or "")) or bool(detect_unit_from_text(line))

def _looks_like_plate(s):
    s = s or ""
    return bool(re.search(r"\d", s)) and not _is_noise_line(s)

def parse_receipt_text(txt):
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    items = [split_label(l) for l in lines]

    def first_value(key):
        for i, (k, v) in enumerate(items):
            if k == key:
                if v: return v, i
                if key in ("unit", "company"):
                    return "", i
                for j in (i + 1, i - 1):
                    if 0 <= j < len(items) and items[j][0] is None and items[j][1]:
                        cand = items[j][1]
                        if _is_noise_line(cand): continue
                        if key == "plate" and not _looks_like_plate(cand): continue
                        return cand, i
                return "", i
        return None, None

    out = {}
    plate_v, i_plate = first_value("plate")
    out["plate"] = fix_plate(plate_v) if (plate_v and _looks_like_plate(plate_v)) else "-"

    unit_v, i_unit = first_value("unit")
    unit = detect_unit_from_text(unit_v) if unit_v else None
    if not unit:
        unit = detect_unit_from_text(txt)
    out["unit"] = unit or UNSPEC

    chassis_v, i_chassis = first_value("chassis")
    chassis = re.sub(r"\s+", "", chassis_v) if chassis_v else ""
    if not chassis:
        m = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", txt)
        chassis = m.group(0) if m else "-"
    out["chassis"] = chassis

    motor_v, i_motor = first_value("motor")
    out["motor"] = re.sub(r"\s+", "", motor_v) if motor_v else "-"

    make_v, _ = first_value("make")
    out["make"] = make_v or "-"
    model_v, i_model = first_value("model")
    out["model"] = model_v or "-"

    insured = "-"
    if any(k == "insured" for k, _ in items):
        start = i_unit if i_unit is not None else (i_plate if i_plate is not None else -1)
        if i_chassis is not None: end = i_chassis
        elif i_motor is not None: end = i_motor
        else: end = len(items)
        frags = []
        for i in range(start + 1, end):
            k, v = items[i]
            if k in (None, "insured", "company") and v:
                if COMPANY_WORDS_RE.search(v): continue
                if v.startswith("وحدة") or detect_unit_from_text(v): continue
                frags.append(v)
        insured = " ".join(frags).strip(" :-") or "-"
    out["insured"] = insured

    i_prem = first_value("premium")[1]
    region = lines
    if i_model is not None and i_prem is not None and i_prem > i_model:
        region = lines[i_model + 1:i_prem]
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", "\n".join(region))
    if len(dates) < 2:
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", txt)
    dates = sorted(dates[:2]) if len(dates) >= 2 else dates
    out["period"] = f"{dates[0]} إلى {dates[1]}" if len(dates) >= 2 else "-"

    amount = None
    for key in ("total", "premium"):
        v, _ = first_value(key)
        if v:
            f = FLOAT_RE.findall(v)
            if f:
                amount = float(f[-1].replace(",", ""))
                break
    if amount is None:
        f = FLOAT_RE.findall(txt)
        amount = float(f[-1].replace(",", "")) if f else 0.0
    out["amount"] = amount

    printed_v, _ = first_value("printed")
    print_time = "-"
    for cand in ([printed_v] if printed_v else []) + [txt]:
        m = TIME_RE.search(cand)
        if m:
            print_time = m.group(0).strip().replace("/", "-")
            break
    dt = parse_print_time(print_time)
    out["dt"] = dt
    out["time"] = dt.strftime("%d-%m-%Y %H:%M") if dt else print_time
    return out

def run_pdftotext(path):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        res = subprocess.run([PDFTOTEXT_EXE, "-layout", "-enc", "UTF-8", path, "-"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding='utf-8', errors='ignore', creationflags=flags, timeout=45)
        return clean_arabic(res.stdout)
    except Exception as e:
        log_exception(f"pdftotext:{os.path.basename(path)}", e)
        return ""

_AR_LETTER_RE = re.compile(r"[\u0621-\u064A]")
_AR_RUN_RE = re.compile(r"[\u0621-\u064A]+")
_LIGA_REV = {"\uFEF5": "آل", "\uFEF6": "آل", "\uFEF7": "أل", "\uFEF8": "أل",
             "\uFEF9": "إل", "\uFEFA": "إل", "\uFEFB": "ال", "\uFEFC": "ال"}
_REV_HINTS = {"مقر", "مسا", "ةدحو", "رورملا", "نمؤملا", "ةحوللا", "هل"}
_FWD_HINTS = {"رقم", "اسم", "وحدة", "المرور", "المؤمن", "اللوحة", "له"}

BBOX_LABELS = [
    ("insured", r"اسم\s*المؤمن\s*له"),
    ("company", r"اسم\s*المؤمن"),
    ("plate", r"رقم\s*اللوحه"),
    ("unit", r"وحده\s*المرور"),
    ("chassis", r"رقم\s*الشاسي"),
    ("motor", r"رقم\s*الموتور"),
    ("make", r"الماركه"),
    ("model", r"الطراز"),
    ("period", r"المده\s*التامينيه"),
    ("premium", r"اجمالي\s*القسط"),
    ("total", r"الاجمالي\s*العام"),
    ("printed", r"تمت\s*الطباعه"),
]

def _fold_ar(t):
    t = re.sub(r"[أإآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", t)

_BBOX_LOGGED = False

def run_pdftotext_bbox(path):
    global _BBOX_LOGGED
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        res = subprocess.run([PDFTOTEXT_EXE, "-bbox", path, "-"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore",
                             creationflags=flags, timeout=45)
    except Exception as e:
        log_exception(f"bbox:{os.path.basename(path)}", e)
        return None, None, []
    out = res.stdout or ""
    pm = re.search(r'<page\s+width="([\d.]+)"\s+height="([\d.]+)"', out)
    if not pm:
        if not _BBOX_LOGGED:
            _BBOX_LOGGED = True
            log_exception("bbox_empty", f"rc={res.returncode} stdout[:300]={out[:300]!r} stderr[:300]={(res.stderr or '')[:300]!r}")
        return None, None, []
    page_end = out.find("</page>")
    if page_end > 0:
        out = out[:page_end]
    words = []
    for m in re.finditer(r'<word\s+xMin="([\d.\-]+)"\s+yMin="([\d.\-]+)"\s+xMax="([\d.\-]+)"\s+yMax="([\d.\-]+)">(.*?)</word>', out):
        words.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), html.unescape(m.group(5))))
    return float(pm.group(1)), float(pm.group(2)), words

def _bbox_words(raw_words):
    base = [clean_arabic(w[4]) for w in raw_words]
    rev_hits = sum(1 for t in base if t in _REV_HINTS)
    fwd_hits = sum(1 for t in base if t in _FWD_HINTS)
    reversed_mode = rev_hits > fwd_hits
    out = []
    for (x0, y0, x1, y1, raw) in raw_words:
        if reversed_mode:
            for k, v in _LIGA_REV.items():
                raw = raw.replace(k, v)
        t = clean_arabic(raw)
        if reversed_mode:
            t = _AR_RUN_RE.sub(lambda m: m.group(0)[::-1], t)
        t = t.strip()
        if t:
            out.append({"x0": x0, "x1": x1, "yc": (y0 + y1) / 2.0, "t": t})
    return out

def _join_value_words(ws):
    lines = []
    for w in sorted(ws, key=lambda w: w["yc"]):
        if lines and abs(w["yc"] - lines[-1][0]) <= 3:
            lines[-1][1].append(w)
        else:
            lines.append([w["yc"], [w]])
    parts = []
    for _, lw in lines:
        has_ar = any(_AR_LETTER_RE.search(w["t"]) for w in lw)
        lw.sort(key=(lambda w: -w["x1"]) if has_ar else (lambda w: w["x0"]))
        parts.append(" ".join(w["t"] for w in lw))
    return re.sub(r"\s+", " ", " ".join(parts)).strip(" :：")

def _value_lines(ws):
    lines = []
    for w in sorted(ws, key=lambda w: w["yc"]):
        if lines and abs(w["yc"] - lines[-1][0]) <= 3:
            lines[-1][1].append(w)
        else:
            lines.append([w["yc"], [w]])
    res = []
    for _, lw in lines:
        has_ar = any(_AR_LETTER_RE.search(w["t"]) for w in lw)
        lw.sort(key=(lambda w: -w["x1"]) if has_ar else (lambda w: w["x0"]))
        t = re.sub(r"\s+", " ", " ".join(w["t"] for w in lw)).strip(" :：")
        if t:
            res.append(t)
    return res

def parse_receipt_bbox(path, fallback_text=""):
    page_w, page_h, raw_words = run_pdftotext_bbox(path)
    if not page_w or not raw_words:
        return None, [], {"error": "no bbox output"}
    words = _bbox_words(raw_words)
    split = page_w * 0.55

    rows = []
    for w in sorted([w for w in words if w["x0"] >= split], key=lambda w: w["yc"]):
        if rows and abs(w["yc"] - rows[-1]["yc"]) <= 4:
            rows[-1]["w"].append(w)
            rows[-1]["yc"] = sum(x["yc"] for x in rows[-1]["w"]) / len(rows[-1]["w"])
        else:
            rows.append({"yc": w["yc"], "w": [w]})

    labels = {}
    for r in rows:
        txt = _fold_ar(" ".join(x["t"] for x in sorted(r["w"], key=lambda w: -w["x1"]))).replace(":", " ")
        txt = re.sub(r"\s+", " ", txt).strip()
        for key, pat in BBOX_LABELS:
            if re.search(pat, txt):
                if key not in labels:
                    labels[key] = r["yc"]
                break

    first_y = (min(labels.values()) - 8) if labels else page_h * 0.04
    last_y = (labels["printed"] + 8) if "printed" in labels else page_h * 0.5
    value_words = [w for w in words if w["x0"] < split and first_y <= w["yc"] <= last_y]
    lines = _value_lines(value_words)
    dbg = {"page": (page_w, page_h), "labels": labels, "lines": lines,
           "words": [(round(w["x0"]), round(w["x1"]), round(w["yc"]), w["t"]) for w in sorted(words, key=lambda w: (w["yc"], -w["x1"]))]}

    if len(labels) < 6 or ("plate" not in labels and "chassis" not in labels):
        return None, lines, dbg

    buckets = {k: [] for k in labels}
    for w in value_words:
        key, dist = min(((k, abs(y - w["yc"])) for k, y in labels.items()), key=lambda kv: kv[1])
        if dist <= 14:
            buckets[key].append(w)
    vals = {k: _join_value_words(v) for k, v in buckets.items()}
    dbg["vals"] = vals

    out = {}
    pv = vals.get("plate", "")
    out["plate"] = fix_plate(pv) if pv.strip(" -") else "-"

    unit = detect_unit_from_text(vals.get("unit", "")) or detect_unit_from_text(fallback_text)
    out["unit"] = unit or UNSPEC

    ch = re.sub(r"\s+", "", vals.get("chassis", ""))
    if not ch:
        m = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", fallback_text or "")
        ch = m.group(0) if m else "-"
    out["chassis"] = ch
    out["motor"] = re.sub(r"\s+", "", vals.get("motor", "")) or "-"
    out["make"] = vals.get("make", "") or "-"
    out["model"] = vals.get("model", "") or "-"
    out["insured"] = vals.get("insured", "").strip(" :-") or "-"

    dates = sorted(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", vals.get("period", "")))[:2]
    out["period"] = f"{dates[0]} إلى {dates[1]}" if len(dates) == 2 else "-"

    amount = None
    for key in ("total", "premium"):
        f = FLOAT_RE.findall(vals.get(key, ""))
        if f:
            amount = float(f[-1].replace(",", ""))
            break
    if amount is None:
        f = FLOAT_RE.findall(fallback_text or "")
        amount = float(f[-1].replace(",", "")) if f else 0.0
    out["amount"] = amount

    print_time = "-"
    for cand in (vals.get("printed", ""), fallback_text or ""):
        m = TIME_RE.search(cand)
        if m:
            print_time = m.group(0).strip().replace("/", "-")
            break
    dt = parse_print_time(print_time)
    out["dt"] = dt
    out["time"] = dt.strftime("%d-%m-%Y %H:%M") if dt else print_time
    return out, lines, dbg

_PLATE_ONLY_RE = re.compile(r"^(?:[\u0621-\u064A]{1,4}\d{1,4}|\d{1,4}[\u0621-\u064A]{1,4})$")

def parse_receipt_by_type(lines, fallback_text=""):
    unit = None
    dates, amounts, tm, rest = [], [], None, []
    for raw in lines:
        l = re.sub(r"\s+", " ", raw or "").strip(" :：")
        if not l or l == "-":
            continue
        m = TIME_RE.search(l)
        if m and not _AR_LETTER_RE.search(l):
            tm = m.group(0).strip().replace("/", "-")
            continue
        ds = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", l)
        if ds and re.fullmatch(r"[\d\s\-]+", l):
            dates += ds
            continue
        if FLOAT_RE.fullmatch(l):
            amounts.append(float(l.replace(",", "")))
            continue
        if re.match(r"^(?:وحدة|منفذ|ميناء|مجمع\s+خدمات)", l):
            u = detect_unit_from_text(l)
            if u:
                unit = unit or u
                continue
        if NOISE_LINE_RE.search(l) or COMPANY_WORDS_RE.search(l):
            continue
        rest.append(l)

    cidx = None
    for i, l in enumerate(rest):
        c = l.replace(" ", "")
        if not _AR_LETTER_RE.search(c) and len(c) >= 10 and re.search(r"[A-Za-z]", c) and re.search(r"\d", c):
            cidx = i
            if re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", c):
                break
    if cidx is None:
        for i, l in enumerate(rest):
            if not _AR_LETTER_RE.search(l):
                cidx = i
                break
    if cidx is None:
        cidx = len(rest)
    head, tail = rest[:cidx], rest[cidx:]

    plate = "-"
    others = []
    for l in head:
        if plate == "-" and _PLATE_ONLY_RE.match(re.sub(r"[\s\-]", "", l)):
            plate = fix_plate(l)
        else:
            others.append(l)

    out = {"plate": plate}
    out["insured"] = " ".join(others).strip(" :-") or "-"
    out["chassis"] = re.sub(r"\s+", "", tail[0]) if len(tail) > 0 else "-"
    out["motor"] = re.sub(r"\s+", "", tail[1]) if len(tail) > 1 else "-"
    out["make"] = tail[2] if len(tail) > 2 else "-"
    out["model"] = " ".join(tail[3:]) if len(tail) > 3 else "-"
    out["unit"] = unit or detect_unit_from_text(fallback_text) or UNSPEC
    ds = sorted(dates)[:2]
    out["period"] = f"{ds[0]} إلى {ds[1]}" if len(ds) == 2 else "-"
    if amounts:
        out["amount"] = amounts[-1]
    else:
        f = FLOAT_RE.findall(fallback_text or "")
        out["amount"] = float(f[-1].replace(",", "")) if f else 0.0
    if not tm:
        m = TIME_RE.search(fallback_text or "")
        tm = m.group(0).strip().replace("/", "-") if m else "-"
    dt = parse_print_time(tm)
    out["dt"] = dt
    out["time"] = dt.strftime("%d-%m-%Y %H:%M") if dt else tm
    return out

def _text_value_lines(txt):
    res = []
    for line in (txt or "").splitlines():
        line = line.strip()
        if not line:
            continue
        k, v = split_label(line)
        if v:
            res.append(v)
    return res

def _receipt_ok(f):
    if not f:
        return False
    ch, mo, ins, mk = f["chassis"], f["motor"], f["insured"], f["make"]
    if _AR_LETTER_RE.search(ch) or _AR_LETTER_RE.search(mo):
        return False
    if ch != "-" and (len(ch) < 5 or not re.search(r"\d", ch)):
        return False
    if ch != "-" and ch == mo:
        return False
    if mk != "-" and mk == mo:
        return False
    if ins == "-":
        return False
    if re.fullmatch(r"[A-Za-z0-9]{8,}", ins.replace(" ", "")):
        return False
    return True

_PDFTOTEXT_VER = None
_DEBUG_COUNT = 0

def _dump_parse_debug(path, method, txt, dbg):
    global _DEBUG_COUNT, _PDFTOTEXT_VER
    if _DEBUG_COUNT >= 12:
        return
    _DEBUG_COUNT += 1
    try:
        if _PDFTOTEXT_VER is None:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            r = subprocess.run([PDFTOTEXT_EXE, "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="ignore", creationflags=flags)
            _PDFTOTEXT_VER = ((r.stderr or "") + (r.stdout or "")).strip().replace("\n", " | ")
        fn = os.path.join(DOCUMENTS_DIR, "parse_debug.txt")
        with open(fn, "a", encoding="utf-8") as fh:
            fh.write("=" * 70 + "\n")
            fh.write(f"{datetime.datetime.now():%d-%m-%Y %H:%M:%S} | {os.path.basename(path)} | method={method}\n")
            fh.write(f"pdftotext: {_PDFTOTEXT_VER}\n")
            fh.write(f"page={dbg.get('page')} labels={dbg.get('labels')}\n")
            fh.write(f"vals={dbg.get('vals')}\n")
            fh.write(f"value_lines={dbg.get('lines')}\n")
            fh.write("--- bbox words (x0, x1, y, text) ---\n")
            for w in dbg.get("words", []):
                fh.write(f"{w}\n")
            fh.write("--- layout text ---\n")
            fh.write((txt or "") + "\n")
    except Exception as e:
        log_exception("dump_parse_debug", e)

# ===== قراءة إضافية لأشكال إيصالات بتفشل فيها القراءة الاحتياطية (بتشتغل بس لو القراءة العادية ما نجحتش) =====
_INLINE_LABELS = [
    ("plate", r"رقم\s*(?:المركب[ةه]|اللوح[ةه])"),
    ("unit", r"وحد[ةه]\s*المرور"),
    ("insured", r"اسم\s*(?:المواطن|المؤمن\s*له)"),
    ("chassis", r"رقم\s*الشاسي[ةه]?"),
    ("motor", r"رقم\s*الموتور"),
    ("make", r"الماركه|الماركة"),
    ("model", r"الطراز"),
    ("amount", r"(?:ال)?مبلغ"),
    ("printed", r"تمت\s*الطباعة(?:\s*في)?"),
]
_VAR_NOISE_RE = re.compile(r"الاستجابة|أعلاه|اعلاه|الشروط|للوثيقة|يرجى|مسح")

def _var_finish(out, txt, tm):
    out["unit"] = out.get("unit") or detect_unit_from_text(txt) or UNSPEC
    if not tm:
        m = TIME_RE.search(txt or "")
        tm = m.group(0).strip().replace("/", "-") if m else "-"
    dt = parse_print_time(tm)
    out["dt"] = dt
    out["time"] = dt.strftime("%d-%m-%Y %H:%M") if dt else tm
    return out

def _parse_inline_labeled(txt):
    """الشكل القديم: كل سطر 'العنوان: القيمة' (رقم المركبة / اسم المواطن / المبلغ ...)."""
    vals, last = {}, None
    for raw in (txt or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            last = None
            continue
        hit = None
        for key, pat in _INLINE_LABELS:
            m = re.match(r"^" + pat + r"\s*[:：]\s*(.*)$", line)
            if m:
                hit = (key, m.group(1).strip())
                break
        if hit:
            key, v = hit
            vals.setdefault(key, v)
            last = "insured" if key == "insured" else None
        elif last == "insured" and ":" not in line and ("تمت" not in line) and not _VAR_NOISE_RE.search(line):
            vals["insured"] = (vals["insured"] + " " + line).strip()
        else:
            last = None
    if len(vals) < 4 or "chassis" not in vals:
        return None
    out = {}
    pv = vals.get("plate", "")
    out["plate"] = fix_plate(pv) if pv.strip(" -") else "-"
    out["unit"] = detect_unit_from_text(vals.get("unit", ""))
    out["insured"] = vals.get("insured", "").strip(" :-") or "-"
    out["chassis"] = re.sub(r"\s+", "", vals.get("chassis", "")) or "-"
    out["motor"] = re.sub(r"\s+", "", vals.get("motor", "")) or "-"
    out["make"] = vals.get("make", "").strip(" .") or "-"
    out["model"] = vals.get("model", "").strip(" .") or "-"
    out["period"] = "-"
    am = re.search(r"\d[\d,]*(?:\.\d+)?", vals.get("amount", ""))
    out["amount"] = float(am.group(0).replace(",", "")) if am else 0.0
    tm = None
    m = TIME_RE.search(vals.get("printed", "") or "")
    if m: tm = m.group(0).strip().replace("/", "-")
    return _var_finish(out, txt, tm)

def _parse_positional_text(txt):
    """الشكل الجديد لما تنسيق النص بيتلخبط (قيم مش قصاد عناوينها): نفس فكرة parse_receipt_by_type
    + مبلغ بـ 'جم' + مدة 'من .. إلى ..' + أول شاسيه بدل آخر واحد."""
    unit, dates, amounts, tm, rest = None, [], [], None, []
    for raw in _text_value_lines(txt):
        l = re.sub(r"\s+", " ", raw or "").strip(" :：")
        if not l or l == "-" or _VAR_NOISE_RE.search(l):
            continue
        m = TIME_RE.search(l)
        if m and not _AR_LETTER_RE.search(l):
            tm = m.group(0).strip().replace("/", "-")
            continue
        md = re.fullmatch(r"(?:من|إلى|الى)\s+(\d{2})-(\d{2})-(\d{4})", l)
        if md:
            dates.append(f"{md.group(3)}-{md.group(2)}-{md.group(1)}")
            continue
        ds = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", l)
        if ds and re.fullmatch(r"[\d\s\-]+", l):
            dates += ds
            continue
        ma = re.fullmatch(r"(\d[\d,]*(?:\.\d+)?)\s*(?:جم|جنيه|EGP)?", l)
        if ma and (FLOAT_RE.fullmatch(ma.group(1)) or re.search(r"[^\d.,]", l)):
            amounts.append(float(ma.group(1).replace(",", "")))
            continue
        if re.match(r"^(?:وحدة|منفذ|ميناء|مجمع\s+خدمات)", l):
            u = detect_unit_from_text(l)
            if u:
                unit = unit or u
                continue
        if NOISE_LINE_RE.search(l) or COMPANY_WORDS_RE.search(l):
            continue
        rest.append(l)
    cidx = None
    for i, l in enumerate(rest):
        c = l.replace(" ", "")
        if not _AR_LETTER_RE.search(c) and len(c) >= 10 and re.search(r"[A-Za-z]", c) and re.search(r"\d", c):
            cidx = i
            break
    if cidx is None:
        for i, l in enumerate(rest):
            if not _AR_LETTER_RE.search(l):
                cidx = i
                break
    if cidx is None:
        return None
    head, tail = rest[:cidx], rest[cidx:]
    plate, others = "-", []
    for l in head:
        if plate == "-" and _PLATE_ONLY_RE.match(re.sub(r"[\s\-]", "", l)):
            plate = fix_plate(l)
        else:
            others.append(l)
    out = {"plate": plate}
    out["insured"] = " ".join(others).strip(" :-") or "-"
    out["chassis"] = re.sub(r"\s+", "", tail[0]) if len(tail) > 0 else "-"
    out["motor"] = re.sub(r"\s+", "", tail[1]) if len(tail) > 1 else "-"
    out["make"] = tail[2].strip(" .") if len(tail) > 2 else "-"
    out["model"] = " ".join(tail[3:]).strip(" .") if len(tail) > 3 else "-"
    out["unit"] = unit
    ds = sorted(dates)[:2]
    out["period"] = f"{ds[0]} إلى {ds[1]}" if len(ds) == 2 else "-"
    out["amount"] = amounts[-1] if amounts else 0.0
    return _var_finish(out, txt, tm)

def _receipt_score(f):
    """كام حقل طالع منطقي. بنستبدل نتيجة القراءة الاحتياطية بس لو القراءة الإضافية أحسن منها فعلًا."""
    if not f: return -1
    s = 0
    if f.get("plate", "-") != "-": s += 1
    ins = f.get("insured", "-")
    if ins != "-" and not re.search(r"اسم\s*المواطن|رقم\s*المركب|المبلغ|[A-Za-z0-9]{6,}", ins): s += 1
    if float(f.get("amount") or 0) > 0: s += 2
    ch, mo = f.get("chassis", "-"), f.get("motor", "-")
    if ch != "-" and len(ch) >= 5 and not _AR_LETTER_RE.search(ch) and re.search(r"\d", ch): s += 1
    if mo != "-" and not _AR_LETTER_RE.search(mo): s += 1
    mk = f.get("make", "-")
    if mk != "-" and mk != mo: s += 1
    md = f.get("model", "-")
    if md != "-" and not re.search(r"المبلغ|جم|من\s+\d|إلى|الاستجابة", md): s += 1
    if f.get("period", "-") != "-": s += 1
    if f.get("dt"): s += 1
    return s

def parse_receipt_variants(txt):
    txt = txt or ""
    cands = []
    if re.search(r"اسم\s*المواطن|رقم\s*المركب", txt):
        cands.append(_parse_inline_labeled)
    cands.append(_parse_positional_text)
    best = None
    for fn in cands:
        try: r = fn(txt)
        except Exception as e:
            log_exception(f"parse_variant:{fn.__name__}", e)
            r = None
        if r and (best is None or _receipt_score(r) > _receipt_score(best)):
            best = r
    return best


def parse_receipt(path, txt):
    old = parse_receipt_text(txt)
    bb, bb_lines, dbg = None, [], {}
    try:
        bb, bb_lines, dbg = parse_receipt_bbox(path, txt)
    except Exception as e:
        log_exception(f"parse_bbox:{os.path.basename(path)}", e)

    chosen, method = None, None
    for name, f in (("bbox", bb), ("text", old)):
        if f and _receipt_ok(f):
            chosen, method = f, name
            break
    if chosen is None:
        for name, lines in (("type-bbox", bb_lines), ("type-text", _text_value_lines(txt))):
            if lines:
                try:
                    f = parse_receipt_by_type(lines, txt)
                except Exception as e:
                    log_exception(f"parse_type:{os.path.basename(path)}", e)
                    continue
                if _receipt_ok(f):
                    chosen, method = f, name
                    break
    if chosen is None:
        chosen, method = (bb, "bbox-unverified") if bb else (old, "text-unverified")

    if method not in ("bbox", "text"):
        try:
            var = parse_receipt_variants(txt)
            if var and _receipt_score(var) > _receipt_score(chosen):
                chosen, method = var, "variant"
        except Exception as e:
            log_exception(f"parse_variants:{os.path.basename(path)}", e)

    if method not in ("bbox", "variant"):
        _dump_parse_debug(path, method, txt, dbg or {})

    norm = lambda p: sorted(re.sub(r"[\s\-]", "", p or ""))
    if chosen is not old and chosen["plate"] != "-" and old["plate"] != "-" and norm(chosen["plate"]) == norm(old["plate"]):
        chosen["plate"] = old["plate"]
    return chosen

def parse_vault_dt(created_at):
    try:
        return datetime.datetime.strptime(created_at.strip(), "%d-%m-%Y %H%M%S")
    except Exception:
        return None

def load_manual_map():
    mp = {}
    try:
        conn = db_connect()
        c = conn.cursor()
        c.execute("SELECT unit, plate, insured, amount, created_at, file_name FROM manual_tx ORDER BY id")
        for u, p, n, a, ca, fn in c.fetchall():
            mp[fn] = (u, p, n, a, ca)
            mp["_" + fn] = (u, p, n, a, ca)
        conn.close()
    except Exception as e:
        log_exception("load_manual_map", e)
    return mp

_PARSE_CACHE = {}

def make_record(path, unit, plate, insured, amount, dt, mdate, is_manual, **extra):
    bname = os.path.basename(path)
    is_void = bname.startswith("_") or bname.lstrip("_") in _VOID_KEYS
    rec = {
        "unit": unit, "plate": plate, "insured": insured, "amount": float(amount),
        "time": dt.strftime("%d-%m-%Y %H:%M") if dt else "-",
        "chassis": "-", "motor": "-", "make": "-", "model": "-", "period": "-",
        "file": bname, "path": path, "is_manual": is_manual,
        "is_void": is_void,
        "legacy_void": bname.startswith("_"),
        "void_reason": _VOID_KEYS.get(bname.lstrip("_"), {}).get("reason", ""),
        "actual_date": dt.date() if dt else mdate,
        "dt_key": dt if dt else datetime.datetime.combine(mdate, datetime.time.min),
    }
    rec.update(extra)
    return rec

def read_pdf_record(path, manual_map):
    b = os.path.basename(path)
    if b.endswith("_cropped.pdf"):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    mdate = datetime.date.fromtimestamp(st.st_mtime)

    if MANUAL_NAME_RE.match(b):
        row = manual_map.get(b)
        clean_b = b.lstrip("_")
        m_amt = re.match(r"^(\d+(?:\.\d{2})?)", clean_b)
        if row:
            u, p, n, a, ca = row
            unit = detect_unit_from_text(u) or UNSPEC
            dt = parse_vault_dt(ca) or datetime.datetime.fromtimestamp(st.st_mtime)
            return make_record(path, unit, p or "-", n or "-", a, dt, mdate, True)
        key = (path, st.st_mtime, st.st_size, "manual")
        if key in _PARSE_CACHE:
            return dict(_PARSE_CACHE[key])
        txt = run_pdftotext(path)
        unit = detect_unit_from_text(txt) or UNSPEC
        tm = TIME_RE.search(txt)
        dt = parse_print_time(tm.group(0).strip().replace("/", "-")) if tm else None
        amt = float(m_amt.group(1)) if m_amt else 0.0
        rec = make_record(path, unit, "-", "-", amt, dt, mdate, True)
        _cache_put(_PARSE_CACHE, key, dict(rec))
        return rec

    key = (path, st.st_mtime, st.st_size)
    if key in _PARSE_CACHE:
        cached = _PARSE_CACHE[key]
        return dict(cached) if cached else None
    txt = run_pdftotext(path)
    if not is_receipt_text(txt):
        _cache_put(_PARSE_CACHE, key, None)
        return None
    f = parse_receipt(path, txt)
    rec = make_record(path, f["unit"], f["plate"], f["insured"], f["amount"], f["dt"], mdate, False,
                      chassis=f["chassis"], motor=f["motor"], make=f["make"],
                      model=f["model"], period=f["period"])
    if not f["dt"]:
        rec["time"] = f["time"]
    _cache_put(_PARSE_CACHE, key, dict(rec))
    return rec

def read_txt_record(tfile, target_date):
    fname = os.path.basename(tfile)
    clean_fn = fname.lstrip("_")
    m_amt = re.search(r"^(\d+(?:\.\d{2})?)", clean_fn)
    if not m_amt:
        return None
    amt = float(m_amt.group(1))
    t_content = ""
    try:
        with open(tfile, "r", encoding="utf-8", errors="ignore") as tf:
            t_content = clean_arabic(tf.read()).strip()
    except Exception as e:
        log_exception(f"read_txt:{fname}", e)
    txt_date = extract_date_from_text(t_content)
    if not txt_date:
        try:
            earliest = min(os.path.getmtime(tfile), os.path.getctime(tfile))
            txt_date = datetime.datetime.fromtimestamp(earliest).date()
        except Exception:
            txt_date = target_date
    unit = detect_unit_from_text(t_content) or UNSPEC
    plate, insured = "-", "-"
    for line in [l.strip() for l in t_content.splitlines() if l.strip()]:
        if "لوحة" in line or "لوحه" in line:
            cv = re.sub(r"^(?:رقم\s+)?(?:ال)?لوح[ةه][:\-\s]*", "", line).strip()
            if cv: plate = cv
        elif "مؤمن" in line or "اسم" in line:
            cv = re.sub(r"^(?:اسم\s+)?(?:ال)?مؤمن(?:\s+له)?[:\-\s]*", "", line).strip()
            if cv: insured = cv
    rec = make_record(tfile, unit, plate, insured, amt, None, txt_date, True)
    rec["time"] = txt_date.strftime("%d-%m-%Y")
    return rec

def clean_download_filename(filename):
    base, ext = os.path.splitext(filename)
    clean_base = re.sub(r"\s*\(\d+\)$", "", base)
    return clean_base + ext

def collect_records(folder_path, target_date, progress=None):
    load_void_map()
    pdf_files = []
    margin = target_date - datetime.timedelta(days=1)
    for f in glob.glob(os.path.join(folder_path, "*.pdf")):
        if f.endswith("_Summary.pdf") or f.endswith("_cropped.pdf"):
            continue
        try:
            if datetime.date.fromtimestamp(os.path.getmtime(f)) < margin:
                continue
        except OSError:
            continue
        pdf_files.append(f)

    arch_day = archive_day_dir(folder_path, target_date)
    if os.path.isdir(arch_day):
        for f in glob.glob(os.path.join(arch_day, "*.pdf")):
            if not os.path.basename(f).startswith("Samary_") and not f.endswith("_cropped.pdf"):
                pdf_files.append(f)

    txt_files = [f for f in glob.glob(os.path.join(folder_path, "*.txt")) if os.path.basename(f) != "Copy_Slip.txt"]
    if os.path.isdir(arch_day):
        txt_files += [f for f in glob.glob(os.path.join(arch_day, "*.txt"))]
    total = len(pdf_files) + len(txt_files)
    manual_map = load_manual_map()
    records = []
    done = 0

    for pdf in pdf_files:
        done += 1
        if progress: progress(done, total, os.path.basename(pdf))
        rec = read_pdf_record(pdf, manual_map)
        if rec and rec["actual_date"] == target_date:
            records.append(refresh_void_flag(rec))

    for tfile in txt_files:
        done += 1
        if progress: progress(done, total, os.path.basename(tfile))
        rec = read_txt_record(tfile, target_date)
        if rec and rec["actual_date"] == target_date:
            records.append(refresh_void_flag(rec))

    records.sort(key=lambda x: x["dt_key"])
    return records

def annotate_records(records):
    for r in records:
        r["_key"] = (r["unit"], r["plate"], r["insured"], round(r["amount"], 2), r["time"],
                     r["chassis"], r["motor"], r["make"], r["model"], r["period"])

    active = [r for r in records if not r.get("is_void")]
    key_counts = Counter(r["_key"] for r in active)
    unit_counter = Counter(r["unit"] for r in active if r["unit"] != UNSPEC)
    device_unit = unit_counter.most_common(1)[0][0] if unit_counter else None

    dup_sig_seen = set()
    browser_dup = {}
    for r in sorted(active, key=lambda x: x["dt_key"]):
        ident = dup_ident(r)
        tx_sig = (ident, r["time"], round(r["amount"], 2))
        if ident is not None and tx_sig in dup_sig_seen:
            browser_dup[id(r)] = True
        else:
            browser_dup[id(r)] = False
            if ident is not None:
                dup_sig_seen.add(tx_sig)

    for r in records:
        if r.get("is_void"):
            reason = r.get("void_reason") or ""
            r["dup_n"], r["is_duplicate"], r["wrong_unit"] = 1, False, False
            r["missing"], r["is_browser_dup"] = [], False
            r["kind"] = "void"
            r["status_text"] = tr("status_void") + (f" ({reason})" if reason else "")
            continue

        n = key_counts[r["_key"]]
        if browser_dup.get(id(r), False) and n < 2:
            n = 2   # نفس المعاملة بملف تاني (اسم مختلف): مش داخلة في الإجمالي، فتظهر "مكرر"
        r["dup_n"] = n
        r["is_duplicate"] = n > 1
        r["wrong_unit"] = bool(device_unit and r["unit"] not in (UNSPEC, device_unit))
        missing = []
        if r["amount"] <= 0:
            missing.append("0 amt")
        if not r["is_manual"]:
            if r["plate"] == "-": missing.append("plate")
            if r["unit"] == UNSPEC: missing.append("unit")
        r["missing"] = missing
        r["is_browser_dup"] = browser_dup.get(id(r), False)

        if r["is_duplicate"]:
            r["kind"], r["status_text"] = "dup", tr("status_dup", n=n)
        elif r["wrong_unit"]:
            r["kind"], r["status_text"] = "wrong", tr("status_wrong")
        elif missing:
            r["kind"], r["status_text"] = "missing", tr("status_missing") + "، ".join(missing)
        elif r["is_manual"]:
            r["kind"], r["status_text"] = "manual", tr("status_manual")
        else:
            r["kind"], r["status_text"] = "ok", tr("status_ok")

    return device_unit

def dup_ident(r):
    """هوية المركبة لكشف التكرار: اللوحة، ولو فاضية فالشاسيه (ثابت للمركبة). None = مفيش هوية فمش بنقارن."""
    if r["plate"] != "-":
        return ("plate", r["plate"])
    ch = (r.get("chassis") or "-").strip()
    return ("chassis", ch) if ch not in ("-", "") else None

def counted_ids(records):
    """المعاملات اللي بتدخل في الإجمالي: كل إيصال نزل في Downloads (مبلغه بيتضاف)، ما عدا اللي اتلغى يدويًا.
    التكرار (نفس اللوحة/الشاسيه + الوقت + المبلغ) مجرد علامة وتلوين في Records Viewer ومبيتشالش من الإجمالي؛
    لو المستخدم شاف تكرار فعلًا بيلغي واحدة يدويًا. نفس الدالة بتحدد الإجمالي في الشاشة والإكسيل وبون الملخص."""
    return {id(r) for r in records if not r.get("is_void")}

def counted_totals(records):
    """(مجموع المبالغ، عدد المعاملات) المحسوبة فعلًا في الإجمالي."""
    ids = counted_ids(records)
    return round(sum(r["amount"] for r in records if id(r) in ids), 2), len(ids)

def build_summary(records, device_unit, date_label):
    units_summary = {}
    valid_total_sum = 0.0
    valid_count = 0
    void_count = 0
    void_sum = 0.0
    counted = counted_ids(records)

    for r in records:
        if r.get("is_void"):
            void_count += 1
            void_sum += r["amount"]
            continue

        u = units_summary.setdefault(r["unit"], {"count": 0, "total": 0.0, "pdf_cnt": 0, "manual_cnt": 0})
        u["count"] += 1
        u["total"] += r["amount"]
        u["manual_cnt" if r["is_manual"] else "pdf_cnt"] += 1

        if id(r) in counted:
            valid_total_sum += r["amount"]
            valid_count += 1

    info = {
        "date_label": date_label,
        "unit": device_unit or UNSPEC,
        "total_count": valid_count,
        "raw_count": len(records),
        "total_sum": round(valid_total_sum, 2),
        "void_count": void_count,
        "void_sum": round(void_sum, 2),
        "pdf_count": sum(1 for r in records if not r["is_manual"] and not r.get("is_void")),
        "manual_count": sum(1 for r in records if r["is_manual"] and not r.get("is_void")),
        "duplicates": sum(1 for r in records if r["is_duplicate"] and not r.get("is_void")),
        "wrong_count": sum(1 for r in records if r["wrong_unit"] and not r.get("is_void")),
        "missing_count": sum(1 for r in records if r["missing"] and not r.get("is_void")),
    }
    return info, units_summary

def write_report(records, out_file):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detailed Report"
    ws.views.sheetView[0].rightToLeft = True

    font_header = Font(name="Arial", size=12, bold=True, color="FFFFFF")
    font_regular = Font(name="Arial", size=11, bold=True, color="000000")
    fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_total = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    KIND_STYLE = {
        "dup": (PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"), "9C0006"),
        "wrong": (PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid"), "833C0B"),
        "missing": (PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"), "7F6000"),
        "manual": (PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid"), "1F3864"),
        "void": (PatternFill(start_color="D1D5DB", end_color="D1D5DB", fill_type="solid"), "4B5563"),
    }
    thin_border = Border(left=Side(style='thin', color='B0B0B0'), right=Side(style='thin', color='B0B0B0'),
                         top=Side(style='thin', color='B0B0B0'), bottom=Side(style='thin', color='B0B0B0'))
    center = Alignment(horizontal="center", vertical="center")

    headers = ["م", "وحدة المرور", "رقم اللوحة", "اسم المؤمن له", "المبلغ (جنيه)",
               "وقت الطباعة", "رقم الشاسية", "رقم الموتور", "الماركة",
               "الطراز", "المدة التأمينية", "اسم الملف", "نوع المعاملة", "داخل الإجمالي (1=نعم)"]
    counted = counted_ids(records)

    ws.row_dimensions[1].height = 28
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font, cell.fill, cell.alignment = font_header, fill_header, center

    current_r = 1
    for idx, rec in enumerate(records, 1):
        current_r += 1
        ws.row_dimensions[current_r].height = 22
        amt_value = -float(rec['amount']) if rec.get('is_void') else float(rec['amount'])
        row_data = [idx, rec['unit'], str(rec['plate']), rec['insured'], amt_value,
                    rec['time'], str(rec['chassis']), str(rec['motor']), rec['make'],
                    rec['model'], rec['period'], rec['file'], rec['status_text'], 1 if id(rec) in counted else 0]
        style = KIND_STYLE.get(rec["kind"])
        for col_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=current_r, column=col_idx, value=val)
            cell.font, cell.border, cell.alignment = font_regular, thin_border, center
            if style:
                cell.fill = style[0]
                cell.font = Font(name="Arial", size=11, bold=True, color=style[1])
            if col_idx == 5:
                cell.number_format = '#,##0.00'

    last_data = max(2, current_r)
    ws.auto_filter.ref = f"A1:N{last_data}"
    ws.freeze_panes = "A2"

    current_r += 1
    tot_label = ws.cell(row=current_r, column=2, value="الصافي الفعلي العام")
    tot_label.font, tot_label.fill, tot_label.border = Font(name="Arial", size=12, bold=True), fill_total, thin_border
    
    valid_count = len(counted)
    cnt_cell = ws.cell(row=current_r, column=4, value=valid_count)
    cnt_cell.font, cnt_cell.fill, cnt_cell.alignment, cnt_cell.border = Font(name="Arial", size=12, bold=True), fill_total, center, thin_border
    sum_cell = ws.cell(row=current_r, column=5, value=f"=SUMPRODUCT(E2:E{last_data},N2:N{last_data})")
    sum_cell.font, sum_cell.fill, sum_cell.alignment, sum_cell.border = Font(name="Arial", size=12, bold=True, color="C00000"), fill_total, center, thin_border
    sum_cell.number_format = '#,##0.00'

    for col_i in range(1, 15): ws.column_dimensions[get_column_letter(col_i)].width = 20
    ws.column_dimensions['D'].width = 32
    ws.column_dimensions['L'].width = 30
    ws.column_dimensions['M'].width = 28
    
    try:
        wb.save(out_file)
    except Exception:
        alt_path = out_file.replace(".xlsx", f"_{int(time.time())}.xlsx")
        try: wb.save(alt_path)
        except Exception as _e: _log_silent("write_report#1", _e)
    return out_file

def _content_stream_bytes(data, page_body):
    m = re.search(rb"/Contents\s+(\d+)\s+0\s+R", page_body)
    if not m: return b""
    om = re.search(rb"(?<!\d)" + m.group(1) + rb"\s+0\s+obj\s*<<(.*?)>>\s*stream\r?\n", data, re.S)
    if not om: return b""
    st = om.end()
    en = data.find(b"endstream", st)
    raw = bytes(data[st:en])
    if b"FlateDecode" in om.group(1):
        try: return zlib.decompress(raw)
        except Exception: return b""
    return raw

def _find_qr_top(content):
    best = None
    for m in re.finditer(rb"([-\d.]+)\s+0\s+0\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+cm\s*/\w+\s+Do", content):
        try: w, h, x, y = [float(v) for v in m.groups()]
        except ValueError: continue
        top = y + h if h > 0 else y
        area = abs(w * h)
        if best is None or area > best[0]:
            best = (area, top)
    return best[1] if best else None

def get_print_time_bottom(pdf_path):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        res = subprocess.run([PDFTOTEXT_EXE, "-bbox", pdf_path, "-"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore",
                             creationflags=flags, timeout=45)
    except Exception as e:
        log_exception("bbox", e)
        return None
    out = res.stdout or ""
    pm = re.search(r'<page\s+width="([\d.]+)"\s+height="([\d.]+)"', out)
    if not pm: return None
    best = None
    for m in re.finditer(r'<word\s+xMin="[\d.]+"\s+yMin="[\d.]+"\s+xMax="[\d.]+"\s+yMax="([\d.]+)">(\d{2}:\d{2})</word>', out):
        best = float(m.group(1))
    if best is None: return None
    return best, float(pm.group(2))

PRINT_TARGET_W_PT = 57 / 25.4 * 72   # عرض الطباعة المطلوب: 57 مم

def scale_pdf_to_print_width(src_pdf, target_w=PRINT_TARGET_W_PT):
    """نسخة مؤقتة من الـ PDF مصغّرة لعرض 57 مم. الإيصالات بتتصمم بعرض 80 مم، وكان الحجم النهائي بيتحدد من
    مقاس الورق المعرّف في كل جهاز (fit): 57x90 بيطلّع الحجم الصح، و80 مم بيطلّعه كبير. دلوقتي البرنامج هو اللي
    بيحدد الحجم. بترجع None لو الصفحة أصلًا بعرض 57 مم أو أقل، أو لو pypdf مش متاح (وساعتها الطباعة زي ما كانت)."""
    if not PYPDF_AVAILABLE:
        return None
    try:
        reader = PdfReader(src_pdf)
        if not reader.pages:
            return None
        w = float(reader.pages[0].mediabox.width)
        if w <= target_w + 2:
            return None
        f = target_w / w
        writer = PdfWriter()
        for pg in reader.pages:
            pg.scale_by(f)
            writer.add_page(pg)
        os.makedirs(PRINT_TEMP_DIR, exist_ok=True)
        dst = os.path.join(PRINT_TEMP_DIR, "s_" + os.path.basename(src_pdf))
        with open(dst, "wb") as fh:
            writer.write(fh)
        return dst
    except Exception as e:
        log_exception("scale_pdf_to_print_width", e)
        return None

def make_print_copy(src_pdf):
    try:
        data = bytearray(open(src_pdf, "rb").read())
        page_obj = None
        for m in re.finditer(rb"\d+\s+0\s+obj(.*?)endobj", data, re.S):
            if re.search(rb"/Type\s*/Page(?![A-Za-z])", m.group(1)):
                page_obj = m
                break
        if not page_obj: return None
        page_body = bytes(data[page_obj.start(1):page_obj.end(1)])
        mb = re.search(rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]", page_body)
        if not mb: return None
        x0, y0, x1, y1 = [float(v) for v in mb.groups()]

        new_y0 = None
        qr_top = _find_qr_top(_content_stream_bytes(data, page_body))
        if qr_top is not None:
            new_y0 = qr_top + 4.5
        else:
            info = get_print_time_bottom(src_pdf)
            if info:
                new_y0 = y1 - (info[0] + 12.0)

        if new_y0 is None: return None
        new_y0 = max(y0, new_y0)
        if new_y0 >= y1 - 40: return None

        new_y1 = y1

        base = page_obj.start(1)
        reg_start, reg_end = base + mb.start(), base + mb.end()
        while True:
            nxt = re.match(rb"\s*/(?:BleedBox|TrimBox|CropBox|ArtBox)\s*\[[^\]]*\]", bytes(data[reg_end:reg_end + 200]))
            if not nxt: break
            reg_end += nxt.end()

        box = f"[{x0:g} {new_y0:.3f} {x1:g} {new_y1:.3f}]".encode()
        old_len = reg_end - reg_start
        new = b"/MediaBox " + box + b" /CropBox " + box
        if len(new) > old_len: new = b"/MediaBox " + box
        if len(new) > old_len: return None

        new = new + b" " * (old_len - len(new))
        data[reg_start:reg_end] = new

        os.makedirs(PRINT_TEMP_DIR, exist_ok=True)
        dst = os.path.join(PRINT_TEMP_DIR, os.path.basename(src_pdf))
        with open(dst, "wb") as f:
            f.write(data)
        return dst
    except Exception as e:
        log_exception("make_print_copy", e)
        return None

class ElevateLoginGate(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.parent = parent
        self.on_success = on_success
        self.title("A2R Authorization")
        self.resizable(False, False)
        set_window_icon_safe(self)
        center_window_relative(self, parent, 360, 205)

        t = THEMES[parent.current_theme_name]
        self.configure(fg_color=t["bg"])

        ctk.CTkLabel(self, text="A2R OPERATIONS", font=(FONT_FAMILY, 15, "bold"), text_color=t["accent"]).pack(pady=(12, 1))
        ctk.CTkLabel(self, text=tr("login_prompt"), font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"]).pack(pady=(0, 6))

        f_entry = ctk.CTkFrame(self, fg_color="transparent")
        f_entry.pack(fill="x", padx=24, pady=4)

        self.e_pwd = ctk.CTkEntry(f_entry, show="•", justify="center", font=(FONT_FAMILY, 13, "bold"),
                                  text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        self.e_pwd.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.e_pwd.bind("<Return>", lambda e: self.check_pwd())
        attach_context_menu(self.e_pwd)

        self.pwd_visible = False
        self.btn_eye = ctk.CTkButton(f_entry, text="👁️", width=35, command=self.toggle_eye, fg_color=t["card"], text_color=t["text"])
        self.btn_eye.pack(side="right")

        self.lbl_err = ctk.CTkLabel(self, text="", text_color=t["danger"], font=(FONT_FAMILY, 10, "bold"))
        self.lbl_err.pack(pady=(1, 0))

        btn_enter = ctk.CTkButton(self, text=tr("btn_full_console"), font=FONT_BTN_MAIN,
                                  fg_color="#DC2626", hover_color="#B91C1C", text_color="#FFFFFF", command=self.check_pwd)
        btn_enter.pack(fill="x", padx=24, pady=(6, 4))

        ctk.CTkLabel(self, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria",
                     font=(FONT_FAMILY, 9, "bold"), text_color="#64748B").pack(pady=(4, 6))
        self.after(150, self.e_pwd.focus_set)

    def toggle_eye(self):
        if self.pwd_visible:
            self.e_pwd.configure(show="•")
            self.btn_eye.configure(text="👁️")
            self.pwd_visible = False
        else:
            self.e_pwd.configure(show="")
            self.btn_eye.configure(text="🙈")
            self.pwd_visible = True

    def check_pwd(self):
        rem = sup_lock_remaining()
        if rem > 0:
            self.lbl_err.configure(text=T2(f"مقفول مؤقتًا. حاول بعد {rem} ثانية.", f"Locked. Try again in {rem}s."))
            self.e_pwd.delete(0, 'end')
            return
        val = self.e_pwd.get().strip().lower()
        h_val = hashlib.sha256(val.encode('utf-8')).hexdigest()
        if is_supervisor_password(val):
            sup_register_success()
            self.destroy()
            self.on_success(is_supervisor=True)
        elif h_val in EMPLOYEE_HASHES:
            sup_register_success()
            self.destroy()
            self.on_success(is_supervisor=False)
        else:
            sup_register_fail()
            self.lbl_err.configure(text=tr("access_denied"))
            self.e_pwd.delete(0, 'end')
            try: winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception as _e: _log_silent("check_pwd#1", _e)

class AdminPasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.title("Admin Access Required")
        self.resizable(False, False)
        set_window_icon_safe(self)
        center_window_relative(self, parent, 320, 160)
        t = THEMES[parent.current_theme_name]
        self.configure(fg_color=t["bg"])

        ctk.CTkLabel(self, text="🔒 Admin Password for Excel", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"]).pack(pady=(12, 4))
        self.e = ctk.CTkEntry(self, show="•", justify="center", font=(FONT_FAMILY, 12, "bold"))
        self.e.pack(padx=20, pady=4, fill="x")
        self.e.focus_set()
        attach_context_menu(self.e)

        def _chk(event=None):
            rem = sup_lock_remaining()
            if rem > 0:
                messagebox.showerror("Access Denied", T2(f"مقفول مؤقتًا. حاول بعد {rem} ثانية.", f"Locked. Try again in {rem}s."))
                self.destroy()
                return
            if is_supervisor_password(self.e.get()):
                sup_register_success()
                self.destroy()
                on_success()
            else:
                sup_register_fail()
                try: winsound.MessageBeep(winsound.MB_ICONHAND)
                except Exception as _e: _log_silent("_chk#1", _e)
                messagebox.showerror("Access Denied", tr("restricted_admin"))
                self.destroy()

        self.e.bind("<Return>", _chk)
        ctk.CTkButton(self, text="Unlock", font=FONT_BTN_SUB, fg_color=t["primary"], command=_chk).pack(pady=8)

class CustomTkinterApp(ctk.CTk):
    def validate_numeric_input(self, val):
        if val == "": return True
        return bool(re.match(r"^[\d,]*\.?\d*$", val))

    def __init__(self):
        super().__init__()
        self.title(f"A2R Operations Console - {APP_OWNER}")
        self.resizable(False, False)
        
        # فرض أبعاد دنيا ثابتة تمنع انكماش النافذة نهائياً
        self.minsize(440, 210)
        set_window_icon_safe(self)

        global CURRENT_LANG
        self.current_lang = "en"
        CURRENT_LANG = "en"
        self.current_theme_name = "Aero Dark"

        self.is_mini_mode = True
        self.auto_sync_enabled = True
        self.auto_print_enabled = True

        self.is_supervisor = False
        self.last_generated_file = None
        self.system_total_sum = 0.0
        self.last_detailed_records = []
        self.last_units_summary = {}
        self.last_summary_info = {}

        self.printed_count_today = 0
        self.processing_lock = threading.Lock()
        self.is_processing = False
        self.last_pdf_state_sig = ""
        self.printed_receipts_set = set()
        self._watch_path = DEFAULT_RECEIPTS_DIR

        self.tray_icon = None
        self._auto_minimize_timer = None
        
        # قراءة متغير الأوتوستارت من سطر الأوامر داخلياً
        self.autostart_silent = ("--autostart" in sys.argv)

        self.setup_ui()
        self.apply_theme(self.current_theme_name)
        self.apply_language(self.current_lang)

        self.reset_all()
        install_clipboard_shortcuts(self)
        self._sync_watch_path()

        # مراقبة نشاط المستخدم لتصفير مؤقت الخمول 30 ثانية
        self.bind_all("<Any-KeyPress>", self._on_user_interaction, add="+")
        self.bind_all("<Motion>", self._on_user_interaction, add="+")
        self.bind_all("<ButtonPress>", self._on_user_interaction, add="+")
        self.bind_all("<MouseWheel>", self._on_user_interaction, add="+")

        p = self.get_clean_path()
        if os.path.exists(p):
            for f in glob.glob(os.path.join(p, "*.pdf")):
                fn = os.path.basename(f)
                self.printed_receipts_set.add(fn)
                self.printed_receipts_set.add(clean_download_filename(fn))

        self.init_watchdogs()
        
        # ربط زر X بالنزول لصينية النظام بجوار الساعة
        self.protocol("WM_DELETE_WINDOW", self.hide_to_system_tray)

        setup_windows_autostart()

        if not PYSTRAY_AVAILABLE:
            log_exception("pystray_import", PYSTRAY_IMPORT_ERROR or "pystray/Pillow not installed or not bundled")

        if PYSTRAY_AVAILABLE and self.tray_icon is None:
            self._init_tray_icon()

        # نبني واجهة الميني دائماً (حتى في التشغيل الصامت) كي تظهر كاملة عند الاستدعاء من الصينية
        # أو عند فتح الـ exe مرة ثانية، ثم نخفي النافذة إذا كان التشغيل تلقائياً مع ويندوز
        if self.autostart_silent:
            self.withdraw()
            self.switch_to_mini_view(show=False)
            if self.tray_icon is not None:
                self.withdraw()      # الصينية شغالة: نخفي النافذة وتظهر الأيقونة بجوار الساعة
            else:
                self.iconify()       # لا توجد صينية: نصغّر لشريط المهام حتى لا يختفي البرنامج
        else:
            self.switch_to_mini_view()

    def on_app_close(self):
        self.hide_to_system_tray()

    def _init_tray_icon(self):
        try:
            menu = pystray.Menu(
                pystray.MenuItem(tr("tray_open"), self.show_from_system_tray, default=True),
                pystray.MenuItem(tr("tray_console"), lambda: self.run_on_main(self.request_full_console_from_tray)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(tr("tray_exit"), self.quit_app_completely)
            )
            self.tray_icon = pystray.Icon("A2R", self._create_tray_image(), "A2R Console", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            self.tray_icon = None
            log_exception("init_tray_icon", e)

    def _trigger_daily_full_archive_once(self):
        today_tag = datetime.date.today().strftime("%Y-%m-%d")
        try:
            conn = db_connect()
            c = conn.cursor()
            c.execute("SELECT meta_value FROM system_meta WHERE meta_key = 'last_full_archive_date'")
            row = c.fetchone()
            last_date = row[0] if row else ""
            if last_date != today_tag:
                target_folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
                if os.path.exists(target_folder) and os.path.isdir(target_folder):
                    self._silent_archive_all_historical(target_folder)
                c.execute("INSERT OR REPLACE INTO system_meta (meta_key, meta_value) VALUES ('last_full_archive_date', ?)", (today_tag,))
                conn.commit()
            conn.close()
        except Exception as e:
            log_exception("trigger_daily_full_archive_once", e)

    def _run_archive_sweep(self, folder_path, progress=None, stage=None):
        """كنس + تحديث ملخصات الأيام اللي اتغيّرت. آمنة لو اتنادت من أكتر من مكان.
        بترجّع None لو كنسة تانية شغالة بالفعل (يعني ماحصلش شغل)، وإلا عدد الملفات المنقولة.
        stage(i, n, name): بتبلّغ تقدّم مرحلة بناء الملخصات/الإكسيل (بعد ما النقل يخلص)."""
        if not _SWEEP_LOCK.acquire(blocking=False): return None
        moved = 0
        try:
            moved, touched = archive_sweep(folder_path, progress)
            _touched = sorted(touched)
            for _i, d_folder in enumerate(_touched, 1):
                d_name = os.path.basename(d_folder)
                if stage:
                    try: stage(_i, len(_touched), d_name)
                    except Exception as _e: _log_silent("run_archive_sweep#stage", _e)
                parent_m = os.path.basename(os.path.dirname(d_folder))
                parent_y = os.path.basename(os.path.dirname(os.path.dirname(d_folder)))
                tag = f"{d_name}-{parent_m.split('-')[0]}-{parent_y}"
                self._generate_day_summary_pdf(d_folder, tag, archive_day_records(d_folder))
                try:
                    _dd = datetime.date(int(parent_y), int(parent_m.split("-")[0]), int(d_name))
                    archive_write_day_excel(d_folder, _dd)
                except Exception as _e:
                    log_exception("archive_day_excel", _e)
        except Exception as e:
            log_exception("run_archive_sweep", e)
        finally:
            _SWEEP_LOCK.release()
        if moved: self._start_archive_maintenance(folder_path)
        return moved

    def _archive_tick(self):
        """كل 10 دقايق: أي ملف مش بتاع النهارده يتأرشف (يغطي تغيير اليوم والملفات اللي فشلت قبل كده)."""
        try:
            folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
            if folder and os.path.isdir(folder) and not self.processing_lock.locked():
                threading.Thread(target=self._run_archive_sweep, args=(folder,), daemon=True).start()
        except Exception as e:
            log_exception("archive_tick", e)
        finally:
            self.after(600000, self._archive_tick)

    def _silent_archive_all_historical(self, folder_path):
        self._run_archive_sweep(folder_path)
        self._start_archive_maintenance(folder_path)

    def _cancel_auto_minimize(self):
        if self._auto_minimize_timer:
            try:
                self.after_cancel(self._auto_minimize_timer)
            except Exception as _e:
                _log_silent("_cancel_auto_minimize#1", _e)
            self._auto_minimize_timer = None

    def _schedule_auto_minimize(self, delay_ms):
        self._cancel_auto_minimize()
        self._auto_minimize_timer = self.after(delay_ms, self._auto_minimize_to_taskbar)

    def _on_user_interaction(self, event=None):
        if not self.is_mini_mode and self.state() == "normal":
            self._schedule_auto_minimize(30000)

    def _auto_minimize_to_taskbar(self):
        try:
            if self.state() == "normal":
                self.iconify()
        except Exception as _e:
            _log_silent("_auto_minimize_to_taskbar#1", _e)

    def _create_tray_image(self):
        ico_path = get_app_icon_path()
        if ico_path:
            try:
                return Image.open(ico_path).convert("RGBA")
            except Exception as _e:
                _log_silent("_create_tray_image#1", _e)
        img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, 60, 60], fill="#080E17", outline="#38BDF8", width=3)
        d.text((16, 18), "A2R", fill="#38BDF8")
        return img

    def hide_to_system_tray(self):
        self._cancel_auto_minimize()
        if not PYSTRAY_AVAILABLE:
            if not getattr(self, "_tray_warned", False):
                self._tray_warned = True
                try:
                    messagebox.showwarning(
                        "System Tray",
                        "ميزة النزول بجوار الساعة غير متاحة في هذه النسخة (مكتبة pystray/Pillow غير مضمّنة في البناء).\n"
                        "سيتم تصغير البرنامج إلى شريط المهام بدلاً من ذلك.\n\n"
                        f"Details: {PYSTRAY_IMPORT_ERROR or 'module not found'}")
                except Exception as _e:
                    _log_silent("hide_to_system_tray#1", _e)
            self.iconify()
            return
        if self.tray_icon is None:
            self._init_tray_icon()
        if self.tray_icon is None:
            # فشل إنشاء الأيقونة: لا نخفي النافذة حتى لا يضيع البرنامج
            self.iconify()
            return
        self.withdraw()

    def show_from_system_tray(self, icon=None, item=None):
        def _restore():
            self.deiconify()
            self.state("normal")
            if self.is_mini_mode:
                self.switch_to_mini_view()
            else:
                self.switch_to_full_view()
            self.lift()
            self.focus_force()
        self.run_on_main(_restore)

    def request_full_console_from_tray(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()
        self.request_full_console()

    def quit_app_completely(self, icon=None, item=None):
        self._cancel_auto_minimize()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception as _e:
                _log_silent("quit_app_completely#1", _e)
        self.run_on_main(self.destroy)

    def fix_printer_paper_action(self):
        ok, msg = configure_printer_57x90_silent()
        play_sound_matched()
        messagebox.showinfo(tr("done"), tr("fix_printer_ok"))

    def reprint_receipt_record(self, rec):
        fpath = rec.get("path", "")
        if not fpath or not os.path.exists(fpath):
            candidates = [
                os.path.join(self.get_clean_path(), rec.get("file", "")),
                os.path.join(self.get_clean_path(), "_" + rec.get("file", "").lstrip("_"))
            ]
            for c in candidates:
                if os.path.exists(c):
                    fpath = c
                    break

        if fpath and os.path.exists(fpath):
            if self.send_to_thermal_printer_57x90(fpath):
                play_sound_matched()
                messagebox.showinfo(tr("done"), tr("reprint_success"))
            else:
                messagebox.showerror("Error", T2("تعذرت الطباعة. اتأكد من الطابعة وحاول تاني.",
                                                 "Printing failed. Check the printer and try again."))
        else:
            messagebox.showerror("Error", f"File not found: {rec.get('file', '')}")

    def _sync_watch_path(self):
        try: self._watch_path = self.get_clean_path()
        except Exception as _e: _log_silent("_sync_watch_path#1", _e)
        try: self.after(1000, self._sync_watch_path)
        except Exception as _e: _log_silent("_sync_watch_path#2", _e)

    def request_full_console(self):
        self._cancel_auto_minimize()
        ElevateLoginGate(self, self.unlock_full_console)

    def unlock_full_console(self, is_supervisor):
        self.is_supervisor = is_supervisor

        # كل الصلاحيات متاحة للجميع (مستخدم أو مشرف) ما عدا زر الإكسل: حصري للمشرف
        for w in (self.cb_d, self.cb_m, self.cb_y):
            w.configure(state="normal")
        for w in (self.btn_yesterday, self.btn_browse, self.btn_open_f):
            w.configure(state="normal")

        self.btn_excel.pack_forget()
        self.btn_arch_hist.pack_forget()
        self.btn_pos_close.pack_forget()
        self.btn_pos_pay.pack_forget()
        if getattr(self, "btn_pos_tools", None) is not None:
            self.btn_pos_tools.pack_forget()
        self.btn_chrome.pack_forget()
        if is_supervisor:
            self.badge_role.configure(text="● ADMIN", text_color="#EF4444")
            self.f_role_btn.configure(border_color="#EF4444")
            if getattr(self, "btn_pos_tools", None) is not None:
                self.btn_pos_tools.pack(side="left", padx=2)
            else:
                self.btn_excel.pack(side="left", padx=2)
                self.btn_arch_hist.pack(side="left", padx=2)
                self.btn_pos_close.pack(side="left", padx=2)
                self.btn_pos_pay.pack(side="left", padx=2)
        else:
            self.badge_role.configure(text="● USER", text_color="#10B981")
            self.f_role_btn.configure(border_color="#10B981")
        self.btn_chrome.pack(side="left", padx=2)

        self.switch_to_full_view()
        # أرشفة تلقائية لكل الأيام السابقة فور الدخول (مستخدم أو مشرف) مع إظهار نافذة التقدم
        self.after(400, self.auto_archive_on_login)
        if not getattr(self, "_archive_tick_started", False):
            self._archive_tick_started = True
            self.after(600000, self._archive_tick)

    def _archive_done_today(self):
        today_tag = datetime.date.today().strftime("%Y-%m-%d")
        try:
            conn = db_connect()
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS system_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT)")
            c.execute("SELECT meta_value FROM system_meta WHERE meta_key = 'last_full_archive_date'")
            row = c.fetchone()
            conn.close()
            return bool(row) and row[0] == today_tag
        except Exception as e:
            log_exception("archive_done_today", e)
            return False

    def _mark_archive_done_today(self):
        today_tag = datetime.date.today().strftime("%Y-%m-%d")
        try:
            conn = db_connect()
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS system_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT)")
            c.execute("INSERT OR REPLACE INTO system_meta (meta_key, meta_value) VALUES ('last_full_archive_date', ?)", (today_tag,))
            conn.commit()
            conn.close()
        except Exception as e:
            log_exception("mark_archive_done_today", e)

    def auto_archive_on_login(self):
        """أرشفة تلقائية مرة واحدة في اليوم، في الخلفية بدون أي نافذة. لما تخلص بيظهر إشعار بجوار الساعة."""
        folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
        if not folder or not os.path.isdir(folder):
            return
        if self._archive_done_today():
            return
        if getattr(self, "_auto_archive_running", False):
            return
        self._auto_archive_running = True

        def work():
            moved, ok = None, False
            try:
                moved = self._run_archive_sweep(folder)
                if moved is not None:             # None = كنسة تانية شغالة، هنحاول تاني في الدورة الجاية
                    self._mark_archive_done_today()
                    self._start_archive_maintenance(folder)
                    ok = True
            except Exception as e:
                log_exception("auto_archive_on_login", e)
            finally:
                self._auto_archive_running = False
            if ok:
                self.run_on_main(lambda: self._notify_archive_done(moved or 0))

        threading.Thread(target=work, daemon=True).start()

    def _tray_notify(self, msg, title="A2R Console", _attempt=0):
        """إشعار ويندوز من أيقونة البرنامج بجوار الساعة."""
        try:
            icon = getattr(self, "tray_icon", None)
            if icon is None:
                return
            if not getattr(icon, "visible", True) and _attempt < 5:   # الأيقونة لسه بتظهر: نحاول بعد ثانيتين
                self.after(2000, lambda: self._tray_notify(msg, title, _attempt + 1))
                return
            icon.notify(msg, title)
        except Exception as e:
            log_exception("tray_notify", e)

    def _notify_archive_done(self, moved=0):
        self._tray_notify(T2("تمت الأرشفة ✓", "Archive completed ✓"))

    def switch_to_mini_view(self, show=True):
        self.is_mini_mode = True
        self.body_full.pack_forget()
        self.b_bar.pack_forget()
        self.btn_back_to_mini.pack_forget()
        self.f_role_btn.pack_forget()
        
        self.btn_elevate.pack(side="right", padx=(6, 0))
        self.body_mini.pack(fill="both", expand=True, padx=12, pady=(4, 4))

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = 440, 210
        self.minsize(440, 210)
        self.geometry(f"{width}x{height}+{(sw-width)//2}+{(sh-height)//2}")
        self.update_idletasks()

        if not show:
            return

        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()
        self._schedule_auto_minimize(5000)

    def switch_to_full_view(self):
        self.is_mini_mode = False
        self.body_mini.pack_forget()
        self.btn_elevate.pack_forget()
        
        self.btn_back_to_mini.pack(side="right", padx=(6, 0))
        self.f_role_btn.pack(side="right", padx=(6, 0))
        self.b_bar.pack(fill="x", side="bottom")
        self.body_full.pack(fill="both", expand=True, padx=8, pady=(2, 0))

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = 590, 465
        self.minsize(590, 465)
        self.geometry(f"{width}x{height}+{(sw-width)//2}+{(sh-height)//2}")
        self.update_idletasks()

        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

        self.bind("<Escape>", lambda e: self.confirm_and_reset())
        self.bind("<Control-r>", lambda e: self.start_thread())
        self.bind("<F2>", lambda e: self.open_manual())
        self.bind("<F3>", lambda e: self.print_slip())
        self.bind("<F4>", lambda e: self.open_cash_counter())

        self._schedule_auto_minimize(30000)

    def run_on_main(self, func):
        self.after(0, func)

    def get_clean_path(self):
        txt = self.e_path.get().strip()
        if txt.startswith("✓ "): return txt[2:].strip()
        elif txt.startswith("⚠️ "): return txt[3:].strip()
        return txt

    def set_path_with_icon(self, raw_path):
        self.e_path.delete(0, 'end')
        if os.path.exists(raw_path) and os.path.isdir(raw_path):
            self.e_path.insert(0, f"✓  {raw_path}")
        else:
            self.e_path.insert(0, f"⚠️  {raw_path}")

    def validate_path_live(self):
        clean_p = self.get_clean_path()
        if os.path.exists(clean_p) and os.path.isdir(clean_p):
            if not self.e_path.get().startswith("✓ "):
                self.e_path.delete(0, 'end')
                self.e_path.insert(0, f"✓  {clean_p}")
        else:
            if not self.e_path.get().startswith("⚠️ "):
                self.e_path.delete(0, 'end')
                self.e_path.insert(0, f"⚠️  {clean_p}")

    def update_live_clock(self):
        now = datetime.datetime.now()
        clock_str = now.strftime("%I:%M:%S %p")
        if hasattr(self, 'lbl_clock'):
            self.lbl_clock.configure(text=clock_str)
        self.after(1000, self.update_live_clock)

    def toggle_mute(self):
        global SOUND_MUTED
        SOUND_MUTED = not SOUND_MUTED
        self.btn_mute.configure(text="🔇 Muted" if SOUND_MUTED else "🔊 Sound")

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, corner_radius=0, height=36)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        f_left = ctk.CTkFrame(self.header, fg_color="transparent")
        f_left.pack(side="left", padx=(10, 0), pady=4)

        self.lbl_logo = ctk.CTkLabel(f_left, text="A2R", font=FONT_TITLE_LOGO)
        self.lbl_logo.pack(side="left", padx=(0, 6))

        self.cb_theme = ctk.CTkComboBox(f_left, values=THEME_KEYS, width=88, height=25, state="readonly",
                                        font=FONT_REGULAR_BOLD, command=self.on_theme_select)
        self.cb_theme.set(self.current_theme_name)
        self.cb_theme.pack(side="left", padx=(0, 3))

        self.btn_lang = ctk.CTkButton(f_left, text="🌐 عربي", width=54, height=25, font=FONT_REGULAR_BOLD,
                                      command=self.toggle_language)
        self.btn_lang.pack(side="left", padx=(0, 3))

        self.btn_mute = ctk.CTkButton(f_left, text="🔇 Muted", width=62, height=25, font=(FONT_FAMILY, 9, "bold"),
                                      fg_color="#334155", hover_color="#475569", command=self.toggle_mute)
        self.btn_mute.pack(side="left")

        f_right = ctk.CTkFrame(self.header, fg_color="transparent")
        f_right.pack(side="right", padx=(0, 10), pady=4)

        self.btn_elevate = ctk.CTkButton(f_right, text=tr("btn_full_console"), width=115, height=26,
                                         font=(FONT_FAMILY, 10, "bold"), fg_color="#DC2626", hover_color="#B91C1C",
                                         border_width=1, border_color="#EF4444", command=self.request_full_console)
        self.btn_elevate.pack(side="right", padx=(6, 0))

        self.btn_back_to_mini = ctk.CTkButton(f_right, text=tr("btn_back_mini"), width=95, height=25,
                                              font=(FONT_FAMILY, 10, "bold"), fg_color="#334155", hover_color="#475569",
                                              command=self.switch_to_mini_view)

        self.f_role_btn = ctk.CTkFrame(f_right, corner_radius=6, border_width=1.2, fg_color="#121E2E")
        self.badge_role = ctk.CTkLabel(self.f_role_btn, text="● USER", font=(FONT_FAMILY, 9, "bold"), padx=8, pady=1)
        self.badge_role.pack()

        self.lbl_clock = ctk.CTkLabel(f_right, text="", font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_clock.pack(side="right", padx=(0, 2))
        self.update_live_clock()

        self.body_mini = ctk.CTkFrame(self, fg_color="transparent")

        self.card_mini_status = ctk.CTkFrame(self.body_mini, corner_radius=10, border_width=1)
        self.card_mini_status.pack(fill="x", pady=(2, 4))

        f_mini_title_row = ctk.CTkFrame(self.card_mini_status, fg_color="transparent")
        f_mini_title_row.pack(fill="x", padx=14, pady=(6, 2))

        self.lbl_mini_title = ctk.CTkLabel(f_mini_title_row, text=tr("mini_station_title"),
                                          font=(FONT_FAMILY, 11, "bold"), text_color="#38BDF8")
        self.lbl_mini_title.pack(side="left")

        self.btn_fix_printer = ctk.CTkButton(f_mini_title_row, text=tr("btn_fix_printer"), width=70, height=22,
                                             font=(FONT_FAMILY, 9, "bold"), fg_color="#D97706", hover_color="#B45309",
                                             text_color="#FFFFFF", command=self.fix_printer_paper_action)
        self.btn_fix_printer.pack(side="right")

        self.lbl_mini_desc = ctk.CTkLabel(self.card_mini_status, text=tr("mini_status_active"),
                                         font=(FONT_FAMILY, 10, "bold"), text_color="#10B981")
        self.lbl_mini_desc.pack(anchor="w", padx=14, pady=(0, 2))

        self.lbl_mini_counter = ctk.CTkLabel(self.card_mini_status, text=tr("mini_printed_count", count=0),
                                            font=(FONT_FAMILY, 9, "bold"), text_color="#94A3B8")
        self.lbl_mini_counter.pack(anchor="w", padx=14, pady=(0, 6))

        self.btn_mini_archive = ctk.CTkButton(self.body_mini, text=tr("clean_downloads"), height=36,
                                              font=FONT_BTN_MAIN, fg_color="#4338CA", hover_color="#3730A3",
                                              text_color="#FFFFFF", command=self.open_downloads_archiver_dialog)
        self.btn_mini_archive.pack(fill="x", pady=(2, 4))

        self.lbl_mini_foot = ctk.CTkLabel(self.body_mini, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria",
                                         font=(FONT_FAMILY, 9, "bold"), text_color="#64748B")
        self.lbl_mini_foot.pack(anchor="center", pady=(0, 0))

        self.b_bar = ctk.CTkFrame(self, corner_radius=0, height=42)
        self.btn_center_box = ctk.CTkFrame(self.b_bar, fg_color="transparent")
        self.btn_center_box.pack(anchor="center", pady=(2, 0))

        self.btn_view_rec = ctk.CTkButton(
            self.btn_center_box, width=115, height=25, font=(FONT_FAMILY, 10, "bold"),
            text_color="#FFFFFF", fg_color="#0284C7", hover_color="#0369A1", border_width=1, border_color="#38BDF8",
            command=self.open_records_viewer
        )
        self.btn_view_rec.pack(side="left", padx=2)

        self.btn_pdf_export = ctk.CTkButton(self.btn_center_box, width=50, height=25, font=FONT_BTN_SUB,
                                           fg_color="#1A2D42", hover_color="#243C56", text_color="#FFFFFF", command=self.export_pdf_summary)
        self.btn_pdf_export.pack(side="left", padx=2)

        self.btn_print_slip = ctk.CTkButton(self.btn_center_box, fg_color="#D97706", hover_color="#B45309", width=85,
                                           height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.print_slip)
        self.btn_print_slip.pack(side="left", padx=2)

        self.btn_excel = ctk.CTkButton(self.btn_center_box, fg_color="#059669", hover_color="#047857", width=85,
                                       height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_excel)

        self.btn_arch_hist = ctk.CTkButton(self.btn_center_box, fg_color="#7C3AED", hover_color="#6D28D9", width=105,
                                           height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_archive_history)
        self.btn_pos_close = ctk.CTkButton(self.btn_center_box, fg_color="#0F766E", hover_color="#115E59", width=105,
                                           height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_pos_closing)
        self.btn_pos_pay = ctk.CTkButton(self.btn_center_box, fg_color="#B45309", hover_color="#92400E", width=105,
                                         height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_pos_payments)

        self.btn_pos_tools = None
        if POS_TOOLS_AVAILABLE:
            try:
                self.btn_pos_tools = make_pos_tools_button(self, self.btn_center_box, width=105, height=25)
            except Exception:
                self.btn_pos_tools = None

        self.btn_chrome = ctk.CTkButton(self.btn_center_box, fg_color="#2563EB", hover_color="#1D4ED8", width=90,
                                        height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_chrome_browser)

        lbl_foot = ctk.CTkLabel(self.b_bar, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria",
                                font=(FONT_FAMILY, 9, "bold"), text_color="#FFFFFF")
        lbl_foot.pack(anchor="center", pady=(0, 2))

        self.body_full = ctk.CTkFrame(self, fg_color="transparent")

        self.card_top = ctk.CTkFrame(self.body_full, corner_radius=10, border_width=1)
        self.card_top.pack(fill="x", pady=(0, 2))

        self.lbl_folder = ctk.CTkLabel(self.card_top, font=FONT_SECTION_LBL)
        self.lbl_folder.pack(anchor="w", padx=8, pady=(2, 1))

        f_dir = ctk.CTkFrame(self.card_top, fg_color="transparent")
        f_dir.pack(fill="x", padx=8, pady=1)

        self.e_path = ctk.CTkEntry(f_dir, font=FONT_ENTRY, height=27, text_color="#FFFFFF")
        self.e_path.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.e_path.bind("<FocusOut>", lambda e: self.validate_path_live())
        attach_context_menu(self.e_path)

        self.btn_browse = ctk.CTkButton(
            f_dir, width=70, height=27, font=FONT_BTN_SUB, text_color="#FFFFFF",
            fg_color="#0284C7", hover_color="#0369A1", border_width=1, border_color="#38BDF8",
            command=self.browse_folder
        )
        self.btn_browse.pack(side="left", padx=(0, 3))

        self.btn_open_f = ctk.CTkButton(
            f_dir, width=60, height=27, font=FONT_BTN_SUB, text_color="#FFFFFF",
            fg_color="#0F766E", hover_color="#115E59", border_width=1, border_color="#2DD4BF",
            command=self.open_current_folder
        )
        self.btn_open_f.pack(side="left")

        self.lbl_d = ctk.CTkLabel(self.card_top, font=FONT_SECTION_LBL)
        self.lbl_d.pack(anchor="w", padx=8, pady=(1, 1))

        f_date = ctk.CTkFrame(self.card_top, fg_color="transparent")
        f_date.pack(fill="x", padx=8, pady=(1, 3))

        today = datetime.date.today()
        self.cb_d = ctk.CTkComboBox(f_date, values=[f"{d:02d}" for d in range(1, 32)], width=52, height=25, font=FONT_REGULAR_BOLD)
        self.cb_d.set(f"{today.day:02d}")
        self.cb_d.pack(side="left", padx=(0, 2))

        self.cb_m = ctk.CTkComboBox(f_date, values=[f"{m:02d}" for m in range(1, 13)], width=52, height=25, font=FONT_REGULAR_BOLD)
        self.cb_m.set(f"{today.month:02d}")
        self.cb_m.pack(side="left", padx=(0, 2))

        self.cb_y = ctk.CTkComboBox(f_date, values=[str(y) for y in range(today.year - 3, today.year + 3)], width=66, height=25, font=FONT_REGULAR_BOLD)
        self.cb_y.set(str(today.year))
        self.cb_y.pack(side="left", padx=(0, 4))

        self.btn_today = ctk.CTkButton(f_date, width=52, height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.set_today)
        self.btn_today.pack(side="left", padx=(0, 2))

        self.btn_yesterday = ctk.CTkButton(f_date, width=62, height=25, font=FONT_BTN_SUB, text_color="#FFFFFF",
                                           fg_color="#334155", hover_color="#475569", command=self.set_yesterday)
        self.btn_yesterday.pack(side="left", padx=(0, 6))

        f_switches = ctk.CTkFrame(f_date, fg_color="transparent")
        f_switches.pack(side="right")

        self.sw_autosync = ctk.CTkSwitch(f_switches, text="", width=36, height=20, command=self.toggle_autosync)
        self.sw_autosync.pack(side="left", padx=(0, 2))
        self.lbl_sw_sync = ctk.CTkLabel(f_switches, text="", font=(FONT_FAMILY, 9, "bold"))
        self.lbl_sw_sync.pack(side="left", padx=(0, 8))

        self.sw_autoprint = ctk.CTkSwitch(f_switches, text="", width=36, height=20, command=self.toggle_autoprint)
        self.sw_autoprint.pack(side="left", padx=(0, 2))
        self.lbl_sw_print = ctk.CTkLabel(f_switches, text="", font=(FONT_FAMILY, 9, "bold"))
        self.lbl_sw_print.pack(side="left")

        self.sw_autosync.select()
        self.sw_autoprint.select()

        self.card_dash = ctk.CTkFrame(self.body_full, corner_radius=10, border_width=1)
        self.card_dash.pack(fill="x", pady=(0, 2))

        dash_grid = ctk.CTkFrame(self.card_dash, fg_color="transparent")
        dash_grid.pack(fill="x", padx=8, pady=3)

        f_kpi = ctk.CTkFrame(dash_grid, fg_color="transparent")
        f_kpi.pack(side="left", fill="both", expand=True)

        pill_c1 = ctk.CTkFrame(f_kpi, fg_color="#07121E", corner_radius=6, border_width=1, border_color="#1E2E42")
        pill_c1.pack(side="left", padx=(0, 4), fill="both", expand=True)
        self.lbl_kpi1_title = ctk.CTkLabel(pill_c1, font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_kpi1_title.pack(anchor="w", padx=6, pady=(1, 0))
        self.lbl_cnt = ctk.CTkLabel(pill_c1, text="0", font=FONT_KPI_VAL, text_color="#FFFFFF")
        self.lbl_cnt.pack(anchor="w", padx=6, pady=(0, 1))

        pill_c2 = ctk.CTkFrame(f_kpi, fg_color="#07121E", corner_radius=6, border_width=1, border_color="#1E2E42")
        pill_c2.pack(side="left", padx=(0, 4), fill="both", expand=True)
        self.lbl_kpi2_title = ctk.CTkLabel(pill_c2, font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_kpi2_title.pack(anchor="w", padx=6, pady=(1, 0))
        self.lbl_sum = ctk.CTkLabel(pill_c2, text="0.00 EGP", font=FONT_KPI_VAL, text_color="#00FF66")
        self.lbl_sum.pack(anchor="w", padx=6, pady=(0, 1))

        f_pos = ctk.CTkFrame(dash_grid, fg_color="transparent")
        f_pos.pack(side="right", fill="both")

        self.lbl_pos_title = ctk.CTkLabel(f_pos, font=FONT_SECTION_LBL)
        self.lbl_pos_title.pack(anchor="w", pady=(0, 1))

        f_pos_in = ctk.CTkFrame(f_pos, fg_color="transparent")
        f_pos_in.pack(fill="x")

        vcmd = (self.register(self.validate_numeric_input), '%P')
        self.e_pos = ctk.CTkEntry(f_pos_in, placeholder_text="POS / Cash Total", width=105, height=25,
                                  justify="center", font=FONT_ENTRY, text_color="#FFFFFF",
                                  validate="key", validatecommand=vcmd)
        self.e_pos.pack(side="left", padx=(0, 3))
        self.e_pos.bind("<Return>", lambda e: self.check_pos())
        attach_context_menu(self.e_pos)

        self.btn_pos_check = ctk.CTkButton(f_pos_in, width=50, height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.check_pos)
        self.btn_pos_check.pack(side="left")

        self.lbl_diff = ctk.CTkLabel(f_pos, text="", font=(FONT_FAMILY, 10, "bold"))
        self.lbl_diff.pack(anchor="w", pady=(1, 0))

        self.card_actions = ctk.CTkFrame(self.body_full, corner_radius=10, border_width=1)
        self.card_actions.pack(fill="x", pady=(0, 2))

        self.btn_run = ctk.CTkButton(self.card_actions, font=FONT_BTN_MAIN, height=30, text_color="#FFFFFF", command=self.start_thread)
        self.btn_run.pack(fill="x", padx=10, pady=(4, 2))

        f_prog = ctk.CTkFrame(self.card_actions, fg_color="transparent")
        f_prog.pack(fill="x", padx=10, pady=(0, 2))

        self.progress_bar = ctk.CTkProgressBar(f_prog, orientation="horizontal", height=6, progress_color="#00FF66", fg_color="#064E3B")
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.lbl_progress_pct = ctk.CTkLabel(f_prog, text="0%", font=(FONT_FAMILY, 10, "bold"), text_color="#FFFFFF", width=34)
        self.lbl_progress_pct.pack(side="right")

        self.lbl_current_file = ctk.CTkLabel(self.card_actions, text="", font=(FONT_FAMILY, 10), text_color="#8FA3B8")
        self.lbl_current_file.pack(anchor="w", padx=12, pady=(0, 2))

        f_act = ctk.CTkFrame(self.card_actions, fg_color="transparent")
        f_act.pack(fill="x", padx=10, pady=(0, 4))

        self.btn_manual = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#0F766E", hover_color="#115E59", height=27, width=72, command=self.open_manual)
        self.btn_manual.pack(side="left", fill="x", expand=True, padx=(0, 1))

        self.btn_summary_reopen = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#7C3AED", hover_color="#6D28D9", height=27, width=72, command=self.reopen_summary_modal)
        self.btn_summary_reopen.pack(side="left", fill="x", expand=True, padx=(1, 1))

        self.btn_cash = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#0D9488", hover_color="#0F766E", height=27, width=60, command=self.open_cash_counter)
        self.btn_cash.pack(side="left", fill="x", expand=True, padx=(1, 1))

        self.btn_archive_downloads = ctk.CTkButton(f_act, font=FONT_BTN_SUB, fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF", height=27, width=68, command=self.open_downloads_archiver_dialog)
        self.btn_archive_downloads.pack(side="left", fill="x", expand=True, padx=(1, 1))

        self.btn_reset = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#EF4444", fg_color="transparent",
                                       hover_color="#1E1E24", border_width=1.5, border_color="#EF4444", height=27, width=52,
                                       command=self.confirm_and_reset)
        self.btn_reset.pack(side="right", fill="x", expand=True, padx=(1, 0))

    def on_theme_select(self, selected_theme):
        self.current_theme_name = selected_theme
        self.apply_theme(selected_theme)

    def apply_theme(self, name):
        t = THEMES[name]
        ctk.set_appearance_mode(t["mode"])
        self.configure(fg_color=t["bg"])
        self.header.configure(fg_color=t["sub_card"])
        self.lbl_logo.configure(text_color=t["accent"])
        self.card_top.configure(fg_color=t["card"], border_color=t["border"])
        self.card_dash.configure(fg_color=t["card"], border_color=t["border"])
        self.card_actions.configure(fg_color=t["card"], border_color=t["border"])
        self.card_mini_status.configure(fg_color=t["card"], border_color=t["border"])
        self.b_bar.configure(fg_color=t["sub_card"])

        self.lbl_folder.configure(text_color=t["accent"])
        self.lbl_d.configure(text_color=t["accent"])
        self.lbl_kpi1_title.configure(text_color=t["accent"])
        self.lbl_kpi2_title.configure(text_color=t["accent"])
        self.lbl_pos_title.configure(text_color=t["accent"])
        self.lbl_sum.configure(text_color="#00FF66")
        self.btn_run.configure(fg_color=t["primary"], hover_color=t["primary_hover"])
        self.btn_pos_check.configure(fg_color=t["primary"], hover_color=t["primary_hover"])
        self._apply_button_roles(t)

        self.update_toggle_appearance()

    def _apply_button_roles(self, t):
        """تلوين كل الأزرار بحسب دورها من الثيم الحالي (تغيير الثيم بيغيّرها كلها)."""
        for role, attrs in BUTTON_ROLES.items():
            col, hov = t.get(role), t.get(role + "_hover")
            if not col:
                continue
            for a in attrs:
                b = getattr(self, a, None)
                if b is None:
                    continue
                try:
                    b.configure(fg_color=col, hover_color=hov)
                except Exception as e:
                    log_exception("apply_button_role:" + a, e)
        for a in ("btn_browse", "btn_view_rec"):   # الحد المضيء حوالين الزرين دول
            b = getattr(self, a, None)
            if b is not None:
                try: b.configure(border_color=t["accent"])
                except Exception as e: log_exception("apply_button_border:" + a, e)

    def update_toggle_appearance(self):
        t = THEMES[self.current_theme_name]
        if self.auto_sync_enabled:
            self.sw_autosync.configure(progress_color=t["success"], button_color="#FFFFFF")
            self.lbl_sw_sync.configure(text=tr("autosync_on"), text_color="#FFFFFF")
        else:
            self.sw_autosync.configure(fg_color=t["border"], button_color=t["text_muted"])
            self.lbl_sw_sync.configure(text=tr("autosync_off"), text_color=t["text_muted"])

        if self.auto_print_enabled:
            self.sw_autoprint.configure(progress_color=t["success"], button_color="#FFFFFF")
            self.lbl_sw_print.configure(text=tr("autoprint_on"), text_color="#FFFFFF")
        else:
            self.sw_autoprint.configure(fg_color=t["border"], button_color=t["text_muted"])
            self.lbl_sw_print.configure(text=tr("autoprint_off"), text_color=t["text_muted"])

    def toggle_autosync(self):
        self.auto_sync_enabled = bool(self.sw_autosync.get())
        self.update_toggle_appearance()

    def toggle_autoprint(self):
        self.auto_print_enabled = bool(self.sw_autoprint.get())
        self.update_toggle_appearance()
        if self.auto_print_enabled:
            p = self.get_clean_path()
            if os.path.exists(p):
                for f in glob.glob(os.path.join(p, "*.pdf")):
                    fn = os.path.basename(f)
                    self.printed_receipts_set.add(fn)
                    self.printed_receipts_set.add(clean_download_filename(fn))

    def toggle_language(self):
        global CURRENT_LANG
        self.current_lang = "ar" if self.current_lang == "en" else "en"
        CURRENT_LANG = self.current_lang
        self.apply_language(self.current_lang)

    def apply_language(self, lang):
        L = LANGUAGES[lang]
        self.btn_lang.configure(text=L["toggle_btn"])
        self.lbl_folder.configure(text=L["dir_path"])
        self.btn_browse.configure(text=L["browse"])
        self.btn_open_f.configure(text=L["open"])
        self.lbl_d.configure(text=L["date_lbl"])
        self.btn_today.configure(text=L["today"])
        self.btn_yesterday.configure(text=L["yesterday"])
        self.btn_run.configure(text=L["start"])
        self.btn_manual.configure(text=L["manual"])
        self.btn_summary_reopen.configure(text=L["summary_btn"])
        self.btn_cash.configure(text=L["cash_btn"])
        self.btn_archive_downloads.configure(text=L["clean_downloads"])
        self.btn_mini_archive.configure(text=L["clean_downloads"])
        self.btn_reset.configure(text=L["reset"])
        self.lbl_kpi1_title.configure(text=L["kpi1"])
        self.lbl_kpi2_title.configure(text=L["kpi2"])
        self.lbl_pos_title.configure(text=L["pos_box_title"])
        self.btn_pos_check.configure(text=L["pos_check_btn"])
        self.btn_view_rec.configure(text=L["view_records"])
        self.btn_pdf_export.configure(text=L["export_pdf"])
        self.btn_print_slip.configure(text=L["print_slip"])
        self.btn_excel.configure(text=L["open_excel"])
        self.btn_arch_hist.configure(text=L["arch_hist_btn"])
        self.btn_pos_close.configure(text=L["pos_close_btn"])
        self.btn_pos_pay.configure(text=L["pos_pay_btn"])
        self.btn_chrome.configure(text=L["open_chrome"])
        self.btn_elevate.configure(text=L["btn_full_console"])
        if POS_TOOLS_AVAILABLE:
            try:
                refresh_pos_tools_button(self)
            except Exception as _e:
                _log_silent("apply_language#1", _e)
        self.btn_back_to_mini.configure(text=L["btn_back_mini"])
        self.lbl_mini_title.configure(text=L["mini_station_title"])
        self.lbl_mini_desc.configure(text=L["mini_status_active"])
        self.lbl_mini_counter.configure(text=tr("mini_printed_count", count=self.printed_count_today))
        self.btn_fix_printer.configure(text=L["btn_fix_printer"])
        self.update_toggle_appearance()
        if self.last_detailed_records:
            annotate_records(self.last_detailed_records)

    def confirm_and_reset(self):
        if messagebox.askyesno(tr("confirm_reset"), tr("confirm_reset")):
            self.reset_all()

    def clear_results(self):
        self.progress_bar.set(0)
        self.lbl_progress_pct.configure(text="0%")
        self.lbl_current_file.configure(text="")
        self.lbl_cnt.configure(text="0")
        self.lbl_sum.configure(text=f"0.00 {tr('currency')}")
        self.lbl_diff.configure(text="")
        self.system_total_sum = 0.0
        self.last_generated_file = None
        self.last_detailed_records = []
        self.last_units_summary = {}
        self.last_summary_info = {}

    def reset_all(self):
        self.set_path_with_icon(DEFAULT_RECEIPTS_DIR)
        self.set_today()
        self.clear_results()
        self.e_pos.delete(0, 'end')

    def set_today(self):
        t = datetime.date.today()
        self.cb_d.set(f"{t.day:02d}")
        self.cb_m.set(f"{t.month:02d}")
        self.cb_y.set(str(t.year))

    def set_yesterday(self):
        y = datetime.date.today() - datetime.timedelta(days=1)
        self.cb_d.set(f"{y.day:02d}")
        self.cb_m.set(f"{y.month:02d}")
        self.cb_y.set(str(y.year))

    def browse_folder(self):
        f = filedialog.askdirectory(initialdir=self.get_clean_path())
        if f:
            self.set_path_with_icon(f)

    def open_current_folder(self):
        p = self.get_clean_path()
        if os.path.exists(p): os.startfile(p)

    def check_pos(self):
        raw = self.e_pos.get().strip().replace(",", "")
        if not raw or not self.last_detailed_records:
            self.lbl_diff.configure(text="")
            return
        try:
            val = float(raw)
            diff = round(val - self.system_total_sum, 2)
            t = THEMES[self.current_theme_name]
            if abs(diff) < 0.01:
                self.lbl_diff.configure(text=tr("pos_matched"), text_color=t["success"])
                play_sound_matched()
            elif diff < 0:
                self.lbl_diff.configure(text=f"{tr('pos_shortage')} -{abs(diff):,.2f}", text_color=t["danger"])
                play_sound_diff()
            else:
                self.lbl_diff.configure(text=f"{tr('pos_excess')} +{diff:,.2f}", text_color=t["warning"])
                play_sound_diff()
        except Exception:
            self.lbl_diff.configure(text="⚠️ Error", text_color="#EF4444")

    def open_chrome_browser(self):
        target_url = "http://192.168.235.50/traffic"
        chrome_candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in chrome_candidates:
            if os.path.exists(path):
                subprocess.Popen([path, target_url])
                return
        webbrowser.open(target_url)

    def init_watchdogs(self):
        def _routine():
            # استبعاد وتسكين الملفات الموجودة قبل تشغيل البرنامج
            initial_path = self._watch_path
            last_seeded = None   # آخر مجلد اتعلّمت ملفاته "اتطبعت"
            if initial_path and os.path.exists(initial_path):
                try:
                    for f in glob.glob(os.path.join(initial_path, "*.pdf")):
                        fn = os.path.basename(f)
                        self.printed_receipts_set.add(fn)
                        self.printed_receipts_set.add(clean_download_filename(fn))
                    last_seeded = initial_path
                except Exception as e:
                    log_exception("init_watchdogs_seed", e)

            _last_sync = [0.0]
            while True:
                time.sleep(0.5 if self.auto_print_enabled else 2)
                try:
                    p = self._watch_path
                    if not p or not os.path.exists(p): continue
                    if p != last_seeded:
                        # مجلد جديد اتختار: الملفات اللي فيه دلوقتي قديمة، مش بتتطبع تلقائيًا.
                        # الطباعة التلقائية بتشتغل بس على الملفات اللي تظهر بعد كده.
                        for f in glob.glob(os.path.join(p, "*.pdf")):
                            fn = os.path.basename(f)
                            self.printed_receipts_set.add(fn)
                            self.printed_receipts_set.add(clean_download_filename(fn))
                        last_seeded = p
                        continue
                    if not (self.auto_print_enabled or self.auto_sync_enabled): continue

                    pdf_files = glob.glob(os.path.join(p, "*.pdf"))

                    if self.auto_print_enabled:
                        for pdf_file in pdf_files:
                            fname = os.path.basename(pdf_file)
                            if fname.endswith("_cropped.pdf") or fname.endswith("_Summary.pdf"):
                                continue
                            if not (fname.lower().startswith("quote_receipt_") or MANUAL_NAME_RE.match(fname)):
                                continue

                            if fname.lstrip("_") in _VOID_KEYS:
                                continue
                            clean_fn = clean_download_filename(fname)
                            if clean_fn not in self.printed_receipts_set and fname not in self.printed_receipts_set:
                                cr_file = pdf_file + ".crdownload"
                                if not os.path.exists(cr_file):
                                    try:
                                        if os.path.getsize(pdf_file) > 1000:
                                            self.printed_receipts_set.add(fname)
                                            self.printed_receipts_set.add(clean_fn)
                                            self._print_queue.put(pdf_file)   # الطباعة في thread مستقل، المراقبة تكمل فورًا
                                    except Exception as _e: _log_silent("_routine#1", _e)

                    if (self.auto_sync_enabled and not self.is_processing and not self.is_mini_mode
                            and time.time() - _last_sync[0] >= 2):
                        _last_sync[0] = time.time()
                        try:
                            valid_pdfs = [f for f in pdf_files if not f.endswith("_Summary.pdf") and not f.endswith("_cropped.pdf")]
                            current_sig = f"{len(valid_pdfs)}_{sum(os.path.getsize(f) for f in valid_pdfs if os.path.exists(f))}"
                            if self.last_pdf_state_sig == "":
                                self.last_pdf_state_sig = current_sig
                            elif current_sig != self.last_pdf_state_sig:
                                self.last_pdf_state_sig = current_sig
                                self.run_on_main(self.start_thread)
                        except Exception as _e: _log_silent("_routine#2", _e)
                except Exception as e:
                    log_exception("watchdog_loop", e)

        def _print_worker():
            while True:
                pdf = self._print_queue.get()
                fname = os.path.basename(pdf)
                try: ok = self.send_to_thermal_printer_57x90(pdf)
                except Exception as e:
                    log_exception(f"print_worker:{fname}", e)
                    ok = False
                if ok:
                    self.printed_count_today += 1
                    self.run_on_main(lambda: self.lbl_mini_counter.configure(
                        text=tr("mini_printed_count", count=self.printed_count_today)))
                else:
                    # مفيش إعادة طباعة تلقائية (ممكن تطلّع إيصال مكرر للعميل): بنبلّغ المستخدم وهو يعيد الطباعة
                    self.run_on_main(lambda fn=fname: self._tray_notify(
                        T2(f"تعذرت طباعة الإيصال: {fn}", f"Printing failed: {fn}"), "A2R Console"))

        self._print_queue = queue.Queue()
        threading.Thread(target=_print_worker, daemon=True).start()
        threading.Thread(target=_routine, daemon=True).start()

    def send_to_thermal_printer_57x90(self, pdf_file_path):
        """يطبع إيصال على 57x90. بيرجّع True لو الطباعة اتبعتت، False لو فشلت أو الطابعة معلّقة."""
        temp_copy = None
        scaled_copy = None
        ok = False
        with _PRINT_LOCK:
            try:
                sumatra_path = os.path.join(BASE_DIR, "SumatraPDF.exe")
                if not os.path.exists(sumatra_path):
                    sumatra_path = os.path.join(BUNDLE_DIR, "SumatraPDF.exe")

                target = pdf_file_path
                clean_name = os.path.basename(pdf_file_path).lstrip("_")
                if clean_name.lower().startswith("quote_receipt_"):
                    temp_copy = make_print_copy(pdf_file_path)
                    if temp_copy:
                        target = temp_copy

                scaled_copy = scale_pdf_to_print_width(target)
                if scaled_copy:
                    target = scaled_copy

                if os.path.exists(sumatra_path):
                    cmd = [
                        sumatra_path,
                        "-print-to-default",
                        "-print-settings", "paper=57 x 90 mm,shrink",
                        "-silent",
                        target
                    ]
                    r = subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0, timeout=90)
                    ok = (r.returncode == 0)
                    if not ok:
                        log_exception(f"auto_print_rc:{os.path.basename(pdf_file_path)}", f"SumatraPDF exit code {r.returncode}")
                else:
                    if sys.platform == "win32":
                        os.startfile(target, "print")
                        ok = True
            except Exception as e:
                log_exception(f"auto_print:{os.path.basename(pdf_file_path)}", e)
        # مسح الملفات المؤقتة في الخلفية: قبل كده كانت بتستنى ثانية كاملة وتعطّل الإيصال اللي بعده
        tmp_files = [x for x in (temp_copy, scaled_copy) if x]
        if tmp_files:
            def _cleanup(files=tmp_files):
                for _tmp in files:
                    try: os.remove(_tmp)
                    except Exception as _e: _log_silent("send_to_thermal_printer_57x90#1", _e)
            _t = threading.Timer(5.0, _cleanup)
            _t.daemon = True
            _t.start()
        return ok

    def open_downloads_archiver_dialog(self):
        try:
            t = THEMES[self.current_theme_name]
            win = ctk.CTkToplevel(self)
            win.title(f"{tr('clean_downloads')} - A2R {APP_VERSION}")
            win.resizable(False, False)
            center_window_relative(win, self, 470, 480)
            win.configure(fg_color=t["bg"])

            ctk.CTkLabel(win, text=tr("arch_title"), font=(FONT_FAMILY, 13, "bold"), text_color=t["accent"]).pack(pady=(10, 2))
            ctk.CTkLabel(win, text=tr("arch_subtitle"), font=(FONT_FAMILY, 9), text_color=t["success"]).pack(pady=(0, 6))

            f_src = ctk.CTkFrame(win, fg_color="transparent")
            f_src.pack(fill="x", padx=16, pady=(0, 4))
            ctk.CTkLabel(f_src, text=tr("arch_dir_lbl"), font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(anchor="w", padx=2, pady=(0, 1))
            
            f_in = ctk.CTkFrame(f_src, fg_color="transparent")
            f_in.pack(fill="x")

            e_arch_dir = ctk.CTkEntry(f_in, font=FONT_ENTRY, height=27, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
            default_dir = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
            e_arch_dir.insert(0, default_dir)
            e_arch_dir.pack(side="left", fill="x", expand=True, padx=(0, 4))
            attach_context_menu(e_arch_dir)

            def _browse_arch():
                d = filedialog.askdirectory(initialdir=e_arch_dir.get().strip(), parent=win)
                if d:
                    e_arch_dir.delete(0, 'end')
                    e_arch_dir.insert(0, d)

            btn_browse_arch = ctk.CTkButton(f_in, text=tr("arch_btn_browse"), width=60, height=27, font=FONT_BTN_SUB,
                                            fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF", command=_browse_arch)
            btn_browse_arch.pack(side="left")

            f_supervisor = ctk.CTkFrame(win, fg_color=t["card"], corner_radius=8, border_width=1, border_color=t["accent"])
            f_supervisor.pack(fill="x", padx=16, pady=(6, 4))

            ctk.CTkLabel(f_supervisor, text=tr("arch_open_day_title"), font=(FONT_FAMILY, 10, "bold"), text_color=t["accent"]).pack(anchor="w", padx=10, pady=(6, 2))

            f_pick_date = ctk.CTkFrame(f_supervisor, fg_color="transparent")
            f_pick_date.pack(fill="x", padx=10, pady=(0, 6))

            today_now = datetime.date.today()
            cb_arch_d = ctk.CTkComboBox(f_pick_date, values=[f"{d:02d}" for d in range(1, 32)], width=50, height=25, font=FONT_REGULAR_BOLD)
            cb_arch_d.set(f"{today_now.day:02d}")
            cb_arch_d.pack(side="left", padx=(0, 2))

            cb_arch_m = ctk.CTkComboBox(f_pick_date, values=[f"{m:02d}" for m in range(1, 13)], width=50, height=25, font=FONT_REGULAR_BOLD)
            cb_arch_m.set(f"{today_now.month:02d}")
            cb_arch_m.pack(side="left", padx=(0, 2))

            cb_arch_y = ctk.CTkComboBox(f_pick_date, values=[str(y) for y in range(today_now.year - 3, today_now.year + 3)], width=64, height=25, font=FONT_REGULAR_BOLD)
            cb_arch_y.set(str(today_now.year))
            cb_arch_y.pack(side="left", padx=(0, 6))

            def _find_day_archive_folder(base_folder, target_dt):
                candidates_root = []
                bname = os.path.basename(os.path.normpath(base_folder)).lower()
                if bname == ARCHIVE_DIRNAME.lower():
                    candidates_root.append(base_folder)
                    candidates_root.append(os.path.dirname(base_folder))
                else:
                    candidates_root.append(os.path.join(base_folder, ARCHIVE_DIRNAME))
                    candidates_root.append(base_folder)

                y_str = str(target_dt.year)
                d_str = f"{target_dt.day:02d}"
                m_prefix = f"{target_dt.month:02d}"

                for root in candidates_root:
                    if not os.path.exists(root) or not os.path.isdir(root):
                        continue
                    y_dir = os.path.join(root, y_str)
                    if not os.path.isdir(y_dir):
                        continue
                    try:
                        for m_entry in os.listdir(y_dir):
                            if m_entry.startswith(m_prefix) and os.path.isdir(os.path.join(y_dir, m_entry)):
                                day_dir = os.path.join(y_dir, m_entry, d_str)
                                if os.path.isdir(day_dir):
                                    return day_dir
                    except Exception as _e:
                        _log_silent("_find_day_archive_folder#1", _e)
                return None

            def _open_selected_day_summary():
                try:
                    s_d = int(cb_arch_d.get())
                    s_m = int(cb_arch_m.get())
                    s_y = int(cb_arch_y.get())
                    target_dt = datetime.date(s_y, s_m, s_d)
                except Exception:
                    messagebox.showerror("Error", tr("invalid_date"), parent=win)
                    return

                src_folder = e_arch_dir.get().strip()
                day_folder = _find_day_archive_folder(src_folder, target_dt)
                date_tag = target_dt.strftime("%d-%m-%Y")

                if day_folder and os.path.isdir(day_folder):
                    summary_candidates = glob.glob(os.path.join(day_folder, "*Samary*.pdf")) + \
                                         glob.glob(os.path.join(day_folder, "*Summary*.pdf"))
                    if summary_candidates:
                        os.startfile(summary_candidates[0])
                        return

                    manual_map = load_manual_map()
                    load_void_map()
                    recs = []
                    for f in glob.glob(os.path.join(day_folder, "*.pdf")):
                        if f.endswith("_cropped.pdf") or "samary" in os.path.basename(f).lower() or "summary" in os.path.basename(f).lower():
                            continue
                        r = read_pdf_record(f, manual_map)
                        if r:
                            recs.append(refresh_void_flag(r))
                    
                    if recs:
                        self._generate_day_summary_pdf(day_folder, date_tag, recs)
                        new_summary = os.path.join(day_folder, f"Samary_{date_tag}.pdf")
                        if os.path.exists(new_summary):
                            os.startfile(new_summary)
                            return

                messagebox.showinfo("Not Found", f"No summary report or archived receipts found for: {date_tag}", parent=win)

            btn_open_samary = ctk.CTkButton(f_pick_date, text=tr("arch_btn_open_day"), font=FONT_BTN_SUB, fg_color="#0F766E",
                                            hover_color="#115E59", text_color="#FFFFFF", width=120, height=26, command=_open_selected_day_summary)
            btn_open_samary.pack(side="left")

            f_prog = ctk.CTkFrame(win, fg_color="transparent")
            f_prog.pack(fill="x", padx=16, pady=(4, 4))
            f_prog.grid_columnconfigure(0, weight=1)

            archive_prog_bar = ctk.CTkProgressBar(f_prog, orientation="horizontal", height=8, progress_color=t["success"])
            archive_prog_bar.set(0)
            archive_prog_bar.grid(row=0, column=0, sticky="ew", padx=(0, 6))

            archive_prog_lbl = ctk.CTkLabel(f_prog, text="0%", font=(FONT_FAMILY, 10, "bold"), width=36, text_color=t["text"])
            archive_prog_lbl.grid(row=0, column=1)

            archive_status_lbl = ctk.CTkLabel(win, text=tr("arch_ready"), font=(FONT_FAMILY, 9), text_color=t["text_muted"])
            archive_status_lbl.pack(pady=(0, 4))

            def _execute(archive_all=False):
                target_folder = e_arch_dir.get().strip()
                if not os.path.exists(target_folder) or not os.path.isdir(target_folder):
                    messagebox.showerror("Error", tr("dir_missing"), parent=win)
                    return
                btn_prev.configure(state="disabled")
                btn_all.configure(state="disabled")
                btn_open_folder.configure(state="disabled")
                btn_browse_arch.configure(state="disabled")
                btn_open_samary.configure(state="disabled")
                threading.Thread(target=self._process_archive_worker, args=(archive_all, win, archive_prog_bar, archive_prog_lbl, archive_status_lbl, target_folder), daemon=True).start()

            btn_prev = ctk.CTkButton(win, text=tr("arch_btn_prev"), font=FONT_BTN_SUB,
                                     fg_color="#0F766E", hover_color="#115E59", height=28, text_color="#FFFFFF", command=lambda: _execute(False))
            btn_prev.pack(fill="x", padx=16, pady=2)

            btn_all = ctk.CTkButton(win, text=tr("arch_btn_all"), font=FONT_BTN_SUB,
                                    fg_color="#312E81", hover_color="#3730A3", height=28, text_color="#FFFFFF", command=lambda: _execute(True))
            btn_all.pack(fill="x", padx=16, pady=2)

            def _open_selected_archive():
                root = ensure_archive_root(e_arch_dir.get().strip())
                if os.path.exists(root): os.startfile(root)

            btn_open_folder = ctk.CTkButton(win, text=tr("arch_btn_open_folder"), font=FONT_BTN_SUB,
                                            fg_color="#1E293B", hover_color="#334155", border_width=1, border_color=t["border"], height=28,
                                            text_color=t["text"], command=_open_selected_archive)
            btn_open_folder.pack(fill="x", padx=16, pady=(3, 8))
        except Exception as e: log_exception("open_archive_dialog", e)

    def open_archive_directory(self):
        p = self.get_clean_path()
        archive_root = ensure_archive_root(p)
        if os.path.exists(archive_root): os.startfile(archive_root)

    def _generate_day_summary_pdf(self, day_folder_path, date_str, records_list):
        if not REPORTLAB_AVAILABLE or not records_list: return
        pdf_path = os.path.join(day_folder_path, f"Samary_{date_str}.pdf")
        try:
            total_sum, total_cnt = counted_totals(records_list)
            pdf_cnt = sum(1 for r in records_list if not r.get('is_manual') and not r.get('is_void'))
            manual_cnt = sum(1 for r in records_list if r.get('is_manual') and not r.get('is_void'))
            void_cnt = sum(1 for r in records_list if r.get('is_void'))
            units_set = set(r['unit'] for r in records_list if not r.get('is_void'))
            unit_name = " + ".join(units_set) if units_set else "وحدة غير محددة"

            PAGE_W, PAGE_H = 226, 480
            c = canvas.Canvas(pdf_path, pagesize=(PAGE_W, PAGE_H))
            font_name = "Helvetica-Bold"

            for f_cand in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]:
                if os.path.exists(f_cand):
                    try:
                        pdfmetrics.registerFont(TTFont("ReceiptArabic", f_cand))
                        font_name = "ReceiptArabic"
                        break
                    except Exception as _e: _log_silent("_generate_day_summary_pdf#1", _e)

            def _ar(txt):
                try: return get_display(arabic_reshaper.reshape(str(txt)))
                except Exception: return str(txt)

            c.setStrokeColorRGB(0.15, 0.35, 0.55)
            c.setLineWidth(1.5)
            c.rect(6, 6, PAGE_W - 12, PAGE_H - 12)

            c.setFont(font_name, 14)
            c.setFillColorRGB(0.05, 0.25, 0.55)
            c.drawCentredString(PAGE_W / 2, PAGE_H - 32, _ar("ملخص الفحص المؤرشف"))
            c.setFont("Helvetica-Bold", 11)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.drawCentredString(PAGE_W / 2, PAGE_H - 50, f"Date: {date_str}")

            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.line(14, PAGE_H - 60, PAGE_W - 14, PAGE_H - 60)

            y = PAGE_H - 88
            rows = [
                ("وحدة المرور", unit_name),
                ("إجمالي العمليات", f"{total_cnt:,}"),
                ("إيصالات إلكترونية", f"{pdf_cnt:,}"),
                ("معاملات يدوية", f"{manual_cnt:,}"),
                ("معاملات ملغية", f"{void_cnt:,}"),
            ]

            for lbl, val in rows:
                c.setFillColorRGB(0.94, 0.96, 0.98)
                c.rect(12, y - 6, PAGE_W - 24, 24, fill=True, stroke=False)
                c.setFont(font_name, 9.5)
                c.setFillColorRGB(0.25, 0.25, 0.25)
                c.drawRightString(PAGE_W - 18, y + 2, _ar(lbl))
                c.setFont(font_name, 10.5)
                c.setFillColorRGB(0.0, 0.0, 0.0)
                c.drawString(18, y + 2, _ar(val))
                y -= 30

            c.setFillColorRGB(0.08, 0.48, 0.28)
            c.roundRect(12, y - 16, PAGE_W - 24, 42, 5, fill=True, stroke=False)
            c.setFont(font_name, 10)
            c.setFillColorRGB(1, 1, 1)
            c.drawRightString(PAGE_W - 20, y + 6, _ar("إجمالي المبالغ:"))
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(PAGE_W / 2, y - 8, f"{total_sum:,.2f} EGP")

            _su = summary_unit_load(_day_iso_from_label(date_str))
            if _su: _draw_summary_unit_block(c, font_name, _ar, PAGE_W, _su[0], _su[1])

            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.line(14, 42, PAGE_W - 14, 42)
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawCentredString(PAGE_W / 2, 26, f"Archived: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
            c.drawCentredString(PAGE_W / 2, 14, f"A2R Console {APP_VERSION} • {APP_OWNER}")
            c.save()
        except Exception as e:
            log_exception("generate_day_summary_pdf", e)

    def _process_archive_worker(self, archive_all, win, p_bar, p_lbl, s_lbl, folder_path, auto=False):
        def prog(i, n, fname):
            pct = int((i / n) * 100) if n else 100
            self.run_on_main(lambda p=pct, f=fname: [
                p_bar.set(p / 100.0), p_lbl.configure(text=f"{p}%"), s_lbl.configure(text=f"Processing: {f}")])

        moved_count = 0
        try:
            def stage(i, n, name):
                self.run_on_main(lambda i=i, n=n, nm=name: [
                    p_bar.set(i / max(1, n)), p_lbl.configure(text=f"{int(i / max(1, n) * 100)}%"),
                    s_lbl.configure(text=T2(f"جاري تحديث ملخص وإكسيل يوم {nm}  ({i}/{n})", f"Updating summary & Excel for day {nm}  ({i}/{n})"))])
            moved_count = self._run_archive_sweep(folder_path, prog, stage) or 0
            if auto: self._mark_archive_done_today()
            self._start_archive_maintenance(folder_path)
        except Exception as e:
            log_exception("archive_worker", e)

        def _complete():
            if auto:
                p_bar.set(1.0)
                p_lbl.configure(text="100%")
                s_lbl.configure(text=f"✓ Archive complete — {moved_count} file(s) archived.")
                try: win.after(1500, win.destroy)
                except Exception as _e: _log_silent("_complete#1", _e)
                return
            try: win.destroy()
            except Exception as _e: _log_silent("_complete#2", _e)
            play_sound_matched()
            messagebox.showinfo(tr("done"), f"Successfully archived {moved_count} files.\nSummary PDFs updated for all affected days.")

        self.run_on_main(_complete)

    def start_thread(self):
        L = LANGUAGES[self.current_lang]
        if not self.processing_lock.acquire(blocking=False): return

        try:
            target_date = datetime.date(int(self.cb_y.get()), int(self.cb_m.get()), int(self.cb_d.get()))
        except Exception:
            self.processing_lock.release()
            messagebox.showerror("Error", L["invalid_date"])
            return

        folder_path = self.get_clean_path()
        if not os.path.exists(folder_path):
            self.processing_lock.release()
            messagebox.showerror("Error", L["dir_missing"])
            return

        if not os.path.exists(PDFTOTEXT_EXE):
            self.processing_lock.release()
            messagebox.showerror("Error", f"{L['pdf_missing']}{BASE_DIR}")
            return

        if not OPENPYXL_AVAILABLE:
            self.processing_lock.release()
            messagebox.showerror("Error", "openpyxl is not installed.")
            return

        self.btn_run.configure(state="disabled")
        self.is_processing = True
        threading.Thread(target=self.process_files, args=(folder_path, target_date), daemon=True).start()

    def process_files(self, folder_path, target_date):
        date_for_filename = target_date.strftime("%d-%m-%Y")
        date_label = target_date.strftime("%d.%m.%Y")

        try:
            self.run_on_main(lambda: self.progress_bar.set(0))

            def _progress(i, total, fname):
                pct = int((i / total) * 100) if total else 100
                self.run_on_main(lambda i=i, t=total, f=fname, p=pct: [
                    self.progress_bar.set(i / max(1, t)),
                    self.lbl_progress_pct.configure(text=f"{p}%"),
                    self.lbl_current_file.configure(text=f"Reading: {f}")
                ])

            records = collect_records(folder_path, target_date, _progress)

            if not records:
                self.run_on_main(self.clear_results)
                if not self.auto_sync_enabled:
                    self.run_on_main(lambda: messagebox.showinfo("Done", f"No receipts found for: {date_label}"))
                return

            device_unit = annotate_records(records)
            info, units_summary = build_summary(records, device_unit, date_label)
            
            report_file_path = os.path.join(DOCUMENTS_DIR, f"Insurance_Report_{date_for_filename}.xlsx")
            out_file = write_report(records, report_file_path)

            self.last_generated_file = out_file
            self.system_total_sum = info["total_sum"]
            self.last_detailed_records = records
            self.last_units_summary = units_summary
            self.last_summary_info = info

            def _finish():
                self.progress_bar.set(1.0)
                self.lbl_progress_pct.configure(text="100%")
                last_f = records[-1]["file"] if records else "None"
                self.lbl_current_file.configure(text=f"Done · {last_f}")
                self.lbl_cnt.configure(text=f"{info['total_count']:,}")
                self.lbl_sum.configure(text=f"{info['total_sum']:,.2f} {tr('currency')}")
                self.check_pos()
                play_sound_matched()

            self.run_on_main(_finish)

        except Exception as ex:
            log_exception("process_critical", ex)
            err_msg = str(ex)
            self.run_on_main(lambda: messagebox.showerror("System Error", err_msg))
        finally:
            self.is_processing = False
            if self.processing_lock.locked(): self.processing_lock.release()
            self.run_on_main(lambda: self.btn_run.configure(state="normal"))

    def open_excel(self):
        if not self.is_supervisor:
            messagebox.showwarning("Restricted", tr("restricted_admin"))
            return
        if self.last_generated_file and os.path.exists(self.last_generated_file):
            os.startfile(self.last_generated_file)
        else:
            messagebox.showinfo("Notice", "Run extraction first!")

    def refresh_after_void_change(self):
        recs = self.last_detailed_records
        old = self.last_summary_info or {}
        device_unit = annotate_records(recs)
        info, units_summary = build_summary(recs, device_unit, old.get("date_label", ""))
        if old.get("unit"):
            info["unit"] = old["unit"]
        self.last_summary_info = info
        self.last_units_summary = units_summary
        self.system_total_sum = info["total_sum"]
        self.lbl_cnt.configure(text=f"{info['total_count']:,}")
        self.lbl_sum.configure(text=f"{info['total_sum']:,.2f} {tr('currency')}")
        self.check_pos()
        try:
            rp = self.last_generated_file
            if rp and os.path.exists(rp):
                with open(rp, "ab"):
                    pass
                write_report(recs, rp)
        except Exception as e:
            log_exception("regen_report_after_void", e)

    def void_selected_record(self, rec, on_done_callback=None):
        try:
            if rec.get("is_void"):
                messagebox.showinfo(tr("done"), tr("void_already"))
                return
            key = void_key(rec.get("file", "") or rec.get("path", ""))
            if not key:
                messagebox.showerror("Error", "Unable to detect receipt key!")
                return

            try:
                parent = (self.focus_get() or self).winfo_toplevel()
            except Exception:
                parent = self
            reason = simpledialog.askstring(tr("void_reason_title"), tr("void_reason_prompt"), parent=parent)
            if reason is None:
                return
            reason = reason.strip()

            add_void(key, rec["amount"], rec.get("plate", "-"), reason)
            rec["is_void"] = True
            rec["void_reason"] = reason

            self.refresh_after_void_change()
            if on_done_callback: on_done_callback()
            messagebox.showinfo(tr("done"), f"Transaction voided: {rec['amount']:.2f} EGP.")
        except Exception as e:
            log_exception("void_record", e)
            messagebox.showerror("Error", f"Void failed: {str(e)}")

    def unvoid_selected_record(self, rec, on_done_callback=None):
        try:
            if not rec.get("is_void"):
                messagebox.showinfo(tr("done"), tr("restore_already"))
                return
            old_path = rec.get("path", "")
            basename = os.path.basename(old_path)

            if basename.startswith("_"):
                if not old_path or not os.path.exists(old_path):
                    messagebox.showerror("Error", "File does not exist in folder!")
                    return
                new_path = os.path.join(os.path.dirname(old_path), basename.lstrip("_"))
                if os.path.exists(new_path):
                    messagebox.showerror("Error", "A file with original name already exists.")
                    return
                try:
                    os.rename(old_path, new_path)
                except OSError as ex:
                    messagebox.showerror("Error", f"Failed to rename file:\n{ex}")
                    return
                rec["path"], rec["file"] = new_path, os.path.basename(new_path)

            remove_void(void_key(rec.get("file", "") or old_path))
            rec["is_void"] = False
            rec["void_reason"] = ""

            self.refresh_after_void_change()
            if on_done_callback: on_done_callback()
            messagebox.showinfo(tr("done"), f"Transaction restored: {rec['amount']:.2f} EGP.")
        except Exception as e:
            log_exception("unvoid_record", e)
            messagebox.showerror("Error", f"Restore failed: {str(e)}")

    def _start_archive_maintenance(self, folder):
        """فهرسة + نسخ احتياطي مخفي في الخلفية (بدون تعطيل الواجهة)."""
        try:
            if folder and os.path.isdir(folder):
                threading.Thread(target=archive_maintenance, args=(folder,), daemon=True).start()
        except Exception as e:
            log_exception("start_archive_maintenance", e)

    def open_archive_history(self):
        """سجل الأرشيف (للمشرف): كل الأيام على الشمال، واختيار يوم بيعرض كل معاملاته على اليمين في نفس النافذة
        (إجمالي اليوم + عدد المعاملات + إكسيل اليوم + إيصال السمري). نافذة Records Viewer بقت لليوم الحالي بس."""
        if not getattr(self, "is_supervisor", False):
            messagebox.showwarning(T2("غير مسموح", "Not allowed"), T2("هذه الأداة للمشرف فقط.", "Supervisor only."))
            return
        folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", tr("dir_missing"))
            return

        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(T2("📚 سجل الأرشيف", "📚 Archive History"))
        win.resizable(True, True)
        set_window_icon_safe(win)
        _sw, _sh = win.winfo_screenwidth(), win.winfo_screenheight()
        center_window_relative(win, self, min(1320, _sw - 40), min(720, _sh - 110))
        win.minsize(min(1000, _sw - 40), 520)
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception as _e: _log_silent("open_archive_history#1", _e)

        ALL = T2("الكل", "All")
        st = {"stats": [], "debounce": None, "iso": None, "recs": [], "recs_iso": None,
              "load_id": 0, "cache": {}, "sel_job": None}

        # ---------- شريط الحالة والأدوات ----------
        bar = ctk.CTkFrame(win, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        bar.pack(fill="x", padx=14, pady=(12, 6))
        status_lbl = ctk.CTkLabel(bar, text="", font=(FONT_FAMILY, 10, "bold"), text_color=t["accent"])
        status_lbl.pack(side="left", padx=12, pady=8)

        def _set_status(txt):
            try:
                if win.winfo_exists(): status_lbl.configure(text=txt)
            except Exception as _e: _log_silent("_set_status#1", _e)

        def run_maintenance(manual=False):
            def prog(i, n):
                self.after(0, lambda: _set_status(T2(f"جاري فهرسة الأرشيف... {i}/{n}", f"Indexing archive... {i}/{n}")))
            def work():
                res = archive_maintenance(folder, prog)
                def fin():
                    if not win.winfo_exists(): return
                    if res is None:
                        _set_status(T2("عملية الفهرسة/النسخ شغالة بالفعل، استنى شوية.", "Maintenance already running."))
                    else:
                        _set_status(T2(f"تم ✓ — جديد: {res[0]} | منسوخ للنسخة الاحتياطية: {res[1]}",
                                       f"Done ✓ — new: {res[0]} | backed up: {res[1]}"))
                    st["cache"].clear()
                    load_days()
                self.after(0, fin)
            _set_status(T2("جاري الفحص...", "Scanning..."))
            threading.Thread(target=work, daemon=True).start()

        def open_backup_folder():
            if os.path.isdir(ARCHIVE_BACKUP_DIR): os.startfile(ARCHIVE_BACKUP_DIR)
            else: messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا توجد نسخة احتياطية بعد. اضغط (تحديث + نسخ).", "No backup yet. Press Refresh + Backup."), parent=win)

        bf = {"running": False}
        def backfill_all():
            if bf["running"]: return
            if not messagebox.askyesno(T2("إنشاء الإكسيل للأيام الناقصة", "Build missing day Excels"),
                                       T2("هيتعمل ملف إكسيل لكل يوم مؤرشف ملوش إكسيل (الأيام القديمة).\nممكن ياخد وقت حسب عدد الأيام. تكمّل؟",
                                          "An Excel file will be built for every archived day that has none (old days).\nThis may take a while. Continue?"), parent=win):
                return
            bf["running"] = True
            def prog(i, n):
                self.after(0, lambda: _set_status(T2(f"جاري إنشاء الإكسيل... {i}/{n}", f"Building Excel files... {i}/{n}")))
            def work():
                try: n = archive_backfill_excels(folder, prog)
                except Exception as e:
                    log_exception("archive_backfill_all", e)
                    n = -1
                def fin():
                    bf["running"] = False
                    if not win.winfo_exists(): return
                    if n < 0: _set_status(T2("حصل خطأ أثناء إنشاء الإكسيل.", "Error while building Excel files."))
                    else: _set_status(T2(f"تم ✓ — اتعمل إكسيل لـ {n} يوم", f"Done ✓ — built Excel for {n} day(s)"))
                self.after(0, fin)
            _set_status(T2("جاري الفحص...", "Scanning..."))
            threading.Thread(target=work, daemon=True).start()

        ctk.CTkButton(bar, text=T2("🛠️ إكسيل الأيام الناقصة", "🛠️ Build missing Excels"), font=FONT_BTN_SUB, width=170, height=30,
                      fg_color="#B45309", hover_color="#92400E", text_color="#FFFFFF",
                      command=backfill_all).pack(side="right", padx=4, pady=6)
        ctk.CTkButton(bar, text=T2("🔄 تحديث + نسخ احتياطي", "🔄 Refresh + Backup"), font=FONT_BTN_SUB, width=160, height=30,
                      fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF",
                      command=lambda: run_maintenance(True)).pack(side="right", padx=4, pady=6)
        ctk.CTkButton(bar, text=T2("🗄️ فتح النسخة الاحتياطية", "🗄️ Open Backup"), font=FONT_BTN_SUB, width=160, height=30,
                      fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF",
                      command=open_backup_folder).pack(side="right", padx=4, pady=6)

        # ---------- ستايل الجداول ----------
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception as _e: _log_silent("open_archive_history#2", _e)
        style.configure("A2R.Treeview", background=t["input"], foreground=t["text"],
                        fieldbackground=t["input"], font=(FONT_FAMILY, 10, "bold"), rowheight=28)
        style.configure("A2R.Treeview.Heading", background=t["card"], foreground=t["accent"],
                        font=(FONT_FAMILY, 11, "bold"), relief="flat")
        def _fixed(option):
            try: return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]
            except Exception: return []
        style.map("A2R.Treeview", background=[("selected", t["primary"])] + _fixed("background"),
                  foreground=[("selected", "#FFFFFF")] + _fixed("foreground"))

        def make_tree(parent, columns, headers, widths):
            fr = ctk.CTkFrame(parent, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
            fr.pack(fill="both", expand=True, padx=2, pady=(4, 2))
            tree = ttk.Treeview(fr, columns=columns, show="headings", style="A2R.Treeview")
            for c in columns:
                tree.heading(c, text=headers[c])
                tree.column(c, width=widths.get(c, 90), anchor="center")
            for kind, (bg, fg) in TAG_COLORS[t["mode"]].items():
                tree.tag_configure(kind, background=bg, foreground=fg)
            vsb = ttk.Scrollbar(fr, orient="vertical", command=tree.yview)
            vsb.pack(side="right", fill="y", padx=2, pady=2)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
            return tree

        tv = ctk.CTkTabview(win, fg_color=t["bg"])
        tv.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        TAB_DAYS = T2("📅 الأيام والمعاملات", "📅 Days & Transactions")
        TAB_SEARCH = T2("🔎 بحث عام في الأرشيف", "🔎 Global Search")
        tab_days = tv.add(TAB_DAYS)
        tab_search = tv.add(TAB_SEARCH)

        # ================= تبويب الأيام والمعاملات (شمال: الأيام | يمين: معاملات اليوم المختار) =================
        body = ctk.CTkFrame(tab_days, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(body, fg_color="transparent", width=400)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.pack_propagate(False)
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        # ---------- الشمال: قائمة كل الأيام ----------
        f1 = ctk.CTkFrame(left, fg_color="transparent")
        f1.pack(fill="x", pady=(2, 2))
        day_q = ctk.CTkEntry(f1, placeholder_text=T2("ابحث عن يوم (15-10-2026)", "Find a day (2026-10-15)"),
                             width=200, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        day_q.pack(side="left", padx=(0, 6))
        attach_context_menu(day_q)
        cb_month = ctk.CTkComboBox(f1, values=[ALL], width=110, font=FONT_ENTRY, fg_color=t["input"], border_color=t["border"],
                                   command=lambda v: apply_days())
        cb_month.set(ALL)
        cb_month.pack(side="left", padx=2)

        def clear_filters():
            day_q.delete(0, "end")
            cb_month.set(ALL)
            apply_days()
        ctk.CTkButton(f1, text="✖", width=34, height=28, font=FONT_BTN_SUB, fg_color="#64748B", hover_color="#475569",
                      text_color="#FFFFFF", command=clear_filters).pack(side="left", padx=4)

        day_cols = ("date", "ops", "total")
        day_hdr = {"date": T2("التاريخ", "Date"), "ops": T2("المعاملات", "Tx"), "total": T2("إجمالي المبلغ", "Total")}
        day_tree = make_tree(left, day_cols, day_hdr, {"date": 120, "ops": 80, "total": 150})
        sum_lbl = ctk.CTkLabel(left, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"], justify="left")
        sum_lbl.pack(anchor="w", padx=8, pady=(2, 0))
        ctk.CTkLabel(left, text=T2("🟥 يوم فيه مكرر    🟨 يوم فيه ناقص", "🟥 has duplicates   🟨 has incomplete"),
                     font=(FONT_FAMILY, 9, "bold"), text_color=t["text_muted"]).pack(anchor="w", padx=8, pady=(0, 2))

        sort_state = {"col": "date", "rev": True}
        def sort_days(col):
            sort_state["rev"] = (not sort_state["rev"]) if sort_state["col"] == col else (col != "date" and True)
            sort_state["col"] = col
            apply_days()
        for c in day_cols:
            day_tree.heading(c, command=lambda c=c: sort_days(c))

        def apply_days(*_):
            q = day_q.get().strip()
            mval = cb_month.get()
            items = []
            for s in st["stats"]:
                day = s["day"]
                if mval != ALL and not day.startswith(mval): continue
                if q:
                    y, m, d = day.split("-")
                    hay = f"{day} {d}-{m}-{y} {d}/{m}/{y}"
                    if q.replace("/", "-") not in hay.replace("/", "-"): continue
                items.append(s)
            key = sort_state["col"]
            items.sort(key=lambda s: s["day"] if key == "date" else s[key], reverse=sort_state["rev"])
            keep = st["iso"]
            day_tree.delete(*day_tree.get_children())
            for s in items:
                y, m, d = s["day"].split("-")
                tag = "dup" if s["dup"] else ("missing" if s["missing"] else "")
                day_tree.insert("", "end", iid=s["day"], tags=(tag,) if tag else (),
                                values=(f"{d}-{m}-{y}", f"{s['ops']:,}", f"{s['total']:,.2f}"))
            if keep and day_tree.exists(keep):
                day_tree.selection_set(keep)
                day_tree.see(keep)
            tot_ops = sum(s["ops"] for s in items)
            tot_amt = sum(s["total"] for s in items)
            sum_lbl.configure(text=T2(f"الأيام: {len(items)}  |  المعاملات: {tot_ops:,}\nالإجمالي: {tot_amt:,.2f} جنيه",
                                      f"Days: {len(items)}  |  Tx: {tot_ops:,}\nTotal: {tot_amt:,.2f} EGP"))

        def load_days():
            try: st["stats"] = archive_day_stats(archive_load_rows())
            except Exception as e:
                log_exception("archive_history_load", e)
                st["stats"] = []
            months = sorted({s["day"][:7] for s in st["stats"]}, reverse=True)
            cb_month.configure(values=[ALL] + months)
            if cb_month.get() not in [ALL] + months: cb_month.set(ALL)
            apply_days()

        for e in (day_q,): e.bind("<KeyRelease>", apply_days)

        # ---------- اليمين: بطاقة اليوم المختار ----------
        hdr = ctk.CTkFrame(right, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["accent"])
        hdr.pack(fill="x", pady=(2, 0))
        day_title = ctk.CTkLabel(hdr, text=T2("👈 اختار يوم من القائمة لعرض معاملاته", "👈 Pick a day from the list"),
                                 font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"])
        day_title.pack(side="left", padx=14, pady=8)

        cards = ctk.CTkFrame(right, fg_color="transparent")
        cards.pack(fill="x", pady=(6, 2))
        card_lbls = {}
        def mk_card(key, title, color):
            f = ctk.CTkFrame(cards, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
            f.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(f, text=title, font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"]).pack(anchor="w", padx=12, pady=(8, 0))
            lb = ctk.CTkLabel(f, text="-", font=(FONT_FAMILY, 18, "bold"), text_color=color)
            lb.pack(anchor="w", padx=12, pady=(0, 8))
            card_lbls[key] = lb
        mk_card("total", T2("إجمالي اليوم (الصافي)", "Day total (net)"), t["success"])
        mk_card("count", T2("عدد المعاملات", "Transactions"), t["accent"])
        mk_card("void", T2("ملغي", "Void"), t["danger"])
        mk_card("dup", T2("مكرر", "Duplicates"), t["warning"])

        # ---------- أزرار اليوم ----------
        def day_folder_of(iso):
            dd = datetime.date.fromisoformat(iso)
            f = archive_day_dir(folder, dd)
            if not os.path.isdir(f): f = archive_day_folder_from_index(iso) or f
            return dd, f

        def d_excel():
            iso = st["iso"]
            if not iso: return
            dd, f = day_folder_of(iso)
            if not os.path.isdir(f):
                messagebox.showerror(T2("غير موجود", "Not found"), f, parent=win)
                return
            xp = archive_day_excel_path(f, dd)
            if os.path.exists(xp):
                os.startfile(xp)
                return
            recs = list(st["recs"]) if st["recs_iso"] == iso and st["recs"] else None
            _set_status(T2("جاري إنشاء إكسيل اليوم...", "Building day Excel..."))
            def work():
                res = archive_write_day_excel(f, dd, recs)
                def fin():
                    if not win.winfo_exists(): return
                    if res and os.path.exists(res):
                        _set_status(T2("تم إنشاء إكسيل اليوم ✓", "Day Excel built ✓"))
                        os.startfile(res)
                    else:
                        _set_status("")
                        messagebox.showerror(T2("خطأ", "Error"), T2("تعذر إنشاء الإكسيل (اتأكد إنه مش مفتوح).", "Could not build the Excel (make sure it is not open)."), parent=win)
                self.after(0, fin)
            threading.Thread(target=work, daemon=True).start()

        def d_summary():
            iso = st["iso"]
            if not iso: return
            dd, f = day_folder_of(iso)
            pdfs = sorted(glob.glob(os.path.join(f, "Samary_*.pdf")))
            if pdfs: os.startfile(pdfs[0])
            else: messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا يوجد إيصال سمري لهذا اليوم.", "No summary receipt for this day."), parent=win)

        def d_folder():
            iso = st["iso"]
            if not iso: return
            dd, f = day_folder_of(iso)
            if os.path.isdir(f): os.startfile(f)
            else: messagebox.showerror(T2("غير موجود", "Not found"), f, parent=win)

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 2))
        def _b(text, color, hover, cmd, w=140):
            ctk.CTkButton(btn_row, text=text, font=FONT_BTN_SUB, fg_color=color, hover_color=hover,
                          text_color="#FFFFFF", width=w, height=32, command=cmd).pack(side="left", padx=(0, 6), pady=2)
        _b(T2("📊 إكسيل اليوم", "📊 Day Excel"), "#059669", "#047857", d_excel, 150)
        _b(T2("📄 إيصال السمري", "📄 Summary receipt"), "#0F766E", "#115E59", d_summary, 160)
        _b(T2("📂 فولدر اليوم", "📂 Day folder"), "#4338CA", "#3730A3", d_folder, 140)

        # ---------- بحث وفلتر معاملات اليوم ----------
        search_row = ctk.CTkFrame(right, corner_radius=10, height=46, fg_color=t["card"], border_width=1, border_color=t["border"])
        search_row.pack(fill="x", pady=(4, 4))
        tx_q = ctk.CTkEntry(search_row, placeholder_text=tr("search_placeholder"), font=FONT_ENTRY, width=280,
                            text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        tx_q.pack(side="left", padx=8, pady=6)
        attach_context_menu(tx_q)
        ALL_ST = T2("كل الحالات", "All statuses")
        status_map = {
            T2("سليم", "OK"): {"ok"}, T2("يدوي", "Manual"): {"manual"},
            T2("مكرر", "Duplicate"): {"dup"}, T2("ملغي", "Void"): {"void"},
            T2("ناقص / وحدة أخرى", "Incomplete / other unit"): {"missing", "wrong"},
        }
        cb_status = ctk.CTkComboBox(search_row, values=[ALL_ST] + list(status_map.keys()), width=170, font=FONT_ENTRY,
                                    fg_color=t["input"], border_color=t["border"], state="readonly",
                                    command=lambda v: refresh_tx())
        cb_status.set(ALL_ST)
        cb_status.pack(side="left", padx=(0, 6), pady=6)
        tx_count = ctk.CTkLabel(search_row, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        tx_count.pack(side="right", padx=14)

        # ---------- جدول معاملات اليوم ----------
        tree_frame = ctk.CTkFrame(right, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        tree_frame.pack(fill="both", expand=True, pady=(0, 2))
        columns = ("idx", "unit", "plate", "insured", "amount", "time", "make", "model", "chassis", "motor", "period", "file", "status")
        headers = {
            "idx": tr("col_idx"), "unit": tr("col_unit"), "plate": tr("col_plate"),
            "insured": tr("col_insured"), "amount": tr("col_amount"), "time": tr("col_time"),
            "make": tr("col_make"), "model": tr("col_model"), "chassis": tr("col_chassis"),
            "motor": tr("col_motor"), "period": tr("col_period"), "file": tr("col_file"), "status": tr("col_status")
        }
        tx_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style="A2R.Treeview")
        _COL_W = {"idx": 42, "unit": 125, "plate": 120, "insured": 190, "amount": 85, "time": 135, "make": 85,
                  "model": 85, "chassis": 140, "motor": 105, "period": 185, "file": 190, "status": 125}
        sort_dirs = {}
        def sort_tx(col):
            recs = st["recs"]
            reverse = sort_dirs.get(col, False)
            sort_dirs[col] = not reverse
            if col == "amount":
                recs.sort(key=lambda r: float(r["amount"]), reverse=reverse)
            elif col in ("idx", "time"):
                recs.sort(key=lambda r: r.get("dt_key") or datetime.datetime.min, reverse=reverse)
            else:
                k = "status_text" if col == "status" else col
                recs.sort(key=lambda r: str(r.get(k, "")), reverse=reverse)
            refresh_tx()
        for col in columns:
            tx_tree.heading(col, text=headers.get(col, col), command=lambda c=col: sort_tx(c))
            tx_tree.column(col, width=_COL_W.get(col, 90), anchor="center", stretch=(col in ("insured", "file")))
        for kind, (bg, fg) in TAG_COLORS[t["mode"]].items():
            tx_tree.tag_configure(kind, background=bg, foreground=fg)
        tx_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tx_tree.yview)
        tx_vsb.pack(side="right", fill="y", padx=2, pady=2)
        tx_hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tx_tree.xview)
        tx_hsb.pack(side="bottom", fill="x", padx=2, pady=2)
        tx_tree.configure(yscrollcommand=tx_vsb.set, xscrollcommand=tx_hsb.set)
        tx_tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)

        def _sel_rec():
            sel = tx_tree.selection()
            if not sel: return None
            try: return st["recs"][int(sel[0])]
            except Exception: return None

        def open_receipt(event=None):
            rec = _sel_rec()
            if not rec: return
            fpath = rec.get("path", "")
            if fpath and os.path.exists(fpath): os.startfile(fpath)
            else: messagebox.showerror("Not Found", f"File not found: {rec.get('file', '')}", parent=win)

        def reprint_receipt():
            rec = _sel_rec()
            if not rec: return
            try: self.reprint_receipt_record(rec)
            except Exception as e: messagebox.showerror("Error", str(e), parent=win)

        def open_receipt_folder():
            rec = _sel_rec()
            p = rec.get("path", "") if rec else ""
            if p and os.path.exists(p): os.startfile(os.path.dirname(p))
            else: d_folder()

        tx_tree.bind("<Double-1>", open_receipt)
        row_menu = tk.Menu(tx_tree, tearoff=0)
        row_menu.add_command(label=tr("menu_open_file"), command=open_receipt)
        row_menu.add_command(label=tr("menu_reprint"), command=reprint_receipt)
        row_menu.add_command(label=T2("📂 فتح الفولدر", "📂 Open folder"), command=open_receipt_folder)
        def _tx_pop(ev):
            it = tx_tree.identify_row(ev.y)
            if it:
                tx_tree.selection_set(it)
                row_menu.tk_popup(ev.x_root, ev.y_root)
        tx_tree.bind("<Button-3>", _tx_pop)

        ctk.CTkLabel(right, text=T2("🟥 مكرر   🟨 ناقص   🟧 وحدة أخرى   ⬛ ملغي (مخصوم)   •   دبل كليك لفتح الإيصال",
                                    "🟥 Duplicate   🟨 Incomplete   🟧 Other unit   ⬛ Void   •   double-click to open receipt"),
                     font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(anchor="w", padx=8, pady=(0, 2))

        def refresh_tx(*_):
            recs = st["recs"]
            q = tx_q.get().strip().lower()
            kinds = status_map.get(cb_status.get())
            tx_tree.delete(*tx_tree.get_children())
            shown = 0
            for i, r in enumerate(recs):
                if kinds and r.get("kind") not in kinds: continue
                if q:
                    full_s = f"{r['unit']} {r['plate']} {r['insured']} {r['time']} {r['chassis']} {r['motor']} {r['make']} {r['model']} {r['file']} {r['status_text']} {r['amount']:.2f}".lower()
                    if q not in full_s: continue
                vals = (i + 1, r["unit"], r["plate"], r["insured"], f"{r['amount']:.2f}", r["time"],
                        r["make"], r["model"], r["chassis"], r["motor"], r["period"], r["file"], r["status_text"])
                tag = r["kind"] if r["kind"] in ("dup", "void", "missing", "wrong") else ""
                tx_tree.insert("", "end", iid=str(i), values=vals, tags=(tag,) if tag else ())
                shown += 1
            tx_count.configure(text=T2(f"المعروض: {shown:,} سجل", f"Showing: {shown:,} rows"))

        def show_day_summary_cards():
            recs = st["recs"]
            tot, cnt = counted_totals(recs)
            card_lbls["total"].configure(text=f"{tot:,.2f}")
            card_lbls["count"].configure(text=f"{cnt:,}")
            card_lbls["void"].configure(text=str(sum(1 for r in recs if r.get("is_void"))))
            card_lbls["dup"].configure(text=str(sum(1 for r in recs if r.get("kind") == "dup")))

        def clear_day_view(msg=None):
            st["recs"], st["recs_iso"] = [], None
            tx_tree.delete(*tx_tree.get_children())
            for k in card_lbls: card_lbls[k].configure(text="-")
            tx_count.configure(text="")
            if msg is not None: day_title.configure(text=msg)

        def show_day(iso):
            """يعرض معاملات اليوم المختار في نفس النافذة (تحميل في الخلفية + كاش)."""
            st["iso"] = iso
            st["load_id"] += 1
            my_id = st["load_id"]
            y, m, d = iso.split("-")
            title = T2(f"📅 يوم {d}-{m}-{y}", f"📅 Day {d}-{m}-{y}")
            if iso in st["cache"]:
                st["recs"], st["recs_iso"] = st["cache"][iso], iso
                day_title.configure(text=title)
                show_day_summary_cards()
                refresh_tx()
                return
            clear_day_view(title + T2("   ⏳ جاري تحميل المعاملات...", "   ⏳ Loading transactions..."))
            try: dd, f = day_folder_of(iso)
            except Exception: return
            if not os.path.isdir(f):
                day_title.configure(text=title + T2("   ⚠️ الفولدر غير موجود", "   ⚠️ Folder not found"))
                return
            def work():
                try: recs = load_archive_day_records(f, dd)
                except Exception as e:
                    log_exception("archive_show_day", e)
                    recs = []
                def fin():
                    if not win.winfo_exists() or my_id != st["load_id"]: return
                    st["cache"][iso] = recs
                    st["recs"], st["recs_iso"] = recs, iso
                    day_title.configure(text=title if recs else title + T2("   (لا توجد معاملات)", "   (no transactions)"))
                    show_day_summary_cards()
                    refresh_tx()
                self.after(0, fin)
            threading.Thread(target=work, daemon=True).start()

        def on_day_select(event=None):
            sel = day_tree.selection()
            if not sel or sel[0] == st["iso"] and st["recs_iso"] == st["iso"]: return
            if st["sel_job"]:
                try: win.after_cancel(st["sel_job"])
                except Exception as _e: _log_silent("on_day_select#1", _e)
            iso = sel[0]
            st["sel_job"] = win.after(150, lambda: show_day(iso))   # تأخير بسيط لو بتتنقل بالأسهم بسرعة
        day_tree.bind("<<TreeviewSelect>>", on_day_select)

        def goto_day(iso):
            tv.set(TAB_DAYS)
            clear_filters()
            if day_tree.exists(iso):
                day_tree.selection_set(iso)
                day_tree.see(iso)
                show_day(iso)

        tx_q.bind("<KeyRelease>", refresh_tx)
        day_menu = tk.Menu(day_tree, tearoff=0)
        day_menu.add_command(label=T2("📊 إكسيل اليوم", "📊 Day Excel"), command=d_excel)
        day_menu.add_command(label=T2("📄 إيصال السمري", "📄 Summary receipt"), command=d_summary)
        day_menu.add_command(label=T2("📂 فولدر اليوم", "📂 Day folder"), command=d_folder)
        def _dpop(ev):
            it = day_tree.identify_row(ev.y)
            if it:
                day_tree.selection_set(it)
                show_day(it)
                day_menu.tk_popup(ev.x_root, ev.y_root)
        day_tree.bind("<Button-3>", _dpop)

        # ================= تبويب البحث العام =================
        f2 = ctk.CTkFrame(tab_search, fg_color="transparent")
        f2.pack(fill="x", pady=(2, 2))
        s_entry = ctk.CTkEntry(f2, placeholder_text=T2("اسم المؤمن له / رقم اللوحة / المبلغ...", "Insured name / plate / amount..."),
                               width=380, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        s_entry.pack(side="left", padx=(0, 8))
        attach_context_menu(s_entry)
        inc_void = ctk.CTkCheckBox(f2, text=T2("إظهار الملغي", "Include void"), font=FONT_SECTION_LBL, text_color=t["text"])
        inc_void.select()
        inc_void.pack(side="left", padx=6)
        s_count = ctk.CTkLabel(f2, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        s_count.pack(side="right", padx=8)

        s_cols = ("date", "unit", "plate", "insured", "amount", "time", "status", "file")
        s_hdr = {"date": T2("يوم الأرشيف", "Archive day"), "unit": T2("الوحدة", "Unit"), "plate": T2("اللوحة", "Plate"),
                 "insured": T2("المؤمن له", "Insured"), "amount": T2("المبلغ", "Amount"), "time": T2("الوقت", "Time"),
                 "status": T2("الحالة", "Status"), "file": T2("الملف", "File")}
        s_tree = make_tree(tab_search, s_cols, s_hdr,
                           {"date": 105, "unit": 140, "plate": 100, "insured": 180, "amount": 90, "time": 120, "status": 80, "file": 170})
        s_paths = {}
        s_days = {}

        def do_search(*_):
            q = s_entry.get().strip()
            s_tree.delete(*s_tree.get_children())
            s_paths.clear()
            s_days.clear()
            if not q:
                s_count.configure(text="")
                return
            try: rows = archive_search(q, include_void=bool(inc_void.get()))
            except Exception as e:
                log_exception("archive_search", e)
                rows = []
            tot = 0.0
            for i, (path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void) in enumerate(rows):
                y, m, d = day.split("-")
                if is_void: status, tag = T2("ملغي", "Void"), "void"
                elif is_manual: status, tag = T2("يدوي", "Manual"), "manual"
                else: status, tag = T2("سليم", "OK"), ""
                if not is_void: tot += amount
                iid = str(i)
                s_paths[iid] = path
                s_days[iid] = day
                s_tree.insert("", "end", iid=iid, tags=(tag,) if tag else (),
                              values=(f"{d}-{m}-{y}", unit, plate, insured, f"{amount:,.2f}", rtime, status, fname))
            s_count.configure(text=T2(f"النتائج: {len(rows):,}  |  الإجمالي (بدون الملغي): {tot:,.2f}",
                                      f"Results: {len(rows):,}  |  Total (excl. void): {tot:,.2f}"))

        def _debounced(*_):
            if st["debounce"]:
                try: win.after_cancel(st["debounce"])
                except Exception as _e: _log_silent("_debounced#1", _e)
            st["debounce"] = win.after(300, do_search)
        s_entry.bind("<KeyRelease>", _debounced)
        s_entry.bind("<Return>", do_search)
        inc_void.configure(command=do_search)

        def open_result(event=None, folder_only=False):
            sel = s_tree.selection()
            if not sel: return
            p = s_paths.get(sel[0], "")
            if not p or not os.path.exists(p):
                messagebox.showerror(T2("غير موجود", "Not found"), os.path.basename(p or ""), parent=win)
                return
            if folder_only: os.startfile(os.path.dirname(p))
            else: os.startfile(p)
        s_tree.bind("<Double-1>", open_result)
        smenu = tk.Menu(s_tree, tearoff=0)
        smenu.add_command(label=T2("📄 فتح الإيصال", "📄 Open receipt"), command=open_result)
        smenu.add_command(label=T2("📂 فتح فولدر اليوم", "📂 Open day folder"), command=lambda: open_result(folder_only=True))
        def view_result_day():
            sel = s_tree.selection()
            if sel and s_days.get(sel[0]): goto_day(s_days[sel[0]])
        smenu.add_command(label=T2("📋 عرض كل معاملات اليوم ده", "📋 View all transactions of this day"), command=view_result_day)
        def _spop(ev):
            it = s_tree.identify_row(ev.y)
            if it:
                s_tree.selection_set(it)
                smenu.tk_popup(ev.x_root, ev.y_root)
        s_tree.bind("<Button-3>", _spop)

        # تشغيل: اعرض اللي في الفهرس فورًا، وبعدين حدّث في الخلفية
        load_days()
        run_maintenance()
        win.after(150, lambda: day_q.focus_set())

    # ================= أدوات POS للمشرف: التقفيل + إيصالات الدفع (بباسورد منفصل) =================
    def _pos_gate(self):
        if not getattr(self, "is_supervisor", False):
            messagebox.showwarning(T2("غير مسموح", "Not allowed"), T2("هذه الأداة للمشرف فقط.", "Supervisor only."))
            return False
        if pos_is_unlocked(): return True
        t = THEMES[self.current_theme_name]
        dlg = ctk.CTkToplevel(self)
        dlg.title(T2("🔐 باسورد الأداة", "🔐 Tool password"))
        dlg.resizable(False, False)
        set_window_icon_safe(dlg)
        center_window_relative(dlg, self, 360, 200)
        dlg.configure(fg_color=t["bg"])
        ok = {"v": False}
        ctk.CTkLabel(dlg, text=T2("أدخل الباسورد الخاص بهذه الأداة", "Enter this tool's password"),
                     font=FONT_SECTION_LBL, text_color=t["text"]).pack(pady=(18, 8))
        ent = ctk.CTkEntry(dlg, show="●", width=260, font=FONT_ENTRY, text_color=t["text"],
                           fg_color=t["input"], border_color=t["border"])
        ent.pack(pady=4)
        msg = ctk.CTkLabel(dlg, text="", font=(FONT_FAMILY, 10, "bold"), text_color="#EF4444")
        msg.pack(pady=2)

        def submit(event=None):
            good, m = pos_check_password(ent.get())
            if good:
                ok["v"] = True; dlg.destroy()
            else:
                msg.configure(text=m); ent.delete(0, "end")
        ent.bind("<Return>", submit)
        ctk.CTkButton(dlg, text=T2("دخول", "Unlock"), width=120, height=32, font=FONT_BTN_SUB, fg_color=t["primary"],
                      hover_color=t["primary_hover"], text_color="#FFFFFF", command=submit).pack(pady=8)
        try: dlg.lift(); dlg.grab_set(); ent.focus_set()
        except Exception as _e: _log_silent("_pos_gate#1", _e)
        self.wait_window(dlg)
        return ok["v"]

    def _pos_need_ocr(self):
        if pos_ocr_init(): return True
        messagebox.showerror(T2("محرك OCR غير متاح", "OCR engine missing"),
                             T2("مفيش محرك قراءة صور شغّال.\n\nالسبب الفعلي:\n", "No working OCR engine.\n\nActual reason:\n") + (_OCR.get("err") or "-") +
                             T2("\n\nالحل: pip install rapidocr onnxruntime pypdfium2\n(لو بتشغّل exe لازم يتبني من جديد بالمكتبات دي)",
                                "\n\nFix: pip install rapidocr onnxruntime pypdfium2\n(for an exe, rebuild it with these packages)"))
        return False

    def _pos_picker_bar(self, parent, t, st, exts, filetypes, on_change):
        fr = ctk.CTkFrame(parent, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        fr.pack(fill="x", padx=12, pady=(10, 4))
        r1 = ctk.CTkFrame(fr, fg_color="transparent"); r1.pack(fill="x", padx=8, pady=(8, 2))
        r2 = ctk.CTkFrame(fr, fg_color="transparent"); r2.pack(fill="x", padx=8, pady=(2, 8))
        lbl_src = ctk.CTkLabel(r1, text="", font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"], anchor="w")
        lbl_out = ctk.CTkLabel(r2, text="", font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"], anchor="w")

        def refresh():
            files = pos_collect_files(st["sources"], exts)
            lbl_src.configure(text=T2(f"المصدر: {len(st['sources'])} اختيار → {len(files)} ملف", f"Source: {len(st['sources'])} picks → {len(files)} files"))
            lbl_out.configure(text=T2("الإخراج: ", "Output: ") + (st["out"] or T2("(لم يتم الاختيار)", "(not chosen)")))
            on_change()

        def add_folder():
            d = filedialog.askdirectory(title=T2("اختر فولدر الصور / الـ PDF", "Choose folder"), parent=parent.winfo_toplevel())
            if d: st["sources"].append(d); refresh()
        def add_files():
            fs = filedialog.askopenfilenames(title=T2("اختر ملفات", "Choose files"), filetypes=filetypes, parent=parent.winfo_toplevel())
            if fs: st["sources"].extend(fs); refresh()
        def clear_src():
            st["sources"].clear(); refresh()
        def pick_out():
            d = filedialog.askdirectory(title=T2("اختر مكان الإخراج", "Choose output folder"), parent=parent.winfo_toplevel())
            if d: st["out"] = d; refresh()

        for txt, cmd, col in ((T2("📁 اختيار فولدر", "📁 Add folder"), add_folder, t["primary"]),
                              (T2("🖼️ اختيار ملفات", "🖼️ Add files"), add_files, t["primary"]),
                              (T2("مسح", "Clear"), clear_src, "#64748B")):
            ctk.CTkButton(r1, text=txt, width=130, height=30, font=FONT_BTN_SUB, fg_color=col, hover_color=t["primary_hover"],
                          text_color="#FFFFFF", command=cmd).pack(side="left", padx=3)
        lbl_src.pack(side="left", padx=10)
        ctk.CTkButton(r2, text=T2("📂 مكان الإخراج", "📂 Output folder"), width=130, height=30, font=FONT_BTN_SUB,
                      fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF", command=pick_out).pack(side="left", padx=3)
        lbl_out.pack(side="left", padx=10)
        return refresh

    # ---------------------------------------- التقفيل ----------------------------------------
    def open_pos_closing(self):
        if not self._pos_gate() or not self._pos_need_ocr(): return
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(T2("🧾 تقفيل POS", "🧾 POS Closing"))
        set_window_icon_safe(win)
        center_window_relative(win, self, 1100, 720)
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception as _e: _log_silent("open_pos_closing#1", _e)
        st = {"sources": [], "out": "", "items": [], "warnings": [], "excluded": [], "stop": False, "busy": False}
        FT = [("Images / PDF", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.pdf")]

        status = ctk.CTkLabel(win, text=T2("اختر مكان الصور أو الـ PDF ومكان الإخراج، ثم اضغط بدء.", "Pick sources and output, then press Start."),
                              font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"], anchor="w")
        bar = ctk.CTkProgressBar(win, height=10); bar.set(0)

        def update_buttons():
            ready = bool(st["sources"]) and bool(st["out"]) and not st["busy"]
            btn_run.configure(state="normal" if ready else "disabled")
        refresh = self._pos_picker_bar(win, t, st, POS_IMG_EXT + (".pdf",), FT, lambda: update_buttons())

        ctrl = ctk.CTkFrame(win, fg_color="transparent"); ctrl.pack(fill="x", padx=12, pady=2)
        cb_rot = ctk.CTkCheckBox(ctrl, text=T2("تدوير الصور المقلوبة تلقائيًا", "Auto-rotate"), font=FONT_SECTION_LBL, text_color=t["text"])
        cb_rot.select(); cb_rot.pack(side="left", padx=6)
        btn_run = ctk.CTkButton(ctrl, text=T2("▶ بدء القراءة", "▶ Start"), width=140, height=32, font=FONT_BTN_SUB,
                                fg_color="#16A34A", hover_color="#15803D", text_color="#FFFFFF", state="disabled")
        btn_run.pack(side="left", padx=6)
        refresh()
        btn_stop = ctk.CTkButton(ctrl, text=T2("⏹ إيقاف", "⏹ Stop"), width=90, height=32, font=FONT_BTN_SUB,
                                 fg_color="#DC2626", hover_color="#B91C1C", text_color="#FFFFFF",
                                 command=lambda: st.__setitem__("stop", True))
        btn_stop.pack(side="left", padx=2)
        status.pack(fill="x", padx=14, pady=(4, 0)); bar.pack(fill="x", padx=14, pady=(2, 4))

        cols = ("order", "unit", "tid", "amount", "date", "status", "file")
        hdr = {"order": T2("رقم", "No."), "unit": T2("الوحدة", "Unit"), "tid": "TID", "amount": T2("المبلغ", "Amount"),
               "date": T2("التاريخ", "Date"), "status": T2("الحالة", "Status"), "file": T2("الملف", "File")}
        tree = pos_make_tree(win, t, cols, hdr, {"order": 60, "unit": 150, "tid": 110, "amount": 110, "date": 80, "status": 130, "file": 280})
        warn_box = ctk.CTkTextbox(win, height=110, font=(FONT_FAMILY, 10), fg_color=t["input"], text_color=t["text"])
        warn_box.pack(fill="x", padx=12, pady=(2, 4))
        sumlbl = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 12, "bold"), text_color=t["accent"], anchor="w")
        sumlbl.pack(fill="x", padx=14)

        def status_of(it):
            if it["skip"]: return T2("مكرر (مستبعد)", "Duplicate"), "void"
            if not it.get("include", True): return T2("مستبعد", "Excluded"), "void"
            if it["tid"] is None or it["amount"] <= 0 or not it["ok"] or it["alt"] is not None:
                return T2("⚠ راجع", "⚠ Review"), "missing"
            return "✓", ""

        def fill_tree():
            tree.delete(*tree.get_children())
            tot = 0.0
            for i, it in enumerate(st["items"]):
                s, tag = status_of(it)
                if not it["skip"] and it.get("include", True) and it["amount"] > 0: tot += it["amount"]
                sfx = f"_{it['suffix']}" if it["suffix"] else ""
                tree.insert("", "end", iid=str(i), tags=(tag,) if tag else (),
                            values=(f"{it['order']}{sfx}" if it["order"] else "-", it["unit"] or "-", it["tid"] or "-",
                                    f"{it['amount']:,.2f}", it["date"] or "-", s, it["label"]))
            sumlbl.configure(text=T2(f"عدد الإيصالات: {len(st['items'])}   |   الإجمالي: {tot:,.2f} جنيه", f"Receipts: {len(st['items'])}  |  Total: {tot:,.2f} EGP"))
            warn_box.configure(state="normal"); warn_box.delete("1.0", "end")
            lines = [f"• {w}" for w in st["warnings"]]
            if st["excluded"]:
                lines.append(T2(f"• اتجاهلت {len(st['excluded'])} إيصال دفع (مش باتش/إقفال): ", f"• Ignored {len(st['excluded'])} payment receipts: ") + "، ".join(st["excluded"][:8]))
            warn_box.insert("1.0", "\n".join(lines) or T2("مفيش تحذيرات.", "No warnings.")); warn_box.configure(state="disabled")

        def run():
            files = pos_collect_files(st["sources"], POS_IMG_EXT + (".pdf",))
            if not files:
                messagebox.showinfo(T2("تنبيه", "Notice"), T2("مفيش صور أو PDF في المصدر المختار.", "No images/PDF in source."), parent=win); return
            st["stop"], st["busy"] = False, True; update_buttons()
            def prog(i, n, label):
                self.after(0, lambda: (bar.set(i / max(1, n)), status.configure(text=T2(f"قراءة {i + 1} من {n}: {label}", f"Reading {i + 1}/{n}: {label}"))))
            def work():
                try:
                    items, w, ex = pos_closing_scan(files, bool(cb_rot.get()), prog, lambda: st["stop"])
                    pos_closing_number(items, w)
                    def fin():
                        st["items"], st["warnings"], st["excluded"], st["busy"] = items, w, ex, False
                        bar.set(1); update_buttons(); fill_tree()
                        status.configure(text=T2(f"تمت القراءة: {len(items)} إيصال. راجع الجدول ثم اضغط إنشاء الملفات.", f"Done: {len(items)} receipts. Review, then Build."))
                        if not items: messagebox.showinfo(T2("تنبيه", "Notice"), T2("لم يتم العثور على إيصالات إقفال.", "No batch-close receipts found."), parent=win)
                    self.after(0, fin)
                except Exception as e:
                    log_exception("pos_closing_run", e)
                    def bad():
                        st["busy"] = False; update_buttons()
                        messagebox.showerror("Error", str(e), parent=win)
                    self.after(0, bad)
            threading.Thread(target=work, daemon=True).start()
        btn_run.configure(command=run)

        tid_choices = [T2("(بدون ماكينة)", "(none)")] + [f"{POS_TERMINALS[POS_NUM_TO_TID[n]][0]} - {POS_TERMINALS[POS_NUM_TO_TID[n]][2]} - {POS_NUM_TO_TID[n]}" for n in range(1, 20)]

        def edit_selected(event=None):
            sel = tree.selection()
            if not sel: return
            it = st["items"][int(sel[0])]
            d = ctk.CTkToplevel(win); d.title(T2("تعديل الإيصال", "Edit receipt")); set_window_icon_safe(d)
            center_window_relative(d, win, 420, 330); d.configure(fg_color=t["bg"])
            ctk.CTkLabel(d, text=it["label"], font=FONT_SECTION_LBL, text_color=t["text"]).pack(pady=(14, 4))
            ctk.CTkLabel(d, text=T2("الماكينة", "Terminal"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=20)
            cb = ctk.CTkComboBox(d, values=tid_choices, width=360, font=FONT_ENTRY, fg_color=t["input"], border_color=t["border"]); cb.pack(padx=20)
            cb.set(next((c for c in tid_choices if it["tid"] and c.endswith(it["tid"])), tid_choices[0]))
            ctk.CTkLabel(d, text=T2("المبلغ", "Amount"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=20, pady=(8, 0))
            e_amt = ctk.CTkEntry(d, width=360, font=FONT_ENTRY, fg_color=t["input"], border_color=t["border"], text_color=t["text"]); e_amt.pack(padx=20)
            e_amt.insert(0, f"{it['amount']:.2f}")
            inc = ctk.CTkCheckBox(d, text=T2("ضمّه في التقفيل", "Include in closing"), font=FONT_SECTION_LBL, text_color=t["text"]); inc.pack(anchor="w", padx=20, pady=8)
            if it.get("include", True) and not it["skip"]: inc.select()
            def save():
                try: amt = _r2(float(e_amt.get().replace(",", "").strip()))
                except ValueError:
                    messagebox.showerror(T2("خطأ", "Error"), T2("المبلغ غير صحيح.", "Invalid amount."), parent=win); return
                v = cb.get()
                if v != tid_choices[0]: pos_apply_tid(it, v.split(" - ")[-1].strip())
                it["amount"], it["how"], it["ok"], it["alt"] = amt, "manual", True, None
                it["include"] = bool(inc.get()); it["skip"] = False
                d.destroy(); fill_tree()
            def open_img():
                try: os.startfile(it["path"])
                except Exception as e: messagebox.showerror("Error", str(e), parent=win)
            r = ctk.CTkFrame(d, fg_color="transparent"); r.pack(pady=10)
            ctk.CTkButton(r, text=T2("💾 حفظ", "💾 Save"), width=110, fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF", command=save).pack(side="left", padx=4)
            ctk.CTkButton(r, text=T2("🖼️ فتح الصورة", "🖼️ Open image"), width=120, fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF", command=open_img).pack(side="left", padx=4)
            try: d.lift(); d.grab_set()
            except Exception as _e: _log_silent("edit_selected#1", _e)
        tree.bind("<Double-1>", edit_selected)

        def build():
            if not st["items"]:
                messagebox.showinfo(T2("تنبيه", "Notice"), T2("اعمل قراءة الأول.", "Run a scan first."), parent=win); return
            if not st["out"]:
                messagebox.showinfo(T2("تنبيه", "Notice"), T2("اختر مكان الإخراج.", "Choose output folder."), parent=win); return
            tpl = _pos_find_template()
            if not tpl:
                tpl = filedialog.askopenfilename(title=T2("اختر قالب الإكسيل (الاسكندريه 00.xlsx)", "Choose Excel template"), filetypes=[("Excel", "*.xlsx")], parent=win) or None
            btn_build.configure(state="disabled"); status.configure(text=T2("جاري إنشاء الملفات...", "Building files..."))
            def work():
                try: res = pos_closing_build(st["items"], st["out"], tpl)
                except Exception as e:
                    log_exception("pos_closing_build", e); res = {"error": str(e)}
                def fin():
                    btn_build.configure(state="normal")
                    if "error" in res:
                        messagebox.showerror("Error", res["error"], parent=win); return
                    msg = T2(f"تم إنشاء:\n• {len(res['pdfs'])} ملف PDF\n• {'إكسيل' if res['xlsx'] else 'بدون إكسيل'}\n• صور مرقّمة\n\nالتاريخ: {res['report_date']}", f"Created {len(res['pdfs'])} PDF, {'Excel' if res['xlsx'] else 'no Excel'}.")
                    if res["notes"]: msg += "\n\n" + "\n".join(res["notes"])
                    status.configure(text=T2("تم الإنشاء ✓", "Built ✓"))
                    messagebox.showinfo(T2("تم", "Done"), msg, parent=win)
                    try: os.startfile(st["out"])
                    except Exception as _e: _log_silent("fin#1", _e)
                self.after(0, fin)
            threading.Thread(target=work, daemon=True).start()

        foot = ctk.CTkFrame(win, fg_color="transparent"); foot.pack(fill="x", padx=12, pady=(4, 12))
        ctk.CTkButton(foot, text=T2("✏️ تعديل المحدد", "✏️ Edit selected"), width=140, height=32, font=FONT_BTN_SUB, fg_color=t["primary"],
                      hover_color=t["primary_hover"], text_color="#FFFFFF", command=edit_selected).pack(side="left", padx=4)
        btn_build = ctk.CTkButton(foot, text=T2("📦 إنشاء الملفات (PDF + إكسيل)", "📦 Build files (PDF + Excel)"), width=230, height=32, font=FONT_BTN_SUB,
                                  fg_color="#16A34A", hover_color="#15803D", text_color="#FFFFFF", command=build)
        btn_build.pack(side="left", padx=4)

    # ---------------------------------------- إيصالات الدفع ----------------------------------------
    def open_pos_payments(self):
        if not self._pos_gate() or not self._pos_need_ocr(): return
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(T2("💳 إيصالات الدفع", "💳 Payment Receipts"))
        set_window_icon_safe(win)
        center_window_relative(win, self, 1150, 720)
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception as _e: _log_silent("open_pos_payments#1", _e)
        st = {"sources": [], "out": "", "res": [], "stop": False, "busy": False}
        FT = [("PDF", "*.pdf")]
        status = ctk.CTkLabel(win, text=T2("اختر ملفات الـ PDF (أو فولدر) ومكان الإخراج، ثم اضغط بدء.", "Pick PDFs and output, then Start."),
                              font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"], anchor="w")
        bar = ctk.CTkProgressBar(win, height=10); bar.set(0)

        def update_buttons():
            btn_run.configure(state="normal" if (st["sources"] and not st["busy"]) else "disabled")
        refresh = self._pos_picker_bar(win, t, st, (".pdf",), FT, lambda: update_buttons())
        ctrl = ctk.CTkFrame(win, fg_color="transparent"); ctrl.pack(fill="x", padx=12, pady=2)
        btn_run = ctk.CTkButton(ctrl, text=T2("▶ بدء الفحص والعد", "▶ Start scan"), width=150, height=32, font=FONT_BTN_SUB,
                                fg_color="#16A34A", hover_color="#15803D", text_color="#FFFFFF", state="disabled")
        btn_run.pack(side="left", padx=6)
        refresh()
        ctk.CTkButton(ctrl, text=T2("⏹ إيقاف", "⏹ Stop"), width=90, height=32, font=FONT_BTN_SUB, fg_color="#DC2626",
                      hover_color="#B91C1C", text_color="#FFFFFF", command=lambda: st.__setitem__("stop", True)).pack(side="left", padx=2)
        status.pack(fill="x", padx=14, pady=(4, 0)); bar.pack(fill="x", padx=14, pady=(2, 4))

        cols = ("order", "unit", "tid", "date", "count", "new", "notes", "file")
        hdr = {"order": T2("رقم", "No."), "unit": T2("الوحدة", "Unit"), "tid": "TID", "date": T2("التاريخ", "Date"),
               "count": T2("العدد", "Count"), "new": T2("الاسم الجديد", "New name"), "notes": T2("ملاحظات", "Notes"), "file": T2("الملف الأصلي", "Original")}
        tree = pos_make_tree(win, t, cols, hdr, {"order": 50, "unit": 120, "tid": 100, "date": 70, "count": 60, "new": 210, "notes": 260, "file": 200})
        sumlbl = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"], anchor="w", justify="left", wraplength=1080)
        sumlbl.pack(fill="x", padx=14, pady=2)

        def fill_tree():
            tree.delete(*tree.get_children())
            total = 0
            for i, r in enumerate(st["res"]):
                total += max(r["count"], 0)
                tree.insert("", "end", iid=str(i), tags=(() if r["ok"] else ("missing",)),
                            values=(r["order"] or "-", r["unit"] or "-", r["tid"] or "-", f"{r['day']}.{r['month']}" if r["day"] else "-",
                                    r["count"], r["new"] or "-", " | ".join(r["notes"]) or "✓", r["name"]))
            got = {r["order"] for r in st["res"] if r["order"]}
            miss = [f"{n} {POS_TERMINALS[POS_NUM_TO_TID[n]][2]}" for n in range(1, 20) if n not in got]
            sumlbl.configure(text=T2(f"الملفات: {len(st['res'])}   |   إجمالي الإيصالات: {total}" + (f"\nماكينات ناقصة: {'، '.join(miss)}" if st["res"] and miss else ""),
                                     f"Files: {len(st['res'])} | Receipts: {total}" + (f"\nMissing machines: {', '.join(miss)}" if st["res"] and miss else "")))

        def make_result(f, r):
            res = {"src": f, "name": os.path.basename(f), "tid": r["tid"], "order": None, "unit": None, "day": r["day"], "month": r["month"],
                   "count": r["count"], "notes": [], "ok": True, "new": None}
            if r["tid"]:
                res["order"], res["unit"] = POS_TERMINALS[r["tid"]][0], POS_TERMINALS[r["tid"]][2]
            else:
                res["ok"] = False; res["notes"].append(T2("مش قادر أعرف الماكينة", "Machine unknown"))
            if not r["day"]:
                res["ok"] = False; res["notes"].append(T2("مش قادر أعرف التاريخ", "Date unknown"))
            if r["tid"] and r["day"]: res["new"] = pos_machine_new_name(r["tid"], r["day"], r["month"])
            if r["seq_min"] is not None and r["count"] != r["seq_max"] - r["seq_min"] + 1:
                res["ok"] = False
                res["notes"].append(T2(f"العدد {r['count']} بس التسلسل {r['seq_max'] - r['seq_min'] + 1} — راجع", f"Count {r['count']} vs sequence {r['seq_max'] - r['seq_min'] + 1}"))
            if r["other_day"]: res["ok"] = False; res["notes"].append(T2("فيه إيصال بتاريخ تاني", "Other-day receipt"))
            if r["partial"]: res["notes"].append(T2(f"{r['partial']} إيصال رقمه مش واضح", f"{r['partial']} unclear"))
            if r["non_payment"]: res["notes"].append(T2("فيه إقفال/ملخص (مش معدود)", "Contains closing/summary"))
            return res

        def run():
            files = pos_collect_files(st["sources"], (".pdf",))
            if not files:
                messagebox.showinfo(T2("تنبيه", "Notice"), T2("مفيش ملفات PDF في المصدر.", "No PDFs."), parent=win); return
            st["stop"], st["busy"], st["res"] = False, True, []; update_buttons(); fill_tree()
            def work():
                out = []
                for i, f in enumerate(files):
                    if st["stop"]: break
                    self.after(0, lambda i=i, f=f: (bar.set(i / len(files)), status.configure(text=T2(f"فحص {i + 1} من {len(files)}: {os.path.basename(f)}", f"Scanning {i + 1}/{len(files)}"))))
                    try:
                        r = pos_count_pdf(f, lambda m, f=f: self.after(0, lambda: status.configure(text=f"{os.path.basename(f)} — {m}")), lambda: st["stop"])
                        out.append(make_result(f, r))
                    except Exception as e:
                        log_exception(f"pos_payment:{f}", e)
                        out.append({"src": f, "name": os.path.basename(f), "tid": None, "order": None, "unit": None, "day": None, "month": None,
                                    "count": 0, "notes": [f"فشل: {e}"], "ok": False, "new": None})
                    st["res"] = list(out)
                    self.after(0, fill_tree)
                used = set()
                for r in st["res"]:           # أسماء مكررة
                    if r["new"]:
                        n, k = r["new"], 2
                        while n in used: n = f"{r['new']}_{k}"; k += 1
                        used.add(n); r["new"] = n
                def fin():
                    st["busy"] = False; update_buttons(); bar.set(1); fill_tree()
                    status.configure(text=T2("تم الفحص. راجع الصفوف الصفراء ثم احفظ النسخ.", "Done. Review yellow rows, then save."))
                self.after(0, fin)
            threading.Thread(target=work, daemon=True).start()
        btn_run.configure(command=run)

        tid_choices = [T2("(بدون ماكينة)", "(none)")] + [f"{POS_TERMINALS[POS_NUM_TO_TID[n]][0]} - {POS_TERMINALS[POS_NUM_TO_TID[n]][2]} - {POS_NUM_TO_TID[n]}" for n in range(1, 20)]
        def edit_selected(event=None):
            sel = tree.selection()
            if not sel: return
            r = st["res"][int(sel[0])]
            d = ctk.CTkToplevel(win); d.title(T2("تعديل", "Edit")); set_window_icon_safe(d)
            center_window_relative(d, win, 420, 360); d.configure(fg_color=t["bg"])
            ctk.CTkLabel(d, text=r["name"], font=FONT_SECTION_LBL, text_color=t["text"]).pack(pady=(14, 4))
            cb = ctk.CTkComboBox(d, values=tid_choices, width=360, font=FONT_ENTRY, fg_color=t["input"], border_color=t["border"]); cb.pack(padx=20, pady=4)
            cb.set(next((c for c in tid_choices if r["tid"] and c.endswith(r["tid"])), tid_choices[0]))
            row = ctk.CTkFrame(d, fg_color="transparent"); row.pack(pady=4)
            ents = {}
            for key, lab, val in (("day", T2("اليوم", "Day"), r["day"]), ("month", T2("الشهر", "Month"), r["month"]), ("count", T2("العدد", "Count"), r["count"])):
                ctk.CTkLabel(row, text=lab, font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left", padx=(8, 2))
                e = ctk.CTkEntry(row, width=60, font=FONT_ENTRY, fg_color=t["input"], border_color=t["border"], text_color=t["text"]); e.pack(side="left")
                e.insert(0, "" if val is None else str(val)); ents[key] = e
            def save():
                try: cnt = int(ents["count"].get())
                except ValueError: messagebox.showerror(T2("خطأ", "Error"), T2("العدد غير صحيح.", "Invalid count."), parent=win); return
                v = cb.get()
                r["tid"] = None if v == tid_choices[0] else v.split(" - ")[-1].strip()
                r["day"], r["month"] = ents["day"].get().strip() or None, ents["month"].get().strip() or None
                r["count"] = cnt
                if r["tid"]: r["order"], r["unit"] = POS_TERMINALS[r["tid"]][0], POS_TERMINALS[r["tid"]][2]
                r["new"] = pos_machine_new_name(r["tid"], r["day"], r["month"]) if (r["tid"] and r["day"] and r["month"]) else None
                r["ok"], r["notes"] = bool(r["new"]), [T2("اتعدّل يدويًا", "Edited manually")]
                d.destroy(); fill_tree()
            ctk.CTkButton(d, text=T2("💾 حفظ", "💾 Save"), width=120, fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF", command=save).pack(pady=12)
            try: d.lift(); d.grab_set()
            except Exception as _e: _log_silent("edit_selected#2", _e)
        tree.bind("<Double-1>", edit_selected)

        def save_copies():
            if not st["out"]: messagebox.showinfo(T2("تنبيه", "Notice"), T2("اختر مكان الإخراج.", "Choose output folder."), parent=win); return
            n = 0
            os.makedirs(st["out"], exist_ok=True)
            for r in st["res"]:
                if not r["new"]: continue
                try: shutil.copy2(r["src"], os.path.join(st["out"], r["new"] + ".pdf")); n += 1
                except Exception as e: log_exception("pos_save_copy", e)
            messagebox.showinfo(T2("تم", "Done"), T2(f"اتحفظ {n} ملف باسمه الجديد (الأصول ماتلمستش).", f"Saved {n} renamed copies (originals untouched)."), parent=win)
            try: os.startfile(st["out"])
            except Exception as _e: _log_silent("save_copies#1", _e)

        def export_xlsx():
            if not st["res"]: return
            if not OPENPYXL_AVAILABLE: messagebox.showerror("Error", "openpyxl missing", parent=win); return
            f = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile="ملخص إيصالات الدفع.xlsx", parent=win)
            if not f: return
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Payments"
            ws.append(["رقم", "الوحدة", "TID", "التاريخ", "عدد الإيصالات", "الاسم الجديد", "ملاحظات", "الملف الأصلي"])
            for r in sorted(st["res"], key=lambda x: (x["order"] or 99, x["name"])):
                ws.append([r["order"], r["unit"], r["tid"], f"{r['day']}.{r['month']}" if r["day"] else "", r["count"], r["new"], " | ".join(r["notes"]), r["name"]])
            ws.append([]); ws.append(["", "الإجمالي", "", "", sum(max(r["count"], 0) for r in st["res"])])
            wb.save(f); messagebox.showinfo(T2("تم", "Done"), f, parent=win)

        foot = ctk.CTkFrame(win, fg_color="transparent"); foot.pack(fill="x", padx=12, pady=(4, 12))
        for txt, cmd, col in ((T2("✏️ تعديل المحدد", "✏️ Edit"), edit_selected, t["primary"]),
                              (T2("💾 حفظ نسخ بالأسماء الجديدة", "💾 Save renamed copies"), save_copies, "#16A34A"),
                              (T2("📊 تصدير ملخص إكسيل", "📊 Export Excel"), export_xlsx, "#4338CA")):
            ctk.CTkButton(foot, text=txt, width=200, height=32, font=FONT_BTN_SUB, fg_color=col, hover_color=t["primary_hover"],
                          text_color="#FFFFFF", command=cmd).pack(side="left", padx=4)

    def open_records_viewer(self):
        if not self.last_detailed_records:
            messagebox.showinfo("Notice", tr("no_records_yet"))
            return
        self._records_window(self.last_detailed_records, live=True)

    def _records_window(self, records, live=True, day_iso=None, day_folder=None):
        """نافذة عرض السجلات: live=True لسجلات اليوم الحالي (فيها إلغاء/استرجاع)، live=False لأي يوم من الأرشيف."""
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        day_txt = ""
        if day_iso:
            yy, mm, dd_ = day_iso.split("-")
            day_txt = f"{dd_}-{mm}-{yy}"
        win.title(tr("records_viewer_title") + (f" — {day_txt}" if day_txt else ""))
        win.resizable(True, True)
        set_window_icon_safe(win)
        _sw, _sh = win.winfo_screenwidth(), win.winfo_screenheight()
        center_window_relative(win, self, min(1340, _sw - 40), min(680, _sh - 110))   # على قد الشاشة
        win.minsize(min(1000, _sw - 40), 420)
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception as _e: _log_silent("_records_window#1", _e)

        if not live:
            hdr = ctk.CTkFrame(win, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["accent"])
            hdr.pack(fill="x", padx=14, pady=(12, 0))
            ctk.CTkLabel(hdr, text=T2(f"📅 أرشيف يوم {day_txt}", f"📅 Archive day {day_txt}"),
                         font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"]).pack(side="left", padx=14, pady=8)

        # ---------- كروت الإحصائيات ----------
        cards = ctk.CTkFrame(win, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=(8, 2))
        card_lbls = {}

        def mk_card(key, title, color):
            f = ctk.CTkFrame(cards, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
            f.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(f, text=title, font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"]).pack(anchor="w", padx=12, pady=(8, 0))
            lb = ctk.CTkLabel(f, text="0", font=(FONT_FAMILY, 18, "bold"), text_color=color)
            lb.pack(anchor="w", padx=12, pady=(0, 8))
            card_lbls[key] = lb

        mk_card("total", T2("إجمالي المبلغ (الصافي)", "Net total"), t["success"])
        mk_card("count", T2("عدد المعاملات", "Transactions"), t["accent"])
        mk_card("shown", T2("صافي المعروض", "Shown total"), t["text"])
        mk_card("void", T2("ملغي", "Void"), t["danger"])
        mk_card("dup", T2("مكرر", "Duplicates"), t["warning"])

        # ---------- البحث والفلاتر ----------
        search_row = ctk.CTkFrame(win, corner_radius=10, height=52, fg_color=t["card"], border_width=1, border_color=t["border"])
        search_row.pack(fill="x", padx=14, pady=(6, 4))

        search_entry = ctk.CTkEntry(search_row, placeholder_text=tr("search_placeholder"), font=FONT_ENTRY, width=300,
                                    text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        search_entry.pack(side="left", padx=8, pady=8)
        search_entry.focus_set()
        attach_context_menu(search_entry)

        amt_entry = ctk.CTkEntry(search_row, placeholder_text=tr("amt_filter_placeholder"), font=FONT_ENTRY, width=95,
                                 text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        amt_entry.pack(side="left", padx=(0, 6), pady=8)
        attach_context_menu(amt_entry)

        ALL_ST = T2("كل الحالات", "All statuses")
        status_map = {
            T2("سليم", "OK"): {"ok"}, T2("يدوي", "Manual"): {"manual"},
            T2("مكرر", "Duplicate"): {"dup"}, T2("ملغي", "Void"): {"void"},
            T2("ناقص / وحدة أخرى", "Incomplete / other unit"): {"missing", "wrong"},
        }
        cb_status = ctk.CTkComboBox(search_row, values=[ALL_ST] + list(status_map.keys()), width=170, font=FONT_ENTRY,
                                    fg_color=t["input"], border_color=t["border"], state="readonly",
                                    command=lambda v: refresh())
        cb_status.set(ALL_ST)
        cb_status.pack(side="left", padx=(0, 6), pady=8)

        count_lbl = ctk.CTkLabel(search_row, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        count_lbl.pack(side="right", padx=14)

        # ---------- الأزرار ----------
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 2))

        def _sel_rec():
            sel = tree.selection()
            if not sel: return None
            try: return records[int(sel[0])]
            except Exception: return None

        def open_selected():
            rec = _sel_rec()
            if not rec: return
            fpath = rec.get("path", "")
            if fpath and os.path.exists(fpath): os.startfile(fpath)
            else: messagebox.showerror("Not Found", f"File not found: {rec.get('file', '')}", parent=win)

        def reprint_selected():
            rec = _sel_rec()
            if not rec: return
            try: self.reprint_receipt_record(rec)
            except Exception as e: messagebox.showerror("Error", str(e), parent=win)

        def open_folder():
            rec = _sel_rec()
            p = rec.get("path", "") if rec else ""
            target = os.path.dirname(p) if p and os.path.exists(p) else day_folder
            if target and os.path.isdir(target): os.startfile(target)

        def open_day_summary():
            if not day_folder: return
            pdfs = sorted(glob.glob(os.path.join(day_folder, "Samary_*.pdf")))
            if pdfs: os.startfile(pdfs[0])
            else: messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا يوجد ملخص لهذا اليوم.", "No summary for this day."), parent=win)

        def cancel_selected():
            rec = _sel_rec()
            if not rec: return
            if rec.get("is_void"):
                messagebox.showinfo(tr("done"), tr("void_already"), parent=win)
                return
            idx = records.index(rec)
            msg = tr("void_confirm_msg", idx=idx + 1, amt=rec['amount'])
            if messagebox.askyesno(tr("void_confirm_title"), msg, parent=win):
                self.void_selected_record(rec, refresh)

        def restore_selected_void():
            rec = _sel_rec()
            if not rec: return
            if not rec.get("is_void"):
                messagebox.showinfo(tr("done"), tr("restore_already"), parent=win)
                return
            idx = records.index(rec)
            msg = tr("restore_confirm_msg", idx=idx + 1, amt=rec['amount'])
            if messagebox.askyesno(tr("restore_confirm_title"), msg, parent=win):
                self.unvoid_selected_record(rec, refresh)

        def export_day_excel():
            try: dd_ = datetime.date.fromisoformat(day_iso)
            except Exception: return
            p_ = archive_write_day_excel(day_folder, dd_, list(records))
            if p_ and os.path.exists(p_): os.startfile(p_)
            else: messagebox.showerror(T2("خطأ", "Error"), T2("تعذر إنشاء الإكسيل (اتأكد إنه مش مفتوح).", "Could not build the Excel (make sure it is not open)."), parent=win)

        def _b(text, color, hover, cmd, w=115):
            ctk.CTkButton(btn_row, text=text, font=FONT_BTN_SUB, fg_color=color, hover_color=hover,
                          text_color="#FFFFFF", width=w, height=30, command=cmd).pack(side="left", padx=(0, 6), pady=2)

        _b(tr("open_pdf_btn"), t["primary"], t["primary_hover"], open_selected)
        _b(tr("btn_reprint"), "#D97706", "#B45309", reprint_selected, 105)
        _b(T2("📂 فتح الفولدر", "📂 Open folder"), "#4338CA", "#3730A3", open_folder, 125)
        if live:
            _b(tr("btn_void_sel"), "#991B1B", "#7F1D1D", cancel_selected, 110)
            _b(tr("btn_restore_sel"), "#0F766E", "#115E59", restore_selected_void)
        else:
            _b(T2("📄 ملخص اليوم", "📄 Day summary"), "#0F766E", "#115E59", open_day_summary, 125)
            _b(T2("📊 إكسيل اليوم", "📊 Day Excel"), "#059669", "#047857", export_day_excel, 125)

        ctk.CTkLabel(win, text=T2("🟥 مكرر   🟨 ناقص   🟧 وحدة أخرى   ⬛ ملغي (مخصوم)   •   دبل كليك لفتح الإيصال",
                                  "🟥 Duplicate   🟨 Incomplete   🟧 Other unit   ⬛ Void   •   double-click to open receipt"),
                     font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(anchor="w", padx=16)

        tree_frame = ctk.CTkFrame(win, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(2, 14))

        columns = ("idx", "unit", "plate", "insured", "amount", "time", "make", "model", "chassis", "motor", "period", "file", "status")
        headers = {
            "idx": tr("col_idx"), "unit": tr("col_unit"), "plate": tr("col_plate"),
            "insured": tr("col_insured"), "amount": tr("col_amount"), "time": tr("col_time"),
            "make": tr("col_make"), "model": tr("col_model"), "chassis": tr("col_chassis"),
            "motor": tr("col_motor"), "period": tr("col_period"), "file": tr("col_file"), "status": tr("col_status")
        }

        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception as _e: _log_silent("_records_window#2", _e)
        style.configure("A2R.Treeview", background=t["input"], foreground=t["text"],
                        fieldbackground=t["input"], font=(FONT_FAMILY, 10, "bold"), rowheight=30)
        style.configure("A2R.Treeview.Heading", background=t["card"], foreground=t["accent"],
                        font=(FONT_FAMILY, 11, "bold"), relief="flat")

        def _fixed(option):
            try:
                return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]
            except Exception: return []
        style.map("A2R.Treeview", background=[("selected", t["primary"])] + _fixed("background"),
                  foreground=[("selected", "#FFFFFF")] + _fixed("foreground"))

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style="A2R.Treeview")

        sort_directions = {}
        def sort_by(col):
            reverse = sort_directions.get(col, False)
            sort_directions[col] = not reverse
            if col == "amount":
                records.sort(key=lambda r: float(r["amount"]), reverse=reverse)
            elif col in ("idx", "time"):
                records.sort(key=lambda r: r.get("dt_key") or datetime.datetime.min, reverse=reverse)
            else:
                k = "status_text" if col == "status" else col
                records.sort(key=lambda r: str(r.get(k, "")), reverse=reverse)
            refresh()

        _COL_W = {"idx": 42, "unit": 125, "plate": 120, "insured": 190, "amount": 85, "time": 135, "make": 85,
                  "model": 85, "chassis": 140, "motor": 105, "period": 185, "file": 190, "status": 125}
        for col in columns:
            tree.heading(col, text=headers.get(col, col), command=lambda c=col: sort_by(c))
            tree.column(col, width=_COL_W.get(col, 90), anchor="center", stretch=(col in ("insured", "file")))

        for kind, (bg, fg) in TAG_COLORS[t["mode"]].items():
            tree.tag_configure(kind, background=bg, foreground=fg)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        vsb.pack(side="right", fill="y", padx=2, pady=2)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        hsb.pack(side="bottom", fill="x", padx=2, pady=2)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        tree.bind("<Double-1>", lambda e: open_selected())

        row_menu = tk.Menu(tree, tearoff=0)
        row_menu.add_command(label=tr("menu_open_file"), command=open_selected)
        row_menu.add_command(label=tr("menu_reprint"), command=reprint_selected)
        row_menu.add_command(label=T2("📂 فتح الفولدر", "📂 Open folder"), command=open_folder)
        if live:
            row_menu.add_separator()
            row_menu.add_command(label=tr("menu_void_tx"), command=cancel_selected)
            row_menu.add_command(label=tr("menu_restore_tx"), command=restore_selected_void)

        def show_row_menu(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                row_menu.tk_popup(event.x_root, event.y_root)

        tree.bind("<Button-3>", show_row_menu)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Control-f>", lambda e: search_entry.focus_set())

        def refresh(*_):
            q = search_entry.get().strip().lower()
            aq = amt_entry.get().strip().replace(",", "")
            kinds = status_map.get(cb_status.get())
            tree.delete(*tree.get_children())
            shown = 0
            shown_valid_sum = 0.0
            counted = counted_ids(records)

            for i, r in enumerate(records):
                if kinds and r.get("kind") not in kinds: continue
                amt_str = f"{r['amount']:.2f}"
                if aq and aq not in amt_str: continue
                if q:
                    full_s = f"{r['unit']} {r['plate']} {r['insured']} {r['time']} {r['chassis']} {r['motor']} {r['make']} {r['model']} {r['file']} {r['status_text']}".lower()
                    if q not in full_s: continue

                vals = (i + 1, r["unit"], r["plate"], r["insured"], amt_str, r["time"],
                        r["make"], r["model"], r["chassis"], r["motor"], r["period"], r["file"], r["status_text"])
                tag = r["kind"] if r["kind"] in ("dup", "void", "missing", "wrong") else ""
                tree.insert("", "end", iid=str(i), values=vals, tags=(tag,) if tag else ())
                shown += 1
                if id(r) in counted:
                    shown_valid_sum += r["amount"]

            tot, cnt = counted_totals(records)
            card_lbls["total"].configure(text=f"{tot:,.2f}")
            card_lbls["count"].configure(text=f"{cnt:,}")
            card_lbls["shown"].configure(text=f"{shown_valid_sum:,.2f}")
            card_lbls["void"].configure(text=str(sum(1 for r in records if r.get("is_void"))))
            card_lbls["dup"].configure(text=str(sum(1 for r in records if r.get("kind") == "dup")))
            count_lbl.configure(text=T2(f"المعروض: {shown:,} سجل", f"Showing: {shown:,} rows"))

        search_entry.bind("<KeyRelease>", refresh)
        amt_entry.bind("<KeyRelease>", refresh)
        refresh()

    def show_custom_summary(self, unit_display_name, total_sum, total_cnt, pdf_count, manual_count, date_label, duplicates=0, wrong=0, missing=0):
        t = THEMES[self.current_theme_name]
        modal = ctk.CTkToplevel(self)
        modal.title(tr("summary_title"))
        modal.resizable(False, False)
        set_window_icon_safe(modal)
        center_window_relative(modal, self, 440, 420)
        modal.configure(fg_color=t["bg"])

        hdr = ctk.CTkFrame(modal, corner_radius=0, height=42, fg_color=t["card"])
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=f"📊  {tr('summary_title')}", font=(FONT_FAMILY, 13, "bold"), text_color=t["accent"]).pack(side="left", padx=14, pady=6)

        card_box = ctk.CTkFrame(modal, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        card_box.pack(fill="both", expand=True, padx=14, pady=10)

        row_u = ctk.CTkFrame(card_box, fg_color="transparent")
        row_u.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(row_u, text=tr("unit_name_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left")

        clean_opts = []
        if unit_display_name: clean_opts.append(clean_arabic(unit_display_name))
        for u in UNIT_NAMES + UNITS_LIST:
            cu = clean_arabic(u)
            if cu not in clean_opts: clean_opts.append(cu)

        def _unit_changed(val):
            if self.last_summary_info is not None:
                self.last_summary_info["unit"] = val

        cb_unit = SafeArabicComboBox(row_u, values=clean_opts, width=200, height=30, font=FONT_REGULAR_BOLD,
                                     fg_color=t["input"], border_color=t["border"], text_color=t["text"],
                                     command=_unit_changed)
        cb_unit.set(clean_arabic(unit_display_name))
        cb_unit.pack(side="right")

        void_cnt = self.last_summary_info.get("void_count", 0)
        void_amt = self.last_summary_info.get("void_sum", 0.0)

        details = [
            (tr("period_lbl"), date_label, t["text"], 12),
            (tr("total_ops_lbl"), f"{total_cnt:,}", t["text"], 13),
            (tr("pdf_lbl"), f"{pdf_count:,}", t["accent"], 12),
            (tr("txt_lbl"), f"{manual_count:,}", t["success"], 12),
            (tr("void_ops_lbl"), f"{void_cnt:,}  (-{void_amt:,.2f} {tr('currency')})", t["danger"], 12),
        ]
        if duplicates: details.append((tr("duplicates_lbl"), f"{duplicates}", t["danger"], 12))
        if wrong: details.append((tr("wrong_lbl"), f"{wrong}", t["warning"], 12))
        details.append((tr("total_amt_lbl"), f"{total_sum:,.2f} {tr('currency')}", t["success"], 16))

        for lbl_t, val_t, val_c, val_sz in details:
            row = ctk.CTkFrame(card_box, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=lbl_t, font=(FONT_FAMILY, 11, "bold"), text_color=t["text"]).pack(side="left")
            ctk.CTkLabel(row, text=val_t, font=(FONT_FAMILY, val_sz, "bold"), text_color=val_c).pack(side="right")

        b_bar = ctk.CTkFrame(modal, fg_color="transparent")
        b_bar.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkButton(b_bar, text="Close", width=70, height=32, font=FONT_BTN_SUB, fg_color=t["border"],
                      hover_color=t["card"], text_color=t["text"], command=modal.destroy).pack(side="right", padx=(4, 0))

        ctk.CTkButton(b_bar, text=tr("export_pdf"), width=90, height=32, font=FONT_BTN_SUB, fg_color=t["primary"],
                      hover_color=t["primary_hover"], text_color="#FFFFFF", command=lambda: self.export_pdf_summary(parent=modal)).pack(side="right", padx=4)

        if self.is_supervisor:
            ctk.CTkButton(b_bar, text=tr("open_excel"), width=95, height=32, font=FONT_BTN_SUB, fg_color=t["success"],
                          hover_color=t["primary_hover"], text_color="#FFFFFF",
                          command=lambda: [modal.destroy(), self.open_excel()]).pack(side="right")

    def reopen_summary_modal(self):
        if not self.last_summary_info:
            messagebox.showinfo("Notice", tr("no_summary_yet"))
            return
        info = self.last_summary_info
        self.show_custom_summary(info["unit"], info["total_sum"], info["total_count"],
                                 info["pdf_count"], info["manual_count"], info["date_label"], info["duplicates"],
                                 info.get("wrong_count", 0), info.get("missing_count", 0))

    def open_manual(self):
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(tr("manual_win_title"))
        win.resizable(False, False)
        center_window_relative(win, self, 380, 340)
        win.configure(fg_color=t["bg"])

        ctk.CTkLabel(win, text=tr("manual_amt_lbl"), font=FONT_SECTION_LBL, text_color=t["warning"]).pack(anchor="w", padx=18, pady=(12, 2))
        e_a = ctk.CTkEntry(win, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"], height=32)
        e_a.pack(fill="x", padx=18)
        attach_context_menu(e_a)

        ctk.CTkLabel(win, text=tr("manual_name_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=18, pady=(6, 2))
        e_name = ctk.CTkEntry(win, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"], height=32)
        e_name.pack(fill="x", padx=18)
        attach_context_menu(e_name)

        ctk.CTkLabel(win, text=tr("manual_plate_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=18, pady=(6, 2))
        e_p = ctk.CTkEntry(win, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"], height=32)
        e_p.pack(fill="x", padx=18)
        attach_context_menu(e_p)

        ctk.CTkLabel(win, text=tr("manual_unit_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=18, pady=(6, 2))
        cb_u = SafeArabicComboBox(win, values=[""] + UNITS_LIST, font=FONT_REGULAR_BOLD, fg_color=t["input"], border_color=t["border"], height=32)
        cb_u.set("")
        cb_u.pack(fill="x", padx=18)
        attach_context_menu(cb_u)

        busy = [False]   # منع الضغط المتكرر (Enter مرتين أو دبل كليك) أثناء الإنشاء والطباعة

        def save(event=None):
            if busy[0]:
                return
            busy[0] = True
            try: btn_gen.configure(state="disabled")
            except Exception as _e: _log_silent("manual_save_btn", _e)
            done = False
            try:
                amt = parse_manual_amount(e_a.get())
                if amt is None:
                    if e_a.get().strip():
                        messagebox.showwarning("Error", "Invalid amount", parent=win)
                    return
                dest = self.get_clean_path()
                file_base, now_dt = unique_manual_filename(dest, amt, datetime.datetime.now())
                t_stamp = now_dt.strftime("%H%M%S")
                date_tag = now_dt.strftime("%d-%m-%Y")
                full_path = os.path.join(dest, file_base)

                u_val = cb_u.get().strip() or "-"
                p_val = e_p.get().strip() or "-"
                n_val = e_name.get().strip() or "-"

                if not REPORTLAB_AVAILABLE:
                    messagebox.showerror("Error", "ReportLab is not installed!", parent=win)
                    return

                self.printed_receipts_set.add(file_base)
                create_manual_receipt_pdf(full_path, u_val, p_val, n_val, amt, op_dt=now_dt)
                db_ok = True
                try:
                    conn = db_connect()
                    try:
                        conn.execute("INSERT INTO manual_tx (unit, plate, insured, amount, created_at, file_name) VALUES (?, ?, ?, ?, ?, ?)",
                                     (u_val, p_val, n_val, amt, f"{date_tag} {t_stamp}", file_base))
                        conn.commit()
                    finally:
                        conn.close()
                except Exception as ex_db:
                    db_ok = False
                    log_exception("insert_vault", ex_db)
                if not db_ok:
                    messagebox.showwarning("Warning", "The receipt was created, but its details (unit / plate / name) "
                                                      "could not be saved. See app_log.txt.", parent=win)

                if self.auto_print_enabled:
                    self.send_to_thermal_printer_57x90(full_path)

                try: os.startfile(full_path)
                except Exception as _e: _log_silent("save#1", _e)
                done = True
                win.destroy()
            except Exception as ex_save:
                messagebox.showerror("Error", f"Failed to generate manual receipt:\n{str(ex_save)}", parent=win)
            finally:
                if not done:
                    busy[0] = False
                    try: btn_gen.configure(state="normal")
                    except Exception as _e: _log_silent("manual_save_btn2", _e)

        e_a.bind("<Return>", save)
        btn_gen = ctk.CTkButton(win, text=tr("manual_generate_btn"), font=FONT_BTN_MAIN, fg_color=t["success"],
                                hover_color=t["primary_hover"], text_color="#FFFFFF", height=36, command=save)
        btn_gen.pack(fill="x", padx=18, pady=16)
        win.after(100, lambda: e_a.focus_set())

    def print_slip(self):
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(tr("slip_dialog_title"))
        win.resizable(False, False)
        center_window_relative(win, self, 340, 285)
        win.configure(fg_color=t["bg"])

        ctk.CTkLabel(win, text=tr("slip_name_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(12, 2))

        cb_employee = SafeArabicComboBox(win, values=[""] + EMPLOYEES_LIST, font=FONT_REGULAR_BOLD, height=32,
                                         fg_color=t["input"], border_color=t["border"])
        cb_employee.set("")
        cb_employee.pack(fill="x", padx=16)
        attach_context_menu(cb_employee)

        ctk.CTkLabel(win, text=tr("slip_unit_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(6, 2))
        cb_u = SafeArabicComboBox(win, values=[""] + UNITS_LIST, font=FONT_REGULAR_BOLD, height=32, fg_color=t["input"], border_color=t["border"])
        cb_u.set("")
        cb_u.pack(fill="x", padx=16)
        attach_context_menu(cb_u)

        lbl_tid = ctk.CTkLabel(win, text="", font=FONT_REGULAR_BOLD, text_color=t["text"])
        lbl_tid.pack(anchor="w", padx=16, pady=(6, 0))

        def _update_tid(*_):
            tid = UNIT_TERMINALS.get(cb_u.get().strip(), "")
            lbl_tid.configure(text=f"Terminal ID: {tid}" if tid else "")

        cb_u._user_command = lambda raw: _update_tid()
        cb_u.bind("<KeyRelease>", _update_tid)

        def do_p(event=None):
            emp_val = cb_employee.get().strip()
            unit_val = cb_u.get().strip()
            tid_val = UNIT_TERMINALS.get(unit_val, "")
            date_val = datetime.date.today().strftime('%d/%m/%Y')
            
            pdf_path = os.path.join(DOCUMENTS_DIR, "Copy_Slip.pdf")
            if create_photocopy_slip_pdf(pdf_path, emp_val, unit_val, date_val, tid_val):
                sumatra_path = os.path.join(BASE_DIR, "SumatraPDF.exe")
                if not os.path.exists(sumatra_path):
                    sumatra_path = os.path.join(BUNDLE_DIR, "SumatraPDF.exe")
                
                if os.path.exists(sumatra_path):
                    cmd = [
                        sumatra_path,
                        "-print-to-default",
                        "-print-settings", "paper=57 x 90 mm,shrink",
                        "-silent",
                        pdf_path
                    ]
                    subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0, timeout=90)
                else:
                    if sys.platform == "win32": os.startfile(pdf_path, "print")
            else:
                txt_path = os.path.join(DOCUMENTS_DIR, "Copy_Slip.txt")
                lines = [l for l in [emp_val, unit_val, (f"TID: {tid_val}" if tid_val else ""), date_val] if l]
                with open(txt_path, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
                if sys.platform == "win32": os.startfile(txt_path, "print")
            win.destroy()

        cb_employee.bind("<Return>", do_p)
        ctk.CTkButton(win, text=tr("slip_btn_print"), font=FONT_BTN_MAIN, height=34, fg_color=t["warning"],
                      hover_color=t["primary_hover"], text_color="#FFFFFF", command=do_p).pack(fill="x", padx=16, pady=16)
        win.after(100, lambda: cb_employee.focus_set())

    def ask_summary_unit(self, parent=None):
        """نافذة صغيرة: اختيار الوحدة (إجباري) قبل عمل إيصال السمري. بترجّع (اسم الوحدة، رقم الترمنل) أو None لو اتقفلت."""
        t = THEMES[self.current_theme_name]
        parent = parent or self
        win = ctk.CTkToplevel(parent)
        win.title(T2("🏢 اختيار الوحدة", "🏢 Choose unit"))
        win.resizable(False, False)
        set_window_icon_safe(win)
        center_window_relative(win, parent, 340, 250)
        try: win.transient(parent)
        except Exception as _e: _log_silent("ask_summary_unit#0", _e)
        win.configure(fg_color=t["bg"])
        res = {"v": None}

        ctk.CTkLabel(win, text=T2("اختار الوحدة (إجباري):", "Choose the unit (required):"),
                     font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(14, 2))
        cb = SafeArabicComboBox(win, values=UNITS_LIST, font=FONT_REGULAR_BOLD, height=32,
                                fg_color=t["input"], border_color=t["border"], state="readonly")
        cb.set("")
        cb.pack(fill="x", padx=16)
        lbl_tid = ctk.CTkLabel(win, text="", font=FONT_REGULAR_BOLD, text_color=t["text"])
        lbl_tid.pack(anchor="w", padx=16, pady=(8, 0))
        msg = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 10, "bold"), text_color="#EF4444")
        msg.pack(anchor="w", padx=16, pady=(2, 0))

        def _update(*_):
            tid = UNIT_TERMINALS.get(cb.get().strip(), "")
            lbl_tid.configure(text=f"Terminal ID: {tid}" if tid else "")
            if tid: msg.configure(text="")
        cb._user_command = lambda raw: _update()

        def ok(event=None):
            u = cb.get().strip()
            if u not in UNIT_TERMINALS:
                msg.configure(text=T2("لازم تختار الوحدة الأول.", "You must choose a unit first."))
                return
            res["v"] = (u, UNIT_TERMINALS.get(u, ""))
            win.destroy()

        ctk.CTkButton(win, text=T2("✅ تأكيد وعمل الإيصال", "✅ Confirm & create receipt"), font=FONT_BTN_MAIN, height=34,
                      fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF",
                      command=ok).pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkButton(win, text=T2("إلغاء", "Cancel"), font=FONT_BTN_SUB, height=28, fg_color=t["border"],
                      hover_color=t["card"], text_color=t["text"], command=win.destroy).pack(fill="x", padx=16, pady=(0, 10))
        win.bind("<Return>", ok)
        try: win.lift(); win.grab_set()
        except Exception as _e: _log_silent("ask_summary_unit#1", _e)
        self.wait_window(win)
        return res["v"]

    def _refresh_archive_day_summary(self, day_iso):
        """لو اليوم ده متأرشف بالفعل، بيعيد عمل إيصال السمري بتاعه في الأرشيف عشان تظهر فيه الوحدة المختارة."""
        try:
            dd = datetime.date.fromisoformat(day_iso)
            folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
            day_dir = archive_day_dir(folder, dd)
        except Exception as e:
            log_exception("refresh_archive_day_summary#1", e)
            return
        if not os.path.isdir(day_dir): return
        def work():
            try:
                recs = archive_day_records(day_dir)
                if recs: self._generate_day_summary_pdf(day_dir, dd.strftime("%d-%m-%Y"), recs)
            except Exception as e:
                log_exception("refresh_archive_day_summary", e)
        threading.Thread(target=work, daemon=True).start()

    def export_pdf_summary(self, parent=None):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error", "ReportLab library required for PDF generation.")
            return
        if not self.last_summary_info or not self.last_generated_file:
            messagebox.showinfo("Notice", "No records available yet. Run extraction first!")
            return

        sel = self.ask_summary_unit(parent)          # اختيار الوحدة إجباري قبل عمل الإيصال
        if not sel: return
        chosen_unit, chosen_tid = sel
        day_iso = _day_iso_from_label((self.last_summary_info or {}).get("date_label", ""))
        if day_iso:
            summary_unit_save(day_iso, chosen_unit, chosen_tid)
            self._refresh_archive_day_summary(day_iso)

        pdf_path = os.path.splitext(self.last_generated_file)[0] + "_Summary.pdf"
        try:
            info = self.last_summary_info
            PAGE_W, PAGE_H = 226, 480
            c = canvas.Canvas(pdf_path, pagesize=(PAGE_W, PAGE_H))
            font_name = "Helvetica-Bold"

            for f_cand in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]:
                if os.path.exists(f_cand):
                    try:
                        pdfmetrics.registerFont(TTFont("ReceiptArabic", f_cand))
                        font_name = "ReceiptArabic"
                        break
                    except Exception as _e: _log_silent("export_pdf_summary#1", _e)

            def _ar(txt):
                try: return get_display(arabic_reshaper.reshape(str(txt)))
                except Exception: return str(txt)

            c.setStrokeColorRGB(0.15, 0.35, 0.55)
            c.setLineWidth(1.5)
            c.rect(6, 6, PAGE_W - 12, PAGE_H - 12)

            c.setFont(font_name, 15)
            c.setFillColorRGB(0.05, 0.25, 0.55)
            c.drawCentredString(PAGE_W / 2, PAGE_H - 32, _ar("إيصال ملخص الفحص"))
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.drawCentredString(PAGE_W / 2, PAGE_H - 52, f"A2R Operations Console {APP_VERSION}")

            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.line(14, PAGE_H - 64, PAGE_W - 14, PAGE_H - 64)

            y = PAGE_H - 92
            rows = [
                ("وحدة المرور", info.get('unit', '-')),
                ("تاريخ التقرير", info.get('date_label', '-')),
                ("إجمالي العمليات", f"{info.get('total_count', 0):,}"),
                ("إيصالات إلكترونية", f"{info.get('pdf_count', 0):,}"),
                ("معاملات يدوية", f"{info.get('manual_count', 0):,}"),
                ("معاملات ملغية", f"{info.get('void_count', 0):,}"),
            ]

            for lbl, val in rows:
                c.setFillColorRGB(0.94, 0.96, 0.98)
                c.rect(12, y - 6, PAGE_W - 24, 24, fill=True, stroke=False)
                c.setFont(font_name, 10)
                c.setFillColorRGB(0.25, 0.25, 0.25)
                c.drawRightString(PAGE_W - 18, y + 2, _ar(lbl))
                c.setFont(font_name, 11)
                c.setFillColorRGB(0.0, 0.0, 0.0)
                c.drawString(18, y + 2, _ar(val))
                y -= 30

            c.setFillColorRGB(0.08, 0.48, 0.28)
            c.roundRect(12, y - 18, PAGE_W - 24, 46, 5, fill=True, stroke=False)
            c.setFont(font_name, 11)
            c.setFillColorRGB(1, 1, 1)
            c.drawRightString(PAGE_W - 20, y + 8, _ar("إجمالي مبالغ السيستم:"))
            c.setFont("Helvetica-Bold", 15)
            c.drawCentredString(PAGE_W / 2, y - 9, f"{info.get('total_sum', 0):,.2f} EGP")

            _draw_summary_unit_block(c, font_name, _ar, PAGE_W, chosen_unit, chosen_tid)

            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.line(14, 46, PAGE_W - 14, 46)
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.35, 0.35, 0.35)
            c.drawCentredString(PAGE_W / 2, 30, f"Printed: {datetime.datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
            c.drawCentredString(PAGE_W / 2, 16, f"Alexandria • {APP_OWNER} • {APP_VERSION}")
            c.save()

            os.startfile(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def open_cash_counter(self):
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(tr("cash_win_title"))
        win.resizable(False, False)
        center_window_relative(win, self, 420, 500)
        win.configure(fg_color=t["bg"])

        ctk.CTkLabel(win, text=tr("cash_hdr"), font=(FONT_FAMILY, 15, "bold"), text_color=t["accent"]).pack(pady=(12, 4))
        f_quick = ctk.CTkFrame(win, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        f_quick.pack(fill="x", padx=16, pady=(4, 8))

        r_c = ctk.CTkFrame(f_quick, fg_color="transparent")
        r_c.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(r_c, text=tr("cash_manual_lbl"), width=150, anchor="w", font=(FONT_FAMILY, 11, "bold"), text_color=t["warning"]).pack(side="left")
        e_manual_cash = ctk.CTkEntry(r_c, width=130, height=30, justify="center", font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        e_manual_cash.pack(side="right")
        attach_context_menu(e_manual_cash)

        r_p = ctk.CTkFrame(f_quick, fg_color="transparent")
        r_p.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(r_p, text=tr("cash_pos_lbl"), width=150, anchor="w", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"]).pack(side="left")
        e_pos_in = ctk.CTkEntry(r_p, width=130, height=30, justify="center", font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        e_pos_in.pack(side="right")
        attach_context_menu(e_pos_in)

        frame_box = ctk.CTkFrame(win, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        frame_box.pack(fill="both", expand=True, padx=16, pady=2)

        denoms = [200, 100, 50, 20, 10, 5, 1]
        entries = {}

        lbl_tot_cash = ctk.CTkLabel(win, text=tr("cash_tot_lbl", sum=0), font=(FONT_FAMILY, 11, "bold"), text_color=t["success"])
        lbl_combined_total = ctk.CTkLabel(win, text=tr("cash_comb_lbl", sum=0), font=(FONT_FAMILY, 12, "bold"), text_color=t["text"])
        lbl_diff_sys = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 11, "bold"))
        current_calculated = [0.0, 0.0]

        def recalc(*_):
            c_sum = 0.0
            for d, ent in entries.items():
                v = ent.get().strip()
                if v.isdigit(): c_sum += int(v) * d

            manual_str = e_manual_cash.get().strip().replace(",", "")
            if manual_str:
                try: c_sum = float(manual_str)
                except Exception as _e: _log_silent("recalc#1", _e)

            current_calculated[0] = c_sum
            lbl_tot_cash.configure(text=tr("cash_tot_lbl", sum=c_sum))

            pos_val = 0.0
            pos_str = e_pos_in.get().strip().replace(",", "")
            if pos_str:
                try: pos_val = float(pos_str)
                except Exception as _e: _log_silent("recalc#2", _e)

            comb = c_sum + pos_val
            current_calculated[1] = comb
            lbl_combined_total.configure(text=tr("cash_comb_lbl", sum=comb))

            if self.system_total_sum > 0:
                diff = round(comb - self.system_total_sum, 2)
                if abs(diff) < 0.01: lbl_diff_sys.configure(text=tr("cash_matched_lbl"), text_color=t["success"])
                elif diff < 0: lbl_diff_sys.configure(text=tr("cash_short_lbl", val=abs(diff)), text_color=t["danger"])
                else: lbl_diff_sys.configure(text=tr("cash_extra_lbl", val=diff), text_color=t["warning"])
            else:
                lbl_diff_sys.configure(text="")

        e_manual_cash.bind("<KeyRelease>", recalc)
        e_pos_in.bind("<KeyRelease>", recalc)

        for d in denoms:
            r = ctk.CTkFrame(frame_box, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=1)
            ctk.CTkLabel(r, text=tr("cash_denom_lbl", d=d), width=90, anchor="w", font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(side="left")
            e = ctk.CTkEntry(r, width=85, height=22, justify="center", font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
            e.pack(side="right")
            e.bind("<KeyRelease>", recalc)
            attach_context_menu(e)
            entries[d] = e

        lbl_tot_cash.pack(pady=(4, 0))
        lbl_combined_total.pack(pady=(1, 0))
        lbl_diff_sys.pack(pady=(1, 6))

        def apply_and_close(event=None):
            if current_calculated[1] > 0:
                self.e_pos.delete(0, 'end')
                self.e_pos.insert(0, f"{current_calculated[1]:.2f}")
                self.check_pos()
            win.destroy()

        btn_apply = ctk.CTkButton(win, text=tr("cash_apply_btn"), font=FONT_BTN_MAIN,
                                  fg_color=t["success"], hover_color=t["primary_hover"], height=36, command=apply_and_close)
        btn_apply.pack(fill="x", padx=20, pady=(0, 12))
        win.bind("<Return>", apply_and_close)
        e_manual_cash.focus_set()

if __name__ == "__main__":
    app = CustomTkinterApp()
    app.mainloop()
