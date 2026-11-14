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

APP_VERSION = "v60-lite"
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



ctk.set_appearance_mode("Dark")
try:
    _tm = ctk.ThemeManager.theme
    for _w, _r in (("CTkButton", 8), ("CTkEntry", 8), ("CTkComboBox", 8), ("CTkOptionMenu", 8), ("CTkFrame", 12)):
        if _w in _tm and "corner_radius" in _tm[_w]: _tm[_w]["corner_radius"] = _r
except Exception:
    pass

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

# ── مقاس الطباعة ──────────────────────────────────────────────────────────────
# بيتحفظ في %APPDATA%\A2R\config.json (فولدر اليوزر نفسه) فمش محتاج صلاحيات أدمن، وكل يوزر له مقاسه.
# المقاس بيتبعت مع كل طباعة (SumatraPDF) بدل ما نغيّر إعدادات الطابعة في الويندوز (دي اللي كانت محتاجة أدمن).
DEFAULT_PRINT_PAPER_MM = (57, 90)
PRINT_PAPER_PRESETS_MM = [(57, 90), (80, 90)]
_PRINT_PAPER_MM = DEFAULT_PRINT_PAPER_MM
_PRINT_PAPER_NAME = ""   # اسم الورق زي ما الدرايفر معرّفه (لو اتختار من القايمة)

def _fmt_mm(v):
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:g}"

def _read_app_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def load_print_paper():
    global _PRINT_PAPER_MM
    try:
        v = _read_app_config().get("print_paper_mm")
        w, h = float(v[0]), float(v[1])
        if 20 <= w <= 300 and 20 <= h <= 600:
            _PRINT_PAPER_MM = (w, h)
            global _PRINT_PAPER_NAME
            _PRINT_PAPER_NAME = str(_read_app_config().get("print_paper_name") or "")
    except Exception as _e:
        _log_silent("load_print_paper#1", _e)

def save_print_paper(w, h, name=""):
    """بترجّع True لو اتحفظ في الملف. المقاس بيتطبّق فورًا حتى لو الحفظ فشل."""
    global _PRINT_PAPER_MM, _PRINT_PAPER_NAME
    _PRINT_PAPER_MM = (float(w), float(h))
    _PRINT_PAPER_NAME = (name or "").strip()
    try:
        d = _read_app_config()
        d["print_paper_mm"] = [float(w), float(h)]
        d["print_paper_name"] = _PRINT_PAPER_NAME
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONFIG_FILE)
        return True
    except Exception as e:
        log_exception("save_print_paper", e)
        return False

def print_paper_label():
    return f"{_fmt_mm(_PRINT_PAPER_MM[0])}x{_fmt_mm(_PRINT_PAPER_MM[1])}"

def print_settings_arg():
    name = _PRINT_PAPER_NAME or f"{_fmt_mm(_PRINT_PAPER_MM[0])} x {_fmt_mm(_PRINT_PAPER_MM[1])} mm"
    return f"paper={name},shrink"

def list_printer_papers():
    """مقاسات الورق اللي درايفر الطابعة الافتراضية بيدعمها: (اسم الطابعة, [(اسم الورق, عرض مم, طول مم)]).
    بتقرا من .NET PrinterSettings فمش محتاجة أدمن. بترجّع ("", []) لو فشلت."""
    if sys.platform != "win32":
        return "", []
    ps_cmd = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Add-Type -AssemblyName System.Drawing; "
        "$ps = New-Object System.Drawing.Printing.PrinterSettings; "
        "$items = @($ps.PaperSizes | ForEach-Object { [pscustomobject]@{n=$_.PaperName; w=$_.Width; h=$_.Height} }); "
        "$o = [pscustomobject]@{printer=$ps.PrinterName; papers=$items}; "
        "ConvertTo-Json -InputObject $o -Depth 3 -Compress"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        d = json.loads(r.stdout.decode("utf-8", "replace").strip())
        papers = d.get("papers") or []
        if isinstance(papers, dict):
            papers = [papers]
        out = []
        for it in papers:
            nm = str(it.get("n") or "").strip()
            w = float(it.get("w")) / 100.0 * 25.4   # PaperSize بالـ 1/100 بوصة
            h = float(it.get("h")) / 100.0 * 25.4
            if nm and w > 0 and h > 0:
                out.append((nm, round(w, 1), round(h, 1)))
        return str(d.get("printer") or ""), out
    except Exception as e:
        log_exception("list_printer_papers", e)
        return "", []
def set_default_printer_paper(w_mm, h_mm):
    """بتضبط مقاس الورق في إعدادات الطابعة الافتراضية لليوزر الحالي (UserPrintTicket): بدون أدمن.
    بترجّع dict فيه: ok, printer, w, h (المقاس الفعلي اللي الدرايفر قبله بالمم) أو err. بتتنفذ في thread مش في الواجهة."""
    if sys.platform != "win32":
        return {"ok": False, "err": "Windows required"}
    w96 = float(w_mm) / 25.4 * 96.0      # PageMediaSize بوحدة 1/96 بوصة
    h96 = float(h_mm) / 25.4 * 96.0
    ps_cmd = (
        "$ErrorActionPreference='Stop'; "
        "try { "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Add-Type -AssemblyName System.Printing; Add-Type -AssemblyName System.Drawing; "
        "$name = (New-Object System.Drawing.Printing.PrinterSettings).PrinterName; "
        "if (-not $name) { throw 'No default printer' }; "
        "$srv = New-Object System.Printing.LocalPrintServer; "
        "$q = New-Object System.Printing.PrintQueue($srv, $name, 1, [System.Printing.PrintSystemDesiredAccess]::UsePrinter); "
        "$new = New-Object System.Printing.PrintTicket; "
        f"$new.PageMediaSize = New-Object System.Printing.PageMediaSize([double]{w96:.3f}, [double]{h96:.3f}); "
        "$m = $q.MergeAndValidatePrintTicket($q.UserPrintTicket, $new); "
        "$q.UserPrintTicket = $m.ValidatedPrintTicket; "
        "$q.Commit(); $q.Refresh(); "
        "$r = $q.UserPrintTicket.PageMediaSize; "
        "ConvertTo-Json -Compress -InputObject @{ok=$true; printer=$name; w=[double]$r.Width; h=[double]$r.Height} "
        "} catch { ConvertTo-Json -Compress -InputObject @{ok=$false; err=$_.Exception.Message} }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        d = json.loads(r.stdout.decode("utf-8", "replace").strip())
        if d.get("ok"):
            d["w"] = round(float(d.get("w") or 0) / 96.0 * 25.4, 1)
            d["h"] = round(float(d.get("h") or 0) / 96.0 * 25.4, 1)
        else:
            log_exception("set_default_printer_paper", d.get("err"))
        return d
    except Exception as e:
        log_exception("set_default_printer_paper", e)
        return {"ok": False, "err": str(e)}

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

load_print_paper()

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
    "Modern Dark": {
        "mode": "Dark",
        "bg": "#0A0A0C", "card": "#131317", "sub_card": "#0F0F12",
        "border": "#26262C", "input": "#0C0C0F", "text": "#F4F4F5",
        "text_muted": "#9A9AA5", "primary": "#2563EB", "primary_hover": "#1D4ED8",
        "success": "#34D399", "danger": "#EF4444", "warning": "#F59E0B", "accent": "#60A5FA"
    },
    "Modern Light": {
        "mode": "Light",
        "bg": "#F4F4F5", "card": "#FFFFFF", "sub_card": "#FAFAFA",
        "border": "#E4E4E7", "input": "#FAFAFA", "text": "#18181B",
        "text_muted": "#71717A", "primary": "#2563EB", "primary_hover": "#1D4ED8",
        "success": "#16A34A", "danger": "#DC2626", "warning": "#D97706", "accent": "#2563EB"
    },
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
    "Modern Dark": {
        "secondary": ("#26262C", "#34343C"), "success_btn": ("#26262C", "#34343C"),
        "tool": ("#26262C", "#34343C"), "warn_btn": ("#26262C", "#34343C"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Modern Light": {
        "secondary": ("#52525B", "#3F3F46"), "success_btn": ("#52525B", "#3F3F46"),
        "tool": ("#52525B", "#3F3F46"), "warn_btn": ("#52525B", "#3F3F46"), "danger_btn": ("#DC2626", "#B91C1C")},
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
# توحيد الألوان: لون أساسي للأزرار المهمة، ولون هادي واحد لباقي الأزرار، وأحمر للخطر فقط
for _n, _r in _ROLE_BTN.items():
    for _k in ("success_btn", "tool", "warn_btn"):
        _r[_k] = _r["secondary"]
for _n, _roles in _ROLE_BTN.items():
    for _k, (_c, _h) in _roles.items():
        THEMES[_n][_k] = _c
        THEMES[_n][_k + "_hover"] = _h

# أي زر في أي دور (أسماء الـ attributes في النافذة الرئيسية)
BUTTON_ROLES = {
    "primary": ["btn_run", "btn_pos_check", "btn_browse"],
    "success_btn": ["btn_manual", "btn_cash", "btn_open_f", "btn_excel"],
    "tool": ["btn_summary_reopen", "btn_archive_downloads", "btn_mini_archive", "btn_chrome"],
    "warn_btn": ["btn_print_slip", "btn_fix_printer"],
    "secondary": ["btn_yesterday", "btn_today", "btn_view_rec", "btn_arch_full", "btn_lang", "btn_mute", "btn_back_to_mini", "btn_pdf_export"],
    "danger_btn": ["btn_elevate"],
}

TAG_COLORS = {
    "Dark": {
        "dup": ("#3B1219", "#FCA5A5"), "wrong": ("#3A1F0F", "#FDBA74"),
        "missing": ("#33290C", "#FDE68A"), "manual": ("#14263F", "#93C5FD"),
        "void": ("#1F1F24", "#8B8B96")
    },
    "Light": {
        "dup": ("#FFC7CE", "#9C0006"), "wrong": ("#F8CBAD", "#833C0B"),
        "missing": ("#FFEB9C", "#7F6000"), "manual": ("#DDEBF7", "#1F3864"),
        "void": ("#E5E7EB", "#4B5563")
    },
}

FONT_FAMILY = "Segoe UI"
FONT_TITLE_LOGO = (FONT_FAMILY, 16, "bold")
FONT_SECTION_LBL = (FONT_FAMILY, 9, "bold")
FONT_REGULAR_BOLD = (FONT_FAMILY, 10, "normal")
FONT_KPI_VAL = (FONT_FAMILY, 15, "bold")
FONT_BTN_MAIN = (FONT_FAMILY, 11, "bold")
FONT_BTN_SUB = (FONT_FAMILY, 10, "bold")
FONT_ENTRY = (FONT_FAMILY, 10, "normal")


def theme_btn_colors(t, kind="quiet"):
    """primary = الإجراء المهم | quiet = باقي الأزرار | danger = خطر (مسح/إلغاء)"""
    if kind == "primary": return t["primary"], t["primary_hover"]
    if kind == "danger": return t["danger_btn"], t["danger_btn_hover"]
    return t["secondary"], t["secondary_hover"]


def style_entry(w, t):
    try:
        w.configure(fg_color=t["input"], border_color=t["border"], text_color=t["text"], border_width=1, corner_radius=8)
    except Exception as _e: _log_silent("style_entry", _e)
    try: w.configure(placeholder_text_color=t["text_muted"])
    except Exception as _e: _log_silent("style_entry#ph", _e)


def style_combo(w, t):
    try:
        w.configure(fg_color=t["input"], border_color=t["border"], button_color=t["border"],
                    button_hover_color=t["primary"], text_color=t["text"], corner_radius=8,
                    dropdown_fg_color=t["card"], dropdown_text_color=t["text"], dropdown_hover_color=t["primary"])
    except Exception as _e: _log_silent("style_combo", _e)


def apply_tree_style(t, rowheight=30):
    """ستايل موحّد لكل الجداول (سجل الأرشيف + عرض السجلات): بدون حدود، عناوين أوضح، صفوف أعلى."""
    style = ttk.Style()
    try: style.theme_use("clam")
    except Exception as _e: _log_silent("apply_tree_style#1", _e)
    try: style.layout("A2R.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    except Exception as _e: _log_silent("apply_tree_style#2", _e)
    style.configure("A2R.Treeview", background=t["input"], foreground=t["text"], fieldbackground=t["input"],
                    font=(FONT_FAMILY, 10, "normal"), rowheight=rowheight, borderwidth=0, relief="flat")
    style.configure("A2R.Treeview.Heading", background=t["sub_card"], foreground=t["text_muted"],
                    font=(FONT_FAMILY, 9, "bold"), relief="flat", borderwidth=0, padding=(4, 5))
    style.map("A2R.Treeview.Heading", background=[("active", t["card"])])
    style.configure("Vertical.TScrollbar", background=t["border"], troughcolor=t["input"], bordercolor=t["input"],
                    arrowcolor=t["text_muted"], lightcolor=t["border"], darkcolor=t["border"], relief="flat")
    style.map("Vertical.TScrollbar", background=[("active", t["primary"])])
    style.configure("Horizontal.TScrollbar", background=t["border"], troughcolor=t["input"], bordercolor=t["input"],
                    arrowcolor=t["text_muted"], lightcolor=t["border"], darkcolor=t["border"], relief="flat")
    style.map("Horizontal.TScrollbar", background=[("active", t["primary"])])
    def _fixed(option):
        try: return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]
        except Exception: return []
    style.map("A2R.Treeview", background=[("selected", t["primary"])] + _fixed("background"),
              foreground=[("selected", "#FFFFFF")] + _fixed("foreground"))
    return style

LANGUAGES = {
    "en": {
        "toggle_btn": "🌐 عربي", "dir_path": "DIRECTORY PATH", "browse": "Browse", "open": "Open",
        "date_lbl": "REPORT DATE", "today": "Today", "yesterday": "Yesterday",
        "start": "⚡ START EXTRACTION", "reset": "Reset",
        "manual": "➕ Manual", "summary_btn": "📊 Summary", "print_slip": "🖨️ Photocopy", "arch_hist_btn": "📚 Archive History", "view_records": "🔍 Records Viewer",
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
        "manual": "➕ إضافة يدوي", "summary_btn": "📊 ملخص الفحص", "print_slip": "🖨️ إيصال تصوير", "arch_hist_btn": "📚 سجل الأرشيف", "view_records": "🔍 عرض السجلات",
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

# حجم موحد لنافذتي 🗂️ سجل الأرشيف و🔍 عرض السجلات: صغيرة في نص الشاشة، والمستخدم يكبّرها لما يحب
LOG_WIN_W, LOG_WIN_H = 1000, 600
LOG_WIN_MIN_W, LOG_WIN_MIN_H = 900, 460

def center_window_on_screen(win, width, height):
    """يوسّط النافذة في نص الشاشة (مش نسبةً للنافذة الرئيسية) من غير transient، فتفضل قابلة للتكبير/التصغير."""
    win.update_idletasks()
    set_window_icon_safe(win)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = min(width, sw - 40), min(height, sh - 110)
    win.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")

# ── تلميحات الأزرار + Esc لكل النوافذ + النوافذ بتفتكر حجمها ومكانها ─────────────────
class _Tooltip:
    """تلميح بيظهر لما الماوس يقف على الزر شوية. text ممكن يكون نص أو دالة بترجّع النص باللغة الحالية."""
    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self._job, self._tip = None, None
        for seq, fn in (("<Enter>", self._schedule), ("<Leave>", self._hide),
                        ("<ButtonPress>", self._hide), ("<Destroy>", self._hide)):
            try: widget.bind(seq, fn, add="+")
            except Exception as _e: _log_silent("tooltip#bind", _e)

    def _schedule(self, e=None):
        self._cancel()
        try: self._job = self.widget.after(self.delay, self._show)
        except Exception: self._job = None

    def _cancel(self):
        if self._job is not None:
            try: self.widget.after_cancel(self._job)
            except Exception as _e: _log_silent("tooltip#cancel", _e)
            self._job = None

    def _show(self):
        self._job = None
        if self._tip is not None: return
        try:
            txt = self.text() if callable(self.text) else self.text
            if not txt: return
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            try: tip.attributes("-topmost", True)
            except Exception as _e: _log_silent("tooltip#topmost", _e)
            tk.Label(tip, text=txt, justify="left", background="#1F2937", foreground="#F9FAFB",
                     relief="solid", borderwidth=1, font=(FONT_FAMILY, 9), padx=6, pady=3).pack()
            tip.update_idletasks()
            x = min(self.widget.winfo_pointerx() + 12, tip.winfo_screenwidth() - tip.winfo_reqwidth() - 4)
            y = self.widget.winfo_pointery() + 18
            tip.wm_geometry(f"+{max(0, x)}+{y}")
            self._tip = tip
        except Exception as e: _log_silent("tooltip#show", e)

    def _hide(self, e=None):
        self._cancel()
        if self._tip is not None:
            try: self._tip.destroy()
            except Exception as _e: _log_silent("tooltip#hide", _e)
            self._tip = None

def add_tooltip(widget, text):
    """بيضيف تلميح للزر (مرة واحدة بس لكل زر). text = نص أو دالة بترجّع النص."""
    try:
        if widget is None or getattr(widget, "_a2r_tip", None) is not None: return
        widget._a2r_tip = _Tooltip(widget, text)
    except Exception as e: _log_silent("add_tooltip", e)

def close_toplevel_gracefully(win):
    """بيقفل النافذة بنفس طريقة زر X: لو ليها WM_DELETE_WINDOW مخصوص بينفّذه، وإلا destroy."""
    try: cmd = win.protocol("WM_DELETE_WINDOW")
    except Exception: cmd = ""
    try:
        if cmd: win.tk.call(cmd)
        else: win.destroy()
    except Exception as e:
        _log_silent("close_toplevel", e)
        try: win.destroy()
        except Exception as _e: _log_silent("close_toplevel#destroy", _e)

def _saved_win_geom(key):
    try:
        g = (_read_app_config().get("win_geom") or {}).get(key)
        if isinstance(g, list) and len(g) == 4: return [int(v) for v in g]
    except Exception as e: _log_silent("saved_win_geom", e)
    return None

def _save_win_geom(key, geom):
    try:
        d = _read_app_config()
        wg = d.get("win_geom") if isinstance(d.get("win_geom"), dict) else {}
        wg[key] = [int(v) for v in geom]
        d["win_geom"] = wg
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONFIG_FILE)
    except Exception as e: log_exception("save_win_geom", e)

def remember_window_geometry(win, key):
    """بيرجّع النافذة لآخر حجم ومكان اتقفلت عليهم (جوه حدود الشاشة)، وبيحفظهم تاني لما تتقفل.
    بيتخزن في %APPDATA%\\A2R\\config.json تحت win_geom لكل يوزر. لازم يتنده بعد ما الحجم الافتراضي يتحط."""
    try:
        saved = _saved_win_geom(key)
        if saved:
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            try: sc = float(win._get_window_scaling()) or 1.0
            except Exception: sc = 1.0
            w, h, x, y = saved
            w = max(300, min(w, int((sw - 20) / sc)))
            h = max(200, min(h, int((sh - 60) / sc)))
            x = max(0, min(x, sw - int(w * sc)))
            y = max(0, min(y, sh - int(h * sc) - 40))
            win.geometry(f"{w}x{h}+{x}+{y}")
        last = {"g": None}

        def _track(e):
            if e.widget is not win: return
            try:
                if win.state() != "normal" or win.attributes("-fullscreen"): return
                nums = [int(n) for n in re.findall(r"-?\d+", win.geometry())]
                if len(nums) == 4: last["g"] = nums
            except Exception as _e: _log_silent("remember_geom#track", _e)

        def _flush(e):
            if e.widget is win and last["g"]: _save_win_geom(key, last["g"])

        win.bind("<Configure>", _track, add="+")
        win.bind("<Destroy>", _flush, add="+")
    except Exception as e: _log_silent("remember_window_geometry", e)

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

# عرض لفة الورق الفعلي في الطابعة (مم) لإيصال المعاملة اليدوية وبون التصوير: 80 للفة 80 مم، 57 للفة 57 مم.
# الإيصال الأساسي (quote_receipt) مش بيتأثر بالرقم ده.
PRINT_ROLL_W_MM = 80

def create_manual_receipt_pdf(filepath, unit_val, plate_val, name_val, amt_val, op_dt=None):
    if not REPORTLAB_AVAILABLE:
        raise Exception("ReportLab is not installed!")
    op_dt = op_dt or datetime.datetime.now()
    PAGE_W, PAGE_H = 160, 240          # مقاس التصميم؛ بيتكبّر بنفس النسبة ليملا عرض اللفة
    _k = (PRINT_ROLL_W_MM * 72 / 25.4) / PAGE_W if PRINT_ROLL_W_MM else 1.0
    c = canvas.Canvas(filepath, pagesize=(PAGE_W * _k, PAGE_H * _k))
    c.scale(_k, _k)
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

SLIP_MARGIN_MM = 2       # المسافة بين إطار البون وحافة الورقة (مم). صغّرها لو عايز الإطار أقرب للحافة
SLIP_TEXT_SCALE = 1.0    # تكبير/تصغير النصوص كلها (1.0 = المقاس الافتراضي الكبير)
SLIP_LINE_FACTOR = 1.0   # ارتفاع السطر = حجم الخط × الرقم ده
SLIP_GAP_FACTOR = 0.10   # المسافة بين الأسطر (نسبة من ارتفاع السطر). صغّرها/كبّرها لتقصير/تطويل الورقة
SLIP_PAD_PT = 8          # مسافة بين الكلام وإطار البون من فوق وتحت (نقطة)
SLIP_MAX_H_MM = 0        # حد أقصى لطول الورقة بالمم (0 = من غير حد)
SLIP_OFFSET_X_MM = 0     # لو الطابعة بتزحزح البون: + يمين / - شمال
SLIP_OFFSET_Y_MM = 0     # + لفوق / - لتحت
SLIP_FONT_CANDIDATES = [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]

def create_photocopy_slip_pdf(filepath, emp_name, unit_name, date_str, terminal_id=""):
    """بون التصوير: عرض الورقة = عرض اللفة، وطولها بيتحسب من الكلام نفسه (ورقة صغيرة) والنصوص كبيرة تملا العرض."""
    if not REPORTLAB_AVAILABLE:
        return False
    _pt = 72 / 25.4
    SHEET_W = _PRINT_PAPER_MM[0] * _pt
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

    m = SLIP_MARGIN_MM * _pt
    fw = SHEET_W - 2 * m                             # عرض الإطار
    inner_w = fw - 2 * 10
    K = SLIP_TEXT_SCALE

    def _fit_text(text, fn, base, min_single):
        base, min_single = base * K, min_single * K
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
        fitted += _fit_text(emp_name, font_name, 34, 22)
    if unit_name:
        fitted += _fit_text(unit_name, font_name, 28, 20)
    if terminal_id:
        fitted += _fit_text(f"TID: {terminal_id}", "Helvetica-Bold", 26, 14)
    fitted += _fit_text(str(date_str), "Helvetica-Bold", 26, 14)

    # طول الورقة = الكلام + مسافات صغيرة بين الأسطر + هامش (ورقة صغيرة مش بتكبر)
    heights = [sz * SLIP_LINE_FACTOR for _, _, sz in fitted]
    n = len(fitted)
    gap = (sum(heights) / n) * SLIP_GAP_FACTOR if n else 0
    block_h = sum(heights) + gap * max(0, n - 1)
    fh = block_h + 2 * SLIP_PAD_PT                   # ارتفاع الإطار
    SHEET_H = fh + 2 * m
    if SLIP_MAX_H_MM:
        SHEET_H = min(SHEET_H, SLIP_MAX_H_MM * _pt)
        fh = SHEET_H - 2 * m

    c = canvas.Canvas(filepath, pagesize=(SHEET_W, SHEET_H))
    ox, oy = SLIP_OFFSET_X_MM * _pt, SLIP_OFFSET_Y_MM * _pt
    fx, fy = m + ox, m + oy
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(2.2)
    c.roundRect(fx, fy, fw, fh, 12, stroke=1, fill=0)

    cursor = fy + fh / 2 + block_h / 2
    c.setFillColorRGB(0, 0, 0)
    for (txt, fn, sz), h in zip(fitted, heights):
        c.setFont(fn, sz)
        c.drawCentredString(fx + fw / 2, cursor - sz * 0.9, txt)
        cursor -= h + gap
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

def archive_maintenance(folder_path, progress=None, full=True):
    """فهرسة + نسخ احتياطي. لو في عملية شغالة بالفعل بترجع None ومش بتتكرر.
    full=False: فهرسة بس (للفتح السريع لنافذة الأرشيف) من غير نسخ احتياطي ولا بناء إكسيلات."""
    if not _ARCHIVE_LOCK.acquire(blocking=False): return None
    try:
        n = archive_index_update(folder_path, progress)
        b = archive_backup(folder_path) if full else 0
        try: _archive_search_rows()
        except Exception as e: log_exception("archive_search_warm", e)
        if full:
            try: archive_backfill_excels(folder_path)     # أي يوم مؤرشف ملوش إكسيل يتبني أوتوماتيك (الموجود بيتخطى)
            except Exception as e: log_exception("archive_maintenance_excels", e)
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

def archive_search(query, include_void=True, limit=3000, min_day=""):
    q = _norm_search(query)
    if not q: return []
    amt = None
    try: amt = float(str(query).strip().replace(",", ""))
    except Exception as _e: _log_silent("archive_search#1", _e)
    out = []
    for r, n_plate, n_insured, n_file in _archive_search_rows():
        path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void = r
        if is_void and not include_void: continue
        if min_day and day < min_day: continue   # وضع اليوزر: آخر أيام محددة بس
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

def archive_unread_by_day():
    """{يوم: عدد الملفات اللي الفهرس معرفش يقراها كإيصال} (ممكن تكون إيصالات فشلت قراءتها أو ملفات تانية)."""
    try:
        conn = _ensure_archive_index()
        try:
            return {d: c for d, c in conn.execute(
                "SELECT day, COUNT(*) FROM archive_index WHERE is_receipt = 0 GROUP BY day").fetchall()}
        finally:
            conn.close()
    except Exception as e:
        log_exception("archive_unread_by_day", e)
        return {}

def archive_all_days():
    try:
        conn = _ensure_archive_index()
        try:
            return [r[0] for r in conn.execute("SELECT DISTINCT day FROM archive_index ORDER BY day").fetchall()]
        finally:
            conn.close()
    except Exception as e:
        log_exception("archive_all_days", e)
        return []

def archive_reindex(folder_path, days=None, progress=None):
    """إعادة قراءة الإيصالات من الأول: بيمسح فهرس الأيام المحددة (days=None يعني كل الأيام) ويقرا الملفات تاني
    بالقارئ الحالي. الفهرس العادي بيتخطى أي ملف تاريخه وحجمه ما اتغيرش، فالأيام اللي اتسجلت غلط (مبلغ صفر)
    كانت بتفضل كده. بترجّع قاموس بالأعداد، أو None لو في فهرسة تانية شغالة ومخلصتش في 30 ثانية."""
    if not _ARCHIVE_LOCK.acquire(timeout=30): return None
    try:
        with _CACHE_LOCK:
            _PARSE_CACHE.clear()
        conn = _ensure_archive_index()
        try:
            if days is None:
                conn.execute("DELETE FROM archive_index")
            else:
                conn.executemany("DELETE FROM archive_index WHERE day = ?", [(d,) for d in days])
            conn.commit()
        finally:
            conn.close()
        n_read = archive_index_update(folder_path, progress)
        try: _archive_search_rows()
        except Exception as e: log_exception("archive_reindex_search_warm", e)

        conn = _ensure_archive_index()
        try:
            where, args = "", []
            if days is not None:
                if not days: return {"read": n_read, "unread": 0, "unread_files": [], "zero_amount": 0}
                where = " AND day IN (%s)" % ",".join("?" * len(days))
                args = list(days)
            unread_files = [r[0] for r in conn.execute(
                "SELECT path FROM archive_index WHERE is_receipt = 0" + where + " LIMIT 50", args).fetchall()]
            unread = conn.execute("SELECT COUNT(*) FROM archive_index WHERE is_receipt = 0" + where, args).fetchone()[0]
            zero_amt = conn.execute(
                "SELECT COUNT(*) FROM archive_index WHERE is_receipt = 1 AND is_void = 0 AND is_manual = 0 AND amount <= 0" + where,
                args).fetchone()[0]
        finally:
            conn.close()
        if unread_files:
            log_exception("archive_reindex_unread", "files not read as receipts: " + " | ".join(unread_files[:20]))
        return {"read": n_read, "unread": unread, "unread_files": unread_files, "zero_amount": zero_amt}
    finally:
        _ARCHIVE_LOCK.release()

import hashlib as _hl, hmac as _hm
import math as _math

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

def scale_pdf_to_print_width(src_pdf, target_w=None):
    """نسخة مؤقتة من الـ PDF مصغّرة لعرض 57 مم. الإيصالات بتتصمم بعرض 80 مم، وكان الحجم النهائي بيتحدد من
    مقاس الورق المعرّف في كل جهاز (fit): 57x90 بيطلّع الحجم الصح، و80 مم بيطلّعه كبير. دلوقتي البرنامج هو اللي
    بيحدد الحجم. بترجع None لو الصفحة أصلًا بعرض 57 مم أو أقل، أو لو pypdf مش متاح (وساعتها الطباعة زي ما كانت)."""
    if not PYPDF_AVAILABLE:
        return None
    if target_w is None:
        target_w = _PRINT_PAPER_MM[0] / 25.4 * 72   # عرض الورق المختار (بيتغيّر من زرار المقاس)
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
        self.current_theme_name = "Modern Dark"

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

    def _paper_btn_text(self):
        return f"⚙️ {print_paper_label()}"

    def fix_printer_paper_action(self):
        """بيفتح نافذة اختيار مقاس الطباعة. مفيش أي تعديل في إعدادات الويندوز/الطابعة، فبيشتغل لأي يوزر عادي."""
        old = getattr(self, "_paper_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift(); old.focus_force(); return
        except Exception as _e: _log_silent("fix_printer_paper_action#0", _e)

        self._cancel_auto_minimize()
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        self._paper_win = win
        win.title(T2("مقاس الطباعة", "Print Size"))
        win.resizable(False, False)
        center_window_relative(win, self, 360, 330)
        win.configure(fg_color=t["bg"])
        try: win.transient(self)
        except Exception as _e: _log_silent("fix_printer_paper_action#1", _e)

        ctk.CTkLabel(win, text=T2("مقاس ورقة الطباعة (مم)", "Paper size (mm)"),
                     font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(12, 4))

        f_pre = ctk.CTkFrame(win, fg_color="transparent")
        f_pre.pack(fill="x", padx=16)

        f_in = ctk.CTkFrame(win, fg_color="transparent")
        f_in.pack(fill="x", padx=16, pady=(10, 0))
        ctk.CTkLabel(f_in, text=T2("العرض", "Width"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left")
        e_w = ctk.CTkEntry(f_in, width=64, height=30, font=FONT_ENTRY, justify="center",
                           fg_color=t["input"], border_color=t["border"], text_color=t["text"])
        e_w.pack(side="left", padx=(6, 12))
        ctk.CTkLabel(f_in, text=T2("الطول", "Height"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left")
        e_h = ctk.CTkEntry(f_in, width=64, height=30, font=FONT_ENTRY, justify="center",
                           fg_color=t["input"], border_color=t["border"], text_color=t["text"])
        e_h.pack(side="left", padx=(6, 0))

        def _fill(w, h):
            e_w.delete(0, "end"); e_w.insert(0, _fmt_mm(w))
            e_h.delete(0, "end"); e_h.insert(0, _fmt_mm(h))

        _fill(*_PRINT_PAPER_MM)
        def _preset(a, b):
            sel["name"] = ""
            _fill(a, b)
        for (pw, ph) in PRINT_PAPER_PRESETS_MM:
            ctk.CTkButton(f_pre, text=f"{_fmt_mm(pw)} × {_fmt_mm(ph)}", width=90, height=28, font=FONT_BTN_SUB,
                          fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF",
                          command=lambda a=pw, b=ph: _preset(a, b)).pack(side="left", padx=(0, 6))

        sel = {"name": _PRINT_PAPER_NAME}
        papers_map = {}

        ctk.CTkLabel(win, text=T2("مقاسات الطابعة الافتراضية", "Default printer paper sizes"),
                     font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(10, 2))
        cb_papers = ctk.CTkComboBox(win, values=[T2("... بقرا المقاسات من الطابعة", "... reading printer sizes")],
                                    height=30, font=FONT_ENTRY, state="readonly",
                                    fg_color=t["input"], border_color=t["border"], text_color=t["text"])
        cb_papers.set(T2("... بقرا المقاسات من الطابعة", "... reading printer sizes"))
        cb_papers.pack(fill="x", padx=16)

        def _on_pick(choice):
            it = papers_map.get(choice)
            if it:
                sel["name"] = it[0]
                _fill(it[1], it[2])

        cb_papers.configure(command=_on_pick)

        def _manual_edit(event=None):
            sel["name"] = ""      # كتبت مقاس بإيدك: مفيش اسم ورق من الدرايفر
        e_w.bind("<KeyRelease>", _manual_edit)
        e_h.bind("<KeyRelease>", _manual_edit)

        def _load_papers():
            prn, items = list_printer_papers()
            def _apply():
                try:
                    if not win.winfo_exists():
                        return
                    if not items:
                        cb_papers.configure(values=[T2("مقدرتش أقرا مقاسات الطابعة", "Could not read printer sizes")])
                        cb_papers.set(T2("مقدرتش أقرا مقاسات الطابعة", "Could not read printer sizes"))
                        return
                    labels = []
                    for (nm, pw, ph) in items:
                        lab = f"{nm}  ({_fmt_mm(pw)}×{_fmt_mm(ph)})"
                        papers_map[lab] = (nm, pw, ph)
                        labels.append(lab)
                    cb_papers.configure(values=labels)
                    cur = next((l for l, v in papers_map.items() if v[0] == sel["name"]), "")
                    cb_papers.set(cur or (prn or T2("اختار مقاس", "Pick a size")))
                except Exception as _e: _log_silent("fix_printer_paper_action#4", _e)
            self.run_on_main(_apply)
        threading.Thread(target=_load_papers, daemon=True).start()

        lbl_err = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 9, "bold"), text_color="#EF4444")
        lbl_err.pack(anchor="w", padx=16, pady=(6, 0))
        ctk.CTkLabel(win, text=T2("المقاس بيتحفظ لليوزر الحالي وبيتطبّق على أي طباعة جاية.",
                                  "Saved for the current user and used for every next print."),
                     font=(FONT_FAMILY, 9), text_color=t["text_muted"], wraplength=300, justify="left").pack(anchor="w", padx=16)

        def _close():
            try: win.destroy()
            except Exception as _e: _log_silent("fix_printer_paper_action#2", _e)
            if getattr(self, "is_mini_mode", False):
                self._schedule_auto_minimize(5000)

        def _save(event=None):
            try:
                if btn_save.cget("state") == "disabled": return   # منع الضغط المتكرر (Enter) أثناء ضبط الطابعة
            except Exception as _e: _log_silent("fix_printer_paper_action#7", _e)
            try:
                w = float(e_w.get().strip().replace(",", "."))
                h = float(e_h.get().strip().replace(",", "."))
            except Exception:
                lbl_err.configure(text=T2("اكتب أرقام صحيحة للعرض والطول", "Enter valid numbers for width and height"))
                return
            if not (20 <= w <= 300 and 20 <= h <= 600):
                lbl_err.configure(text=T2("المقاس خارج المدى المسموح (العرض 20-300، الطول 20-600)",
                                          "Size out of range (width 20-300, height 20-600)"))
                return
            saved = save_print_paper(w, h, sel["name"])
            self.btn_fix_printer.configure(text=self._paper_btn_text())
            try: btn_save.configure(state="disabled", text=T2("⏳ بضبط إعدادات الطابعة...", "⏳ Setting printer..."))
            except Exception as _e: _log_silent("fix_printer_paper_action#5", _e)

            def _apply_printer():
                res = set_default_printer_paper(w, h)
                def _done():
                    try:
                        play_sound_matched()
                        if res.get("ok"):
                            aw, ah = res.get("w", 0), res.get("h", 0)
                            exact = abs(aw - w) <= 2 and abs(ah - h) <= 2
                            if exact:
                                msg = T2(f"تم ضبط الطابعة الافتراضية ({res.get('printer','')}) على {_fmt_mm(w)}×{_fmt_mm(h)} مم.",
                                         f"Default printer ({res.get('printer','')}) set to {_fmt_mm(w)}x{_fmt_mm(h)} mm.")
                                messagebox.showinfo(tr("done"), msg, parent=win)
                            else:
                                msg = T2(f"الطابعة ({res.get('printer','')}) قبلت مقاس مختلف: {_fmt_mm(aw)}×{_fmt_mm(ah)} مم بدل {_fmt_mm(w)}×{_fmt_mm(h)}.\n"
                                         f"الدرايفر مش بيدعم المقاس ده بالظبط.",
                                         f"Printer ({res.get('printer','')}) accepted a different size: {_fmt_mm(aw)}x{_fmt_mm(ah)} mm instead of {_fmt_mm(w)}x{_fmt_mm(h)}.\n"
                                         f"The driver does not support this exact size.")
                                messagebox.showwarning(tr("done"), msg, parent=win)
                        else:
                            msg = T2("المقاس اتحفظ في البرنامج لكن معرفتش أغيّر إعدادات الطابعة الافتراضية.\n"
                                     "اتأكد إن فيه طابعة افتراضية متوصلة، والتفاصيل في app_log.txt.",
                                     "Size saved in the app, but the default printer settings could not be changed.\n"
                                     "Make sure a default printer is connected. Details in app_log.txt.")
                            messagebox.showwarning(tr("done"), msg, parent=win)
                    except Exception as _e: _log_silent("fix_printer_paper_action#6", _e)
                    _close()
                self.run_on_main(_done)
            threading.Thread(target=_apply_printer, daemon=True).start()

        btn_save = ctk.CTkButton(win, text=T2("حفظ", "Save"), font=FONT_BTN_MAIN, height=34, fg_color=t["warning"],
                                 hover_color=t["warning"], text_color="#FFFFFF", command=_save)
        btn_save.pack(fill="x", padx=16, pady=(8, 0))
        win.bind("<Return>", _save)
        win.bind("<Escape>", lambda e: _close())
        win.protocol("WM_DELETE_WINDOW", _close)
        try: e_w.focus_set()
        except Exception as _e: _log_silent("fix_printer_paper_action#3", _e)

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
        self.btn_arch_full.pack_forget()
        self.btn_chrome.pack_forget()
        if is_supervisor:
            self.badge_role.configure(text="● ADMIN", text_color="#EF4444")
            self.f_role_btn.configure(border_color="#EF4444")
            self.btn_arch_full.pack(side="left", padx=2)
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
            c.execute("INSERT OR REPLACE INTO system_meta (meta_key, meta_value) VALUES ('last_full_archive_time', ?)",
                      (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),))
            conn.commit()
            conn.close()
        except Exception as e:
            log_exception("mark_archive_done_today", e)

    def _archive_done_time(self):
        """وقت آخر أرشفة ناجحة على الجهاز ده (HH:MM) لو اتعملت النهارده، وإلا نص فاضي."""
        try:
            conn = db_connect()
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS system_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT)")
            c.execute("SELECT meta_value FROM system_meta WHERE meta_key = 'last_full_archive_time'")
            row = c.fetchone()
            conn.close()
            val = row[0] if row else ""
            if val.startswith(datetime.date.today().strftime("%Y-%m-%d")):
                return val[11:16]
        except Exception as e:
            log_exception("archive_done_time", e)
        return ""

    def _archive_fill_missing(self, folder_path):
        """يكمّل أي يوم مؤرشف ناقصه إيصال السمري أو إكسيل اليوم (الأيام الكاملة بتتخطى فورًا).
        بترجّع عدد الأيام اللي اتكمّلت، أو None لو في فهرسة تانية شغالة وماخلصتش."""
        root = os.path.join(folder_path, ARCHIVE_DIRNAME)
        if not os.path.isdir(root): return 0
        if not _ARCHIVE_LOCK.acquire(timeout=120): return None
        built = 0
        try:
            todo = []
            for dp, _dn, fns in os.walk(root):
                parts = os.path.relpath(dp, root).split(os.sep)
                if len(parts) != 3: continue
                try: d = datetime.date(int(parts[0]), int(parts[1].split("-")[0]), int(parts[2]))
                except Exception: continue
                if not any(f.lower().endswith((".pdf", ".txt")) and not f.startswith(("Samary_", "Details_"))
                           and not f.endswith(("_cropped.pdf", "_Summary.pdf")) for f in fns): continue
                need_pdf = REPORTLAB_AVAILABLE and not any(f.startswith("Samary_") and f.lower().endswith(".pdf") for f in fns)
                need_xlsx = OPENPYXL_AVAILABLE and not os.path.exists(archive_day_excel_path(dp, d))
                if need_pdf or need_xlsx: todo.append((dp, d, need_pdf, need_xlsx))
            for dp, d, need_pdf, need_xlsx in sorted(todo, key=lambda x: x[1]):
                try:
                    tag = d.strftime("%d-%m-%Y")
                    if need_pdf:
                        recs = archive_day_records(dp)
                        if recs: self._generate_day_summary_pdf(dp, tag, recs)
                    if need_xlsx: archive_write_day_excel(dp, d)
                    if (need_pdf and os.path.exists(os.path.join(dp, f"Samary_{tag}.pdf"))) or \
                       (need_xlsx and os.path.exists(archive_day_excel_path(dp, d))):
                        built += 1
                except Exception as e:
                    log_exception(f"archive_fill_missing:{dp}", e)
        finally:
            _ARCHIVE_LOCK.release()
        return built

    def auto_archive_on_login(self):
        """عند دخول الوضع الكامل (يوزر أو مشرف)، في الخلفية بدون أي نافذة:
        - لو الأرشفة الكاملة لسه ماتعملتش النهارده: كنس كل الملفات القديمة للأرشيف + استكمال أي سمري/إكسيل ناقص لكل الأيام.
        - لو اتعملت: يفحص بس الأيام اللي ناقصها سمري أو إكسيل ويبنيها (من غير كنس).
        إشعار بجوار الساعة لما يخلص لو اتعمل شغل."""
        folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
        if not folder or not os.path.isdir(folder):
            return
        if getattr(self, "_auto_archive_running", False):
            return
        done_today = self._archive_done_today()
        self._auto_archive_running = True

        def work():
            swept, ok, filled = 0, False, 0
            try:
                if not done_today:
                    r = self._run_archive_sweep(folder)
                    if r is not None:             # None = كنسة تانية شغالة، هنحاول تاني في الدورة الجاية
                        swept, ok = r, True
                filled = self._archive_fill_missing(folder) or 0
                if ok:
                    self._mark_archive_done_today()
                    self._start_archive_maintenance(folder)
            except Exception as e:
                log_exception("auto_archive_on_login", e)
            finally:
                self._auto_archive_running = False
            if ok or filled:
                self.run_on_main(lambda: self._notify_archive_done(swept, filled))

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

    def _notify_archive_done(self, moved=0, filled=0):
        msg = T2("تمت الأرشفة ✓", "Archive completed ✓")
        if filled:
            msg += T2(f" — اتكمّل {filled} يوم ناقص", f" — completed {filled} incomplete day(s)")
        self._tray_notify(msg)

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
        self.update_idletasks()
        width, height = max(430, self.winfo_reqwidth()), max(330, self.winfo_reqheight())
        self.minsize(width, height)
        self.geometry(f"{width}x{height}+{(sw-width)//2}+{(sh-height)//2}")
        self.update_idletasks()

        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

        # Esc بيقفل النوافذ الفرعية بس. النافذة الرئيسية مفيهاش Esc (المسح بزر "مسح" المخصوص عشان ما يتمسحش بالغلط)
        if not getattr(self, "_esc_bound", False):
            self.bind_all("<Escape>", self._on_global_escape, add="+")
            self._esc_bound = True
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
        self.header = ctk.CTkFrame(self, corner_radius=0, height=34)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        f_left = ctk.CTkFrame(self.header, fg_color="transparent")
        f_left.pack(side="left", padx=(10, 0), pady=4)

        self.lbl_logo = ctk.CTkLabel(f_left, text="A2R", font=FONT_TITLE_LOGO)
        self.lbl_logo.pack(side="left", padx=(0, 6))

        self.cb_theme = ctk.CTkComboBox(f_left, values=THEME_KEYS, width=100, height=24, state="readonly",
                                        font=FONT_REGULAR_BOLD, command=self.on_theme_select)
        self.cb_theme.set(self.current_theme_name)
        self.cb_theme.pack(side="left", padx=(0, 3))

        self.btn_lang = ctk.CTkButton(f_left, text="🌐 عربي", width=58, height=24, font=FONT_REGULAR_BOLD,
                                      command=self.toggle_language)
        self.btn_lang.pack(side="left", padx=(0, 3))

        self.btn_mute = ctk.CTkButton(f_left, text="🔇 Muted", width=68, height=24, font=(FONT_FAMILY, 9, "bold"),
                                      fg_color="#334155", hover_color="#475569", command=self.toggle_mute)
        self.btn_mute.pack(side="left")

        f_right = ctk.CTkFrame(self.header, fg_color="transparent")
        f_right.pack(side="right", padx=(0, 10), pady=4)

        self.btn_elevate = ctk.CTkButton(f_right, text=tr("btn_full_console"), width=105, height=24,
                                         font=(FONT_FAMILY, 9, "bold"), fg_color="#DC2626", hover_color="#B91C1C",
                                         border_width=1, border_color="#EF4444", command=self.request_full_console)
        self.btn_elevate.pack(side="right", padx=(6, 0))

        self.btn_back_to_mini = ctk.CTkButton(f_right, text=tr("btn_back_mini"), width=88, height=24,
                                              font=(FONT_FAMILY, 10, "bold"), fg_color="#334155", hover_color="#475569",
                                              command=self.switch_to_mini_view)

        self.f_role_btn = ctk.CTkFrame(f_right, corner_radius=6, border_width=1.2, fg_color="#121E2E")
        self.badge_role = ctk.CTkLabel(self.f_role_btn, text="● USER", font=(FONT_FAMILY, 9, "bold"), padx=8, pady=1)
        self.badge_role.pack()

        self.lbl_clock = ctk.CTkLabel(f_right, text="", font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_clock.pack(side="right", padx=(0, 2))
        self.update_live_clock()

        self.body_mini = ctk.CTkFrame(self, fg_color="transparent")

        self.card_mini_status = ctk.CTkFrame(self.body_mini, corner_radius=12, border_width=1)
        self.card_mini_status.pack(fill="x", pady=(2, 4))

        f_mini_title_row = ctk.CTkFrame(self.card_mini_status, fg_color="transparent")
        f_mini_title_row.pack(fill="x", padx=14, pady=(6, 2))

        self.lbl_mini_title = ctk.CTkLabel(f_mini_title_row, text=tr("mini_station_title"),
                                          font=(FONT_FAMILY, 11, "bold"), text_color="#38BDF8")
        self.lbl_mini_title.pack(side="left")

        self.btn_fix_printer = ctk.CTkButton(f_mini_title_row, text=self._paper_btn_text(), width=70, height=22,
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

        self.b_bar = ctk.CTkFrame(self, corner_radius=0, height=44)
        self.btn_center_box = ctk.CTkFrame(self.b_bar, fg_color="transparent")
        self.btn_center_box.pack(anchor="center", pady=(3, 0))

        self.btn_view_rec = ctk.CTkButton(
            self.btn_center_box, width=115, height=24, font=(FONT_FAMILY, 10, "bold"),
            text_color="#FFFFFF", fg_color="#0284C7", hover_color="#0369A1",
            command=self.open_records_viewer
        )
        self.btn_view_rec.pack(side="left", padx=2)

        self.btn_pdf_export = ctk.CTkButton(self.btn_center_box, width=50, height=24, font=FONT_BTN_SUB,
                                           fg_color="#1A2D42", hover_color="#243C56", text_color="#FFFFFF", command=self.export_pdf_summary)
        self.btn_pdf_export.pack(side="left", padx=2)

        self.btn_print_slip = ctk.CTkButton(self.btn_center_box, fg_color="#D97706", hover_color="#B45309", width=85,
                                           height=24, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.print_slip)
        self.btn_print_slip.pack(side="left", padx=2)

        self.btn_excel = ctk.CTkButton(self.btn_center_box, fg_color="#059669", hover_color="#047857", width=85,
                                       height=24, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_excel)

        # النسخة المخففة: بدل زر المشرف (التقفيل/الدفع) فيه زر واحد بيفتح سجل الأرشيف الكامل (للمشرف فقط)
        self.btn_arch_full = ctk.CTkButton(self.btn_center_box, fg_color="#7C3AED", hover_color="#6D28D9", width=105,
                                           height=24, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_archive_history)

        self.btn_chrome = ctk.CTkButton(self.btn_center_box, fg_color="#2563EB", hover_color="#1D4ED8", width=90,
                                        height=24, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.open_chrome_browser)

        self.lbl_foot = ctk.CTkLabel(self.b_bar, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria",
                                font=(FONT_FAMILY, 9, "bold"), text_color="#FFFFFF")
        self.lbl_foot.pack(anchor="center", pady=(0, 1))

        self.body_full = ctk.CTkFrame(self, fg_color="transparent")

        self.card_top = ctk.CTkFrame(self.body_full, corner_radius=12, border_width=1)
        self.card_top.pack(fill="x", pady=(0, 3))

        self.lbl_folder = ctk.CTkLabel(self.card_top, font=FONT_SECTION_LBL)
        self.lbl_folder.pack(anchor="w", padx=8, pady=(3, 1))

        f_dir = ctk.CTkFrame(self.card_top, fg_color="transparent")
        f_dir.pack(fill="x", padx=8, pady=1)

        self.e_path = ctk.CTkEntry(f_dir, font=FONT_ENTRY, height=26, text_color="#FFFFFF")
        self.e_path.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.e_path.bind("<FocusOut>", lambda e: self.validate_path_live())
        attach_context_menu(self.e_path)

        self.btn_browse = ctk.CTkButton(
            f_dir, width=64, height=26, font=FONT_BTN_SUB, text_color="#FFFFFF",
            fg_color="#0284C7", hover_color="#0369A1", border_width=1, border_color="#38BDF8",
            command=self.browse_folder
        )
        self.btn_browse.pack(side="left", padx=(0, 3))

        self.btn_open_f = ctk.CTkButton(
            f_dir, width=54, height=26, font=FONT_BTN_SUB, text_color="#FFFFFF",
            fg_color="#0F766E", hover_color="#115E59",
            command=self.open_current_folder
        )
        self.btn_open_f.pack(side="left")

        self.lbl_d = ctk.CTkLabel(self.card_top, font=FONT_SECTION_LBL)
        self.lbl_d.pack(anchor="w", padx=8, pady=(2, 1))

        f_date = ctk.CTkFrame(self.card_top, fg_color="transparent")
        f_date.pack(fill="x", padx=8, pady=(1, 4))

        today = datetime.date.today()
        self.cb_d = ctk.CTkComboBox(f_date, values=[f"{d:02d}" for d in range(1, 32)], width=48, height=24, font=FONT_REGULAR_BOLD)
        self.cb_d.set(f"{today.day:02d}")
        self.cb_d.pack(side="left", padx=(0, 2))

        self.cb_m = ctk.CTkComboBox(f_date, values=[f"{m:02d}" for m in range(1, 13)], width=48, height=24, font=FONT_REGULAR_BOLD)
        self.cb_m.set(f"{today.month:02d}")
        self.cb_m.pack(side="left", padx=(0, 2))

        self.cb_y = ctk.CTkComboBox(f_date, values=[str(y) for y in range(today.year - 3, today.year + 3)], width=60, height=24, font=FONT_REGULAR_BOLD)
        self.cb_y.set(str(today.year))
        self.cb_y.pack(side="left", padx=(0, 4))

        self.btn_today = ctk.CTkButton(f_date, width=50, height=24, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.set_today)
        self.btn_today.pack(side="left", padx=(0, 2))

        self.btn_yesterday = ctk.CTkButton(f_date, width=62, height=24, font=FONT_BTN_SUB, text_color="#FFFFFF",
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

        self.card_dash = ctk.CTkFrame(self.body_full, corner_radius=12, border_width=1)
        self.card_dash.pack(fill="x", pady=(0, 3))

        dash_grid = ctk.CTkFrame(self.card_dash, fg_color="transparent")
        dash_grid.pack(fill="x", padx=8, pady=4)

        f_kpi = ctk.CTkFrame(dash_grid, fg_color="transparent")
        f_kpi.pack(side="left", fill="both", expand=True)

        self.pill_c1 = ctk.CTkFrame(f_kpi, fg_color="#07121E", corner_radius=6, border_width=1, border_color="#1E2E42")
        self.pill_c1.pack(side="left", padx=(0, 4), fill="both", expand=True)
        self.lbl_kpi1_title = ctk.CTkLabel(self.pill_c1, font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_kpi1_title.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_cnt = ctk.CTkLabel(self.pill_c1, text="0", font=FONT_KPI_VAL, text_color="#FFFFFF")
        self.lbl_cnt.pack(anchor="w", padx=6, pady=(0, 2))

        self.pill_c2 = ctk.CTkFrame(f_kpi, fg_color="#07121E", corner_radius=6, border_width=1, border_color="#1E2E42")
        self.pill_c2.pack(side="left", padx=(0, 4), fill="both", expand=True)
        self.lbl_kpi2_title = ctk.CTkLabel(self.pill_c2, font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_kpi2_title.pack(anchor="w", padx=6, pady=(2, 0))
        self.lbl_sum = ctk.CTkLabel(self.pill_c2, text="0.00 EGP", font=FONT_KPI_VAL, text_color="#00FF66")
        self.lbl_sum.pack(anchor="w", padx=6, pady=(0, 2))

        f_pos = ctk.CTkFrame(dash_grid, fg_color="transparent")
        f_pos.pack(side="right", fill="both")

        self.lbl_pos_title = ctk.CTkLabel(f_pos, font=FONT_SECTION_LBL)
        self.lbl_pos_title.pack(anchor="w", pady=(0, 1))

        f_pos_in = ctk.CTkFrame(f_pos, fg_color="transparent")
        f_pos_in.pack(fill="x")

        vcmd = (self.register(self.validate_numeric_input), '%P')
        self.e_pos = ctk.CTkEntry(f_pos_in, placeholder_text="POS / Cash Total", width=98, height=24,
                                  justify="center", font=FONT_ENTRY, text_color="#FFFFFF",
                                  validate="key", validatecommand=vcmd)
        self.e_pos.pack(side="left", padx=(0, 3))
        self.e_pos.bind("<Return>", lambda e: self.check_pos())
        attach_context_menu(self.e_pos)

        self.btn_pos_check = ctk.CTkButton(f_pos_in, width=48, height=24, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.check_pos)
        self.btn_pos_check.pack(side="left")

        self.lbl_diff = ctk.CTkLabel(f_pos, text="", font=(FONT_FAMILY, 10, "bold"))
        self.lbl_diff.pack(anchor="w", pady=(1, 0))

        self.card_actions = ctk.CTkFrame(self.body_full, corner_radius=12, border_width=1)
        self.card_actions.pack(fill="x", pady=(0, 3))

        self.btn_run = ctk.CTkButton(self.card_actions, font=FONT_BTN_MAIN, height=30, text_color="#FFFFFF", command=self.start_thread)
        self.btn_run.pack(fill="x", padx=8, pady=(4, 3))

        f_prog = ctk.CTkFrame(self.card_actions, fg_color="transparent")
        f_prog.pack(fill="x", padx=10, pady=(0, 2))

        self.progress_bar = ctk.CTkProgressBar(f_prog, orientation="horizontal", height=6, progress_color="#00FF66", fg_color="#064E3B")
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.lbl_progress_pct = ctk.CTkLabel(f_prog, text="0%", font=(FONT_FAMILY, 10, "bold"), text_color="#FFFFFF", width=34)
        self.lbl_progress_pct.pack(side="right")

        self.lbl_current_file = ctk.CTkLabel(self.card_actions, text="", font=(FONT_FAMILY, 10), text_color="#8FA3B8", height=12)
        self.lbl_current_file.pack(anchor="w", padx=12, pady=(0, 0))

        f_act = ctk.CTkFrame(self.card_actions, fg_color="transparent")
        f_act.pack(fill="x", padx=8, pady=(1, 5))

        self.btn_manual = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#0F766E", hover_color="#115E59", height=26, width=72, command=self.open_manual)
        self.btn_manual.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.btn_summary_reopen = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#7C3AED", hover_color="#6D28D9", height=26, width=72, command=self.reopen_summary_modal)
        self.btn_summary_reopen.pack(side="left", fill="x", expand=True, padx=(2, 2))

        self.btn_cash = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#0D9488", hover_color="#0F766E", height=26, width=60, command=self.open_cash_counter)
        self.btn_cash.pack(side="left", fill="x", expand=True, padx=(2, 2))

        self.btn_archive_downloads = ctk.CTkButton(f_act, font=FONT_BTN_SUB, fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF", height=26, width=68, command=self.open_downloads_archiver_dialog)
        self.btn_archive_downloads.pack(side="left", fill="x", expand=True, padx=(2, 2))

        self.btn_reset = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#EF4444", fg_color="transparent",
                                       hover_color="#1E1E24", border_width=1.5, border_color="#EF4444", height=26, width=52,
                                       command=self.confirm_and_reset)
        self.btn_reset.pack(side="right", fill="x", expand=True, padx=(2, 0))
        self._install_tooltips()

    def _on_global_escape(self, e=None):
        """Esc = قفل النافذة الفرعية اللي عليها الفوكس. النوافذ اللي ليها Esc خاص بيها (زي سجل الأرشيف) بتفضل زي ما هي."""
        try: top = e.widget.winfo_toplevel()
        except Exception: return
        if top is self or not isinstance(top, ctk.CTkToplevel): return
        try:
            if top.bind("<Escape>"): return
        except Exception as _e: _log_silent("global_escape#bind", _e)
        close_toplevel_gracefully(top)

    def _install_tooltips(self):
        """تلميح (الاسم + الاختصار) لأزرار النافذة الرئيسية. النص بيتحسب وقت الظهور فيتبع لغة البرنامج."""
        tips = {
            "btn_run":              (lambda: T2("تشغيل الفحص وتجميع الإيصالات (Ctrl+R)", "Run scan & collect receipts (Ctrl+R)")),
            "btn_manual":           (lambda: T2("إدخال يدوي (F2)", "Manual entry (F2)")),
            "btn_print_slip":       (lambda: T2("إيصال تصوير (F3)", "Photocopy slip (F3)")),
            "btn_cash":             (lambda: T2("حاسبة الكاش (F4)", "Cash calculator (F4)")),
            "btn_summary_reopen":   (lambda: T2("إعادة فتح ملخص الفحص", "Reopen scan summary")),
            "btn_archive_downloads": (lambda: T2("أرشفة الجهاز", "Archive this device")),
            "btn_mini_archive":     (lambda: T2("أرشفة الجهاز", "Archive this device")),
            "btn_reset":            (lambda: T2("مسح النتائج وإرجاع المسار والتاريخ (بيطلب تأكيد)", "Clear results and reset path/date (asks to confirm)")),
            "btn_view_rec":         (lambda: T2("عرض السجلات", "Records viewer")),
            "btn_pdf_export":       (lambda: T2("تصدير ملخص PDF", "Export PDF summary")),
            "btn_excel":            (lambda: T2("فتح ملف الإكسيل", "Open Excel file")),
            "btn_arch_full":        (lambda: T2("سجل الأرشيف الكامل (كل الأيام)", "Full archive history (all days)")),
            "btn_chrome":           (lambda: T2("فتح المتصفح", "Open browser")),
            "btn_today":            (lambda: T2("تاريخ النهارده", "Set date to today")),
            "btn_yesterday":        (lambda: T2("تاريخ امبارح", "Set date to yesterday")),
            "btn_browse":           (lambda: T2("اختيار مجلد الإيصالات", "Choose receipts folder")),
            "btn_open_f":           (lambda: T2("فتح المجلد", "Open folder")),
            "btn_pos_check":        (lambda: T2("مطابقة مع إجمالي POS", "Compare with POS total")),
            "btn_lang":             (lambda: T2("تغيير اللغة", "Switch language")),
            "btn_mute":             (lambda: T2("كتم / تشغيل الصوت", "Mute / unmute sound")),
        }
        for name, fn in tips.items():
            add_tooltip(getattr(self, name, None), fn)

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

        self.lbl_folder.configure(text_color=t["text_muted"])
        self.lbl_d.configure(text_color=t["text_muted"])
        self.lbl_kpi1_title.configure(text_color=t["text_muted"])
        self.lbl_kpi2_title.configure(text_color=t["text_muted"])
        self.lbl_pos_title.configure(text_color=t["text_muted"])
        self.lbl_sum.configure(text_color=t["success"])
        try:
            self.lbl_cnt.configure(text_color=t["text"])
            for _p in (self.pill_c1, self.pill_c2):
                _p.configure(fg_color=t["input"], border_color=t["border"], corner_radius=10)
            self.progress_bar.configure(progress_color=t["success"], fg_color=t["border"])
            self.lbl_progress_pct.configure(text_color=t["text"])
            self.lbl_current_file.configure(text_color=t["text_muted"])
            self.lbl_foot.configure(text_color=t["text_muted"])
            self.lbl_clock.configure(text_color=t["accent"])
            self.f_role_btn.configure(fg_color=t["card"])
            for _e in (self.e_path, self.e_pos): style_entry(_e, t)
            for _c in (self.cb_d, self.cb_m, self.cb_y, self.cb_theme): style_combo(_c, t)
            apply_tree_style(t, 25)
        except Exception as _e: log_exception("apply_theme_extras", _e)
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
        for a in ("btn_browse",):   # الحد المضيء حوالين زر الاختيار
            b = getattr(self, a, None)
            if b is not None:
                try: b.configure(border_width=0)
                except Exception as e: log_exception("apply_button_border:" + a, e)

    def update_toggle_appearance(self):
        t = THEMES[self.current_theme_name]
        if self.auto_sync_enabled:
            self.sw_autosync.configure(progress_color=t["success"], button_color="#FFFFFF")
            self.lbl_sw_sync.configure(text=tr("autosync_on"), text_color=t["text"])
        else:
            self.sw_autosync.configure(fg_color=t["border"], button_color=t["text_muted"])
            self.lbl_sw_sync.configure(text=tr("autosync_off"), text_color=t["text_muted"])

        if self.auto_print_enabled:
            self.sw_autoprint.configure(progress_color=t["success"], button_color="#FFFFFF")
            self.lbl_sw_print.configure(text=tr("autoprint_on"), text_color=t["text"])
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
        self.btn_arch_full.configure(text=L["arch_hist_btn"])
        self.btn_chrome.configure(text=L["open_chrome"])
        self.btn_elevate.configure(text=L["btn_full_console"])
        self.btn_back_to_mini.configure(text=L["btn_back_mini"])
        self.lbl_mini_title.configure(text=L["mini_station_title"])
        self.lbl_mini_desc.configure(text=L["mini_status_active"])
        self.lbl_mini_counter.configure(text=tr("mini_printed_count", count=self.printed_count_today))
        self.btn_fix_printer.configure(text=self._paper_btn_text())
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

                if not MANUAL_NAME_RE.match(clean_name):      # الإيصال اليدوي بيطبع بعرض اللفة كامل
                    scaled_copy = scale_pdf_to_print_width(target)
                if scaled_copy:
                    target = scaled_copy

                if os.path.exists(sumatra_path):
                    cmd = [
                        sumatra_path,
                        "-print-to-default",
                        "-print-settings", print_settings_arg(),
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
        """زر 📦 الأرشفة (متاح لأي مستخدم): بيأرشف الجهاز ده لو لسه ما اتأرشفش النهارده فقط.
        مفيش اختيار فولدر ولا تصفح أيام هنا — عرض أي يوم بتفاصيله موجود للمشرف بس في 🗂️ سجل الأرشيف.
        الأرشفة التلقائية (عند الدخول + كل 10 دقايق) شغالة زي ما هي ومش بتعتمد على النافذة دي."""
        try:
            old = getattr(self, "_user_archive_win", None)
            if old is not None:
                try:
                    if old.winfo_exists():
                        old.lift(); old.focus_force()
                        return
                except Exception as _e: _log_silent("user_archive#exists", _e)

            t = THEMES[self.current_theme_name]
            folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
            # المشرف بيفتح السجل من زر 📚 سجل الأرشيف في الشريط الرئيسي؛ لو الزر ده مش موجود عنده نسيب الزر هنا كبديل
            _has_hub = getattr(self, "btn_arch_full", None) is not None
            _show_hist = not (getattr(self, "is_supervisor", False) and _has_hub)
            win = ctk.CTkToplevel(self)
            self._user_archive_win = win
            win.title(f"{tr('clean_downloads')} - A2R {APP_VERSION}")
            win.resizable(False, False)
            center_window_relative(win, self, 450, 385 if _show_hist else 330)
            win.configure(fg_color=t["bg"])

            ctk.CTkLabel(win, text=T2("📦 أرشفة الجهاز", "📦 Device Archive"),
                         font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"]).pack(pady=(12, 2))
            ctk.CTkLabel(win, text=T2("بتنقل إيصالات الأيام السابقة للأرشيف وتعمل إكسيل وملخص (عدد المعاملات والإجمالي) لكل يوم",
                                      "Moves previous days' receipts to the archive and builds an Excel + summary (count & total) per day"),
                         font=(FONT_FAMILY, 9), text_color=t["text_muted"], wraplength=410, justify="center").pack(padx=16, pady=(0, 8))

            card = ctk.CTkFrame(win, fg_color=t["card"], corner_radius=12, border_width=1, border_color=t["border"])
            card.pack(fill="x", padx=16, pady=(0, 6))
            ctk.CTkLabel(card, text=T2("المجلد:", "Folder:"), font=(FONT_FAMILY, 10, "bold"),
                         text_color=t["text"]).pack(anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(card, text=folder or "-", font=(FONT_FAMILY, 9), text_color=t["text_muted"],
                         wraplength=400, justify="left").pack(anchor="w", padx=12, pady=(0, 4))
            lbl_state = ctk.CTkLabel(card, text="", font=(FONT_FAMILY, 12, "bold"), wraplength=400)
            lbl_state.pack(padx=12, pady=(2, 10))

            f_prog = ctk.CTkFrame(win, fg_color="transparent")
            f_prog.pack(fill="x", padx=16, pady=(2, 2))
            f_prog.grid_columnconfigure(0, weight=1)
            p_bar = ctk.CTkProgressBar(f_prog, orientation="horizontal", height=8, progress_color=t["success"])
            p_bar.set(0)
            p_bar.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            p_lbl = ctk.CTkLabel(f_prog, text="0%", font=(FONT_FAMILY, 10, "bold"), width=36, text_color=t["text"])
            p_lbl.grid(row=0, column=1)
            s_lbl = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 9), text_color=t["text_muted"], wraplength=410)
            s_lbl.pack(pady=(0, 4))

            st = {"busy": False}

            def _alive():
                try: return bool(win.winfo_exists())
                except Exception: return False

            def refresh_state():
                if not _alive(): return
                auto_running = bool(getattr(self, "_auto_archive_running", False))
                if st["busy"] or auto_running:
                    lbl_state.configure(text=T2("⏳ جاري الأرشفة...", "⏳ Archiving..."), text_color=t["warning"])
                    btn_go.configure(state="disabled", text=T2("جاري الأرشفة...", "Archiving..."))
                    if auto_running and not st["busy"]:
                        win.after(1500, refresh_state)      # الأرشفة التلقائية شغالة: نراقبها لحد ما تخلص
                elif self._archive_done_today():
                    tm = self._archive_done_time()
                    lbl_state.configure(
                        text=T2("✓ الجهاز ده اتأرشف النهارده", "✓ This device is already archived today") + (f"  ({tm})" if tm else ""),
                        text_color=t["success"])
                    btn_go.configure(state="disabled", text=T2("تمت الأرشفة ✓", "Archived ✓"))
                else:
                    lbl_state.configure(text=T2("الجهاز ده لسه ما اتأرشفش النهارده", "This device has not been archived today"),
                                        text_color=t["danger"])
                    btn_go.configure(state="normal", text=T2("🗄️ أرشفة الآن", "🗄️ Archive now"))

            def _start():
                if st["busy"] or getattr(self, "_auto_archive_running", False): return refresh_state()
                if self._archive_done_today(): return refresh_state()      # الجهاز اتأرشف خلاص: مفيش أرشفة تانية من هنا
                if not folder or not os.path.isdir(folder):
                    messagebox.showerror("Error", tr("dir_missing"), parent=win)
                    return
                st["busy"] = True
                p_bar.set(0); p_lbl.configure(text="0%")
                refresh_state()

                def ui(fn):
                    def _run():
                        if _alive():
                            try: fn()
                            except Exception as _e: _log_silent("user_archive#ui", _e)
                    self.run_on_main(_run)

                def prog(i, n, fname):
                    pct = int((i / n) * 100) if n else 100
                    ui(lambda: [p_bar.set(pct / 100.0), p_lbl.configure(text=f"{pct}%"),
                                s_lbl.configure(text=T2(f"جاري نقل: {fname}", f"Moving: {fname}"))])

                def stage(i, n, name):
                    pct = int(i / max(1, n) * 100)
                    ui(lambda: [p_bar.set(i / max(1, n)), p_lbl.configure(text=f"{pct}%"),
                                s_lbl.configure(text=T2(f"جاري تحديث ملخص وإكسيل يوم {name}  ({i}/{n})",
                                                        f"Updating summary & Excel for day {name}  ({i}/{n})"))])

                def work():
                    moved, ok = None, False
                    try:
                        moved = self._run_archive_sweep(folder, prog, stage)
                        if moved is not None:           # None = كنسة تانية شغالة (مفيش شغل حصل)
                            self._mark_archive_done_today()
                            self._start_archive_maintenance(folder)
                            ok = True
                    except Exception as e:
                        log_exception("user_archive_worker", e)
                    st["busy"] = False

                    def fin():
                        if ok:
                            p_bar.set(1.0); p_lbl.configure(text="100%")
                            s_lbl.configure(text=T2(f"✓ تمت الأرشفة — {moved or 0} ملف اتنقل", f"✓ Done — {moved or 0} file(s) archived"))
                            play_sound_matched()
                            # بعد ما الأرشفة تخلص بنجاح: النافذة تتقفل لوحدها بعد ثانيتين ونص
                            def _auto_close():
                                if _alive():
                                    try: win.destroy()
                                    except Exception as _e: _log_silent("user_archive#autoclose", _e)
                            try: win.after(2500, _auto_close)
                            except Exception as _e: _log_silent("user_archive#autoclose_sched", _e)
                        elif moved is None and not ok:
                            s_lbl.configure(text=T2("فيه أرشفة شغالة حالياً، جرّب بعد شوية.", "Another archive is running, try again shortly."))
                        else:
                            s_lbl.configure(text=T2("حصل خطأ أثناء الأرشفة (متسجّل في app_log.txt).", "Archive failed (see app_log.txt)."))
                        refresh_state()
                    ui(fin)

                threading.Thread(target=work, daemon=True).start()

            btn_go = ctk.CTkButton(win, text="", font=FONT_BTN_MAIN, height=38, text_color="#FFFFFF",
                                   fg_color=t["primary"], hover_color=t["primary_hover"], command=_start)
            btn_go.pack(fill="x", padx=16, pady=(4, 6))

            if _show_hist:
                btn_hist = ctk.CTkButton(win, text=T2("📚 سجل الأرشيف", "📚 Archive History"), font=FONT_BTN_MAIN, height=38,
                                         text_color="#FFFFFF", fg_color=t["secondary"], hover_color=t["secondary_hover"],
                                         command=self.open_archive_history)
                btn_hist.pack(fill="x", padx=16, pady=(0, 6))

            ctk.CTkLabel(win, text=(T2("المشرف: كل الأيام بتفاصيلها • المستخدم: آخر 7 أيام للقراءة فقط",
                                       "Supervisor: all days in full • User: last 7 days, read-only") if _show_hist else
                                    T2("🗂️ سجل الأرشيف متاح من زر 🛠️ المشرف", "🗂️ Archive history is available from the 🛠️ Supervisor button")),
                         font=(FONT_FAMILY, 9), text_color=t["text_muted"], wraplength=410, justify="center").pack(padx=16, pady=(0, 8))

            refresh_state()
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

    def _rearchive_days(self, folder, days, progress=None, stage=None):
        """إعادة الأرشفة: كنس أي ملف لسه برا الأرشيف + إعادة قراءة إيصالات الأيام + إعادة بناء إيصال السمري وإكسيل اليوم.
        days=None يعني كل الأيام. بترجّع قاموس النتيجة أو None لو الفهرسة مشغولة."""
        try: self._run_archive_sweep(folder)
        except Exception as e: log_exception("rearchive_sweep", e)
        res = archive_reindex(folder, days, progress)
        if res is None: return None
        targets = sorted(days) if days is not None else archive_all_days()
        rebuilt = 0
        for i, iso in enumerate(targets, 1):
            try:
                dd = datetime.date.fromisoformat(iso)
                f = archive_day_dir(folder, dd)
                if not os.path.isdir(f): f = archive_day_folder_from_index(iso) or f
                if not os.path.isdir(f): continue
                if stage:
                    try: stage(i, len(targets), iso)
                    except Exception as _e: _log_silent("rearchive_days#stage", _e)
                recs = archive_day_records(f)
                if not recs: continue
                tag = dd.strftime("%d-%m-%Y")
                self._generate_day_summary_pdf(f, tag, recs)
                new_pdf = os.path.join(f, f"Samary_{tag}.pdf")
                if os.path.exists(new_pdf):
                    for old in glob.glob(os.path.join(f, "Samary_*.pdf")):   # أي سمري قديم بإسم تاني كان ممكن يتفتح بالغلط
                        if os.path.normcase(old) != os.path.normcase(new_pdf):
                            try: os.remove(old)
                            except Exception as _e: _log_silent("rearchive_days#rm_old", _e)
                archive_write_day_excel(f, dd)
                rebuilt += 1
            except Exception as e:
                log_exception(f"rearchive_day:{iso}", e)
        res["rebuilt"] = rebuilt
        res["days"] = len(targets)
        self._start_archive_maintenance(folder)   # نسخة احتياطية للأرشيف بعد التحديث
        return res

    def _start_archive_maintenance(self, folder):
        """فهرسة + نسخ احتياطي مخفي في الخلفية (بدون تعطيل الواجهة)."""
        try:
            if folder and os.path.isdir(folder):
                threading.Thread(target=archive_maintenance, args=(folder,), daemon=True).start()
        except Exception as e:
            log_exception("start_archive_maintenance", e)

    def open_archive_history(self):
        """سجل الأرشيف: كل الأيام على الشمال، واختيار يوم بيعرض كل معاملاته على اليمين في نفس النافذة.
        المشرف: كل الأدوات. اليوزر: قراءة فقط لآخر USER_DAYS أيام (إجمالي كل يوم + كل المعاملات + بحث + فتح الإيصال)
        بدون فتح فولدر الأرشيف ولا الإكسيل ولا النسخ الاحتياطي، مع زرار إعادة أرشفة الكل بصمت (إشعار عند الانتهاء بس)."""
        is_admin = bool(getattr(self, "is_supervisor", False))
        USER_DAYS = 7
        # منع تكرار النافذة: لو مفتوحة بنفس الصلاحية نرفعها قدام، ولو الصلاحية اتغيرت نقفلها ونفتح بالجديدة
        _old = getattr(self, "_arch_win", None)
        try:
            if _old is not None and _old.winfo_exists():
                if getattr(self, "_arch_win_admin", None) == is_admin:
                    try:
                        if _old.state() == "iconic": _old.deiconify()
                    except Exception as _e: _log_silent("open_archive_history#restore", _e)
                    _old.lift(); _old.focus_force()
                    return
                _old.destroy()
        except Exception as _e: _log_silent("open_archive_history#dup", _e)
        folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", tr("dir_missing"))
            return
        cutoff_iso = "" if is_admin else (datetime.date.today() - datetime.timedelta(days=USER_DAYS)).isoformat()

        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        self._arch_win, self._arch_win_admin = win, is_admin
        win.title(T2("📚 سجل الأرشيف", "📚 Archive History"))
        win.resizable(True, True)
        set_window_icon_safe(win)
        _sw, _sh = win.winfo_screenwidth(), win.winfo_screenheight()
        center_window_on_screen(win, LOG_WIN_W, LOG_WIN_H)
        remember_window_geometry(win, "archive_history")
        try: win.transient("")   # center_window_relative بتخليها transient = ويندوز بيشيل أزرار التصغير/التكبير وبتختفي من شريط المهام
        except Exception as _e: _log_silent("open_archive_history#transient", _e)
        win.minsize(min(LOG_WIN_MIN_W, _sw - 40), min(LOG_WIN_MIN_H, _sh - 100))
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception as _e: _log_silent("open_archive_history#1", _e)

        ALL = T2("الكل", "All")
        st = {"stats": [], "debounce": None, "iso": None, "recs": [], "recs_iso": None,
              "load_id": 0, "cache": {}, "sel_job": None}

        # ---------- شريط الحالة والأدوات ----------
        bar = ctk.CTkFrame(win, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
        bar.pack(fill="x", padx=14, pady=(12, 6))
        status_lbl = ctk.CTkLabel(bar, text="", font=(FONT_FAMILY, 10, "bold"), text_color=t["accent"])
        status_lbl.pack(side="left", padx=12, pady=8)

        def _set_status(txt):
            try:
                if win.winfo_exists(): status_lbl.configure(text=txt)
            except Exception as _e: _log_silent("_set_status#1", _e)

        def run_maintenance(manual=False, light=False):
            def prog(i, n):
                self.after(0, lambda: _set_status(T2(f"جاري فهرسة الأرشيف... {i}/{n}", f"Indexing archive... {i}/{n}")))
            def work():
                res = archive_maintenance(folder, prog, full=not light)
                def fin():
                    if not win.winfo_exists(): return
                    if res is None:
                        _set_status("" if light else T2("عملية الفهرسة/النسخ شغالة بالفعل، استنى شوية.", "Maintenance already running."))
                    elif light:
                        _set_status(T2(f"جاهز ✓ — جديد: {res[0]}", f"Ready ✓ — new: {res[0]}"))
                    else:
                        _set_status(T2(f"تم ✓ — جديد: {res[0]} | منسوخ للنسخة الاحتياطية: {res[1]}",
                                       f"Done ✓ — new: {res[0]} | backed up: {res[1]}"))
                    st["cache"].clear()
                    load_days()
                self.after(0, fin)
            _set_status(T2("جاري الفحص...", "Scanning..."))
            threading.Thread(target=work, daemon=True).start()

        def open_backup_folder():
            if not is_admin: return
            if os.path.isdir(ARCHIVE_BACKUP_DIR): os.startfile(ARCHIVE_BACKUP_DIR)
            else: messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا توجد نسخة احتياطية بعد. اضغط (تحديث + نسخ).", "No backup yet. Press Refresh + Backup."), parent=win)

        # ---------- إعادة الأرشفة ----------
        rb = {"running": False, "btn": None}

        def _set_rearch_btn(running):
            b = rb.get("btn")
            if b is None: return
            try:
                b.configure(state="disabled" if running else "normal",
                            text=T2("⏳ جاري إعادة الأرشفة...", "⏳ Re-archiving...") if running
                            else T2("♻️ إعادة أرشفة الكل", "♻️ Re-archive all"))
            except Exception as _e: _log_silent("_set_rearch_btn#1", _e)

        def run_rearchive(days, ask=True, silent=False):
            """days=None: كل الأيام. بتقرا الإيصالات من الأول وتعيد بناء إجمالي اليوم والسمري والإكسيل."""
            if rb["running"]: return
            if days is not None and not days:
                messagebox.showinfo(T2("تنبيه", "Notice"), T2("مفيش أيام مطابقة.", "No matching days."), parent=win)
                return
            what = T2("كل الأيام", "all days") if days is None else T2(f"{len(days)} يوم", f"{len(days)} day(s)")
            if ask and not messagebox.askyesno(
                    T2("إعادة الأرشفة", "Re-archive"),
                    T2(f"هتتعمل إعادة قراءة لإيصالات {what} وإعادة بناء إجمالي اليوم وإيصال السمري وإكسيل اليوم.\n"
                       "الإيصالات نفسها مش بتتغير ولا بتتمسح. تكمّل؟",
                       f"Receipts of {what} will be re-read and the day total, summary receipt and day Excel rebuilt.\n"
                       "The receipts themselves are not changed or deleted. Continue?"), parent=win):
                return
            rb["running"] = True
            if silent: _set_rearch_btn(True)
            def prog(i, n):
                self.after(0, lambda: _set_status(T2(f"جاري إعادة قراءة الإيصالات... {i}/{n}", f"Re-reading receipts... {i}/{n}")))
            def stage(i, n, iso):
                self.after(0, lambda: _set_status(T2(f"جاري إعادة بناء الملخصات... {i}/{n} ({iso})", f"Rebuilding summaries... {i}/{n} ({iso})")))
            def work():
                try: res = self._rearchive_days(folder, days, None if silent else prog, None if silent else stage)
                except Exception as e:
                    log_exception("rearchive", e)
                    res = {"error": True}
                def fin():
                    rb["running"] = False
                    if silent:
                        try: _set_rearch_btn(False) if win.winfo_exists() else None
                        except Exception as _e: _log_silent("run_rearchive#btn", _e)
                        if res is None: _msg = T2("فهرسة تانية شغالة، جرّب بعد شوية.", "Another indexing job is running, try again shortly.")
                        elif res.get("error"): _msg = T2("حصل خطأ أثناء إعادة الأرشفة (راجع ملف اللوج).", "Error while re-archiving (see log).")
                        else: _msg = T2(f"تمت إعادة أرشفة كل الأيام ✓ ({res['rebuilt']} يوم)", f"All days re-archived ✓ ({res['rebuilt']} days)")
                        self._tray_notify(_msg)
                        if getattr(self, "tray_icon", None) is None:      # مفيش أيقونة جنب الساعة: نبّه برسالة بدل الإشعار
                            messagebox.showinfo(T2("إعادة الأرشفة", "Re-archive"), _msg, parent=self)
                    if not win.winfo_exists(): return
                    st["cache"].clear()
                    load_days()
                    if st["iso"] and day_tree.exists(st["iso"]): show_day(st["iso"])
                    if silent: return                     # بصمت: من غير رسائل حالة ولا تحذيرات
                    if res is None:
                        _set_status(T2("فهرسة تانية شغالة، جرّب بعد شوية.", "Another indexing job is running, try again shortly."))
                    elif res.get("error"):
                        _set_status(T2("حصل خطأ أثناء إعادة الأرشفة (راجع ملف اللوج).", "Error while re-archiving (see log)."))
                    else:
                        _set_status(T2(f"تمت إعادة الأرشفة ✓ — أيام اتبنى لها ملخص: {res['rebuilt']} | إيصالات اتقرت: {res['read']}",
                                       f"Re-archive done ✓ — days rebuilt: {res['rebuilt']} | receipts read: {res['read']}"))
                        warn = []
                        if res.get("zero_amount"):
                            warn.append(T2(f"• {res['zero_amount']} إيصال لسه مبلغه صفر بعد إعادة القراءة (القارئ مش قادر يلقط المبلغ منه).",
                                           f"• {res['zero_amount']} receipt(s) still have a zero amount after re-reading."))
                        if res.get("unread"):
                            warn.append(T2(f"• {res['unread']} ملف مقدرش يتقري كإيصال (أسماء أول الملفات في ملف اللوج).",
                                           f"• {res['unread']} file(s) could not be read as receipts (first names are in the log)."))
                        if warn:
                            messagebox.showwarning(T2("نتيجة إعادة الأرشفة", "Re-archive result"), "\n".join(warn), parent=win)
                self.after(0, fin)
            _set_status(T2("جاري إعادة الأرشفة...", "Re-archiving..."))
            threading.Thread(target=work, daemon=True).start()

        def open_rearchive():
            if rb["running"]: return
            dlg = ctk.CTkToplevel(win)
            dlg.title(T2("♻️ إعادة الأرشفة", "♻️ Re-archive"))
            dlg.resizable(False, False)
            set_window_icon_safe(dlg)
            center_window_relative(dlg, win, 470, 300)
            dlg.configure(fg_color=t["bg"])
            try: dlg.grab_set()
            except Exception as _e: _log_silent("open_rearchive#grab", _e)
            ctk.CTkLabel(dlg, text=T2("إعادة قراءة الإيصالات من الأول وإعادة بناء إجمالي اليوم وإيصال السمري وإكسيل اليوم. استخدمها لو في أيام إجماليها صفر أو فيها أخطاء.",
                                      "Re-read receipts and rebuild day total, summary receipt and day Excel. Use it for days with a zero total or errors."),
                         font=(FONT_FAMILY, 10, "bold"), text_color=t["text"], wraplength=430, justify="left").pack(anchor="w", padx=16, pady=(14, 8))
            scope = tk.StringVar(value="zero")
            opts = [("zero", T2("الأيام اللي إجماليها صفر أو فيها ناقص", "Days with a zero total or incomplete rows")),
                    ("shown", T2("كل الأيام الظاهرة في القايمة (حسب الشهر/البحث)", "All days currently listed (month/search filter)")),
                    ("all", T2("كل الأيام (ممكن ياخد وقت)", "All days (may take a while)"))]
            for val, lab in opts:
                ctk.CTkRadioButton(dlg, text=lab, variable=scope, value=val, font=FONT_SECTION_LBL,
                                   text_color=t["text"]).pack(anchor="w", padx=22, pady=3)
            def go():
                mode = scope.get()
                if mode == "zero": days = sorted({x["day"] for x in st["stats"] if x["total"] <= 0 or x["missing"]})
                elif mode == "shown": days = list(day_tree.get_children())
                else: days = None
                if mode == "all" and not messagebox.askyesno(
                        T2("⚠️ تحذير: كل الأيام", "⚠️ Warning: all days"),
                        T2("إنت اخترت إعادة أرشفة كل الأيام.\nده بيمسح الفهرس كله ويقرا كل الإيصالات من الأول وممكن ياخد وقت طويل لو الأرشيف كبير.\n"
                           "الإيصالات نفسها مش بتتغير. متأكد؟",
                           "You chose to re-archive ALL days.\nThis clears the whole index and re-reads every receipt, which can take a long time.\n"
                           "The receipts themselves are not changed. Sure?"),
                        icon="warning", default="no", parent=dlg):
                    return
                try: dlg.destroy()
                except Exception as _e: _log_silent("open_rearchive#destroy", _e)
                run_rearchive(days, ask=(mode != "all"))
            ctk.CTkButton(dlg, text=T2("▶ ابدأ", "▶ Start"), font=FONT_BTN_MAIN, height=34, fg_color=t["primary"],
                          hover_color=t["primary_hover"], text_color="#FFFFFF", command=go).pack(fill="x", padx=16, pady=(14, 0))

        # ---------- تكبير / ملء الشاشة / تصغير ----------
        fs = {"on": False}
        def toggle_fullscreen(event=None):
            fs["on"] = not fs["on"]
            try: win.attributes("-fullscreen", fs["on"])
            except Exception as _e: _log_silent("toggle_fullscreen#1", _e)
        def exit_fullscreen(event=None):
            if fs["on"]: toggle_fullscreen()
            else: close_toplevel_gracefully(win)      # Esc تاني (أو أول مرة لو مش fullscreen) = يقفل السجل
        def minimize_win():
            try:
                if fs["on"]: toggle_fullscreen()
                win.iconify()
            except Exception as _e: _log_silent("minimize_win#1", _e)
        win.bind("<F11>", toggle_fullscreen)
        win.bind("<Escape>", exit_fullscreen)

        def open_archive_root():
            if not is_admin: return
            root = ensure_archive_root(folder)
            if os.path.isdir(root): os.startfile(root)

        def toggle_zoom():
            try: win.state("normal" if win.state() == "zoomed" else "zoomed")
            except Exception as _e: _log_silent("toggle_zoom#1", _e)

        if is_admin:
            more_menu = tk.Menu(win, tearoff=0)
            more_menu.add_command(label=T2("♻️ إعادة الأرشفة...", "♻️ Re-archive..."), command=open_rearchive)
            more_menu.add_separator()
            more_menu.add_command(label=T2("📂 فتح فولدر الأرشيف", "📂 Open archive folder"), command=open_archive_root)
            more_menu.add_command(label=T2("🗄️ فتح النسخة الاحتياطية", "🗄️ Open backup"), command=open_backup_folder)
            more_menu.add_separator()
            more_menu.add_command(label=T2("⛶ ملء الشاشة (F11)", "⛶ Fullscreen (F11)"), command=toggle_fullscreen)
            def show_more():
                try: more_menu.tk_popup(btn_more.winfo_rootx(), btn_more.winfo_rooty() + btn_more.winfo_height())
                finally: more_menu.grab_release()

            btn_more = ctk.CTkButton(bar, text=T2("⚙️ المزيد ▾", "⚙️ More ▾"), font=FONT_BTN_SUB, width=110, height=30,
                                     fg_color=t["secondary"], hover_color=t["secondary_hover"], text_color="#FFFFFF", command=show_more)
            btn_more.pack(side="right", padx=4, pady=6)
            ctk.CTkButton(bar, text=T2("🗖 تكبير", "🗖 Zoom"), font=FONT_BTN_SUB, width=90, height=30,
                          fg_color=t["secondary"], hover_color=t["secondary_hover"], text_color="#FFFFFF",
                          command=toggle_zoom).pack(side="right", padx=4, pady=6)
            ctk.CTkButton(bar, text=T2("🔄 تحديث + نسخ", "🔄 Refresh + Backup"), font=FONT_BTN_SUB, width=150, height=30,
                          fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF",
                          command=lambda: run_maintenance(True)).pack(side="right", padx=4, pady=6)
        else:
            ctk.CTkButton(bar, text=T2("🗖 تكبير", "🗖 Zoom"), font=FONT_BTN_SUB, width=90, height=30,
                          fg_color=t["secondary"], hover_color=t["secondary_hover"], text_color="#FFFFFF",
                          command=toggle_zoom).pack(side="right", padx=4, pady=6)
            rb["btn"] = ctk.CTkButton(bar, text=T2("♻️ إعادة أرشفة الكل", "♻️ Re-archive all"), font=FONT_BTN_SUB, width=160,
                                      height=30, fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF",
                                      command=lambda: run_rearchive(None, ask=False, silent=True))
            rb["btn"].pack(side="right", padx=4, pady=6)
            ctk.CTkLabel(bar, text=T2(f"📅 عرض آخر {USER_DAYS} أيام", f"📅 Last {USER_DAYS} days"),
                         font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"]).pack(side="left", padx=8)

        # ---------- ستايل الجداول ----------
        apply_tree_style(t, 25)

        def make_tree(parent, columns, headers, widths):
            fr = ctk.CTkFrame(parent, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
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

        tv = ctk.CTkTabview(win, fg_color=t["bg"], segmented_button_fg_color=t["card"],
                            segmented_button_selected_color=t["primary"], segmented_button_selected_hover_color=t["primary_hover"],
                            segmented_button_unselected_color=t["card"], segmented_button_unselected_hover_color=t["border"],
                            text_color="#FFFFFF")
        tv.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        TAB_DAYS = T2("📅 الأيام والمعاملات", "📅 Days & Transactions")
        TAB_SEARCH = T2("🔎 بحث عام في الأرشيف", "🔎 Global Search")
        tab_days = tv.add(TAB_DAYS)
        tab_search = tv.add(TAB_SEARCH)

        # ================= تبويب الأيام والمعاملات (شمال: الأيام | يمين: معاملات اليوم المختار) =================
        # فاصل قابل للسحب بين قايمة الأيام والمعاملات
        body = tk.PanedWindow(tab_days, orient="horizontal", sashwidth=8, sashrelief="flat", bd=0,
                              bg=t["border"], opaqueresize=True)
        body.pack(fill="both", expand=True)
        left = ctk.CTkFrame(body, fg_color=t["bg"], width=400)
        left.pack_propagate(False)
        right = ctk.CTkFrame(body, fg_color=t["bg"])
        body.add(left, minsize=300, width=400, stretch="never")
        body.add(right, minsize=520, stretch="always")

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
        style_combo(cb_month, t)
        cb_month.pack(side="left", padx=2)

        def clear_filters():
            day_q.delete(0, "end")
            cb_month.set(ALL)
            apply_days()
        ctk.CTkButton(f1, text="✖", width=34, height=28, font=FONT_BTN_SUB, fg_color=t["secondary"], hover_color=t["secondary_hover"],
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
            try:
                st["stats"] = archive_day_stats(archive_load_rows())
                # أيام كل ملفاتها مقدرناش نقراها كانت مختفية من القايمة؛ بنظهرها بصفر وبعلامة "ناقص" عشان تتعاد أرشفتها
                have = {x["day"] for x in st["stats"]}
                for _d, _c in archive_unread_by_day().items():
                    if _d not in have:
                        st["stats"].append({"day": _d, "ops": 0, "total": 0.0, "manual": 0, "void": 0,
                                            "dup": 0, "missing": _c})
                if cutoff_iso: st["stats"] = [x for x in st["stats"] if x["day"] >= cutoff_iso]   # اليوزر: آخر أسبوع بس
                st["stats"].sort(key=lambda x: x["day"], reverse=True)
            except Exception as e:
                log_exception("archive_history_load", e)
                st["stats"] = []
            months = sorted({s["day"][:7] for s in st["stats"]}, reverse=True)
            cb_month.configure(values=[ALL] + months)
            if cb_month.get() not in [ALL] + months: cb_month.set(ALL)
            apply_days()

        for e in (day_q,): e.bind("<KeyRelease>", apply_days)

        # ---------- اليمين: بطاقة اليوم المختار ----------
        hdr = ctk.CTkFrame(right, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["accent"])
        hdr.pack(fill="x", pady=(2, 0))
        day_title = ctk.CTkLabel(hdr, text=T2("👈 اختار يوم من القائمة لعرض معاملاته", "👈 Pick a day from the list"),
                                 font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"])
        day_title.pack(side="left", padx=14, pady=8)

        cards = ctk.CTkFrame(right, fg_color="transparent")
        cards.pack(fill="x", pady=(6, 2))
        card_lbls = {}
        def mk_card(key, title, color):
            f = ctk.CTkFrame(cards, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
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
            if not is_admin: return        # الإكسيل حصري للمشرف
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
            if pdfs:
                os.startfile(pdfs[0])
                return
            if not os.path.isdir(f):
                messagebox.showerror(T2("غير موجود", "Not found"), f, parent=win)
                return
            if not REPORTLAB_AVAILABLE:
                messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا يوجد إيصال سمري لهذا اليوم.", "No summary receipt for this day."), parent=win)
                return
            _set_status(T2("جاري إنشاء إيصال السمري...", "Building summary receipt..."))
            def work():
                try:
                    recs = archive_day_records(f)
                    if recs: self._generate_day_summary_pdf(f, dd.strftime("%d-%m-%Y"), recs)
                except Exception as e: log_exception("archive_d_summary", e)
                def fin():
                    if not win.winfo_exists(): return
                    made = sorted(glob.glob(os.path.join(f, "Samary_*.pdf")))
                    if made:
                        _set_status(T2("تم إنشاء إيصال السمري ✓", "Summary receipt built ✓"))
                        os.startfile(made[0])
                    else:
                        _set_status("")
                        messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا توجد معاملات لبناء السمري لهذا اليوم.", "No transactions to build a summary for this day."), parent=win)
                self.after(0, fin)
            threading.Thread(target=work, daemon=True).start()

        def d_folder():
            if not is_admin: return        # فولدر الأرشيف للمشرف بس
            iso = st["iso"]
            if not iso: return
            dd, f = day_folder_of(iso)
            if os.path.isdir(f): os.startfile(f)
            else: messagebox.showerror(T2("غير موجود", "Not found"), f, parent=win)

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 2))
        def _b(text, kind, cmd, w=140):
            _fg, _hv = theme_btn_colors(t, kind)
            ctk.CTkButton(btn_row, text=text, font=FONT_BTN_SUB, fg_color=_fg, hover_color=_hv, corner_radius=8,
                          text_color="#FFFFFF", width=w, height=28, command=cmd).pack(side="left", padx=(0, 6), pady=2)
        if is_admin: _b(T2("📊 إكسيل اليوم", "📊 Day Excel"), "quiet", d_excel, 125)
        _b(T2("📄 إيصال السمري", "📄 Summary receipt"), "primary", d_summary, 135)
        if is_admin:
            _b(T2("📂 فولدر اليوم", "📂 Day folder"), "quiet", d_folder, 115)
            _b(T2("♻️ إعادة أرشفة اليوم", "♻️ Re-archive day"), "danger",
               lambda: run_rearchive([st["iso"]] if st["iso"] else []), 145)

        # ---------- بحث وفلتر معاملات اليوم ----------
        search_row = ctk.CTkFrame(right, corner_radius=12, height=46, fg_color=t["card"], border_width=1, border_color=t["border"])
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
        style_combo(cb_status, t)
        cb_status.pack(side="left", padx=(0, 6), pady=6)
        tx_count = ctk.CTkLabel(search_row, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        tx_count.pack(side="right", padx=14)

        # ---------- جدول معاملات اليوم ----------
        tree_frame = ctk.CTkFrame(right, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
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
            if not is_admin: return
            p = rec.get("path", "") if rec else ""
            if p and os.path.exists(p): os.startfile(os.path.dirname(p))
            else: d_folder()

        tx_tree.bind("<Double-1>", open_receipt)
        row_menu = tk.Menu(tx_tree, tearoff=0)
        row_menu.add_command(label=tr("menu_open_file"), command=open_receipt)
        row_menu.add_command(label=tr("menu_reprint"), command=reprint_receipt)
        if is_admin: row_menu.add_command(label=T2("📂 فتح الفولدر", "📂 Open folder"), command=open_receipt_folder)
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
        if is_admin: day_menu.add_command(label=T2("📊 إكسيل اليوم", "📊 Day Excel"), command=d_excel)
        day_menu.add_command(label=T2("📄 إيصال السمري", "📄 Summary receipt"), command=d_summary)
        if is_admin:
            day_menu.add_command(label=T2("📂 فولدر اليوم", "📂 Day folder"), command=d_folder)
            day_menu.add_command(label=T2("♻️ إعادة أرشفة اليوم ده", "♻️ Re-archive this day"),
                                 command=lambda: run_rearchive([st["iso"]] if st["iso"] else []))
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
            try: rows = archive_search(q, include_void=bool(inc_void.get()), min_day=cutoff_iso)
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
            if folder_only:
                if is_admin: os.startfile(os.path.dirname(p))
            else: os.startfile(p)
        s_tree.bind("<Double-1>", open_result)
        smenu = tk.Menu(s_tree, tearoff=0)
        smenu.add_command(label=T2("📄 فتح الإيصال", "📄 Open receipt"), command=open_result)
        if is_admin: smenu.add_command(label=T2("📂 فتح فولدر اليوم", "📂 Open day folder"), command=lambda: open_result(folder_only=True))
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
        load_days()                       # اعرض الفهرس الموجود فورًا
        run_maintenance(light=True)       # فهرسة بس؛ النسخ الاحتياطي والإكسيلات بزرار "تحديث + نسخ" أو في الخلفية
        win.after(150, lambda: day_q.focus_set())

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
        center_window_on_screen(win, LOG_WIN_W, LOG_WIN_H)
        remember_window_geometry(win, "records_viewer")
        win.minsize(min(LOG_WIN_MIN_W, _sw - 40), min(LOG_WIN_MIN_H, _sh - 100))
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception as _e: _log_silent("_records_window#1", _e)

        if not live:
            hdr = ctk.CTkFrame(win, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["accent"])
            hdr.pack(fill="x", padx=14, pady=(12, 0))
            ctk.CTkLabel(hdr, text=T2(f"📅 أرشيف يوم {day_txt}", f"📅 Archive day {day_txt}"),
                         font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"]).pack(side="left", padx=14, pady=8)

        # ---------- كروت الإحصائيات ----------
        cards = ctk.CTkFrame(win, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=(8, 2))
        card_lbls = {}

        def mk_card(key, title, color):
            f = ctk.CTkFrame(cards, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
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
        search_row = ctk.CTkFrame(win, corner_radius=12, height=52, fg_color=t["card"], border_width=1, border_color=t["border"])
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
        style_combo(cb_status, t)
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

        def _b(text, kind, cmd, w=115):
            _fg, _hv = theme_btn_colors(t, kind)
            ctk.CTkButton(btn_row, text=text, font=FONT_BTN_SUB, fg_color=_fg, hover_color=_hv, corner_radius=8,
                          text_color="#FFFFFF", width=w, height=28, command=cmd).pack(side="left", padx=(0, 6), pady=2)

        _b(tr("open_pdf_btn"), "primary", open_selected)
        _b(tr("btn_reprint"), "quiet", reprint_selected, 105)
        _b(T2("📂 فتح الفولدر", "📂 Open folder"), "quiet", open_folder, 125)
        if live:
            _b(tr("btn_void_sel"), "danger", cancel_selected, 110)
            _b(tr("btn_restore_sel"), "quiet", restore_selected_void)
        else:
            _b(T2("📄 ملخص اليوم", "📄 Day summary"), "quiet", open_day_summary, 125)
            _b(T2("📊 إكسيل اليوم", "📊 Day Excel"), "quiet", export_day_excel, 125)

        ctk.CTkLabel(win, text=T2("🟥 مكرر   🟨 ناقص   🟧 وحدة أخرى   ⬛ ملغي (مخصوم)   •   دبل كليك لفتح الإيصال",
                                  "🟥 Duplicate   🟨 Incomplete   🟧 Other unit   ⬛ Void   •   double-click to open receipt"),
                     font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(anchor="w", padx=16)

        tree_frame = ctk.CTkFrame(win, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(2, 14))

        columns = ("idx", "unit", "plate", "insured", "amount", "time", "make", "model", "chassis", "motor", "period", "file", "status")
        headers = {
            "idx": tr("col_idx"), "unit": tr("col_unit"), "plate": tr("col_plate"),
            "insured": tr("col_insured"), "amount": tr("col_amount"), "time": tr("col_time"),
            "make": tr("col_make"), "model": tr("col_model"), "chassis": tr("col_chassis"),
            "motor": tr("col_motor"), "period": tr("col_period"), "file": tr("col_file"), "status": tr("col_status")
        }

        apply_tree_style(t, 26)

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

        card_box = ctk.CTkFrame(modal, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
        card_box.pack(fill="both", expand=True, padx=14, pady=10)

        row_u = ctk.CTkFrame(card_box, fg_color="transparent")
        row_u.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(row_u, text=tr("unit_name_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left")

        # قايمة الوحدات = الوحدات اللي في إيصالات اليوم نفسها (الأكتر أولًا)، والاختيار إجباري (قراءة فقط، مفيش كتابة حرة).
        # لو مفيش ولا وحدة اتقرت من الإيصالات (إيصالات يدوية بس مثلًا) بنرجع لقايمة الوحدات الكاملة عشان المستخدم ميتعلقش.
        _recs = getattr(self, "last_detailed_records", None) or []
        _cnt = Counter(clean_arabic(r["unit"]) for r in _recs if r.get("unit") and r["unit"] != UNSPEC)
        clean_opts = [u for u, _n in _cnt.most_common()]
        _dn = clean_arabic(unit_display_name) if unit_display_name and unit_display_name != UNSPEC else ""
        if _dn and _dn not in clean_opts:
            clean_opts.insert(0, _dn)
        if not clean_opts:
            for u in UNIT_NAMES + UNITS_LIST:
                cu = clean_arabic(u)
                if cu not in clean_opts: clean_opts.append(cu)
        _sel_unit = _dn if _dn in clean_opts else clean_opts[0]

        def _unit_changed(val):
            if self.last_summary_info is not None:
                self.last_summary_info["unit"] = val

        cb_unit = SafeArabicComboBox(row_u, values=clean_opts, width=200, height=30, font=FONT_REGULAR_BOLD,
                                     fg_color=t["input"], border_color=t["border"], text_color=t["text"],
                                     command=_unit_changed, state="readonly")
        cb_unit.set(_sel_unit)
        cb_unit.pack(side="right")
        _unit_changed(_sel_unit)

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
                    # الطباعة في thread الطباعة (الطابور) بدل ما تقفل الواجهة لحد ما الطابعة ترد
                    try: self._print_queue.put(full_path)
                    except Exception as _e: _log_silent("manual_print_queue", _e)

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
                        "-print-settings", "shrink",     # البون: من غير paper= عشان طول الورقة يتبع الـ PDF الصغير مش 57x90
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
        f_quick = ctk.CTkFrame(win, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
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

        frame_box = ctk.CTkFrame(win, corner_radius=12, fg_color=t["card"], border_width=1, border_color=t["border"])
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
