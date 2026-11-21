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
        _kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        _kernel32.CreateMutexW.restype = wintypes.HANDLE
        _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        _user32.FindWindowW.restype = wintypes.HWND
        _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        _user32.ShowWindow.restype = wintypes.BOOL
        _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        _user32.SetForegroundWindow.restype = wintypes.BOOL
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
from concurrent.futures import ThreadPoolExecutor, as_completed
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

APP_VERSION = "v92"
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
    for _w, _r in (("CTkButton", 10), ("CTkEntry", 9), ("CTkComboBox", 9), ("CTkOptionMenu", 9), ("CTkFrame", 14)):
        if _w in _tm and "corner_radius" in _tm[_w]: _tm[_w]["corner_radius"] = _r
    _tm["CTkButton"]["border_width"] = 0
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

_CONFIG_LOCK = threading.Lock()

def _read_app_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _save_app_prefs(**updates):
    """يحفظ تفضيلات الجهاز (اللغة، الثيم، الصوت، المزامنة/الطباعة التلقائية) في config.json.
    مسار الفحص مش بيتحفظ عشان يرجع دايمًا لـ Downloads مع كل تشغيل."""
    with _CONFIG_LOCK:
        try:
            d = _read_app_config()
            d.update(updates)
            tmp = CONFIG_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, CONFIG_FILE)
            return True
        except Exception as e:
            log_exception("save_app_prefs", e)
            return False

def load_print_paper():
    global _PRINT_PAPER_MM
    try:
        v = _read_app_config().get("print_paper_mm")
        if not v:
            return   # لسه مفيش مقاس محفوظ: استخدم الافتراضي من غير ضوضاء في السجل
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

def print_settings_arg(scaled=True):
    """إعدادات الطباعة لـ SumatraPDF:
    نرسل paper= فقط لو في اسم ورق حقيقي من درايفر الطابعة (الأسماء الوهمية بيتجاهلها SumatraPDF).
    ولو الصفحة اتظبط مقاسها بـ pypdf بنستخدم noscale عشان الدرايفر ميرجعش يصغّرها."""
    mode = "noscale" if scaled else "shrink"
    if _PRINT_PAPER_NAME:
        return f"paper={_PRINT_PAPER_NAME},{mode}"
    return mode

def get_default_printer_name():
    """يجلب اسم الطابعة الافتراضية مباشرة من Win32 API أو الريجستري (فوري بدون PowerShell أو أدمن)."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
        sz = wintypes.DWORD(0)
        winspool.GetDefaultPrinterW(None, ctypes.byref(sz))
        if sz.value > 0:
            buf = ctypes.create_unicode_buffer(sz.value)
            if winspool.GetDefaultPrinterW(buf, ctypes.byref(sz)):
                if buf.value.strip():
                    return buf.value.strip()
    except Exception as e:
        _log_silent("get_default_printer_win32", e)
    if WINREG_AVAILABLE:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Windows")
            val, _ = winreg.QueryValueEx(key, "Device")
            winreg.CloseKey(key)
            if val:
                return str(val).split(",")[0].strip()
        except Exception as e:
            _log_silent("get_default_printer_reg", e)
    return ""

def open_default_printer_preferences():
    """يفتح نافذة إعدادات الطابعة الافتراضية (Printing Preferences) مباشرة بدون أدمن، مع بديل لوحة الطابعات."""
    if sys.platform != "win32":
        return False
    prn = get_default_printer_name()
    sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    rundll = os.path.join(sys32, "rundll32.exe")
    if not os.path.exists(rundll):
        rundll = "rundll32.exe"
    try:
        if prn:
            subprocess.Popen([rundll, "printui.dll,PrintUIEntry", "/e", "/n", prn])
            return True
    except Exception as e:
        log_exception("open_default_printer_preferences#ui", e)
    try:
        subprocess.Popen(["control", "printers"])
        return True
    except Exception as e:
        log_exception("open_default_printer_preferences#ctrl", e)
    try:
        os.startfile("ms-settings:printers")
        return True
    except Exception as e:
        log_exception("open_default_printer_preferences#ms", e)
    return False

def list_printer_papers():
    """مقاسات الورق اللي درايفر الطابعة الافتراضية بيدعمها: (اسم الطابعة, [(اسم الورق, عرض مم, طول مم)]).
    يستخدم Win32 DeviceCapabilitiesW مباشرة (فوري بدون PowerShell أو أدمن)، مع PowerShell كبديل احتياطي."""
    if sys.platform != "win32":
        return "", []
    prn = get_default_printer_name()
    if prn:
        try:
            import ctypes
            from ctypes import wintypes
            class _POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
            winspool.DeviceCapabilitiesW.argtypes = [
                wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.WORD, ctypes.c_void_p, ctypes.c_void_p
            ]
            winspool.DeviceCapabilitiesW.restype = wintypes.DWORD
            DC_PAPERSIZE = 3
            DC_PAPERNAMES = 16
            n_names = winspool.DeviceCapabilitiesW(prn, None, DC_PAPERNAMES, None, None)
            n_sizes = winspool.DeviceCapabilitiesW(prn, None, DC_PAPERSIZE, None, None)
            if 0 < n_names < 10000 and 0 < n_sizes < 10000:
                cnt = min(n_names, n_sizes)
                name_buf = ctypes.create_unicode_buffer(n_names * 64)
                size_buf = (_POINT * n_sizes)()
                winspool.DeviceCapabilitiesW(prn, None, DC_PAPERNAMES, ctypes.byref(name_buf), None)
                winspool.DeviceCapabilitiesW(prn, None, DC_PAPERSIZE, ctypes.byref(size_buf), None)
                out = []
                for i in range(cnt):
                    raw_nm = name_buf[i * 64:(i + 1) * 64]
                    nm = raw_nm.split("\x00", 1)[0].strip()
                    w = round(size_buf[i].x / 10.0, 1)
                    h = round(size_buf[i].y / 10.0, 1)
                    if nm and w > 0 and h > 0:
                        out.append((nm, w, h))
                if out:
                    return prn, out
        except Exception as e:
            log_exception("list_printer_papers_win32", e)

    # بديل احتياطي عبر PowerShell لو Win32 مرجعش مقاسات
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
            w = float(it.get("w")) / 100.0 * 25.4
            h = float(it.get("h")) / 100.0 * 25.4
            if nm and w > 0 and h > 0:
                out.append((nm, round(w, 1), round(h, 1)))
        return str(d.get("printer") or prn or ""), out
    except Exception as e:
        log_exception("list_printer_papers", e)
        return prn, []
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
    """اتصال موحّد بقاعدة البيانات مع تفعيل WAL ومهلة انتظار 15 ثانية لمنع database is locked."""
    conn = sqlite3.connect(DB_FILE, timeout=15)
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
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
    "Windows Dark": {
        "mode": "Dark",
        "bg": "#202020", "card": "#2B2B2B", "sub_card": "#272727",
        "border": "#454545", "input": "#232323", "text": "#FFFFFF",
        "text_muted": "#9E9E9E", "primary": "#0078D4", "primary_hover": "#1B86D9",
        "success": "#6CCB5F", "danger": "#F1707B", "warning": "#FFB900", "accent": "#60CDFF"
    },
    "Windows Light": {
        "mode": "Light",
        "bg": "#F3F3F3", "card": "#FFFFFF", "sub_card": "#FAFAFA",
        "border": "#DDDDDD", "input": "#FFFFFF", "text": "#1B1B1B",
        "text_muted": "#616161", "primary": "#0078D4", "primary_hover": "#106EBE",
        "success": "#107C10", "danger": "#C42B1C", "warning": "#B44A0C", "accent": "#005A9E"
    },
    "Modern Dark": {
        "mode": "Dark",
        "bg": "#1A1F2B", "card": "#262D3E", "sub_card": "#202636",
        "border": "#3A4358", "input": "#1B2130", "text": "#F5F6FA",
        "text_muted": "#AEB6C8", "primary": "#2563EB", "primary_hover": "#1D4ED8",
        "success": "#34D399", "danger": "#F87171", "warning": "#F59E0B", "accent": "#E5B93C"
    },
    "Modern Light": {
        "mode": "Light",
        "bg": "#F4F4F5", "card": "#FFFFFF", "sub_card": "#FAFAFA",
        "border": "#E4E4E7", "input": "#FAFAFA", "text": "#18181B",
        "text_muted": "#52525B", "primary": "#2563EB", "primary_hover": "#1D4ED8",
        "success": "#15803D", "danger": "#B91C1C", "warning": "#B45309", "accent": "#854D0E"
    },
    "Aero Dark": {
        "mode": "Dark",
        "bg": "#080E17", "card": "#121E2E", "sub_card": "#0F1926",
        "border": "#1E2E42", "input": "#0A131F", "text": "#FFFFFF",
        "text_muted": "#8FA3B8", "primary": "#0284C7", "primary_hover": "#0369A1",
        "success": "#10B981", "danger": "#F87171", "warning": "#F59E0B", "accent": "#38BDF8"
    },
    "Light Modern": {
        "mode": "Light",
        "bg": "#F1F5F9", "card": "#FFFFFF", "sub_card": "#E2E8F0",
        "border": "#CBD5E1", "input": "#F8FAFC", "text": "#0F172A",
        "text_muted": "#475569", "primary": "#0284C7", "primary_hover": "#0369A1",
        "success": "#047857", "danger": "#B91C1C", "warning": "#B45309", "accent": "#0369A1"
    },
    "Cyber Amber": {
        "mode": "Dark",
        "bg": "#0B0B0D", "card": "#17171C", "sub_card": "#111114",
        "border": "#282832", "input": "#0E0E12", "text": "#FFFFFF",
        "text_muted": "#9CA3AF", "primary": "#D97706", "primary_hover": "#B45309",
        "success": "#10B981", "danger": "#F87171", "warning": "#F59E0B", "accent": "#FBBF24"
    },
    "Emerald Glass": {
        "mode": "Dark",
        "bg": "#04120D", "card": "#0A291E", "sub_card": "#061F17",
        "border": "#123829", "input": "#051811", "text": "#FFFFFF",
        "text_muted": "#86EFAC", "primary": "#059669", "primary_hover": "#047857",
        "success": "#10B981", "danger": "#FB7185", "warning": "#F59E0B", "accent": "#34D399"
    },
    "Royal Purple": {
        "mode": "Dark",
        "bg": "#0E0717", "card": "#1E1033", "sub_card": "#170C28",
        "border": "#2C1B4D", "input": "#110920", "text": "#FFFFFF",
        "text_muted": "#A8A29E", "primary": "#7C3AED", "primary_hover": "#6D28D9",
        "success": "#10B981", "danger": "#F87171", "warning": "#F59E0B", "accent": "#C084FC"
    },
    "Luxury Gold": {
        "mode": "Dark",
        "bg": "#110F0A", "card": "#1D1911", "sub_card": "#16130C",
        "border": "#52431E", "input": "#14110B", "text": "#FFFBEB",
        "text_muted": "#D4B872", "primary": "#9A6F08", "primary_hover": "#7A5806",
        "success": "#10B981", "danger": "#F87171", "warning": "#F59E0B", "accent": "#F5C542"
    },
    "Metallic Silver": {
        "mode": "Dark",
        "bg": "#16191F", "card": "#232832", "sub_card": "#1C2028",
        "border": "#5C6778", "input": "#1A1E26", "text": "#F8FAFC",
        "text_muted": "#CBD5E1", "primary": "#4B5563", "primary_hover": "#374151",
        "success": "#34D399", "danger": "#F87171", "warning": "#FBBF24", "accent": "#E2E8F0"
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
    "Windows Dark": {
        "secondary": ("#333333", "#414141"), "success_btn": ("#2B2B2B", "#17352B"),
        "tool": ("#2B2B2B", "#242145"), "warn_btn": ("#2B2B2B", "#3A2A14"), "danger_btn": ("#2B2B2B", "#3A1D1D")},
    "Windows Light": {
        "secondary": ("#FFFFFF", "#F0F0F0"), "success_btn": ("#FFFFFF", "#F0F0F0"),
        "tool": ("#FFFFFF", "#F0F0F0"), "warn_btn": ("#FFFFFF", "#F0F0F0"), "danger_btn": ("#C42B1C", "#A5231B")},
    "Modern Dark": {
        "secondary": ("#334155", "#475569"), "success_btn": ("#059669", "#047857"),
        "tool": ("#4F46E5", "#4338CA"), "warn_btn": ("#D97706", "#B45309"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Modern Light": {
        "secondary": ("#52525B", "#3F3F46"), "success_btn": ("#059669", "#047857"),
        "tool": ("#4F46E5", "#4338CA"), "warn_btn": ("#D97706", "#B45309"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Aero Dark": {
        "secondary": ("#334155", "#475569"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Light Modern": {
        "secondary": ("#475569", "#334155"), "success_btn": ("#047857", "#065F46"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Cyber Amber": {
        "secondary": ("#3F3F46", "#52525B"), "success_btn": ("#047857", "#065F46"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Emerald Glass": {
        "secondary": ("#1E3A34", "#2A4D45"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#6D28D9", "#5B21B6"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#BE123C", "#9F1239")},
    "Royal Purple": {
        "secondary": ("#3B2A5A", "#4C3A73"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#1D4ED8", "#1E40AF"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
    "Luxury Gold": {
        "secondary": ("#3A311D", "#4E4226"), "success_btn": ("#0F766E", "#115E59"),
        "tool": ("#7C5A10", "#63460B"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#B91C1C", "#991B1B")},
    "Metallic Silver": {
        "secondary": ("#3F4756", "#525C6E"), "success_btn": ("#059669", "#047857"),
        "tool": ("#475569", "#334155"), "warn_btn": ("#B45309", "#92400E"), "danger_btn": ("#DC2626", "#B91C1C")},
}
for _n, _roles in _ROLE_BTN.items():
    for _k, (_c, _h) in _roles.items():
        THEMES[_n][_k] = _c
        THEMES[_n][_k + "_hover"] = _h

# الأزرار المحايدة في الثيم الفاتح تحتاج نصًا داكنًا بأسلوب ويندوز
for _rk in ("secondary", "success_btn", "tool", "warn_btn"):
    THEMES["Windows Light"][_rk + "_text"] = "#1B1B1B"

# ستايل زر التصفير لكل الأزرار في الوضع الداكن: خلفية محايدة وإطار ونص بلون الزر
# ألوان الأزرار الأصلية من الثيمات الحالية (Modern Dark) بنفس التوزيع المعتاد
THEMES["Windows Dark"].update(
    primary_fg="#2B2B2B", primary_hoverbg="#1E2A44", primary_border="#2563EB", primary_text="#3B82F6",
    success_btn_border="#059669", success_btn_text="#34D399",
    tool_border="#4F46E5", tool_text="#818CF8",
    warn_btn_border="#D97706", warn_btn_text="#F59E0B",
    danger_btn_border="#DC2626", danger_btn_text="#F87171",
)

# أي زر في أي دور (أسماء الـ attributes في النافذة الرئيسية)
BUTTON_ROLES = {
    "primary": ["btn_run", "btn_pos_check", "btn_browse", "btn_view_rec"],
    "success_btn": ["btn_manual", "btn_cash", "btn_open_f", "btn_excel"],
    "tool": ["btn_summary_reopen", "btn_archive_downloads", "btn_arch_full"],
    "warn_btn": ["btn_print_slip", "btn_fix_printer", "btn_mini_reprint"],
    "secondary": ["btn_yesterday", "btn_today", "btn_lang", "btn_mute", "btn_back_to_mini", "btn_pdf_export", "btn_chrome"],
    "danger_btn": ["btn_elevate"],
}

TAG_COLORS = {
    "Dark": {
        "odd": ("#22293A", "#F5F6FA"),
        "dup": ("#6B1D2B", "#FECACA"), "wrong": ("#633A16", "#FED7AA"),
        "missing": ("#5A4B14", "#FEF08A"), "manual": ("#1E3A68", "#BFDBFE"),
        "void": ("#4A1D6B", "#F5D0FE")
    },
    "Light": {
        "odd": ("#F1F5F9", "#18181B"),
        "dup": ("#FFC7CE", "#9C0006"), "wrong": ("#F8CBAD", "#833C0B"),
        "missing": ("#FFEB9C", "#7F6000"), "manual": ("#DDEBF7", "#1F3864"),
        "void": ("#E9D5FF", "#581C87")
    },
}

FONT_FAMILY = "Segoe UI"
FONT_TITLE_LOGO = (FONT_FAMILY, 18, "bold")
FONT_SECTION_LBL = (FONT_FAMILY, 10, "bold")
FONT_REGULAR_BOLD = (FONT_FAMILY, 11, "bold")
FONT_KPI_VAL = (FONT_FAMILY, 16, "bold")
FONT_BTN_MAIN = (FONT_FAMILY, 12, "bold")
FONT_BTN_SUB = (FONT_FAMILY, 11, "bold")
FONT_ENTRY = (FONT_FAMILY, 11, "bold")


def theme_btn_colors(t, kind="quiet"):
    """primary = الإجراء المهم | quiet = باقي الأزرار | danger = خطر (مسح/إلغاء)"""
    if kind == "primary": return t["primary"], t["primary_hover"]
    if kind == "danger": return t["danger_btn"], t["danger_btn_hover"]
    return t["secondary"], t["secondary_hover"]


_KIND_ROLE = {"primary": "primary", "success": "success_btn", "tool": "tool",
              "warn": "warn_btn", "danger": "danger_btn", "quiet": "secondary"}

def _ghost(t, role):
    """ألوان زر حسب الثيم: ثيمات الإطار الملون (Windows) ترجع خلفية محايدة وإطارًا ونصًا بلون الزر، وغيرها اللون المعبأ المعتاد."""
    if t.get(role + "_text"):
        return {"fg_color": t.get(role + "_fg", t[role]),
                "hover_color": t.get(role + "_hoverbg", t[role + "_hover"]),
                "border_width": 1, "border_color": t.get(role + "_border", t["border"]),
                "text_color": t[role + "_text"], "text_color_disabled": t["text_muted"]}
    return {"fg_color": t[role], "hover_color": t[role + "_hover"], "text_color": "#FFFFFF"}

def make_themed_button(parent, t, kind="quiet", **kw):
    role = _KIND_ROLE.get(kind, "secondary")
    kw.update(_ghost(t, role))
    return ctk.CTkButton(parent, **kw)


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
                    font=(FONT_FAMILY, 10, "bold"), rowheight=rowheight, borderwidth=0, relief="flat")
    style.configure("A2R.Treeview.Heading", background=t["sub_card"], foreground=t["accent"],
                    font=(FONT_FAMILY, 10, "bold"), relief="flat", borderwidth=0, padding=(6, 6))
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
        "legend_text": "🟥 Duplicate   🟪 Voided (Deducted)",
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
        "mini_reprint_last": "🖨️ Reprint Last",
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
        "legend_text": "🟥 مكرر   🟪 ملغي (مخصوم)",
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
        "mini_reprint_last": "🖨️ إعادة طباعة الأخير",
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

def _win_scale(win):
    try:
        sc = float(win._get_window_scaling())
        return sc if sc > 0 else 1.0
    except Exception:
        return 1.0

def _focus_target(widget):
    if widget is None:
        return
    try:
        t = _entry_widget(widget)
        if t is not None and t.winfo_exists():
            t.focus_force()
            t.focus_set()
    except Exception as _e:
        _log_silent("focus_target", _e)

def _set_win_alpha(win, alpha):
    """تغيير شفافية النافذة بسلاسة (0.0 أثناء الرسم، 1.0 بعد الاكتمال) بدون withdraw اللي بتتعارض مع CustomTkinter."""
    try:
        if win.winfo_exists():
            win.attributes("-alpha", float(alpha))
    except Exception as _e:
        _log_silent("set_win_alpha", _e)

def _win32_raise(win):
    """رفع فعلي للنافذة نفسها على مستوى ويندوز 64-bit باستخدام GetAncestor(GA_ROOT) بدون المساس بالنافذة الرئيسية."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.BringWindowToTop.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        hwnd = wintypes.HWND(win.winfo_id())
        root_hwnd = user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT = 2 (النافذة نفسها فقط، ليس المالك)
        SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040
        HWND_TOPMOST = wintypes.HWND(-1)
        HWND_NOTOPMOST = wintypes.HWND(-2)
        user32.SetWindowPos(root_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.BringWindowToTop(root_hwnd)
        user32.SetForegroundWindow(root_hwnd)
        user32.SetWindowPos(root_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception as _e:
        _log_silent("win32_raise", _e)

def bring_window_to_front(win, focus_widget=None, delay=15):
    """يظهر النافذة مكتملة في إطار واحد بسلاسة ويرفعها أمام البرنامج بشكل مضمون مع توجيه مؤشر الكتابة."""
    def _raise():
        try:
            if not win.winfo_exists():
                return
            win.update_idletasks()
            try:
                if win.state() != "normal":
                    win.deiconify()
                    win.state("normal")
            except Exception as _e:
                _log_silent("bring_window_to_front#st", _e)
            _set_win_alpha(win, 1.0)
            win.lift()
            win.attributes("-topmost", True)
            _win32_raise(win)
            win.focus_force()
            if focus_widget is not None:
                _focus_target(focus_widget)
            def _release():
                try:
                    if not win.winfo_exists():
                        return
                    _set_win_alpha(win, 1.0)
                    win.attributes("-topmost", False)
                    win.lift()
                    _win32_raise(win)
                    if focus_widget is not None:
                        _focus_target(focus_widget)
                except Exception as _e:
                    _log_silent("bring_window_to_front#rel", _e)
            # 360ms: بعد انتهاء مؤقت CustomTkinter (200ms) وتطبيق الأيقونة (300ms) عشان النافذة تفضل قدام التطبيق دائمًا
            win.after(360, _release)
        except Exception as _e:
            _log_silent("bring_window_to_front", _e)
    try:
        if delay <= 0:
            _raise()
        else:
            win.after(delay, _raise)
    except Exception as _e:
        _log_silent("bring_window_to_front#sched", _e)

def center_window_relative(win, parent, width, height, focus_widget=None):
    win.update_idletasks()
    set_window_icon_safe(win)
    sc = _win_scale(win)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = min(int(width), int((sw - 40) / sc))
    h = min(int(height), int((sh - 80) / sc))
    pw_phys, ph_phys = int(w * sc), int(h * sc)
    try: parent_hidden = (parent.state() == "withdrawn")
    except Exception: parent_hidden = False
    if parent_hidden:
        x = max(0, (sw - pw_phys) // 2)
        y = max(0, (sh - ph_phys) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        bring_window_to_front(win, focus_widget=focus_widget)
        return
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    x = max(0, min(px + (pw - pw_phys) // 2, sw - pw_phys - 10))
    y = max(0, min(py + (ph - ph_phys) // 2, sh - ph_phys - 40))
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.transient(parent)
    bring_window_to_front(win, focus_widget=focus_widget)

def fit_and_center(win, parent, width, min_height=180, focus_widget=None):
    """يحسب الارتفاع الفعلي للنافذة بعد رسم كل العناصر حتى لا يُقص أي زر أو تذييل، ثم يوسّطها ويرفعها للأمام."""
    win.update_idletasks()
    sc = _win_scale(win)
    req_h = max(int(min_height), int(win.winfo_reqheight() / sc) + 10)
    center_window_relative(win, parent, width, req_h, focus_widget=focus_widget)

# حجم موحد ومتناسق لنافذتي 📚 سجل الأرشيف و🔍 عرض السجلات (يحترم نسبة تكبير شاشة ويندوز)
LOG_WIN_W, LOG_WIN_H = 880, 510
LOG_WIN_MIN_W, LOG_WIN_MIN_H = 740, 410

def center_window_on_screen(win, width, height, show=True):
    """يوسّط النافذة في نص الشاشة مع مراعاة نسبة تكبير ويندوز."""
    win.update_idletasks()
    set_window_icon_safe(win)
    sc = _win_scale(win)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = min(int(width), int((sw - 48) / sc))
    h = min(int(height), int((sh - 100) / sc))
    pw_phys, ph_phys = int(w * sc), int(h * sc)
    x = max(0, (sw - pw_phys) // 2)
    y = max(0, (sh - ph_phys) // 2 - 16)
    win.geometry(f"{w}x{h}+{x}+{y}")
    if show:
        bring_window_to_front(win)

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
    "القبارى", "مصطفى كامل", "مديرية الأمن", "ميناء الإسكندرية", "مجمع خدمات مصر",
    "ابيس (احتياطي)",
    "برج العرب (احتياطي 1)",
    "برج العرب (احتياطي 2)",
    "المنتزة (احتياطي)",
    "محرم بك (احتياطي)",
    "العجمي (احتياطي)"
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
    "ابيس (احتياطي)": "50325765",
    "برج العرب (احتياطي 1)": "50322364",
    "برج العرب (احتياطي 2)": "50322361",
    "المنتزة (احتياطي)": "50382150",
    "محرم بك (احتياطي)": "50381092",
    "العجمي (احتياطي)": "50381077",
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
    PAGE_W, PAGE_H = 160, 240          # مقاس التصميم؛ بيتكبّر بنفس النسبة ليملا عرض الورق المختار
    roll_w_mm = _PRINT_PAPER_MM[0] if (_PRINT_PAPER_MM and _PRINT_PAPER_MM[0] > 0) else 57.0
    _k = (roll_w_mm * 72 / 25.4) / PAGE_W
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

# ================= إضافة كروم المدمجة v2.0.0 (الشريط الجانبي + جسر محلي 127.0.0.1) =================
CHROME_EXT_DIR = os.path.join(ARCHIVE_BACKUP_DIR, "A2R_Chrome_Extension")
LOCAL_BRIDGE_HOST = "127.0.0.1"
LOCAL_BRIDGE_PORT = 47221
_CHROME_EXT_TEXT_FILES = {
    'manifest.json': '{\n  "manifest_version": 3,\n  "name": "A2R Operations Console",\n  "version": "2.9.1",\n  "description": "A2R Operations Console - Persistent Slim Resizable Sidebar (170px) & Offline Traffic Portal Manager",\n  "permissions": [\n    "tabs",\n    "alarms",\n    "sidePanel",\n    "activeTab",\n    "scripting",\n    "storage"\n  ],\n  "host_permissions": [\n    "http://127.0.0.1:47221/*"\n  ],\n  "action": {\n    "default_title": "A2R Operations Console",\n    "default_icon": {\n      "16": "icons/icon16.png",\n      "48": "icons/icon48.png",\n      "128": "icons/icon128.png"\n    }\n  },\n  "side_panel": {\n    "default_path": "sidepanel.html"\n  },\n  "content_scripts": [\n    {\n      "matches": [\n        "http://*/*",\n        "https://*/*"\n      ],\n      "js": [\n        "content_sidebar.js"\n      ],\n      "run_at": "document_start"\n    }\n  ],\n  "web_accessible_resources": [\n    {\n      "resources": [\n        "sidepanel.html",\n        "sidepanel.css",\n        "sidepanel.js",\n        "icons/*"\n      ],\n      "matches": [\n        "http://*/*",\n        "https://*/*"\n      ]\n    }\n  ],\n  "background": {\n    "service_worker": "background.js"\n  },\n  "icons": {\n    "16": "icons/icon16.png",\n    "48": "icons/icon48.png",\n    "128": "icons/icon128.png"\n  }\n}\n',
    'background.js': '// A2R Operations Console - Chrome Extension v2.7.0 (100% Offline)\n// 1) Persistent resizable slim sidebar (132px) across ALL web tabs (state & width saved in chrome.storage.local)\n// 2) Auto-pin Traffic Portal tab & keep last 4 PDF receipt tabs\n// 3) 40-second IDLE auto-return to Traffic Portal (192.168.235.50)\n\nconst PORTAL_HOST = "192.168.235.50";\nconst MAX_RECEIPT_TABS = 4;\nconst DEFAULT_IDLE_SEC = 40;\nlet idleReturnSec = DEFAULT_IDLE_SEC;\ntry {\n  chrome.storage.local.get({ a2r_idle_sec: DEFAULT_IDLE_SEC }, (res) => {\n    idleReturnSec = Number(res.a2r_idle_sec);\n    if (isNaN(idleReturnSec)) idleReturnSec = DEFAULT_IDLE_SEC;\n  });\n  chrome.storage.onChanged.addListener((changes, area) => {\n    if (area === "local" && changes.a2r_idle_sec) {\n      idleReturnSec = Number(changes.a2r_idle_sec.newValue);\n      if (isNaN(idleReturnSec)) idleReturnSec = DEFAULT_IDLE_SEC;\n    }\n  });\n} catch (_) {}\nconst KEY_OPEN = "a2r_sidebar_open";\nconst KEY_WIDTH = "a2r_sidebar_width_v3";\n\nlet lastActivityTs = Date.now();\nlet returnedForCurrentIdle = false;\n\ntry {\n  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {\n    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});\n  }\n} catch (_) {}\n\nfunction getTabUrl(tab) {\n  return ((tab && (tab.url || tab.pendingUrl)) || "").toLowerCase();\n}\n\nfunction canInjectSlimSidebar(tab) {\n  const u = getTabUrl(tab);\n  if (!u.startsWith("http://") && !u.startsWith("https://")) return false;\n  if (u.startsWith("https://chrome.google.com/webstore") || u.startsWith("https://chromewebstore.google.com")) return false;\n  if (u.endsWith(".pdf") || u.includes("quote_receipt") || u.includes("127.0.0.1:47221/api/pdf")) return false;\n  return true;\n}\n\nchrome.action.onClicked.addListener((tab) => {\n  if (!tab || tab.id === undefined) return;\n  markUserActive();\n\n  if (!canInjectSlimSidebar(tab)) {\n    try {\n      if (chrome.sidePanel && chrome.sidePanel.open && tab.windowId !== undefined) {\n        chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});\n      }\n    } catch (_) {}\n    return;\n  }\n\n  chrome.storage.local.get({ [KEY_OPEN]: true, [KEY_WIDTH]: 0 }, (res) => {\n    // v92: الضغط على أيقونة الإضافة يفتح الشريط دائمًا (الإغلاق من زر ✕ فقط)\n    const nextOpen = true;\n    const savedWidth = res[KEY_WIDTH] || 0;\n    chrome.storage.local.set({ [KEY_OPEN]: nextOpen });\n\n    chrome.tabs.sendMessage(tab.id, { type: "A2R_SET_SIDEBAR", open: nextOpen, width: savedWidth }).catch(async () => {\n      try {\n        await chrome.scripting.executeScript({\n          target: { tabId: tab.id },\n          files: ["content_sidebar.js"],\n        });\n        await chrome.tabs.sendMessage(tab.id, { type: "A2R_SET_SIDEBAR", open: nextOpen, width: savedWidth });\n      } catch (_) {\n        try {\n          if (chrome.sidePanel && chrome.sidePanel.open && tab.windowId !== undefined) {\n            chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});\n          }\n        } catch (_) {}\n      }\n    });\n  });\n});\n\nfunction isPortalTab(tab) {\n  const u = getTabUrl(tab);\n  if (!u.includes(PORTAL_HOST)) return false;\n  if (u.includes("quote_receipt") || u.includes(".pdf") || u.startsWith("blob:") || u.includes("receipt")) {\n    return false;\n  }\n  return true;\n}\n\nfunction isProtectedChromePage(tab) {\n  const u = getTabUrl(tab);\n  return u.startsWith("chrome://extensions") || u.startsWith("chrome://settings");\n}\n\nfunction isReceiptPdfTab(tab, portalTabIds) {\n  if (!tab || tab.pinned) return false;\n  const u = getTabUrl(tab);\n  if (!u) return false;\n  if (isPortalTab(tab)) return false;\n\n  if (u.includes("quote_receipt") || u.includes("127.0.0.1:47221/api/pdf")) return true;\n  if (u.includes(PORTAL_HOST) && (u.includes(".pdf") || u.startsWith("blob:") || u.includes("receipt"))) {\n    return true;\n  }\n  if (\n    tab.openerTabId &&\n    portalTabIds.has(tab.openerTabId) &&\n    (u.includes(".pdf") || u.startsWith("blob:") || u.startsWith("data:application/pdf"))\n  ) {\n    return true;\n  }\n  return false;\n}\n\nfunction markUserActive() {\n  lastActivityTs = Date.now();\n  returnedForCurrentIdle = false;\n}\n\nasync function maintainPinAndReceipts(windowId) {\n  try {\n    const tabs = await chrome.tabs.query({ windowId });\n    const portalTabs = tabs.filter(isPortalTab);\n    const portalTabIds = new Set(portalTabs.map((t) => t.id));\n    for (const pt of portalTabs) {\n      if (!pt.pinned) {\n        chrome.tabs.update(pt.id, { pinned: true }).catch(() => {});\n      }\n    }\n    const receiptTabs = tabs\n      .filter((t) => isReceiptPdfTab(t, portalTabIds))\n      .sort((a, b) => a.id - b.id);\n    if (receiptTabs.length > MAX_RECEIPT_TABS) {\n      const toClose = receiptTabs.slice(0, receiptTabs.length - MAX_RECEIPT_TABS);\n      for (const oldTab of toClose) {\n        chrome.tabs.remove(oldTab.id).catch(() => {});\n      }\n    }\n  } catch (_) {}\n}\n\nasync function checkIdleAndReturnToPortal() {\n  try {\n    if (returnedForCurrentIdle) return;\n    const idleSec = (Date.now() - lastActivityTs) / 1000;\n    if (!idleReturnSec) return;\n    if (idleSec < idleReturnSec) return;\n\n    let activeTabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });\n    if (!activeTabs || !activeTabs.length) {\n      activeTabs = await chrome.tabs.query({ active: true });\n    }\n    if (!activeTabs || !activeTabs.length) return;\n\n    const curTab = activeTabs[0];\n    if (!curTab || isPortalTab(curTab) || isProtectedChromePage(curTab)) return;\n\n    let winTabs = await chrome.tabs.query({ windowId: curTab.windowId });\n    let portal = winTabs.find(isPortalTab);\n\n    if (portal) {\n      if (!portal.active) {\n        returnedForCurrentIdle = true;\n        await chrome.tabs.update(portal.id, { active: true });\n      }\n      return;\n    }\n\n    const allTabs = await chrome.tabs.query({});\n    portal = allTabs.find(isPortalTab);\n    if (portal && portal.id !== curTab.id) {\n      returnedForCurrentIdle = true;\n      if (portal.windowId !== undefined) {\n        await chrome.windows.update(portal.windowId, { focused: true }).catch(() => {});\n      }\n      await chrome.tabs.update(portal.id, { active: true }).catch(() => {});\n    }\n  } catch (_) {}\n}\n\nsetInterval(checkIdleAndReturnToPortal, 2000);\n\nfunction scheduleAlarmFallback() {\n  try {\n    if (!idleReturnSec) return;\n    chrome.alarms.clear("a2r_idle_check").catch(() => {});\n    chrome.alarms.create("a2r_idle_check", { when: Date.now() + idleReturnSec * 1000 });\n  } catch (_) {}\n}\n\nchrome.alarms.onAlarm.addListener((alarm) => {\n  if (alarm && alarm.name === "a2r_idle_check") {\n    checkIdleAndReturnToPortal();\n  }\n});\n\nchrome.runtime.onMessage.addListener((msg) => {\n  if (!msg) return;\n  if (msg.type === "A2R_USER_ACTIVITY") {\n    markUserActive();\n    scheduleAlarmFallback();\n  } else if (msg.type === "A2R_GOTO_PORTAL") {\n    (async () => {\n      try {\n        const all = await chrome.tabs.query({});\n        const portal = all.find(isPortalTab);\n        if (portal) {\n          if (portal.windowId !== undefined) await chrome.windows.update(portal.windowId, { focused: true }).catch(() => {});\n          await chrome.tabs.update(portal.id, { active: true }).catch(() => {});\n        } else {\n          await chrome.tabs.create({ url: "http://" + PORTAL_HOST + "/" }).catch(() => {});\n        }\n      } catch (_) {}\n    })();\n  } else if (msg.type === "A2R_OPEN_TAB" && msg.url) {\n    chrome.tabs.create({ url: msg.url }).catch(() => {});\n  }\n});\n\nchrome.tabs.onCreated.addListener((tab) => {\n  if (!tab) return;\n  markUserActive();\n  scheduleAlarmFallback();\n  if (tab.windowId !== undefined) maintainPinAndReceipts(tab.windowId);\n});\n\nchrome.tabs.onActivated.addListener((activeInfo) => {\n  if (!activeInfo) return;\n  markUserActive();\n  scheduleAlarmFallback();\n  if (activeInfo.windowId !== undefined) maintainPinAndReceipts(activeInfo.windowId);\n});\n\nchrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {\n  if (!tab) return;\n  if (changeInfo.status === "complete" || changeInfo.url) {\n    if (tab.windowId !== undefined) maintainPinAndReceipts(tab.windowId);\n  }\n});\n',
    'content_sidebar.js': '// A2R Operations Console - Persistent Resizable Slim Sidebar (170px, Push-Layout, Chrome Dark) + Idle Detector\n(() => {\n  const HOST_ID = "a2r-slim-sidebar-host";\n  const PUSH_STYLE_ID = "a2r-slim-sidebar-push-style";\n  const KEY_OPEN = "a2r_sidebar_open";\n  const KEY_WIDTH = "a2r_sidebar_width_v3";\n  const KEY_SITES = "a2r_sidebar_sites";\n  const PORTAL_HOST = "192.168.235.50";\n  const DEFAULT_WIDTH = 170;\n  const MIN_WIDTH = 145;\n  const MAX_WIDTH = 480;\n\n  // v91: العرض الافتراضي نسبة من عرض نافذة المتصفح (12%) بحد أدنى 150 وأقصى 300\n  function autoWidth() {\n    return Math.max(150, Math.min(300, Math.round(window.innerWidth * 0.12)));\n  }\n  let currentWidth = autoWidth();\n\n  function clampWidth(w) {\n    const n = Math.round(Number(w) || DEFAULT_WIDTH);\n    return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, n));\n  }\n\n  function applyPagePush(w) {\n    let st = document.getElementById(PUSH_STYLE_ID);\n    if (!st) {\n      st = document.createElement("style");\n      st.id = PUSH_STYLE_ID;\n      (document.head || document.documentElement).appendChild(st);\n    }\n    st.textContent = `\n      html {\n        width: calc(100% - ${w}px) !important;\n        max-width: calc(100% - ${w}px) !important;\n        margin-right: ${w}px !important;\n        box-sizing: border-box !important;\n      }\n      body {\n        max-width: 100% !important;\n        box-sizing: border-box !important;\n      }\n    `;\n  }\n\n  function removePagePush() {\n    const st = document.getElementById(PUSH_STYLE_ID);\n    if (st) st.remove();\n  }\n\n  function applyWidth(w) {\n    currentWidth = clampWidth(w);\n    const host = document.getElementById(HOST_ID);\n    if (host) {\n      host.style.setProperty("width", `${currentWidth}px`, "important");\n      applyPagePush(currentWidth);\n    }\n  }\n\n  function closeSidebar() {\n    const el = document.getElementById(HOST_ID);\n    if (el) el.remove();\n    removePagePush();\n  }\n\n  function openSidebar(widthPx = currentWidth) {\n    currentWidth = clampWidth(widthPx);\n    const existing = document.getElementById(HOST_ID);\n    if (existing) {\n      existing.style.setProperty("width", `${currentWidth}px`, "important");\n      applyPagePush(currentWidth);\n      return;\n    }\n\n    applyPagePush(currentWidth);\n\n    const host = document.createElement("div");\n    host.id = HOST_ID;\n    host.style.cssText = [\n      "position:fixed",\n      "top:0",\n      "right:0",\n      `width:${currentWidth}px`,\n      "height:100vh",\n      "z-index:2147483647",\n      "box-shadow:-1px 0 8px rgba(0,0,0,0.35)",\n      "border-left:1px solid #3C4043",\n      "background:#202124",\n      "margin:0",\n      "padding:0",\n      "overflow:hidden",\n      "box-sizing:border-box"\n    ].join(" !important;") + " !important;";\n\n    // Easy-to-grab 8px left-edge drag handle with subtle center grip pill\n    const handle = document.createElement("div");\n    handle.title = "اسحب لتكبير أو تصغير العرض (دبل كليك للحجم التلقائي حسب المتصفح)";\n    handle.style.cssText = [\n      "position:absolute",\n      "top:0",\n      "left:0",\n      "width:8px",\n      "height:100%",\n      "cursor:ew-resize",\n      "z-index:10",\n      "background:transparent",\n      "display:flex",\n      "align-items:center",\n      "justify-content:center",\n      "transition:background 0.15s ease"\n    ].join(" !important;") + " !important;";\n\n    const grip = document.createElement("div");\n    grip.style.cssText = [\n      "width:3px",\n      "height:38px",\n      "border-radius:3px",\n      "background:rgba(154,160,166,0.45)",\n      "pointer-events:none"\n    ].join(" !important;") + " !important;";\n    handle.appendChild(grip);\n\n    handle.addEventListener("mouseenter", () => {\n      handle.style.setProperty("background", "rgba(138, 180, 248, 0.25)", "important");\n      grip.style.setProperty("background", "#8AB4F8", "important");\n    });\n    handle.addEventListener("mouseleave", () => {\n      if (!handle.dataset.dragging) {\n        handle.style.setProperty("background", "transparent", "important");\n        grip.style.setProperty("background", "rgba(154,160,166,0.45)", "important");\n      }\n    });\n\n    handle.addEventListener("dblclick", (ev) => {\n      ev.preventDefault();\n      ev.stopPropagation();\n      applyWidth(autoWidth());\n      try { chrome.storage.local.set({ [KEY_WIDTH]: currentWidth }); } catch (_) {}\n    });\n\n    handle.addEventListener("mousedown", (ev) => {\n      ev.preventDefault();\n      ev.stopPropagation();\n      handle.dataset.dragging = "1";\n      handle.style.setProperty("background", "rgba(138, 180, 248, 0.45)", "important");\n      grip.style.setProperty("background", "#8AB4F8", "important");\n\n      const shield = document.createElement("div");\n      shield.style.cssText = "position:fixed !important;inset:0 !important;z-index:2147483647 !important;cursor:ew-resize !important;background:transparent !important;";\n      (document.documentElement || document.body).appendChild(shield);\n\n      const onMove = (mEv) => {\n        const w = clampWidth(window.innerWidth - mEv.clientX);\n        applyWidth(w);\n        notifyActivity();\n      };\n\n      const onUp = () => {\n        delete handle.dataset.dragging;\n        handle.style.setProperty("background", "transparent", "important");\n        grip.style.setProperty("background", "rgba(154,160,166,0.45)", "important");\n        window.removeEventListener("mousemove", onMove, true);\n        window.removeEventListener("mouseup", onUp, true);\n        shield.remove();\n        try { chrome.storage.local.set({ [KEY_WIDTH]: currentWidth }); } catch (_) {}\n      };\n\n      window.addEventListener("mousemove", onMove, true);\n      window.addEventListener("mouseup", onUp, true);\n    });\n\n    const iframe = document.createElement("iframe");\n    iframe.src = chrome.runtime.getURL("sidepanel.html?mode=slim");\n    iframe.style.cssText = "width:100% !important;height:100% !important;border:0 !important;display:block !important;background:#202124 !important;";\n    iframe.allow = "clipboard-write";\n\n    host.appendChild(handle);\n    host.appendChild(iframe);\n    (document.documentElement || document.body).appendChild(host);\n  }\n\n  function setSidebarOpen(open, persist = false) {\n    if (open) openSidebar(currentWidth);\n    else closeSidebar();\n    if (persist) {\n      try { chrome.storage.local.set({ [KEY_OPEN]: !!open }); } catch (_) {}\n    }\n    return { open: !!open };\n  }\n\n  function toggleSidebar() {\n    const next = !document.getElementById(HOST_ID);\n    return setSidebarOpen(next, true);\n  }\n\n  window.__a2rToggleSidebar = toggleSidebar;\n\n  if (window.__a2rSlimSidebarLoaded) return;\n  window.__a2rSlimSidebarLoaded = true;\n\n  let lastPing = 0;\n  function notifyActivity() {\n    const now = Date.now();\n    if (now - lastPing < 2000) return;\n    lastPing = now;\n    try {\n      chrome.runtime.sendMessage({ type: "A2R_USER_ACTIVITY" }).catch(() => {});\n    } catch (_) {}\n  }\n\n  ["mousedown", "pointerdown", "click", "keydown", "input", "wheel", "scroll", "mousemove", "touchstart"].forEach((evName) => {\n    window.addEventListener(evName, notifyActivity, { passive: true, capture: true });\n  });\n\n  // الفتح التلقائي: على بوابة المرور + المواقع المثبتة فقط (بدل كل المواقع)\n  let lastOpenEnabled = true;\n  let pinnedSites = {};\n  function siteAllowed() {\n    const host = location.hostname;\n    return host === PORTAL_HOST || !!pinnedSites[host];\n  }\n  try {\n    chrome.storage.local.get({ [KEY_OPEN]: true, [KEY_WIDTH]: 0, [KEY_SITES]: {} }, (res) => {\n      if (chrome.runtime.lastError) return;\n      currentWidth = Number(res[KEY_WIDTH]) > 0 ? clampWidth(res[KEY_WIDTH]) : autoWidth();\n      lastOpenEnabled = res[KEY_OPEN] !== false;\n      pinnedSites = res[KEY_SITES] || {};\n      if (lastOpenEnabled && siteAllowed()) {\n        openSidebar(currentWidth);\n      }\n    });\n  } catch (_) {}\n\n  // Live sync open/close state and resized width across ALL open tabs simultaneously\n  try {\n    chrome.storage.onChanged.addListener((changes, area) => {\n      if (area !== "local") return;\n      if (changes[KEY_WIDTH] && changes[KEY_WIDTH].newValue !== undefined) {\n        applyWidth(changes[KEY_WIDTH].newValue);\n      }\n      if (changes[KEY_OPEN] && changes[KEY_OPEN].newValue !== undefined) {\n        lastOpenEnabled = changes[KEY_OPEN].newValue !== false;\n        if (changes[KEY_OPEN].newValue) openSidebar(currentWidth);\n        else closeSidebar();\n      }\n      if (changes[KEY_SITES]) {\n        pinnedSites = changes[KEY_SITES].newValue || {};\n        if (!siteAllowed()) closeSidebar();\n        else if (lastOpenEnabled) openSidebar(currentWidth);\n      }\n    });\n  } catch (_) {}\n\n  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {\n    if (!msg) return;\n    if (msg.type === "A2R_TOGGLE_SIDEBAR") {\n      sendResponse(toggleSidebar());\n      return true;\n    }\n    if (msg.type === "A2R_SET_SIDEBAR") {\n      if (Number(msg.width) > 0) currentWidth = clampWidth(msg.width);\n      sendResponse(setSidebarOpen(!!msg.open, false));\n      return true;\n    }\n  });\n\n  window.addEventListener("message", (ev) => {\n    if (!ev || !ev.data) return;\n    if (ev.data.type === "A2R_TOGGLE_SITE") {\n      const host = location.hostname;\n      try {\n        chrome.storage.local.get({ [KEY_SITES]: {} }, (res) => {\n          const sites = res[KEY_SITES] || {};\n          const fixed = host === PORTAL_HOST;\n          if (!fixed) {\n            if (sites[host]) { delete sites[host]; closeSidebar(); }\n            else sites[host] = true;\n            pinnedSites = sites;\n            chrome.storage.local.set({ [KEY_SITES]: sites });\n          }\n          if (ev.source) ev.source.postMessage({ type: "A2R_SITE_STATE", pinned: fixed || !!sites[host], fixed }, "*");\n        });\n      } catch (_) {}\n      return;\n    }\n    if (ev.data.type === "A2R_QUERY_SITE") {\n      const host = location.hostname;\n      try {\n        chrome.storage.local.get({ [KEY_SITES]: {} }, (res) => {\n          const sites = res[KEY_SITES] || {};\n          if (ev.source) ev.source.postMessage({ type: "A2R_SITE_STATE", pinned: host === PORTAL_HOST || !!sites[host], fixed: host === PORTAL_HOST }, "*");\n        });\n      } catch (_) {}\n      return;\n    }\n    if (ev.data.type === "A2R_CLOSE_SIDEBAR") {\n      setSidebarOpen(false, true);\n    } else if (ev.data.type === "A2R_USER_ACTIVITY") {\n      notifyActivity();\n    }\n  });\n})();\n',
    'sidepanel.html': '<!DOCTYPE html>\n<html lang="ar" dir="rtl">\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>A2R Operations Console</title>\n  <link rel="stylesheet" href="sidepanel.css">\n</head>\n<body>\n  <header class="topbar">\n    <div class="brand">\n      <span class="logo">A2R</span>\n      <span id="connBadge" class="badge offline">● مغلق</span>\n    </div>\n    <div class="top-actions">\n      <button id="btnPinSite" class="icon-btn hidden" title="تشغيل الإضافة تلقائيًا على هذا الموقع">📍</button>\n      <button id="btnTopOpenApp" class="icon-btn" title="إظهار البرنامج">🖥️</button>\n      <button id="btnCloseSlim" class="icon-btn close-btn hidden" title="إغلاق">✕</button>\n    </div>\n  </header>\n\n  <button id="btnPortal" class="btn portal" title="الرجوع لتبويب بوابة المرور">🏠 البوابة</button>\n\n  <nav class="tabs">\n    <button class="tab-btn active" data-tab="home">الرئيسية</button>\n    <button class="tab-btn" data-tab="records">السجلات</button>\n    <button class="tab-btn" data-tab="archive">الأرشيف</button>\n  </nav>\n\n  <div id="toast" class="toast hidden"></div>\n\n  <main class="content">\n    <!-- TAB 1: HOME -->\n    <section id="tab-home" class="tab-pane active">\n      <div class="stack">\n        <div class="kpi-card green">\n          <div class="kpi-title">إجمالي السيستم</div>\n          <div id="kpiSum" class="kpi-val green-txt">0.00</div>\n        </div>\n\n        <div class="kpi-card blue">\n          <div class="kpi-title">عدد العمليات</div>\n          <div id="kpiCount" class="kpi-val">0</div>\n        </div>\n\n        <div class="kpi-mini-stack hidden" aria-hidden="true">\n          <div class="mini-line"><span>مطبوع اليوم</span><strong id="kpiPrinted">0</strong></div>\n          <div class="mini-line"><span>ملغي</span><strong id="kpiVoid">0</strong></div>\n          <div class="mini-line"><span>مكرر</span><strong id="kpiDup">0</strong></div>\n        </div>\n\n        <!-- الأزرار بالترتيب المطلوب -->\n        <button id="btnScan" class="btn primary full">⚡ فحص اليوم</button>\n        <div id="scanProg" class="scan-prog hidden"><div id="scanProgFill" class="scan-prog-fill"></div><span id="scanProgPct" class="scan-prog-pct">0%</span></div>\n\n        <button id="btnSummaryPdf" class="btn neutral full">📄 ملخص الفحص PDF</button>\n        <div id="summaryBox" class="card compact hidden">\n          <div class="row-between">\n            <span class="card-title">اختر الوحدة للملخص</span>\n            <button id="btnSumCancel" class="chip-btn">✕</button>\n          </div>\n          <select id="sumUnit" class="input full mt-4"></select>\n          <div id="sumTid" class="hint mt-4">الماكينة: —</div>\n          <button id="btnSumPrint" class="btn primary full mt-4">📄 فتح الملخص PDF</button>\n        </div>\n\n        <button id="btnQuickManual" class="btn neutral full">➕ معاملة يدوية</button>\n        <div id="manualBox" class="card compact hidden">\n          <div class="row-between">\n            <span class="card-title">معاملة يدوية PDF</span>\n            <button id="btnManualCancel" class="chip-btn">✕</button>\n          </div>\n          <input id="mAmount" type="number" step="0.01" placeholder="المبلغ + Enter *" class="input full mt-4">\n          <input id="mName" type="text" placeholder="اسم المؤمن له (اختياري)" class="input full mt-4">\n          <input id="mPlate" type="text" placeholder="رقم اللوحة (اختياري)" class="input full mt-4">\n          <select id="mUnit" class="input full mt-4"></select>\n          <button id="btnAddManual" class="btn primary full mt-4">توليد وطباعة (Enter)</button>\n        </div>\n\n        <button id="btnViewRecords" class="btn neutral full">🔍 عرض السجل</button>\n\n        <button id="btnReprintLast" class="btn neutral full">🖨️ طباعة الأخير</button>\n\n        <div id="archStatus" class="arch-pill">—</div>\n\n        <div class="settings-row">\n          <span>الرجوع التلقائي للبوابة</span>\n          <select id="selIdle" class="input">\n            <option value="0">إيقاف</option>\n            <option value="40">40 ثانية</option>\n            <option value="120">دقيقتان</option>\n          </select>\n        </div>\n      </div>\n    </section>\n\n    <!-- TAB 2: RECORDS -->\n    <section id="tab-records" class="tab-pane">\n      <div class="card compact">\n        <input id="recSearch" type="text" placeholder="بحث اسم، لوحة، شاسيه، مبلغ..." class="input full">\n        <select id="recFilter" class="input full mt-4">\n          <option value="all">كل الحالات</option>\n          <option value="ok">سليم</option>\n          <option value="manual">يدوي</option>\n          <option value="dup">مكرر</option>\n          <option value="void">ملغي</option>\n        </select>\n        <div id="recStats" class="hint mt-4">0 سجل</div>\n      </div>\n      <div id="recList" class="list-box"></div>\n    </section>\n\n    <!-- TAB 3: ARCHIVE -->\n    <section id="tab-archive" class="tab-pane">\n      <div class="card compact">\n        <input id="archQuery" type="text" placeholder="بحث في الأرشيف..." class="input full">\n        <button id="btnArchSearch" class="btn primary full mt-4">🔎 بحث</button>\n        <div id="archAuthRow" class="mt-4">\n          <input id="archPwd" type="password" placeholder="كلمة مرور المشرف" class="input full">\n          <button id="btnArchUnlock" class="btn neutral full mt-4">دخول المشرف</button>\n        </div>\n        <div id="archRoleHint" class="hint mt-4">آخر 7 أيام (للمشرف: الكل)</div>\n      </div>\n      <div id="archResults" class="list-box"></div>\n    </section>\n  </main>\n\n  <footer class="footer">\n    <span id="footVer">A2R • Ahmed Ramadan</span>\n  </footer>\n\n  <script src="sidepanel.js"></script>\n</body>\n</html>\n',
    'sidepanel.css': '* { box-sizing: border-box; margin: 0; padding: 0; }\n:root {\n  --bg: #202124;\n  --surface: #292A2D;\n  --surface-hover: #35363A;\n  --input: #171717;\n  --border: #3C4043;\n  --text: #E8EAED;\n  --muted: #9AA0A6;\n  --accent: #8AB4F8;\n  --accent-bg: #1A73E8;\n  --accent-bg-h: #1B66C9;\n  --green: #81C995;\n  --warn: #FDD663;\n  --danger: #F28B82;\n}\nbody {\n  font-family: "Segoe UI", Roboto, Tahoma, sans-serif;\n  background: var(--bg);\n  color: var(--text);\n  font-size: 11px;\n  display: flex;\n  flex-direction: column;\n  height: 100vh;\n  overflow: hidden;\n  -webkit-font-smoothing: antialiased;\n}\n.topbar {\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  padding: 6px 6px 5px;\n  background: var(--bg);\n  border-bottom: 1px solid var(--border);\n}\n.brand { display: flex; align-items: center; gap: 5px; }\n.logo { font-size: 12px; font-weight: 700; color: var(--text); letter-spacing: 0.4px; }\n.badge { font-size: 8.5px; font-weight: 600; padding: 1px 5px; border-radius: 99px; }\n.badge.online { background: rgba(129, 201, 149, 0.14); color: var(--green); }\n.badge.offline { background: rgba(242, 139, 130, 0.14); color: var(--danger); }\n.top-actions { display: flex; gap: 3px; }\n.icon-btn {\n  background: transparent; color: var(--muted); border: 1px solid transparent;\n  border-radius: 50%; width: 22px; height: 22px; cursor: pointer; font-size: 10.5px;\n  display: flex; align-items: center; justify-content: center; transition: background 0.15s;\n}\n.icon-btn:hover { background: var(--surface-hover); color: var(--text); }\n.icon-btn.close-btn:hover { background: rgba(242, 139, 130, 0.18); color: var(--danger); }\n\n.tabs {\n  display: grid;\n  grid-template-columns: repeat(3, 1fr);\n  gap: 3px;\n  padding: 5px 5px;\n  background: var(--bg);\n  border-bottom: 1px solid var(--border);\n}\n.tab-btn {\n  background: transparent; color: var(--muted); border: 1px solid transparent;\n  border-radius: 14px; padding: 5px 2px; font-weight: 600; font-size: 10px; cursor: pointer;\n  transition: background 0.15s, color 0.15s;\n}\n.tab-btn:hover { background: var(--surface); color: var(--text); }\n.tab-btn.active {\n  background: rgba(138, 180, 248, 0.16);\n  color: var(--accent);\n  border-color: rgba(138, 180, 248, 0.35);\n}\n\n.content { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 6px 5px; }\n.content::-webkit-scrollbar { width: 4px; }\n.content::-webkit-scrollbar-thumb { background: #4A4D51; border-radius: 4px; }\n.tab-pane { display: none; }\n.tab-pane.active { display: block; }\n\n.stack { display: flex; flex-direction: column; gap: 6px; }\n.hidden { display: none !important; }\n\n.card {\n  background: var(--surface); border: 1px solid var(--border);\n  border-radius: 8px; padding: 7px 6px; margin-bottom: 6px;\n}\n.card.compact { padding: 6px; }\n.card-title { font-size: 10px; font-weight: 600; color: var(--accent); }\n.hint { font-size: 8.5px; color: var(--muted); }\n.center { text-align: center; }\n\n.row-between { display: flex; align-items: center; justify-content: space-between; }\n.full { width: 100%; }\n.mt-4 { margin-top: 5px; }\n\n.input {\n  background: var(--input); color: var(--text); border: 1px solid var(--border);\n  border-radius: 6px; padding: 6px 6px; font-size: 10px; outline: none; width: 100%;\n  transition: border-color 0.15s;\n}\n.input:focus { border-color: var(--accent); }\n.input::placeholder { color: #7F868C; }\n\n/* أزرار بنمط جوجل كروم الداكن */\n.btn {\n  border: 1px solid var(--border); border-radius: 18px; padding: 8px 6px; min-height: 34px;\n  color: var(--text); font-weight: 600; font-size: 10.5px; line-height: 1.25;\n  cursor: pointer; text-align: center; display: flex; align-items: center;\n  justify-content: center; gap: 4px; word-break: break-word;\n  transition: background 0.15s, border-color 0.15s;\n}\n.btn.primary {\n  background: var(--accent-bg); border-color: var(--accent-bg); color: #FFFFFF;\n}\n.btn.primary:hover { background: var(--accent-bg-h); border-color: var(--accent-bg-h); }\n.btn.neutral { background: var(--surface); color: var(--text); }\n.btn.neutral:hover { background: var(--surface-hover); border-color: #5F6368; }\n.btn:disabled { opacity: 0.5; cursor: not-allowed; }\n\n.chip-btn {\n  background: var(--surface-hover); color: var(--text); border: 1px solid var(--border);\n  border-radius: 12px; padding: 1px 6px; font-size: 9px; font-weight: 600; cursor: pointer;\n}\n.chip-btn:hover { border-color: var(--accent); color: var(--accent); }\n\n.kpi-card {\n  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;\n  padding: 6px 7px;\n}\n.kpi-title { font-size: 9px; color: var(--muted); font-weight: 600; }\n.kpi-val { font-size: 15px; font-weight: 700; margin-top: 2px; direction: ltr; text-align: right; color: var(--text); }\n.green-txt { color: var(--green); }\n\n.kpi-mini-stack {\n  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;\n  padding: 5px 7px; display: flex; flex-direction: column; gap: 3px; font-size: 9.5px;\n}\n.mini-line { display: flex; justify-content: space-between; color: var(--muted); }\n.mini-line strong { color: var(--text); font-weight: 600; }\n\n.arch-pill {\n  background: transparent; border: 1px solid var(--border); border-radius: 8px;\n  padding: 5px 4px; font-size: 8.5px; font-weight: 600; text-align: center; color: var(--green);\n}\n\n.match-result { font-size: 9.5px; font-weight: 600; margin-top: 4px; min-height: 12px; }\n.match-ok { color: var(--green); }\n.match-short { color: var(--danger); }\n.match-extra { color: var(--warn); }\n\n.list-box { display: flex; flex-direction: column; gap: 5px; }\n.rec-item {\n  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;\n  padding: 6px 5px; border-right: 3px solid var(--accent);\n}\n.rec-item.kind-dup { background: rgba(242, 139, 130, 0.12); border-right-color: var(--danger); }\n.rec-item.kind-void { background: rgba(197, 138, 249, 0.12); border-right-color: #C58AF9; }\n.rec-item.kind-manual { background: rgba(138, 180, 248, 0.1); border-right-color: var(--accent); }\n.rec-item.kind-missing, .rec-item.kind-wrong { background: rgba(253, 214, 99, 0.1); border-right-color: var(--warn); }\n\n.rec-top { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 9.5px; gap: 3px; }\n.rec-amt { color: var(--green); font-size: 10px; white-space: nowrap; }\n.rec-item.kind-void .rec-amt { color: #D7AEFB; text-decoration: line-through; }\n.rec-meta { font-size: 8.5px; color: var(--muted); margin-top: 2px; line-height: 1.3; word-break: break-word; }\n.rec-actions { display: flex; flex-direction: column; gap: 3px; margin-top: 5px; }\n.rec-actions button {\n  width: 100%; padding: 4px 4px; font-size: 9.5px; border-radius: 12px; border: 1px solid var(--border);\n  background: var(--bg); color: var(--text); cursor: pointer; font-weight: 600;\n}\n.rec-actions button:hover { background: var(--surface-hover); border-color: var(--accent); }\n.rec-actions button.btn-v { color: var(--danger); }\n.rec-actions button.btn-r { color: var(--green); }\n\n.denom-stack { display: flex; flex-direction: column; gap: 3px; }\n.denom-item { display: flex; align-items: center; gap: 3px; font-size: 9.5px; }\n.denom-item span { width: 32px; color: var(--muted); font-weight: 600; }\n.denom-item input { flex: 1; text-align: center; padding: 3px 2px; }\n.cash-summary {\n  background: var(--input); border: 1px solid var(--border); border-radius: 6px;\n  padding: 5px; font-size: 9.5px; display: flex; flex-direction: column; gap: 2px;\n}\n\n.toast {\n  position: fixed; bottom: 24px; left: 5px; right: 5px; z-index: 99;\n  background: #303134; color: var(--text); border: 1px solid var(--border);\n  box-shadow: 0 2px 8px rgba(0,0,0,0.45);\n  border-radius: 8px; padding: 6px 6px; font-size: 9.5px; font-weight: 600; text-align: center;\n}\n\n.footer {\n  padding: 4px 5px; background: var(--bg); border-top: 1px solid var(--border);\n  text-align: center; font-size: 8.5px; color: var(--muted); font-weight: 500;\n}\n\n/* تكيف تلقائي عند تكبير عرض الشريط الجانبي بالسحب */\n@media (min-width: 210px) {  /* لوحة كروم الجانبية فقط (body.sp)؛ الشريط الملصوق يكبر بالـzoom */\n  body.sp { font-size: 12px; }\n  body.sp .logo { font-size: 13.5px; }\n  body.sp .badge { font-size: 10px; padding: 2px 7px; }\n  body.sp .tab-btn { font-size: 11px; padding: 6px 4px; }\n  body.sp .kpi-title { font-size: 10.5px; }\n  body.sp .kpi-val { font-size: 19px; }\n  body.sp .btn { font-size: 11.5px; min-height: 36px; padding: 9px 10px; }\n  body.sp .input { font-size: 11.5px; padding: 7px 8px; }\n  body.sp .rec-top { font-size: 11.5px; }\n  body.sp .rec-amt { font-size: 12px; }\n  body.sp .rec-meta { font-size: 10px; }\n  body.sp .rec-actions { flex-direction: row; }\n}\n\n/* v2.8: شريط تقدم الفحص + صف سبب الإلغاء + صف الإعدادات + زر تثبيت الموقع */\n.scan-prog { position: relative; background: var(--input); border: 1px solid var(--border); border-radius: 99px; height: 14px; overflow: hidden; }\n.scan-prog-fill { height: 100%; width: 0%; background: var(--accent-bg); transition: width 0.3s ease; }\n.scan-prog-pct { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 8.5px; font-weight: 700; color: var(--text); direction: ltr; }\n.settings-row { display: flex; align-items: center; justify-content: space-between; gap: 5px; font-size: 9px; color: var(--muted); font-weight: 600; padding: 2px 1px; }\n.settings-row select { width: auto; padding: 3px 4px; }\n.icon-btn.pinned { color: var(--accent); border-color: rgba(138,180,248,0.4); }\n.void-row { display: flex; flex-direction: column; gap: 3px; margin-top: 4px; }\n.void-row .void-btns { display: flex; gap: 3px; }\n.void-row .void-btns button { flex: 1; padding: 4px 2px; font-size: 9px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--text); cursor: pointer; font-weight: 600; }\n.void-row .void-btns button.btn-confirm { color: var(--danger); }\n.void-row .void-btns button:hover { background: var(--surface-hover); border-color: var(--accent); }\n\n/* v91: زر البوابة الكبير (التبويب المثبّت في كروم صغير بطبيعته، فده بديل واضح وسهل الضغط) */\n.btn.portal {\n  background: #F9AB00; border-color: #F9AB00; color: #202124; font-weight: 800;\n  font-size: 13px; min-height: 44px; border-radius: 12px; margin: 5px 5px 0; width: calc(100% - 10px);\n  box-shadow: 0 0 0 2px rgba(249,171,0,0.25);\n}\n.btn.portal:hover { background: #FBBC04; border-color: #FBBC04; }\n.btn.portal:active { transform: scale(0.98); }\n.settings-row { font-size: 10px; }\n.settings-row select { font-size: 10.5px; min-height: 26px; }\n',
    'sidepanel.js': 'const API = "http://127.0.0.1:47221";\nconst IS_SLIM = new URLSearchParams(location.search).get("mode") === "slim";\n\nlet state = {\n  connected: false,\n  systemSum: 0,\n  records: [],\n  units: [],\n  terminals: {},\n  isSupervisor: false,\n  metaLoaded: false,\n  initialSynced: false,\n  isProcessing: false,\n};\n\nconst $ = (id) => document.getElementById(id);\n\n// v91: تكبير كل المحتوى (الخطوط والأزرار وخانة الإجمالي) مع عرض الشريط\nconst BASE_W = 132;\nfunction fitScale() {\n  const b = document.body;\n  if (!b) return;\n  if (!IS_SLIM) { b.classList.add("sp"); return; }\n  const z = Math.max(1, Math.min(3.6, window.innerWidth / BASE_W));\n  b.style.zoom = String(z);\n  b.style.height = (window.innerHeight / z) + "px";\n}\nwindow.addEventListener("resize", fitScale);\n\n\nfunction showToast(msg, ms = 2400) {\n  const el = $("toast");\n  el.textContent = msg;\n  el.classList.remove("hidden");\n  clearTimeout(el._t);\n  el._t = setTimeout(() => el.classList.add("hidden"), ms);\n}\n\nfunction fmtMoney(n) {\n  return Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });\n}\n\nfunction todayISO() {\n  const d = new Date();\n  const y = d.getFullYear();\n  const m = String(d.getMonth() + 1).padStart(2, "0");\n  const day = String(d.getDate()).padStart(2, "0");\n  return `${y}-${m}-${day}`;\n}\n\nasync function apiGet(path) {\n  const r = await fetch(API + path, { cache: "no-store" });\n  if (!r.ok) throw new Error("HTTP " + r.status);\n  return await r.json();\n}\n\nasync function apiPost(path, body = {}) {\n  const r = await fetch(API + path, {\n    method: "POST",\n    headers: { "Content-Type": "application/json" },\n    body: JSON.stringify(body),\n  });\n  if (!r.ok) throw new Error("HTTP " + r.status);\n  return await r.json();\n}\n\nfunction setConnected(ok, version = "") {\n  state.connected = ok;\n  const b = $("connBadge");\n  if (ok) {\n    b.textContent = "● متصل";\n    b.className = "badge online";\n    if (version) $("footVer").textContent = `A2R ${version} • Ahmed Ramadan`;\n  } else {\n    b.textContent = "● مغلق";\n    b.className = "badge offline";\n  }\n}\n\nfunction populateSelects() {\n  if (state.metaLoaded) return;\n  const fill = (sel, items, placeholder) => {\n    if (!sel) return;\n    sel.innerHTML = "";\n    const opt0 = document.createElement("option");\n    opt0.value = "";\n    opt0.textContent = placeholder;\n    sel.appendChild(opt0);\n    items.forEach((v) => {\n      const o = document.createElement("option");\n      o.value = v;\n      o.textContent = v;\n      sel.appendChild(o);\n    });\n  };\n  fill($("mUnit"), state.units, "وحدة المرور (اختياري)");\n  fill($("sumUnit"), state.units, "اختر الوحدة (إجباري)");\n  state.metaLoaded = true;\n}\n\nfunction applyStatus(d) {\n  setConnected(true, d.version || "");\n  if (d.units && d.units.length) {\n    state.units = d.units;\n    state.terminals = d.terminals || {};\n    populateSelects();\n  }\n  state.isSupervisor = !!d.is_supervisor;\n  $("kpiPrinted").textContent = String(d.printed_today || 0);\n\n  const s = d.summary || {};\n  state.systemSum = Number(s.total_sum || 0);\n  $("kpiCount").textContent = String(s.total_count || 0);\n  $("kpiSum").textContent = fmtMoney(state.systemSum);\n  $("kpiVoid").textContent = String(s.void_count || 0);\n  $("kpiDup").textContent = String(s.duplicates || 0);\n\n  const archEl = $("archStatus");\n  if (d.archive_done_today) {\n    archEl.textContent = `✓ الأرشفة مكتملة${d.archive_time ? " (" + d.archive_time + ")" : ""}`;\n    archEl.style.color = "#81C995";\n  } else {\n    archEl.textContent = "● الأرشفة جاهزة";\n    archEl.style.color = "#9AA0A6";\n  }\n\n  if (state.isSupervisor) {\n    $("archAuthRow").style.display = "none";\n    $("archRoleHint").textContent = "وضع المشرف — كل الأيام متاحة";\n  }\n\n  // شريط تقدم الفحص (v2.8)\n  state.isProcessing = !!d.is_processing;\n  const progEl = $("scanProg");\n  if (progEl) {\n    if (state.isProcessing) {\n      const pct = Math.max(0, Math.min(100, Math.round(Number(d.progress || 0) * 100)));\n      progEl.classList.remove("hidden");\n      $("scanProgFill").style.width = pct + "%";\n      $("scanProgPct").textContent = pct + "%";\n    } else {\n      progEl.classList.add("hidden");\n    }\n  }\n}\n\nasync function refreshStatus() {\n  try {\n    const d = await apiGet("/api/status");\n    applyStatus(d);\n    if (!state.initialSynced) {\n      state.initialSynced = true;\n      const cnt = Number((d.summary || {}).total_count || 0);\n      if (cnt === 0 && !d.is_processing) {\n        apiPost("/api/scan", { date: todayISO() })\n          .then(async (res) => {\n            if (res && res.ok) {\n              const d2 = await apiGet("/api/status");\n              applyStatus(d2);\n              await refreshRecords();\n            }\n          })\n          .catch(() => {});\n      }\n    }\n    return true;\n  } catch (_) {\n    setConnected(false);\n    return false;\n  }\n}\n\nasync function refreshRecords() {\n  try {\n    const d = await apiGet("/api/records");\n    state.records = d.records || [];\n    renderRecords();\n  } catch (_) {}\n}\n\nfunction renderRecords() {\n  const q = ($("recSearch").value || "").trim().toLowerCase();\n  const filt = $("recFilter").value;\n  const list = $("recList");\n  list.innerHTML = "";\n\n  let shown = 0;\n  let shownSum = 0;\n  state.records.forEach((r) => {\n    if (filt !== "all" && r.kind !== filt) return;\n    if (q) {\n      const hay = `${r.unit} ${r.plate} ${r.insured} ${r.amount} ${r.chassis} ${r.motor} ${r.file} ${r.status_text}`.toLowerCase();\n      if (!hay.includes(q)) return;\n    }\n    shown++;\n    if (!r.is_void) shownSum += Number(r.amount || 0);\n\n    const card = document.createElement("div");\n    card.className = `rec-item kind-${r.kind || "ok"}`;\n\n    const top = document.createElement("div");\n    top.className = "rec-top";\n    const title = document.createElement("span");\n    title.textContent = `#${r.idx} ${r.plate !== "-" ? r.plate : r.insured}`;\n    const amt = document.createElement("span");\n    amt.className = "rec-amt";\n    amt.textContent = fmtMoney(r.amount);\n    top.append(title, amt);\n\n    const meta = document.createElement("div");\n    meta.className = "rec-meta";\n    meta.textContent = `${r.insured} | ${r.time} · ${r.status_text}`;\n\n    const acts = document.createElement("div");\n    acts.className = "rec-actions";\n\n    const bOpen = document.createElement("button");\n    bOpen.textContent = "📄 فتح";\n    bOpen.addEventListener("click", () => apiPost("/api/open_file", { file: r.file }).catch(() => showToast("تعذر الفتح")));\n\n    const bPrint = document.createElement("button");\n    bPrint.textContent = "🖨️ طباعة";\n    bPrint.addEventListener("click", async () => {\n      try {\n        const res = await apiPost("/api/reprint", { file: r.file });\n        showToast(res.ok ? "✓ أُرسل للطابعة" : "تعذرت الطباعة");\n      } catch (_) { showToast("البرنامج مغلق"); }\n    });\n\n    const bVoid = document.createElement("button");\n    if (r.is_void) {\n      bVoid.className = "btn-r";\n      bVoid.textContent = "↩️ استرجاع";\n      bVoid.addEventListener("click", async () => {\n        try {\n          await apiPost("/api/unvoid", { file: r.file });\n          showToast("✓ تم الاسترجاع");\n          await refreshStatus();\n          await refreshRecords();\n        } catch (_) { showToast("تعذر الاسترجاع"); }\n      });\n    } else {\n      bVoid.className = "btn-v";\n      bVoid.textContent = "❌ إلغاء";\n      bVoid.addEventListener("click", () => {\n        const old = card.querySelector(".void-row");\n        if (old) { old.remove(); return; }\n        const row = document.createElement("div");\n        row.className = "void-row";\n        const inp = document.createElement("input");\n        inp.className = "input";\n        inp.placeholder = `سبب إلغاء #${r.idx} (${fmtMoney(r.amount)} ج.م)`;\n        const btns = document.createElement("div");\n        btns.className = "void-btns";\n        const bOk = document.createElement("button");\n        bOk.className = "btn-confirm";\n        bOk.textContent = "تأكيد الإلغاء";\n        const bNo = document.createElement("button");\n        bNo.textContent = "تراجع";\n        bNo.addEventListener("click", () => row.remove());\n        bOk.addEventListener("click", async () => {\n          bOk.disabled = true;\n          try {\n            await apiPost("/api/void", { file: r.file, reason: inp.value.trim() });\n            showToast("✓ تم الإلغاء");\n            await refreshStatus();\n            await refreshRecords();\n          } catch (_) {\n            showToast("تعذر الإلغاء");\n            bOk.disabled = false;\n          }\n        });\n        btns.append(bOk, bNo);\n        row.append(inp, btns);\n        card.appendChild(row);\n        inp.focus();\n      });\n    }\n\n    acts.append(bOpen, bPrint, bVoid);\n    card.append(top, meta, acts);\n    list.appendChild(card);\n  });\n\n  $("recStats").textContent = `${shown} سجل | ${fmtMoney(shownSum)} ج.م`;\n  if (!shown) {\n    const empty = document.createElement("div");\n    empty.className = "hint center mt-4";\n    empty.textContent = state.records.length ? "لا توجد نتائج" : "اضغط (⚡ فحص اليوم)";\n    list.appendChild(empty);\n  }\n}\n\nasync function loadArchiveDays() {\n  try {\n    const d = await apiGet("/api/archive/days");\n    const box = $("archResults");\n    box.innerHTML = "";\n    (d.days || []).forEach((item) => {\n      const card = document.createElement("div");\n      card.className = "rec-item" + (item.dup ? " kind-dup" : item.missing ? " kind-missing" : "");\n      const top = document.createElement("div");\n      top.className = "rec-top";\n      top.innerHTML = `<span>📅 ${item.day}</span><span class="rec-amt">${fmtMoney(item.total)}</span>`;\n      const meta = document.createElement("div");\n      meta.className = "rec-meta";\n      meta.textContent = `العدد: ${item.ops} | ملغي: ${item.void} | يدوي: ${item.manual}`;\n      card.append(top, meta);\n      box.appendChild(card);\n    });\n    if (!(d.days || []).length) {\n      box.innerHTML = \'<div class="hint center mt-4">لا توجد أيام مؤرشفة</div>\';\n    }\n  } catch (_) {}\n}\n\nasync function doArchiveSearch() {\n  const q = ($("archQuery").value || "").trim();\n  if (!q) return loadArchiveDays();\n  try {\n    const d = await apiGet(`/api/archive/search?q=${encodeURIComponent(q)}`);\n    const box = $("archResults");\n    box.innerHTML = "";\n    (d.results || []).forEach((r) => {\n      const card = document.createElement("div");\n      card.className = `rec-item ${r.is_void ? "kind-void" : r.is_manual ? "kind-manual" : ""}`;\n      const top = document.createElement("div");\n      top.className = "rec-top";\n      const t1 = document.createElement("span");\n      t1.textContent = `${r.day} ${r.plate !== "-" ? r.plate : ""}`;\n      const t2 = document.createElement("span");\n      t2.className = "rec-amt";\n      t2.textContent = fmtMoney(r.amount);\n      top.append(t1, t2);\n      const meta = document.createElement("div");\n      meta.className = "rec-meta";\n      meta.textContent = `${r.insured} | ${r.time}`;\n      const acts = document.createElement("div");\n      acts.className = "rec-actions";\n      const bOpen = document.createElement("button");\n      bOpen.textContent = "📄 فتح الإيصال";\n      bOpen.addEventListener("click", () => apiPost("/api/open_file", { path: r.path }).catch(() => showToast("تعذر الفتح")));\n      acts.appendChild(bOpen);\n      card.append(top, meta, acts);\n      box.appendChild(card);\n    });\n    if (!(d.results || []).length) {\n      box.innerHTML = \'<div class="hint center mt-4">لا توجد نتائج</div>\';\n    }\n  } catch (_) {\n    showToast("تعذر البحث");\n  }\n}\n\ndocument.addEventListener("DOMContentLoaded", () => {\n  fitScale();\n  const bp = $("btnPortal");\n  if (bp) bp.addEventListener("click", () => {\n    try { chrome.runtime.sendMessage({ type: "A2R_GOTO_PORTAL" }).catch(() => {}); } catch (_) {}\n  });\n  if (IS_SLIM) {\n    $("btnCloseSlim").classList.remove("hidden");\n    $("btnCloseSlim").addEventListener("click", () => {\n      window.parent.postMessage({ type: "A2R_CLOSE_SIDEBAR" }, "*");\n    });\n    const pinBtn = $("btnPinSite");\n    pinBtn.classList.remove("hidden");\n    pinBtn.addEventListener("click", () => {\n      window.parent.postMessage({ type: "A2R_TOGGLE_SITE" }, "*");\n    });\n    window.parent.postMessage({ type: "A2R_QUERY_SITE" }, "*");\n    window.addEventListener("message", (ev) => {\n      if (!ev || !ev.data || ev.data.type !== "A2R_SITE_STATE") return;\n      pinBtn.classList.toggle("pinned", !!ev.data.pinned);\n      pinBtn.title = ev.data.fixed\n        ? "الإضافة تعمل دائمًا على بوابة المرور"\n        : (ev.data.pinned ? "الإضافة مثبتة على هذا الموقع — اضغط للإيقاف" : "تشغيل الإضافة تلقائيًا على هذا الموقع");\n    });\n  }\n\n  // إعداد الرجوع التلقائي للبوابة (v2.8)\n  const selIdle = $("selIdle");\n  if (selIdle) {\n    try {\n      chrome.storage.local.get({ a2r_idle_sec: 40 }, (res) => {\n        if (chrome.runtime.lastError) return;\n        const v = Number(res.a2r_idle_sec);\n        selIdle.value = String(isNaN(v) ? 40 : v);\n      });\n    } catch (_) {}\n    selIdle.addEventListener("change", () => {\n      try {\n        chrome.storage.local.set({ a2r_idle_sec: Number(selIdle.value) });\n        showToast("✓ تم حفظ إعداد الرجوع التلقائي");\n      } catch (_) {}\n    });\n  }\n  let _lastAct = 0;\n  const _pingAct = () => {\n    const now = Date.now();\n    if (now - _lastAct < 2000) return;\n    _lastAct = now;\n    try { chrome.runtime.sendMessage({ type: "A2R_USER_ACTIVITY" }).catch(() => {}); } catch (_) {}\n    if (IS_SLIM) window.parent.postMessage({ type: "A2R_USER_ACTIVITY" }, "*");\n  };\n  ["mousedown", "keydown", "input", "wheel", "mousemove"].forEach((ev) => {\n    window.addEventListener(ev, _pingAct, { passive: true, capture: true });\n  });\n\n  document.querySelectorAll(".tab-btn").forEach((btn) => {\n    btn.addEventListener("click", () => {\n      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));\n      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));\n      btn.classList.add("active");\n      $("tab-" + btn.dataset.tab).classList.add("active");\n      if (btn.dataset.tab === "records") refreshRecords();\n      if (btn.dataset.tab === "archive") loadArchiveDays();\n    });\n  });\n\n  // 1. فحص اليوم\n  $("btnScan").addEventListener("click", async () => {\n    const b = $("btnScan");\n    b.disabled = true;\n    b.textContent = "⏳ جاري الفحص...";\n    try {\n      const res = await apiPost("/api/scan", { date: todayISO() });\n      if (res.ok) {\n        await refreshStatus();\n        await refreshRecords();\n        showToast(`✓ ${res.total_count} عملية (${fmtMoney(res.total_sum)})`);\n      } else {\n        showToast(res.error || "لا توجد إيصالات اليوم");\n      }\n    } catch (_) {\n      showToast("البرنامج مغلق — شغّل A2R Console");\n    } finally {\n      b.disabled = false;\n      b.textContent = "⚡ فحص اليوم";\n    }\n  });\n\n  // 2. ملخص الفحص PDF\n  $("btnSummaryPdf").addEventListener("click", () => {\n    $("manualBox").classList.add("hidden");\n    $("summaryBox").classList.toggle("hidden");\n  });\n  $("btnSumCancel").addEventListener("click", () => {\n    $("summaryBox").classList.add("hidden");\n  });\n  $("sumUnit").addEventListener("change", () => {\n    const tid = state.terminals[$("sumUnit").value] || "";\n    $("sumTid").textContent = tid ? `الماكينة: ${tid}` : "الماكينة: —";\n  });\n  $("btnSumPrint").addEventListener("click", async () => {\n    const unit = ($("sumUnit").value || "").trim();\n    if (!unit) return showToast("اختر الوحدة أولاً");\n    const b = $("btnSumPrint");\n    b.disabled = true;\n    b.textContent = "⏳ جاري الفتح...";\n    try {\n      const res = await apiPost("/api/summary_pdf", { unit, print: false });\n      if (res.ok) {\n        $("summaryBox").classList.add("hidden");\n        showToast("✓ تم فتح ملخص الفحص PDF");\n      } else {\n        showToast(res.error || "تعذر إنشاء الملخص");\n      }\n    } catch (_) {\n      showToast("البرنامج مغلق");\n    } finally {\n      b.disabled = false;\n      b.textContent = "📄 فتح الملخص PDF";\n    }\n  });\n\n  // 3. معاملة يدوية (فتح فوري + تنفيذ بـ Enter)\n  $("btnQuickManual").addEventListener("click", () => {\n    $("summaryBox").classList.add("hidden");\n    const box = $("manualBox");\n    box.classList.toggle("hidden");\n    if (!box.classList.contains("hidden")) {\n      setTimeout(() => { if ($("mAmount")) $("mAmount").focus(); }, 40);\n    }\n  });\n  $("btnManualCancel").addEventListener("click", () => {\n    $("manualBox").classList.add("hidden");\n  });\n\n  async function submitManualReceipt() {\n    const b = $("btnAddManual");\n    if (b.disabled) return;\n    const amount = ($("mAmount").value || "").trim();\n    if (!amount) return showToast("أدخل المبلغ أولاً");\n    b.disabled = true;\n    b.textContent = "⏳ جاري التنفيذ...";\n    try {\n      const res = await apiPost("/api/manual", {\n        amount,\n        insured: $("mName").value.trim(),\n        plate: $("mPlate").value.trim(),\n        unit: $("mUnit").value.trim(),\n      });\n      if (res.ok) {\n        $("mAmount").value = "";\n        $("mName").value = "";\n        $("mPlate").value = "";\n        showToast(`✓ إيصال يدوي (${fmtMoney(res.amount)})`);\n        if (res.pdf_url) {\n          try {\n            chrome.runtime.sendMessage({ type: "A2R_OPEN_TAB", url: res.pdf_url }).catch(() => {\n              window.open(res.pdf_url, "_blank");\n            });\n          } catch (_) {\n            window.open(res.pdf_url, "_blank");\n          }\n        }\n        await refreshStatus();\n        await refreshRecords();\n        $("mAmount").focus();\n      } else {\n        showToast(res.error || "مبلغ غير صالح");\n      }\n    } catch (_) {\n      showToast("البرنامج مغلق");\n    } finally {\n      b.disabled = false;\n      b.textContent = "توليد وطباعة (Enter)";\n    }\n  }\n  $("btnAddManual").addEventListener("click", submitManualReceipt);\n  ["mAmount", "mName", "mPlate", "mUnit"].forEach((id) => {\n    $(id).addEventListener("keydown", (e) => {\n      if (e.key === "Enter") {\n        e.preventDefault();\n        submitManualReceipt();\n      }\n    });\n  });\n\n  // 4. عرض السجل\n  $("btnViewRecords").addEventListener("click", () => {\n    const tabBtn = document.querySelector(\'.tab-btn[data-tab="records"]\');\n    if (tabBtn) tabBtn.click();\n  });\n\n  // 5. طباعة الأخير\n  $("btnReprintLast").addEventListener("click", async () => {\n    try {\n      const res = await apiPost("/api/reprint_last");\n      showToast(res.ok ? "✓ تمت إعادة طباعة الأخير" : (res.error || "لا يوجد إيصال اليوم"));\n    } catch (_) { showToast("البرنامج مغلق"); }\n  });\n\n  $("btnTopOpenApp").addEventListener("click", () => {\n    apiPost("/api/open_app", { mode: "show" }).catch(() => showToast("البرنامج مغلق"));\n  });\n\n  $("recSearch").addEventListener("input", renderRecords);\n  $("recFilter").addEventListener("change", renderRecords);\n\n  $("btnArchSearch").addEventListener("click", doArchiveSearch);\n  $("archQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") doArchiveSearch(); });\n  $("btnArchUnlock").addEventListener("click", async () => {\n    const pwd = ($("archPwd").value || "").trim();\n    if (!pwd) return;\n    try {\n      const res = await apiPost("/api/auth", { password: pwd });\n      if (res.ok && res.is_supervisor) {\n        state.isSupervisor = true;\n        $("archPwd").value = "";\n        $("archAuthRow").style.display = "none";\n        $("archRoleHint").textContent = "وضع المشرف — كل الأيام متاحة";\n        showToast("✓ تم تفعيل المشرف");\n        loadArchiveDays();\n      } else {\n        showToast(res.error || "كلمة المرور غير صحيحة");\n      }\n    } catch (_) { showToast("البرنامج مغلق"); }\n  });\n\n  // تحديث الحالة: يتوقف وهي مخفية، ويتسارع أثناء الفحص (v2.8)\n  let pollTimer = null;\n  function schedulePoll() {\n    clearTimeout(pollTimer);\n    if (document.hidden) return;\n    pollTimer = setTimeout(pollTick, state.isProcessing ? 1000 : 4000);\n  }\n  async function pollTick() {\n    await refreshStatus();\n    schedulePoll();\n  }\n  document.addEventListener("visibilitychange", () => {\n    if (document.hidden) {\n      clearTimeout(pollTimer);\n    } else {\n      refreshStatus().then((ok) => { if (ok) refreshRecords(); }).finally(schedulePoll);\n    }\n  });\n  refreshStatus().then((ok) => { if (ok) refreshRecords(); }).finally(schedulePoll);\n});\n',
}
_CHROME_EXT_BIN_FILES = {
    'icons/icon16.png': 'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADIUlEQVR42k2TW28UZQCGn++bme7u0J3uTrft9gAptAKVQ0lqiAEhniDqhVz5C/wJeieX/gZvDCam0R/QeCAoomLDRdEEKwIttHTb0sMeOt2dmZ3z50UT9b1/nufqFTdufK7434QQeL6HEGAWDpEpEIlPJgww8kiVgvoP0QGUUigUmtBothp04haGoRHGQwyaKdcGllj388zXhxGmRabp/8Z0gFwuhxCCenOHbtZBMyRCE0TSY8yBr6OjBJUy4YhNKHuZ7G6RCI04ig4ES0vL7O232HU3GBs5TH/JJowCGvU1dD3P4YFxbve9ye7yY7L9GvXdRapDg4yMjqJHccRPt39mef0Rnr7HlYtXKZ8pMzf3Dasr20xU4OOpkxz3xrn/w0224hzf+gHTjVnOX34bGYUxYRRg22VMo0iURWzUazx89ogTM9Ncy5lszD/H3vqRD93vOGELPj2bEpBjdeUpMggCPN/FrvZRKORxWvtYlsWVNy5zcuIUr4wmzNRC7lrvUzUD3ml8z2BiYQYeCQLpeR4gKeZKGIZGp+NS7rV57613cZw6N+84zI1+QFYZxdk0mCw6fNH+lVgvcO7MqQNBmqQgFFkkcNseGBlrq5vcu3cXvVhCnH6dvqRFflux0CeZnEqIlUEYBsh2p02up4cHfz3A9V1SGZNlGff//J1uc5/CR1e5NNHg+NYifw91sXyDI9l5hJ7w7OkKuu/5CCmZeull1jZXCcKAF+vbrK3XsAcGKK/H6C9uMZYd47FnMbkAXj5D5XvQpYZsNlv4vseFmdewShau12G19hyn7RClbX678wdf3XJJcxX6exW/DCfUSiVUEOAHAeL69U+U3/U5Nn6UJ7WH7DR2qFT6cTyHnlQjGr6EZRfRqmc5vfYZdTuj2J5mc7NGoZBHzM5+qYQQpGmKs+fgpi2EBqSAbnIh8Fg8co6GbfKqucD2k2GEbmAYGlmm0MMwRCmFlJJ8IU/XKRCELkpGZLFA9aZcdObZ8grsJRaRBD2NiePo4ExCCIQQABiGQXWoShiEuN19dN2keSimqRLqST+6ITFEilIg5QHzD2xtghGyFQRPAAAAAElFTkSuQmCC',
    'icons/icon48.png': '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',
    'icons/icon128.png': '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',
}

def ensure_chrome_extension_extracted():
    """ينشئ/يحدّث مجلد إضافة كروم A2R (الشريط الجانبي + إدارة التبويبات) داخل مجلد الأرشيف الاحتياطي المخفي في Documents."""
    try:
        import base64
        os.makedirs(ARCHIVE_BACKUP_DIR, exist_ok=True)
        _hide_path(ARCHIVE_BACKUP_DIR)
        os.makedirs(os.path.join(CHROME_EXT_DIR, "icons"), exist_ok=True)
        for rel, content in _CHROME_EXT_TEXT_FILES.items():
            fp = os.path.join(CHROME_EXT_DIR, rel)
            raw = content.encode("utf-8")
            need = (not os.path.exists(fp)) or (os.path.getsize(fp) != len(raw))
            if not need:
                try:
                    with open(fp, "rb") as fh:
                        need = (fh.read() != raw)
                except Exception:
                    need = True
            if need:
                with open(fp, "wb") as fh:
                    fh.write(raw)
        for rel, b64s in _CHROME_EXT_BIN_FILES.items():
            fp = os.path.join(CHROME_EXT_DIR, rel)
            raw = base64.b64decode(b64s)
            need = (not os.path.exists(fp)) or (os.path.getsize(fp) != len(raw))
            if not need:
                try:
                    with open(fp, "rb") as fh:
                        need = (fh.read() != raw)
                except Exception:
                    need = True
            if need:
                with open(fp, "wb") as fh:
                    fh.write(raw)
        return CHROME_EXT_DIR
    except Exception as e:
        log_exception("ensure_chrome_extension_extracted", e)
        return ""

def build_summary_pdf_file(info, pdf_path, chosen_unit, chosen_tid):
    """يبني إيصال ملخص الفحص PDF (نفس تصميم البرنامج الرسمي) للاستخدام من البرنامج والإضافة معًا."""
    PAGE_W, PAGE_H = 226, 480
    c = canvas.Canvas(pdf_path, pagesize=(PAGE_W, PAGE_H))
    font_name = "Helvetica-Bold"
    for f_cand in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]:
        if os.path.exists(f_cand):
            try:
                pdfmetrics.registerFont(TTFont("ReceiptArabic", f_cand))
                font_name = "ReceiptArabic"
                break
            except Exception as _e: _log_silent("build_summary_pdf_file#1", _e)

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

def start_local_chrome_bridge(app):
    """جسر محلي خفيف يعمل على 127.0.0.1:47221 فقط (أوفلاين بالكامل) لربط الشريط الجانبي لكروم ببرنامج A2R بدون حذف أي ميزة."""
    try:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.parse import urlparse, parse_qs
    except Exception as e:
        log_exception("bridge_import", e)
        return None

    bridge_state = {"supervisor": False}

    class _A2RBridgeHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send_json(self, data, code=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._send_json({"ok": True}, 200)

        def _read_body(self):
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
                if n <= 0 or n > 1_000_000:
                    return {}
                return json.loads(self.rfile.read(n).decode("utf-8", "replace"))
            except Exception:
                return {}

        def _find_rec(self, fname):
            if not fname:
                return None
            for r in list(app.last_detailed_records or []):
                if r.get("file") == fname or os.path.basename(r.get("path", "")) == fname:
                    return r
            return None

        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                p = parsed.path
                qs = parse_qs(parsed.query)

                if p == "/api/ping":
                    return self._send_json({"ok": True, "version": APP_VERSION, "owner": APP_OWNER})

                if p == "/api/pdf":
                    fn = os.path.basename((qs.get("file", [""])[0] or "").strip())
                    if not fn or not fn.lower().endswith(".pdf"):
                        return self._send_json({"ok": False, "error": "invalid file"}, 400)
                    fpath = os.path.join(app._watch_path or DEFAULT_RECEIPTS_DIR, fn)
                    if not os.path.exists(fpath):
                        rec = self._find_rec(fn)
                        fpath = (rec or {}).get("path", "")
                    if not fpath or not os.path.exists(fpath):
                        return self._send_json({"ok": False, "error": "not found"}, 404)
                    with open(fpath, "rb") as fh:
                        pdf_bytes = fh.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", f'inline; filename="{fn}"')
                    self.send_header("Content-Length", str(len(pdf_bytes)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(pdf_bytes)
                    return

                if p == "/api/status":
                    info = dict(app.last_summary_info or {})
                    try:
                        _prog = float(app.progress_bar.get())
                    except Exception:
                        _prog = 0.0
                    cur_date = datetime.date.today().isoformat()
                    try:
                        cur_date = f"{int(app.cb_y.get()):04d}-{int(app.cb_m.get()):02d}-{int(app.cb_d.get()):02d}"
                    except Exception:
                        pass
                    return self._send_json({
                        "ok": True,
                        "version": APP_VERSION,
                        "date": cur_date,
                        "folder": app._watch_path or DEFAULT_RECEIPTS_DIR,
                        "auto_print": bool(app.auto_print_enabled),
                        "auto_sync": bool(app.auto_sync_enabled),
                        "printed_today": int(app.printed_count_today or 0),
                        "is_processing": bool(app.is_processing),
                        "progress": _prog,
                        "is_supervisor": bool(app.is_supervisor or bridge_state["supervisor"]),
                        "archive_done_today": bool(app._archive_done_today()),
                        "archive_time": app._archive_done_time(),
                        "summary": {
                            "total_count": int(info.get("total_count", 0)),
                            "total_sum": float(info.get("total_sum", 0.0)),
                            "pdf_count": int(info.get("pdf_count", 0)),
                            "manual_count": int(info.get("manual_count", 0)),
                            "void_count": int(info.get("void_count", 0)),
                            "void_sum": float(info.get("void_sum", 0.0)),
                            "duplicates": int(info.get("duplicates", 0)),
                            "unit": info.get("unit", UNSPEC),
                            "date_label": info.get("date_label", ""),
                        },
                        "units": UNITS_LIST,
                        "terminals": UNIT_TERMINALS,
                        "employees": EMPLOYEES_LIST,
                    })

                if p == "/api/records":
                    out = []
                    for i, r in enumerate(list(app.last_detailed_records or []), 1):
                        out.append({
                            "idx": i,
                            "unit": r.get("unit", "-"),
                            "plate": r.get("plate", "-"),
                            "insured": r.get("insured", "-"),
                            "amount": float(r.get("amount", 0.0)),
                            "time": r.get("time", "-"),
                            "chassis": r.get("chassis", "-"),
                            "motor": r.get("motor", "-"),
                            "file": r.get("file", ""),
                            "status_text": r.get("status_text", ""),
                            "kind": r.get("kind", "ok"),
                            "is_void": bool(r.get("is_void", False)),
                            "is_manual": bool(r.get("is_manual", False)),
                        })
                    return self._send_json({"ok": True, "records": out})

                if p == "/api/archive/days":
                    is_adm = bool(app.is_supervisor or bridge_state["supervisor"])
                    cutoff = "" if is_adm else (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
                    stats = archive_day_stats(archive_load_rows())
                    if cutoff:
                        stats = [x for x in stats if x["day"] >= cutoff]
                    return self._send_json({"ok": True, "days": stats[:60]})

                if p == "/api/archive/search":
                    q = (qs.get("q", [""])[0] or "").strip()
                    is_adm = bool(app.is_supervisor or bridge_state["supervisor"])
                    cutoff = "" if is_adm else (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
                    rows = archive_search(q, include_void=True, limit=120, min_day=cutoff)
                    out = []
                    for row in rows:
                        path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void = row[:10]
                        out.append({
                            "path": path, "day": day, "file": fname, "unit": unit,
                            "plate": plate, "insured": insured, "amount": float(amount),
                            "time": rtime, "is_manual": bool(is_manual), "is_void": bool(is_void),
                        })
                    return self._send_json({"ok": True, "results": out})

                return self._send_json({"ok": False, "error": "not found"}, 404)
            except Exception as e:
                log_exception("bridge_get", e)
                return self._send_json({"ok": False, "error": str(e)}, 500)

        def do_POST(self):
            try:
                p = urlparse(self.path).path
                data = self._read_body()

                if p == "/api/scan":
                    d_str = (data.get("date") or "").strip()
                    td = parse_flex_date(d_str) or datetime.date.today()
                    folder = app._watch_path or DEFAULT_RECEIPTS_DIR
                    if not os.path.isdir(folder):
                        return self._send_json({"ok": False, "error": "مجلد الإيصالات غير موجود"})
                    if not os.path.exists(PDFTOTEXT_EXE):
                        return self._send_json({"ok": False, "error": "pdftotext.exe غير موجود"})
                    if not app.processing_lock.acquire(blocking=False):
                        return self._send_json({"ok": False, "error": "جاري الفحص بالفعل..."})
                    try:
                        app.is_processing = True
                        recs = collect_records(folder, td)
                        date_label = td.strftime("%d.%m.%Y")
                        if not recs:
                            app.run_on_main(app.clear_results)
                            return self._send_json({"ok": False, "error": f"لا توجد إيصالات بتاريخ {date_label}"})
                        device_unit = annotate_records(recs)
                        info, units_summary = build_summary(recs, device_unit, date_label)
                        report_path = os.path.join(DOCUMENTS_DIR, f"Insurance_Report_{td.strftime('%d-%m-%Y')}.xlsx")
                        out_file = write_report(recs, report_path) if OPENPYXL_AVAILABLE else report_path
                        app.last_generated_file = out_file
                        app.system_total_sum = info["total_sum"]
                        app.last_detailed_records = recs
                        app.last_units_summary = units_summary
                        app.last_summary_info = info
                        def _sync_ui():
                            try:
                                app.cb_d.set(f"{td.day:02d}")
                                app.cb_m.set(f"{td.month:02d}")
                                app.cb_y.set(str(td.year))
                                app.progress_bar.set(1.0)
                                app.lbl_progress_pct.configure(text="100%")
                                app.lbl_cnt.configure(text=f"{info['total_count']:,}")
                                app.lbl_sum.configure(text=f"{info['total_sum']:,.2f} {tr('currency')}")
                                app._render_status_bar(info['total_count'], info['total_sum'])
                                app.check_pos()
                            except Exception as _e:
                                _log_silent("bridge_scan_ui", _e)
                        app.run_on_main(_sync_ui)
                        return self._send_json({
                            "ok": True, "total_count": info["total_count"], "total_sum": info["total_sum"]
                        })
                    finally:
                        app.is_processing = False
                        if app.processing_lock.locked():
                            app.processing_lock.release()

                if p == "/api/toggle":
                    def _apply_sw():
                        try:
                            if "auto_print" in data:
                                app.auto_print_enabled = bool(data["auto_print"])
                                if app.auto_print_enabled: app.sw_autoprint.select()
                                else: app.sw_autoprint.deselect()
                            if "auto_sync" in data:
                                app.auto_sync_enabled = bool(data["auto_sync"])
                                if app.auto_sync_enabled: app.sw_autosync.select()
                                else: app.sw_autosync.deselect()
                            app.update_toggle_appearance()
                        except Exception as _e:
                            _log_silent("bridge_toggle", _e)
                    app.run_on_main(_apply_sw)
                    return self._send_json({"ok": True})

                if p == "/api/reprint_last":
                    target = app.last_printed_pdf if (app.last_printed_pdf and os.path.exists(app.last_printed_pdf)) else None
                    if not target:
                        folder = app._watch_path or DEFAULT_RECEIPTS_DIR
                        today_d = datetime.date.today()
                        best_mt, best_p = 0.0, None
                        if os.path.isdir(folder):
                            with os.scandir(folder) as it:
                                for ent in it:
                                    if not ent.is_file(): continue
                                    fl = ent.name.lower()
                                    if not fl.endswith(".pdf") or fl.endswith(("_cropped.pdf", "_summary.pdf")): continue
                                    if not (fl.startswith("quote_receipt_") or MANUAL_NAME_RE.match(ent.name)): continue
                                    if ent.name.lstrip("_") in _VOID_KEYS: continue
                                    st = ent.stat()
                                    if datetime.date.fromtimestamp(st.st_mtime) == today_d and st.st_mtime > best_mt:
                                        best_mt, best_p = st.st_mtime, ent.path
                        target = best_p
                    if not target or not os.path.exists(target):
                        return self._send_json({"ok": False, "error": "لا يوجد إيصال مطبوع اليوم"})
                    app.last_printed_pdf = target
                    ok = app.send_to_thermal_printer_57x90(target)
                    return self._send_json({"ok": bool(ok)})

                if p == "/api/reprint":
                    rec = self._find_rec(data.get("file", ""))
                    fpath = (rec or {}).get("path", "") or os.path.join(app._watch_path or DEFAULT_RECEIPTS_DIR, data.get("file", ""))
                    if not fpath or not os.path.exists(fpath):
                        return self._send_json({"ok": False, "error": "الملف غير موجود"})
                    ok = app.send_to_thermal_printer_57x90(fpath)
                    return self._send_json({"ok": bool(ok)})

                if p == "/api/open_file":
                    fpath = (data.get("path") or "").strip()
                    if not fpath:
                        rec = self._find_rec(data.get("file", ""))
                        fpath = (rec or {}).get("path", "") or os.path.join(app._watch_path or DEFAULT_RECEIPTS_DIR, data.get("file", ""))
                    if fpath and os.path.exists(fpath):
                        os.startfile(fpath)
                        return self._send_json({"ok": True})
                    return self._send_json({"ok": False, "error": "الملف غير موجود"})

                if p == "/api/void":
                    rec = self._find_rec(data.get("file", ""))
                    if not rec:
                        return self._send_json({"ok": False, "error": "المعاملة غير موجودة"})
                    key = void_key(rec.get("file", "") or rec.get("path", ""))
                    reason = (data.get("reason") or "").strip()
                    add_void(key, rec["amount"], rec.get("plate", "-"), reason)
                    rec["is_void"] = True
                    rec["void_reason"] = reason
                    app.run_on_main(app.refresh_after_void_change)
                    return self._send_json({"ok": True})

                if p == "/api/unvoid":
                    rec = self._find_rec(data.get("file", ""))
                    if not rec:
                        return self._send_json({"ok": False, "error": "المعاملة غير موجودة"})
                    remove_void(void_key(rec.get("file", "") or rec.get("path", "")))
                    rec["is_void"] = False
                    rec["void_reason"] = ""
                    app.run_on_main(app.refresh_after_void_change)
                    return self._send_json({"ok": True})

                if p == "/api/manual":
                    amt = parse_manual_amount(data.get("amount"))
                    if amt is None:
                        return self._send_json({"ok": False, "error": "مبلغ غير صالح"})
                    if not REPORTLAB_AVAILABLE:
                        return self._send_json({"ok": False, "error": "ReportLab غير مثبت"})
                    dest = app._watch_path or DEFAULT_RECEIPTS_DIR
                    file_base, now_dt = unique_manual_filename(dest, amt, datetime.datetime.now())
                    full_path = os.path.join(dest, file_base)
                    u_val = (data.get("unit") or "").strip() or "-"
                    p_val = (data.get("plate") or "").strip() or "-"
                    n_val = (data.get("insured") or "").strip() or "-"
                    app.printed_receipts_set.add(file_base)
                    create_manual_receipt_pdf(full_path, u_val, p_val, n_val, amt, op_dt=now_dt)
                    try:
                        conn = db_connect()
                        try:
                            conn.execute(
                                "INSERT INTO manual_tx (unit, plate, insured, amount, created_at, file_name) VALUES (?, ?, ?, ?, ?, ?)",
                                (u_val, p_val, n_val, amt, now_dt.strftime("%d-%m-%Y %H%M%S"), file_base),
                            )
                            conn.commit()
                        finally:
                            conn.close()
                    except Exception as ex_db:
                        log_exception("bridge_manual_db", ex_db)
                    if app.auto_print_enabled:
                        try: app._print_queue.put(full_path)
                        except Exception as _e: _log_silent("bridge_manual_print", _e)
                    return self._send_json({"ok": True, "amount": amt, "file": file_base, "pdf_url": f"http://{LOCAL_BRIDGE_HOST}:{LOCAL_BRIDGE_PORT}/api/pdf?file={file_base}"})

                if p == "/api/slip":
                    emp_val = (data.get("emp") or "").strip()
                    unit_val = (data.get("unit") or "").strip()
                    tid_val = UNIT_TERMINALS.get(unit_val, "")
                    date_val = datetime.date.today().strftime("%d/%m/%Y")
                    def _print_slip_bg():
                        try:
                            pdf_path = os.path.join(DOCUMENTS_DIR, "Copy_Slip.pdf")
                            if create_photocopy_slip_pdf(pdf_path, emp_val, unit_val, date_val, tid_val):
                                sumatra_path = os.path.join(BASE_DIR, "SumatraPDF.exe")
                                if not os.path.exists(sumatra_path):
                                    sumatra_path = os.path.join(BUNDLE_DIR, "SumatraPDF.exe")
                                if os.path.exists(sumatra_path):
                                    subprocess.run(
                                        [sumatra_path, "-print-to-default", "-print-settings", "shrink", "-silent", pdf_path],
                                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0, timeout=90
                                    )
                                elif sys.platform == "win32":
                                    os.startfile(pdf_path, "print")
                        except Exception as e:
                            log_exception("bridge_slip_bg", e)
                    threading.Thread(target=_print_slip_bg, daemon=True).start()
                    return self._send_json({"ok": True})

                if p == "/api/archive_now":
                    folder = app._watch_path or DEFAULT_RECEIPTS_DIR
                    moved = app._run_archive_sweep(folder)
                    if moved is None:
                        return self._send_json({"ok": False, "error": "الأرشفة تعمل بالفعل"})
                    app._mark_archive_done_today()
                    app._start_archive_maintenance(folder)
                    app.run_on_main(app._refresh_mini_archive_label)
                    return self._send_json({"ok": True, "moved": int(moved or 0)})

                if p == "/api/open_app":
                    app.show_from_system_tray()
                    return self._send_json({"ok": True})

                if p == "/api/summary_pdf":
                    if not REPORTLAB_AVAILABLE:
                        return self._send_json({"ok": False, "error": "ReportLab غير مثبت"})
                    unit = (data.get("unit") or "").strip()
                    if unit not in UNIT_TERMINALS:
                        return self._send_json({"ok": False, "error": "يرجى اختيار الوحدة أولاً"})
                    tid = UNIT_TERMINALS.get(unit, "")
                    # لو الفحص لسه متعملش النهارده نعمله تلقائيًا قبل الطباعة
                    if not app.last_summary_info:
                        td = datetime.date.today()
                        folder = app._watch_path or DEFAULT_RECEIPTS_DIR
                        if os.path.isdir(folder) and os.path.exists(PDFTOTEXT_EXE) and app.processing_lock.acquire(blocking=False):
                            try:
                                recs = collect_records(folder, td)
                                if recs:
                                    du = annotate_records(recs)
                                    info_, us_ = build_summary(recs, du, td.strftime("%d.%m.%Y"))
                                    rp = os.path.join(DOCUMENTS_DIR, f"Insurance_Report_{td.strftime('%d-%m-%Y')}.xlsx")
                                    app.last_generated_file = write_report(recs, rp) if OPENPYXL_AVAILABLE else rp
                                    app.system_total_sum = info_["total_sum"]
                                    app.last_detailed_records = recs
                                    app.last_units_summary = us_
                                    app.last_summary_info = info_
                            finally:
                                if app.processing_lock.locked():
                                    app.processing_lock.release()
                    if not app.last_summary_info:
                        return self._send_json({"ok": False, "error": "لا توجد إيصالات اليوم لعمل الملخص"})
                    info = dict(app.last_summary_info)
                    day_iso = _day_iso_from_label(info.get("date_label", "")) or datetime.date.today().isoformat()
                    summary_unit_save(day_iso, unit, tid)
                    app._refresh_archive_day_summary(day_iso)
                    base_file = app.last_generated_file or os.path.join(DOCUMENTS_DIR, f"Insurance_Report_{datetime.date.today().strftime('%d-%m-%Y')}.xlsx")
                    pdf_path = os.path.splitext(base_file)[0] + "_Summary.pdf"
                    build_summary_pdf_file(info, pdf_path, unit, tid)
                    printed = False
                    if data.get("print", False):
                        printed = bool(app.send_to_thermal_printer_57x90(pdf_path))
                    if not printed:
                        try: os.startfile(pdf_path)
                        except Exception as _e: _log_silent("bridge_summary_open", _e)
                    return self._send_json({"ok": True, "printed": printed, "path": pdf_path})

                if p == "/api/auth":
                    rem = sup_lock_remaining()
                    if rem > 0:
                        return self._send_json({"ok": False, "error": f"مقفول مؤقتًا ({rem}ث)"})
                    val = (data.get("password") or "").strip().lower()
                    if is_supervisor_password(val):
                        sup_register_success()
                        bridge_state["supervisor"] = True
                        return self._send_json({"ok": True, "is_supervisor": True})
                    sup_register_fail()
                    return self._send_json({"ok": False, "error": "كلمة المرور غير صحيحة"})

                return self._send_json({"ok": False, "error": "not found"}, 404)
            except Exception as e:
                log_exception("bridge_post", e)
                return self._send_json({"ok": False, "error": str(e)}, 500)

    try:
        srv = ThreadingHTTPServer((LOCAL_BRIDGE_HOST, LOCAL_BRIDGE_PORT), _A2RBridgeHandler)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
    except Exception as e:
        log_exception("start_local_chrome_bridge", e)
        return None


_FTS5_SUPPORTED = None

def _has_fts5(conn):
    global _FTS5_SUPPORTED
    if _FTS5_SUPPORTED is not None:
        return _FTS5_SUPPORTED
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS archive_fts USING fts5(path UNINDEXED, search_text, tokenize='unicode61')")
        _FTS5_SUPPORTED = True
    except Exception as e:
        _log_silent("fts5_init", e)
        _FTS5_SUPPORTED = False
    return _FTS5_SUPPORTED

def _norm_fts_text(unit, plate, insured, fname, chassis, motor):
    parts = [unit, plate, insured, fname, chassis, motor]
    tokens = []
    for p in parts:
        s = clean_arabic(str(p or "")).lower()
        for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
            s = s.replace(a, b)
        s_sp = re.sub(r"[^0-9a-zء-ي]+", " ", s).strip()
        s_cp = re.sub(r"\s+", "", s_sp)
        if s_sp and s_sp != "-":
            tokens.append(s_sp)
        if s_cp and s_cp != s_sp and s_cp != "-":
            tokens.append(s_cp)
    return " ".join(tokens)

def _ensure_archive_index():
    conn = db_connect()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS archive_index (
            path TEXT PRIMARY KEY, day TEXT, file TEXT, unit TEXT, plate TEXT,
            insured TEXT, amount REAL, rec_time TEXT, is_manual INTEGER,
            is_void INTEGER, is_receipt INTEGER, mtime REAL, size INTEGER,
            chassis TEXT DEFAULT '-', motor TEXT DEFAULT '-'
        )
    ''')
    cols = {r[1] for r in conn.execute("PRAGMA table_info(archive_index)").fetchall()}
    if "chassis" not in cols:
        conn.execute("ALTER TABLE archive_index ADD COLUMN chassis TEXT DEFAULT '-'")
    if "motor" not in cols:
        conn.execute("ALTER TABLE archive_index ADD COLUMN motor TEXT DEFAULT '-'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_arch_day ON archive_index(day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_arch_unit ON archive_index(unit)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_arch_amount ON archive_index(amount)")
    if _has_fts5(conn):
        fts_cnt = conn.execute("SELECT COUNT(*) FROM archive_fts").fetchone()[0]
        rec_cnt = conn.execute("SELECT COUNT(*) FROM archive_index WHERE is_receipt = 1").fetchone()[0]
        if rec_cnt > 0 and fts_cnt == 0:
            rows = conn.execute(
                "SELECT path, unit, plate, insured, file, IFNULL(chassis,'-'), IFNULL(motor,'-') "
                "FROM archive_index WHERE is_receipt = 1").fetchall()
            conn.executemany(
                "INSERT INTO archive_fts (path, search_text) VALUES (?, ?)",
                [(r[0], _norm_fts_text(r[1], r[2], r[3], r[4], r[5], r[6])) for r in rows]
            )
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
        use_fts = _has_fts5(conn)
        if stale:
            conn.executemany("DELETE FROM archive_index WHERE path = ?", stale)
            if use_fts:
                conn.executemany("DELETE FROM archive_fts WHERE path = ?", stale)

        todo = []
        for p, day in files:
            try: st = os.stat(p)
            except OSError: continue
            old = existing.get(p)
            if old and abs(old[0] - st.st_mtime) < 1 and old[1] == st.st_size: continue
            todo.append((p, day, st))

        def _read_one(item):
            p_, day_, st_ = item
            try:
                if p_.lower().endswith(".txt"):
                    return p_, day_, st_, read_txt_record(p_, datetime.date.fromisoformat(day_))
                return p_, day_, st_, read_pdf_record(p_, manual_map)
            except Exception as e:
                log_exception(f"archive_index:{os.path.basename(p_)}", e)
                return p_, day_, st_, None

        def _store_one(p, day, st, rec):
            fname = os.path.basename(p)
            if rec:
                ch = str(rec.get("chassis") or "-")
                mo = str(rec.get("motor") or "-")
                row = (p, day, fname, rec["unit"], rec["plate"], rec["insured"], float(rec["amount"]),
                       rec["time"], int(bool(rec["is_manual"])), int(bool(rec["is_void"])), 1, st.st_mtime, st.st_size, ch, mo)
            else:
                ch, mo = "-", "-"
                row = (p, day, fname, "", "-", "-", 0.0, "-", 0, 0, 0, st.st_mtime, st.st_size, ch, mo)
            conn.execute(
                "INSERT OR REPLACE INTO archive_index "
                "(path, day, file, unit, plate, insured, amount, rec_time, is_manual, is_void, is_receipt, mtime, size, chassis, motor) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            if use_fts:
                conn.execute("DELETE FROM archive_fts WHERE path = ?", (p,))
                if rec:
                    conn.execute("INSERT INTO archive_fts (path, search_text) VALUES (?, ?)",
                                 (p, _norm_fts_text(rec["unit"], rec["plate"], rec["insured"], fname, ch, mo)))

        total = len(todo)
        if total > 3:
            workers = min(4, max(2, os.cpu_count() or 2))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for i, fut in enumerate(as_completed([ex.submit(_read_one, it) for it in todo]), 1):
                    p, day, st, rec = fut.result()
                    _store_one(p, day, st, rec)
                    done_new += 1
                    if i % 40 == 0:
                        conn.commit()
                        if progress: progress(i, total)
        else:
            for i, it in enumerate(todo, 1):
                p, day, st, rec = _read_one(it)
                _store_one(p, day, st, rec)
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
    """صفوف الأرشيف + النصوص المُطبَّعة (plate/insured/file/chassis/motor/unit) محسوبة مرة واحدة كـ Fallback."""
    conn = _ensure_archive_index()
    try:
        sig = conn.execute("SELECT COUNT(*), IFNULL(SUM(mtime),0), IFNULL(SUM(is_void),0), "
                           "IFNULL(SUM(amount),0) FROM archive_index").fetchone()
        with _ARCH_SEARCH_LOCK:
            if _ARCH_SEARCH_CACHE["sig"] == sig:
                return _ARCH_SEARCH_CACHE["rows"]
        rows = conn.execute(
            "SELECT path, day, file, unit, plate, insured, amount, rec_time, is_manual, is_void, "
            "IFNULL(chassis,'-'), IFNULL(motor,'-') "
            "FROM archive_index WHERE is_receipt = 1").fetchall()
    finally:
        conn.close()
    prepared = [
        (r, _norm_search(r[4]), _norm_search(r[5]), _norm_search(r[2]),
         _norm_search(r[10]), _norm_search(r[11]), _norm_search(r[3]))
        for r in rows
    ]
    with _ARCH_SEARCH_LOCK:
        _ARCH_SEARCH_CACHE["sig"] = sig
        _ARCH_SEARCH_CACHE["rows"] = prepared
    return prepared

def _parse_amount_query(raw_q):
    """يدعم مبلغ محدد (521.57) أو نطاق مبلغ (500-1000 أو 500..1000)."""
    s = str(raw_q or "").strip().replace(",", "")
    if not s:
        return None, None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-|\.\.)\s*(\d+(?:\.\d+)?)", s)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return (lo, hi) if lo <= hi else (hi, lo)
    try:
        v = float(s)
        return v - 0.005, v + 0.005
    except Exception:
        return None, None

def archive_units_list(min_day=""):
    conn = _ensure_archive_index()
    try:
        if min_day:
            rows = conn.execute(
                "SELECT DISTINCT unit FROM archive_index WHERE is_receipt = 1 AND day >= ? AND unit != '' ORDER BY unit",
                (min_day,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT unit FROM archive_index WHERE is_receipt = 1 AND unit != '' ORDER BY unit").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()

def archive_search(query="", include_void=True, limit=3000, min_day="", max_day="", unit_filter="", status_filter="all"):
    raw_q = str(query or "").strip()
    q_norm = _norm_search(raw_q)
    amt_lo, amt_hi = _parse_amount_query(raw_q)
    has_filter = bool(min_day or max_day or unit_filter or (status_filter and status_filter != "all"))
    if not q_norm and amt_lo is None and not has_filter:
        return []

    where = ["a.is_receipt = 1"]
    params = []
    if not include_void and status_filter != "void":
        where.append("a.is_void = 0")
    if status_filter == "void":
        where.append("a.is_void = 1")
    elif status_filter == "manual":
        where.append("a.is_void = 0 AND a.is_manual = 1")
    elif status_filter == "ok":
        where.append("a.is_void = 0 AND a.is_manual = 0")
    if min_day:
        where.append("a.day >= ?")
        params.append(min_day)
    if max_day:
        where.append("a.day <= ?")
        params.append(max_day)
    if unit_filter:
        where.append("a.unit = ?")
        params.append(unit_filter)

    conn = _ensure_archive_index()
    try:
        # 1. بحث بالفلاتر فقط أو بالمبلغ/النطاق مباشرة عبر فهرس SQLite
        if not q_norm or amt_lo is not None:
            sql_where = list(where)
            sql_params = list(params)
            if amt_lo is not None:
                # لو رقم واحد: نطابق المبلغ أو نسمح بمطابقة جزء من اللوحة/الشاسيه/الملف
                if abs(amt_hi - amt_lo) <= 0.02 and q_norm:
                    pass  # هنكمل للبحث النصي + المبلغ تحت
                else:
                    sql_where.append("a.amount BETWEEN ? AND ?")
                    sql_params.extend([amt_lo, amt_hi])
                    sql = (
                        "SELECT a.path, a.day, a.file, a.unit, a.plate, a.insured, a.amount, a.rec_time, "
                        "a.is_manual, a.is_void, IFNULL(a.chassis,'-'), IFNULL(a.motor,'-') "
                        "FROM archive_index a WHERE " + " AND ".join(sql_where) +
                        " ORDER BY a.day DESC, a.rec_time DESC LIMIT ?"
                    )
                    sql_params.append(limit)
                    return conn.execute(sql, sql_params).fetchall()
            else:
                sql = (
                    "SELECT a.path, a.day, a.file, a.unit, a.plate, a.insured, a.amount, a.rec_time, "
                    "a.is_manual, a.is_void, IFNULL(a.chassis,'-'), IFNULL(a.motor,'-') "
                    "FROM archive_index a WHERE " + " AND ".join(sql_where) +
                    " ORDER BY a.day DESC, a.rec_time DESC LIMIT ?"
                )
                sql_params.append(limit)
                return conn.execute(sql, sql_params).fetchall()

        # 2. بحث فوري عبر SQLite FTS5 (يدعم الكلمات المتعددة والبادئات) + مطابقة المبلغ لو رقم
        if _has_fts5(conn):
            raw_tokens = [t for t in re.split(r"[\s\-_]+", clean_arabic(raw_q).lower()) if t]
            norm_tokens = []
            for tk in raw_tokens:
                for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
                    tk = tk.replace(a, b)
                tk = re.sub(r"[^0-9a-zء-ي]", "", tk)
                if tk:
                    norm_tokens.append(tk)
            if norm_tokens:
                fts_match = " AND ".join(f'"{tk}"*' for tk in norm_tokens)
                fts_where = list(where)
                fts_params = list(params)
                if amt_lo is not None:
                    fts_where.append("(a.path IN (SELECT path FROM archive_fts WHERE archive_fts MATCH ?) OR a.amount BETWEEN ? AND ?)")
                    fts_params.extend([fts_match, amt_lo, amt_hi])
                else:
                    fts_where.append("a.path IN (SELECT path FROM archive_fts WHERE archive_fts MATCH ?)")
                    fts_params.append(fts_match)
                sql = (
                    "SELECT a.path, a.day, a.file, a.unit, a.plate, a.insured, a.amount, a.rec_time, "
                    "a.is_manual, a.is_void, IFNULL(a.chassis,'-'), IFNULL(a.motor,'-') "
                    "FROM archive_index a WHERE " + " AND ".join(fts_where) +
                    " ORDER BY a.day DESC, a.rec_time DESC LIMIT ?"
                )
                fts_params.append(limit)
                rows = conn.execute(sql, fts_params).fetchall()
                if rows:
                    return rows
    except Exception as e:
        log_exception("archive_search_fts", e)
    finally:
        conn.close()

    # 3. Fallback: بحث جزئي داخل الكلمة (substring) عبر الكاش المطبّع (مثلاً آخر 4 أرقام من الشاسيه)
    out = []
    for r, n_plate, n_insured, n_file, n_chassis, n_motor, n_unit in _archive_search_rows():
        path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void, ch, mo = r
        if is_void and not include_void and status_filter != "void": continue
        if status_filter == "void" and not is_void: continue
        if status_filter == "manual" and (is_void or not is_manual): continue
        if status_filter == "ok" and (is_void or is_manual): continue
        if min_day and day < min_day: continue
        if max_day and day > max_day: continue
        if unit_filter and unit != unit_filter: continue
        hit = (q_norm in n_plate or q_norm in n_insured or q_norm in n_file
               or q_norm in n_chassis or q_norm in n_motor or q_norm in n_unit)
        if not hit and amt_lo is not None and amt_lo <= amount <= amt_hi:
            hit = True
        if hit:
            out.append(r)
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
_CACHE_MISS = object()

def _cache_get(cache, key):
    """قراءة آمنة مع التعدد (Threads) من الكاش، ترجع _CACHE_MISS لو المفتاح غير موجود."""
    with _CACHE_LOCK:
        return cache.get(key, _CACHE_MISS)

def _cache_put(cache, key, val):
    """تخزين مؤقت بحد أقصى: لما يعدّي الحد بنشيل أقدم نصف الإدخالات (القاموس بيحفظ ترتيب الإضافة).
    قبل كده الـ cache كان بيكبر مع كل ملف أُرشف طول عمر البرنامج."""
    with _CACHE_LOCK:
        cache[key] = val
        if len(cache) > _CACHE_LIMIT:
            for k in list(cache)[:_CACHE_LIMIT // 2]:
                cache.pop(k, None)

def _is_pdf_ready(path):
    """يتحقق أن ملف الـ PDF اكتملت كتابته بالكامل (يبدأ بـ %PDF- وينتهي بـ %%EOF وقابل للقراءة) قبل الطباعة."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(8)
            if not head.startswith(b"%PDF-"):
                return False
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size <= 1000:
                return False
            fh.seek(max(0, size - 2048))
            tail = fh.read(2048)
            return b"%%EOF" in tail
    except OSError:
        return False

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
        file_date = _cache_get(_SWEEP_CACHE, ck)
        if file_date is _CACHE_MISS:
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
                if _has_fts5(conn):
                    conn.execute("DELETE FROM archive_fts")
            else:
                if _has_fts5(conn):
                    conn.executemany("DELETE FROM archive_fts WHERE path IN (SELECT path FROM archive_index WHERE day = ?)", [(d,) for d in days])
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
EMPLOYEE_HASHES = {
    "05c8bd5d4dcdb18b690e160fd7a5c5190ee9ce7eb565d88f8e7b1f81b5f25bf6",
    "06ff8a72d6c750f6190e3be9beee93480751e63429b79a4a9a3409d537cf4710",
    "158a323a7ba44870f23d96f1516dd70aa48e9a72db4ebb026b0a89e212a208ab",
    "165940940a02a187e4463ff467090930038c5af8fc26107bf301e714f599a1da",
    "1c6bf6cd5656b79a9cd667582d2b31a6bcdd071acd1f1fdc0bb653df031fe409",
    "2759755265efab6b9a509e4c2662aead97747c0b5ad16694dd72fef521b5d1aa",
    "38aaaa2726ae59363be8267ddf3c887e125abf3872a221c3048c931b73563e4e",
    "5994471abb01112afcc18159f6cc74b4f511b99806da59b3caf5a9c173cacfc5",
    "65ec295e41007d643b557a13a2d8fda976f887ab352ee51debba9417914e686e",
    "67a375e4ddcdb509545a752ea82be28b546ded87431078fe6fc1ead202f5815c",
    "922da9fd247cabfaa88ac472af4e4910cab8b5a5cd1f243ce15a9cd80b844384",
    "9a54ca89652e118aef6d89047338e990240c40ec810f3f5dd00f191acd7feff2",
    "9b59026d8817985b390666d0fe1695b63d9be2e7a60e3c07274193642eda3247",
    "a4f1a218260b2efd0b86780410a4e0ec643bd33dcadc9ae2c6d8e2282ae01115",
    "a7be8e1fe282a37cd666e0632b17d933fa13f21addf4798fc0455bc166e2488c",
    "ad5055ce5b414306010f3e844346b669fbf99b47b5f9f3a4e589c86a216fdcaf",
    "aeba47c17ca09557808c333b49af210a0209aff6b4334fa7192aaed69c5f36dd",
    "aff4d166083896b1584b9b3ed2b89cce8c9abe10fe384342d1ed2e73114c819e",
    "ec9b8e7a0da6fa1d24ebb7546db2f67ca2320b110c93ede3c5c5d3ef13ebe1ab",
    "ed823ec32c5d4e9ca9dd968bb0fe9366b7d904ce0cae615308ddd5b89f0e6a3a",
    "f1294f35f19846cd012506eadcc13ecda95eb7ddc6c661bc1b9402c4b00eb703",
}

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


def _text_parse_complete(f):
    return (
        _receipt_ok(f)
        and f.get("plate", "-") != "-"
        and f.get("unit", UNSPEC) != UNSPEC
        and float(f.get("amount") or 0) > 0
        and f.get("dt") is not None
        and f.get("chassis", "-") != "-"
    )

def parse_receipt(path, txt):
    old = parse_receipt_text(txt)
    if _text_parse_complete(old):
        return old
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
        cached_m = _cache_get(_PARSE_CACHE, key)
        if cached_m is not _CACHE_MISS:
            return dict(cached_m)
        txt = run_pdftotext(path)
        unit = detect_unit_from_text(txt) or UNSPEC
        tm = TIME_RE.search(txt)
        dt = parse_print_time(tm.group(0).strip().replace("/", "-")) if tm else None
        amt = float(m_amt.group(1)) if m_amt else 0.0
        rec = make_record(path, unit, "-", "-", amt, dt, mdate, True)
        _cache_put(_PARSE_CACHE, key, dict(rec))
        return rec

    key = (path, st.st_mtime, st.st_size)
    cached = _cache_get(_PARSE_CACHE, key)
    if cached is not _CACHE_MISS:
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

    if len(pdf_files) > 3:
        workers = min(4, max(2, os.cpu_count() or 2))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            fut_map = {ex.submit(read_pdf_record, pdf, manual_map): pdf for pdf in pdf_files}
            for fut in as_completed(fut_map):
                pdf = fut_map[fut]
                done += 1
                if progress: progress(done, total, os.path.basename(pdf))
                try:
                    rec = fut.result()
                except Exception as e:
                    log_exception(f"collect_pdf:{os.path.basename(pdf)}", e)
                    rec = None
                if rec and rec["actual_date"] == target_date:
                    records.append(refresh_void_flag(rec))
    else:
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

def scale_pdf_to_print_width(src_pdf, target_w=None, target_h=None):
    """ينشئ نسخة مؤقتة من الـ PDF بمقاس الورق المختار (عرض وطول) مع الحفاظ على التناسب.
    يدعم التصغير والتكبير ليعكس أي تعديل في مقاس الطباعة فعليًا بدون الحاجة لصلاحيات أدمن."""
    if not PYPDF_AVAILABLE:
        return None
    if target_w is None:
        target_w = _PRINT_PAPER_MM[0] / 25.4 * 72.0
    if target_h is None:
        target_h = _PRINT_PAPER_MM[1] / 25.4 * 72.0
    try:
        reader = PdfReader(src_pdf)
        if not reader.pages:
            return None
        pw = float(reader.pages[0].mediabox.width)
        ph = float(reader.pages[0].mediabox.height)
        if pw <= 0 or ph <= 0:
            return None
        f = min(target_w / pw, target_h / ph)
        if abs(f - 1.0) < 0.01:
            return None
        writer = PdfWriter()
        for pg in reader.pages:
            pg = writer.add_page(pg)   # لازم الصفحة تتسجل في الـ writer الأول قبل التعديل (pypdf 7 بيرفض scale على صفحة يتيمة)
            pg.scale_by(f)
        os.makedirs(PRINT_TEMP_DIR, exist_ok=True)
        dst = os.path.join(PRINT_TEMP_DIR, "s_" + os.path.basename(src_pdf))
        with open(dst, "wb") as fh:
            writer.write(fh)
        return dst
    except Exception as e:
        log_exception("scale_pdf_to_print_width", e)
        return None

def create_test_print_pdf(filepath, w_mm, h_mm):
    """إيصال اختبار صغير بإطار واضح ومقاس الورقة بالمم للتحقق الفوري من مقاس الطباعة."""
    if not REPORTLAB_AVAILABLE:
        return False
    pt = 72.0 / 25.4
    pw, ph = float(w_mm) * pt, float(h_mm) * pt
    c = canvas.Canvas(filepath, pagesize=(pw, ph))
    m = 4.0
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.5)
    c.rect(m, m, max(10, pw - 2 * m), max(10, ph - 2 * m))
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", max(8, min(13, pw * 0.08)))
    c.drawCentredString(pw / 2, ph * 0.66, "A2R TEST PRINT")
    c.setFont("Helvetica-Bold", max(8, min(14, pw * 0.09)))
    c.drawCentredString(pw / 2, ph * 0.48, f"{_fmt_mm(w_mm)} x {_fmt_mm(h_mm)} mm")
    c.setFont("Helvetica", max(6, min(9, pw * 0.055)))
    c.drawCentredString(pw / 2, ph * 0.28, datetime.datetime.now().strftime("%d-%m-%Y  %H:%M"))
    c.save()
    return True

def _make_print_copy_pypdf(src_pdf):
    """بديل آمن للقص باستخدام pypdf في حال كانت بنية ملف الـ PDF مضغوطة أو غير متوافقة مع التعديل المباشر."""
    if not PYPDF_AVAILABLE:
        return None
    try:
        reader = PdfReader(src_pdf)
        if not reader.pages:
            return None
        pg = reader.pages[0]
        x0, y0 = float(pg.mediabox.left), float(pg.mediabox.bottom)
        x1, y1 = float(pg.mediabox.right), float(pg.mediabox.top)

        new_y0 = None
        try:
            contents = pg.get_contents()
            raw_c = contents.get_data() if contents is not None else b""
            qr_top = _find_qr_top(raw_c)
            if qr_top is not None:
                new_y0 = qr_top + 4.5
        except Exception as _e:
            _log_silent("make_print_copy_pypdf#qr", _e)

        if new_y0 is None:
            info = get_print_time_bottom(src_pdf)
            if info:
                new_y0 = y1 - (info[0] + 12.0)

        if new_y0 is None:
            return None
        new_y0 = max(y0, new_y0)
        if new_y0 >= y1 - 40:
            return None

        pg.mediabox.lower_left = (x0, new_y0)
        pg.mediabox.upper_right = (x1, y1)
        pg.cropbox.lower_left = (x0, new_y0)
        pg.cropbox.upper_right = (x1, y1)

        writer = PdfWriter()
        writer.add_page(pg)
        os.makedirs(PRINT_TEMP_DIR, exist_ok=True)
        dst = os.path.join(PRINT_TEMP_DIR, os.path.basename(src_pdf))
        with open(dst, "wb") as fh:
            writer.write(fh)
        return dst
    except Exception as e:
        log_exception("make_print_copy_pypdf", e)
        return None

def make_print_copy(src_pdf):
    try:
        data = bytearray(open(src_pdf, "rb").read())
        page_obj = None
        for m in re.finditer(rb"\d+\s+0\s+obj(.*?)endobj", data, re.S):
            if re.search(rb"/Type\s*/Page(?![A-Za-z])", m.group(1)):
                page_obj = m
                break
        if not page_obj:
            return _make_print_copy_pypdf(src_pdf)
        page_body = bytes(data[page_obj.start(1):page_obj.end(1)])
        mb = re.search(rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]", page_body)
        if not mb:
            return _make_print_copy_pypdf(src_pdf)
        x0, y0, x1, y1 = [float(v) for v in mb.groups()]

        new_y0 = None
        qr_top = _find_qr_top(_content_stream_bytes(data, page_body))
        if qr_top is not None:
            new_y0 = qr_top + 4.5
        else:
            info = get_print_time_bottom(src_pdf)
            if info:
                new_y0 = y1 - (info[0] + 12.0)

        if new_y0 is None:
            return _make_print_copy_pypdf(src_pdf)
        new_y0 = max(y0, new_y0)
        if new_y0 >= y1 - 40:
            return None

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
        if len(new) > old_len:
            return _make_print_copy_pypdf(src_pdf)

        new = new + b" " * (old_len - len(new))
        data[reg_start:reg_end] = new

        os.makedirs(PRINT_TEMP_DIR, exist_ok=True)
        dst = os.path.join(PRINT_TEMP_DIR, os.path.basename(src_pdf))
        with open(dst, "wb") as f:
            f.write(data)
        return dst
    except Exception as e:
        log_exception("make_print_copy", e)
        return _make_print_copy_pypdf(src_pdf)

class ElevateLoginGate(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        _set_win_alpha(self, 0.0)
        self.parent = parent
        self.on_success = on_success
        self.title("A2R Authorization")
        self.resizable(False, False)
        set_window_icon_safe(self)

        t = THEMES[parent.current_theme_name]
        self.configure(fg_color=t["bg"])

        ctk.CTkFrame(self, height=3, corner_radius=0, fg_color=t["danger_btn"]).pack(fill="x")

        card = ctk.CTkFrame(self, corner_radius=14, fg_color=t["card"], border_width=1, border_color=t["border"])
        card.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(card, text="A2R OPERATIONS", height=24, font=(FONT_FAMILY, 16, "bold"), text_color=t["accent"]).pack(pady=(10, 2))
        ctk.CTkLabel(card, text=tr("login_prompt"), height=18, font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"]).pack(pady=(0, 8))

        f_entry = ctk.CTkFrame(card, fg_color="transparent")
        f_entry.pack(fill="x", padx=16, pady=2)

        self.e_pwd = ctk.CTkEntry(f_entry, show="•", justify="center", height=34, font=(FONT_FAMILY, 13, "bold"),
                                  text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        self.e_pwd.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.e_pwd.bind("<Return>", lambda e: self.check_pwd())
        attach_context_menu(self.e_pwd)

        self.pwd_visible = False
        self.btn_eye = ctk.CTkButton(f_entry, text="👁️", width=40, height=34, corner_radius=9, command=self.toggle_eye,
                                     **_ghost(t, "secondary"))
        self.btn_eye.pack(side="right")

        self.lbl_err = ctk.CTkLabel(card, text="", height=16, text_color=t["danger"], font=(FONT_FAMILY, 10, "bold"))
        self.lbl_err.pack(pady=(2, 0))

        btn_enter = ctk.CTkButton(card, text=tr("btn_full_console"), font=FONT_BTN_MAIN, height=34, corner_radius=10,
                                  **_ghost(t, "danger_btn"),
                                  command=self.check_pwd)
        btn_enter.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(self, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria", height=18,
                     font=(FONT_FAMILY, 9, "bold"), text_color=t["text_muted"]).pack(pady=(0, 8))
        fit_and_center(self, parent, 365, min_height=225, focus_widget=self.e_pwd)
        try: self.grab_set()
        except Exception as _e: _log_silent("ElevateLoginGate#grab", _e)

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

class CustomTkinterApp(ctk.CTk):
    def validate_numeric_input(self, val):
        if val == "": return True
        return bool(re.match(r"^[\d,]*\.?\d*$", val))

    def __init__(self):
        super().__init__()
        _set_win_alpha(self, 0.0)   # شفافية مؤقتة أثناء بناء العناصر لتفتح النافذة مكتملة في إطار واحد بدون اختفاء أو تقطيع
        self.title(f"A2R Operations Console - {APP_OWNER}")
        self.resizable(False, False)
        
        # فرض أبعاد دنيا ثابتة تمنع انكماش النافذة نهائياً
        self.minsize(440, 210)
        set_window_icon_safe(self)

        global CURRENT_LANG, SOUND_MUTED
        _cfg = _read_app_config()
        _saved_lang = _cfg.get("lang")
        self.current_lang = _saved_lang if _saved_lang in LANGUAGES else "en"
        CURRENT_LANG = self.current_lang
        _saved_theme = _cfg.get("theme")
        self.current_theme_name = _saved_theme if _saved_theme in THEMES else "Windows Dark"
        if "sound_muted" in _cfg:
            SOUND_MUTED = bool(_cfg.get("sound_muted"))

        self.is_mini_mode = True
        # المزامنة والطباعة الفورية تعملان دائمًا مع كل تشغيل للجهاز/البرنامج
        self.auto_sync_enabled = True
        self.auto_print_enabled = True

        self.is_supervisor = False
        self.last_generated_file = None
        self.system_total_sum = 0.0
        self.last_detailed_records = []
        self.last_units_summary = {}
        self.last_summary_info = {}

        self.printed_count_today = 0
        self._printed_count_day = datetime.date.today()
        self.last_printed_pdf = None
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

        # تنزيل/تحديث إضافة كروم تلقائيًا داخل مجلد الأرشيف الاحتياطي في Documents + تشغيل الجسر المحلي (127.0.0.1)
        threading.Thread(target=ensure_chrome_extension_extracted, daemon=True).start()
        self._bridge_server = start_local_chrome_bridge(self)

        # مزامنة فورية صامتة لإجمالي اليوم فور التشغيل (حتى يظهر الرقم الفعلي مباشرة في الإضافة)
        self.after(1500, lambda: self.start_thread() if (self.auto_sync_enabled and not self.is_processing) else None)

        # تشغيل الأرشفة التلقائية الكاملة فور إقلاع الجهاز/التطبيق (حتى في وضع الميني أو بجوار الساعة)
        self._refresh_mini_archive_label()
        self._archive_tick_started = True
        self.after(2500, self.auto_archive_on_login)
        self.after(600000, self._archive_tick)

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

    def _has_open_child_windows(self):
        """يتحقق إذا كانت هناك أي نافذة فرعية مفتوحة (حاسبة الكاش، الإضافة اليدوية، الأرشيف، عرض السجلات، إلخ)."""
        try:
            for w in self.winfo_children():
                if isinstance(w, (tk.Toplevel, ctk.CTkToplevel)):
                    try:
                        if w.winfo_exists() and w.state() != "withdrawn":
                            return True
                    except Exception:
                        pass
        except Exception as _e:
            _log_silent("_has_open_child_windows", _e)
        return False

    def _auto_minimize_to_taskbar(self):
        try:
            if self._has_open_child_windows():
                self._schedule_auto_minimize(15000)
                return
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
            _set_win_alpha(self, 1.0)
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
        if getattr(self, "_bridge_server", None):
            try: self._bridge_server.shutdown()
            except Exception as _e: _log_silent("quit_bridge", _e)
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
        _set_win_alpha(win, 0.0)
        self._paper_win = win
        win.title(T2("مقاس الطباعة", "Print Size"))
        win.resizable(False, False)
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
            # لو فيه مقاس مطابق جوه درايفر الطابعة نختاره تلقائيًا
            for lab, (nm, pw, ph) in papers_map.items():
                if abs(pw - a) <= 3 and abs(ph - b) <= 3:
                    sel["name"] = nm
                    try: cb_papers.set(lab)
                    except Exception as _e: _log_silent("fp_preset#cb", _e)
                    break
            _fill(a, b)
        for (pw, ph) in PRINT_PAPER_PRESETS_MM:
            ctk.CTkButton(f_pre, text=f"{_fmt_mm(pw)} × {_fmt_mm(ph)}", width=90, height=28, font=FONT_BTN_SUB,
                          **_ghost(t, "primary"),
                          command=lambda a=pw, b=ph: _preset(a, b)).pack(side="left", padx=(0, 6))

        sel = {"name": _PRINT_PAPER_NAME}
        papers_map = {}

        ctk.CTkLabel(win, text=T2("مقاسات الطابعة الافتراضية", "Default printer paper sizes"),
                     font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(10, 2))
        cb_papers = ctk.CTkComboBox(win, values=[T2("... بقرا المقاسات من الطابعة", "... reading printer sizes")],
                                    height=32, font=FONT_ENTRY, state="readonly")
        cb_papers.set(T2("... بقرا المقاسات من الطابعة", "... reading printer sizes"))
        style_combo(cb_papers, t)
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
                     font=(FONT_FAMILY, 9), text_color=t["text"], wraplength=300, justify="left").pack(anchor="w", padx=16)

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

        def _test_print():
            try:
                w = float(e_w.get().strip().replace(",", "."))
                h = float(e_h.get().strip().replace(",", "."))
            except Exception:
                lbl_err.configure(text=T2("اكتب أرقام صحيحة للعرض والطول", "Enter valid numbers for width and height"))
                return
            if not (20 <= w <= 300 and 20 <= h <= 600):
                lbl_err.configure(text=T2("المقاس خارج المدى المسموح", "Size out of range"))
                return
            save_print_paper(w, h, sel["name"])
            self.btn_fix_printer.configure(text=self._paper_btn_text())
            try: btn_test.configure(state="disabled", text=T2("⏳ جاري الطباعة...", "⏳ Printing..."))
            except Exception as _e: _log_silent("fp_test#dis", _e)

            def _bg():
                ok = False
                try:
                    os.makedirs(PRINT_TEMP_DIR, exist_ok=True)
                    tp = os.path.join(PRINT_TEMP_DIR, "a2r_test_size.pdf")
                    if create_test_print_pdf(tp, w, h):
                        ok = self.send_to_thermal_printer_57x90(tp, is_test=True)
                except Exception as e:
                    log_exception("test_print", e)
                def _fin():
                    try:
                        if win.winfo_exists():
                            btn_test.configure(state="normal", text=T2("🖨️ طباعة تجريبية", "🖨️ Test Print"))
                            if ok:
                                play_sound_matched()
                                lbl_err.configure(text=T2("✓ تم إرسال ورقة الاختبار للطابعة", "✓ Test page sent to printer"), text_color=t["success"])
                            else:
                                lbl_err.configure(text=T2("تعذرت الطباعة — تأكد من الطابعة", "Print failed — check printer"), text_color=t["danger"])
                    except Exception as _e: _log_silent("fp_test#fin", _e)
                self.run_on_main(_fin)
            threading.Thread(target=_bg, daemon=True).start()

        f_fp_tools = ctk.CTkFrame(win, fg_color="transparent")
        f_fp_tools.pack(fill="x", padx=16, pady=(8, 4))
        btn_test = ctk.CTkButton(f_fp_tools, text=T2("🖨️ طباعة تجريبية", "🖨️ Test Print"), font=FONT_BTN_SUB,
                                 height=32, corner_radius=9, **_ghost(t, "primary"), command=_test_print)
        btn_test.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(f_fp_tools, text=T2("⚙️ إعدادات الدرايفر", "⚙️ Driver Settings"), font=FONT_BTN_SUB,
                      height=32, corner_radius=9, **_ghost(t, "secondary"), command=lambda: threading.Thread(target=open_default_printer_preferences, daemon=True).start()
                      ).pack(side="right", fill="x", expand=True, padx=(4, 0))

        btn_save = ctk.CTkButton(win, text=T2("حفظ وتطبيق", "Save & Apply"), font=FONT_BTN_MAIN, height=36, corner_radius=10,
                                 fg_color=t["warn_btn"], hover_color=t["warn_btn_hover"], text_color="#FFFFFF", command=_save)
        btn_save.pack(fill="x", padx=16, pady=(4, 10))
        win.bind("<Return>", _save)
        win.bind("<Escape>", lambda e: _close())
        win.protocol("WM_DELETE_WINDOW", _close)
        fit_and_center(win, self, 365, min_height=340, focus_widget=e_w)

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

    def reprint_last_receipt(self):
        """إعادة طباعة آخر إيصال تم طباعته (أو أحدث إيصال في المجلد اليوم لو البرنامج لسه مفتوح)."""
        self._cancel_auto_minimize()
        target = self.last_printed_pdf if (self.last_printed_pdf and os.path.exists(self.last_printed_pdf)) else None
        if not target:
            p = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
            if p and os.path.isdir(p):
                today_d = datetime.date.today()
                best_mt, best_p = 0.0, None
                try:
                    with os.scandir(p) as it:
                        for ent in it:
                            if not ent.is_file(): continue
                            fn = ent.name
                            fn_l = fn.lower()
                            if not fn_l.endswith(".pdf") or fn_l.endswith("_cropped.pdf") or fn_l.endswith("_summary.pdf"):
                                continue
                            if not (fn_l.startswith("quote_receipt_") or MANUAL_NAME_RE.match(fn)):
                                continue
                            if fn.lstrip("_") in _VOID_KEYS:
                                continue
                            st = ent.stat()
                            if datetime.date.fromtimestamp(st.st_mtime) == today_d and st.st_mtime > best_mt:
                                best_mt, best_p = st.st_mtime, ent.path
                except Exception as e:
                    log_exception("reprint_last_scan", e)
                target = best_p

        if not target or not os.path.exists(target):
            messagebox.showinfo(T2("تنبيه", "Notice"),
                                T2("لا يوجد إيصال مطبوع اليوم لإعادة طباعته.", "No receipt printed today to reprint."))
            if self.is_mini_mode:
                self._schedule_auto_minimize(5000)
            return

        self.last_printed_pdf = target
        try: self.btn_mini_reprint.configure(state="disabled")
        except Exception as _e: _log_silent("reprint_last#dis", _e)

        def _work():
            ok = self.send_to_thermal_printer_57x90(target)
            def _done():
                try: self.btn_mini_reprint.configure(state="normal")
                except Exception as _e: _log_silent("reprint_last#en", _e)
                if ok:
                    play_sound_matched()
                    self._tray_notify(T2(f"تمت إعادة طباعة: {os.path.basename(target)}",
                                         f"Reprinted: {os.path.basename(target)}"))
                else:
                    messagebox.showerror("Error", T2("تعذرت الطباعة. اتأكد من الطابعة وحاول تاني.",
                                                     "Printing failed. Check the printer and try again."))
                if self.is_mini_mode:
                    self._schedule_auto_minimize(5000)
            self.run_on_main(_done)

        threading.Thread(target=_work, daemon=True).start()

    def _sync_watch_path(self):
        try: self._watch_path = self.get_clean_path()
        except Exception as _e: _log_silent("_sync_watch_path#1", _e)
        try: self.after(1000, self._sync_watch_path)
        except Exception as _e: _log_silent("_sync_watch_path#2", _e)

    def request_full_console(self):
        old = getattr(self, "_login_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift(); old.focus_force(); return
        except Exception as _e: _log_silent("request_full_console#exists", _e)
        self._cancel_auto_minimize()
        self._login_win = ElevateLoginGate(self, self.unlock_full_console)

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
            self.badge_role.configure(text="● ADMIN", text_color="#DC2626")
            self.f_role_btn.configure(border_color="#DC2626")
            self.btn_arch_full.pack(side="left", padx=2)
            self.btn_excel.pack(side="left", padx=2)   # زر الإكسيل حصري للمشرف — كان مضروب pack_forget من غير ما يترجع
        else:
            self.badge_role.configure(text="● USER", text_color="#059669")
            self.f_role_btn.configure(border_color="#059669")
        self.btn_chrome.pack(side="left", padx=2)

        self.switch_to_full_view()
        # حساب إجمالي إيصالات اليوم الموجودة فور الدخول للنسخة الكاملة بدون انتظار نزول ملف جديد
        if self.auto_sync_enabled and not self.is_processing:
            self.after(250, self.start_thread)
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

    def _refresh_mini_archive_label(self):
        lbl = getattr(self, "lbl_mini_archive", None)
        if lbl is None:
            return
        try:
            t = THEMES[self.current_theme_name]
            if getattr(self, "_auto_archive_running", False):
                lbl.configure(text=T2("⏳ الأرشفة التلقائية: جاري التحديث...", "⏳ Auto-Archive: Updating..."),
                              text_color=t["warning"])
            elif self._archive_done_today():
                tm = self._archive_done_time()
                suf = f" ({tm})" if tm else ""
                lbl.configure(text=T2(f"● الأرشفة التلقائية: مكتملة اليوم ✓{suf}", f"● Auto-Archive: Completed today ✓{suf}"),
                              text_color=t["success"])
            else:
                lbl.configure(text=T2("● الأرشفة التلقائية: جاهزة في الخلفية", "● Auto-Archive: Ready in background"),
                              text_color=t["text_muted"])
        except Exception as _e:
            _log_silent("refresh_mini_archive_label", _e)

    def auto_archive_on_login(self):
        """تعمل تلقائيًا فور تشغيل الجهاز/البرنامج (في الميني أو بجوار الساعة) وحتى في أول تشغيل للتطبيق:
        - كنس كل ملفات الأيام السابقة للأرشيف + توليد إيصال السمري وإكسيل اليوم لكل يوم مؤرشف.
        - استكمال أي سمري أو إكسيل ناقص لأيام مؤرشفة سابقًا + تحديث فهرس البحث FTS5 في الخلفية."""
        folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
        if not folder or not os.path.isdir(folder):
            return
        if getattr(self, "_auto_archive_running", False):
            return
        done_today = self._archive_done_today()
        self._auto_archive_running = True
        self._refresh_mini_archive_label()

        def work():
            swept, ok, filled = 0, False, 0
            try:
                if not done_today:
                    r = self._run_archive_sweep(folder)
                    if r is not None:             # None = كنسة تانية شغالة، هنحاول تاني في الدورة الجاية
                        swept, ok = r, True
                filled = self._archive_fill_missing(folder) or 0
                if ok or (not done_today and filled >= 0):
                    self._mark_archive_done_today()
                    self._start_archive_maintenance(folder)
                elif filled > 0:
                    self._start_archive_maintenance(folder)
            except Exception as e:
                log_exception("auto_archive_on_login", e)
            finally:
                self._auto_archive_running = False
            self.run_on_main(self._refresh_mini_archive_label)
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
        if show:
            _set_win_alpha(self, 0.0)
        self.body_full.pack_forget()
        self.b_bar.pack_forget()
        self.btn_back_to_mini.pack_forget()
        self.f_role_btn.pack_forget()
        
        self.body_mini.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        self._refresh_mini_archive_label()

        sc = _win_scale(self)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.update_idletasks()
        width = 425
        req_h = int(self.winfo_reqheight() / sc)
        height = max(210, req_h + 6)
        self.minsize(width, height)
        x = max(0, (sw - int(width * sc)) // 2)
        y = max(0, (sh - int(height * sc)) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.update_idletasks()

        if not show:
            _set_win_alpha(self, 1.0)
            return

        try:
            if self.state() != "normal":
                self.deiconify()
                self.state("normal")
        except Exception as _e:
            _log_silent("switch_to_mini#show", _e)
        self.update()
        _set_win_alpha(self, 1.0)
        self.lift()
        self.focus_force()
        self._schedule_auto_minimize(5000)

    def switch_to_full_view(self):
        self.is_mini_mode = False
        _set_win_alpha(self, 0.0)
        self.body_mini.pack_forget()
        
        self.btn_back_to_mini.pack(side="right", padx=(6, 0))
        self.f_role_btn.pack(side="right", padx=(6, 0))
        self.b_bar.pack(fill="x", side="bottom")
        self.body_full.pack(fill="both", expand=True, padx=6, pady=(2, 0))

        sc = _win_scale(self)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.update_idletasks()
        req_w = int(self.winfo_reqwidth() / sc)
        req_h = int(self.winfo_reqheight() / sc)
        width = min(max(600, req_w), int((sw - 40) / sc))
        height = min(max(330, req_h), int((sh - 80) / sc))
        self.minsize(width, height)
        x = max(0, (sw - int(width * sc)) // 2)
        y = max(0, (sh - int(height * sc)) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.update_idletasks()

        try:
            if self.state() != "normal":
                self.deiconify()
                self.state("normal")
        except Exception as _e:
            _log_silent("switch_to_full#show", _e)
        self.update()
        _set_win_alpha(self, 1.0)
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
        _save_app_prefs(sound_muted=SOUND_MUTED)

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, corner_radius=0, height=44)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header_line = ctk.CTkFrame(self, height=2, corner_radius=0, fg_color="#2563EB")
        self.header_line.pack(fill="x")

        f_left = ctk.CTkFrame(self.header, fg_color="transparent")
        f_left.pack(side="left", padx=(12, 0), pady=6)

        self.lbl_logo = ctk.CTkLabel(f_left, text="A2R", font=(FONT_FAMILY, 22, "bold"))
        self.lbl_logo.pack(side="left", padx=(0, 8))

        self.cb_theme = ctk.CTkComboBox(f_left, values=THEME_KEYS, width=132, height=27, state="readonly",
                                        font=FONT_REGULAR_BOLD, command=self.on_theme_select)
        self.cb_theme.set(self.current_theme_name)
        self.cb_theme.pack(side="left", padx=(0, 4))

        self.btn_lang = ctk.CTkButton(f_left, text="🌐 عربي", width=62, height=27, corner_radius=8,
                                      font=(FONT_FAMILY, 10, "bold"), command=self.toggle_language)
        self.btn_lang.pack(side="left", padx=(0, 4))

        self.btn_mute = ctk.CTkButton(f_left, text=("🔇 Muted" if SOUND_MUTED else "🔊 Sound"), width=66, height=27, corner_radius=8,
                                      font=(FONT_FAMILY, 9, "bold"), fg_color="#334155", hover_color="#475569",
                                      command=self.toggle_mute)
        self.btn_mute.pack(side="left")

        f_right = ctk.CTkFrame(self.header, fg_color="transparent")
        f_right.pack(side="right", padx=(0, 10), pady=6)

        self.btn_back_to_mini = ctk.CTkButton(f_right, text=tr("btn_back_mini"), width=96, height=27, corner_radius=8,
                                              font=(FONT_FAMILY, 10, "bold"), fg_color="#334155", hover_color="#475569",
                                              command=self.switch_to_mini_view)

        self.f_role_btn = ctk.CTkFrame(f_right, corner_radius=8, border_width=1.2, fg_color="#121E2E")
        self.badge_role = ctk.CTkLabel(self.f_role_btn, text="● USER", height=20, font=(FONT_FAMILY, 9, "bold"), padx=8, pady=1)
        self.badge_role.pack()

        self.lbl_clock = ctk.CTkLabel(f_right, text="", font=(FONT_FAMILY, 10, "bold"), text_color="#38BDF8")
        self.lbl_clock.pack(side="right", padx=(0, 2))
        self.update_live_clock()

        self.body_mini = ctk.CTkFrame(self, fg_color="transparent")

        self.card_mini_status = ctk.CTkFrame(self.body_mini, corner_radius=8, border_width=1)
        self.card_mini_status.pack(fill="x", pady=(2, 4))

        f_mini_title_row = ctk.CTkFrame(self.card_mini_status, fg_color="transparent")
        f_mini_title_row.pack(fill="x", padx=12, pady=(7, 3))

        self.lbl_mini_title = ctk.CTkLabel(f_mini_title_row, text=tr("mini_station_title"), height=20,
                                          font=(FONT_FAMILY, 12, "bold"), text_color="#38BDF8")
        self.lbl_mini_title.pack(side="left")

        self.btn_fix_printer = ctk.CTkButton(f_mini_title_row, text=self._paper_btn_text(), width=78, height=24,
                                             corner_radius=7, font=(FONT_FAMILY, 9, "bold"), fg_color="#D97706",
                                             hover_color="#B45309", text_color="#FFFFFF", command=self.fix_printer_paper_action)
        self.btn_fix_printer.pack(side="right")

        self.lbl_mini_desc = ctk.CTkLabel(self.card_mini_status, text=tr("mini_status_active"), height=18,
                                         font=(FONT_FAMILY, 10, "bold"), text_color="#10B981")
        self.lbl_mini_desc.pack(anchor="w", padx=12, pady=(0, 1))

        self.lbl_mini_counter = ctk.CTkLabel(self.card_mini_status, text=tr("mini_printed_count", count=0), height=18,
                                            font=(FONT_FAMILY, 10, "bold"), text_color="#94A3B8")
        self.lbl_mini_counter.pack(anchor="w", padx=12, pady=(0, 1))

        self.lbl_mini_archive = ctk.CTkLabel(self.card_mini_status, text="", height=18,
                                             font=(FONT_FAMILY, 9, "bold"), text_color="#94A3B8")
        self.lbl_mini_archive.pack(anchor="w", padx=12, pady=(0, 7))

        f_mini_btns = ctk.CTkFrame(self.body_mini, fg_color="transparent")
        f_mini_btns.pack(fill="x", pady=(0, 5))

        self.btn_mini_reprint = ctk.CTkButton(f_mini_btns, text=tr("mini_reprint_last"), height=34, corner_radius=9,
                                              font=(FONT_FAMILY, 11, "bold"), fg_color="#D97706", hover_color="#B45309",
                                              text_color="#FFFFFF", command=self.reprint_last_receipt)
        self.btn_mini_reprint.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_elevate = ctk.CTkButton(f_mini_btns, text=tr("btn_full_console"), height=34, corner_radius=9,
                                         font=(FONT_FAMILY, 11, "bold"), fg_color="#DC2626", hover_color="#B91C1C",
                                         border_width=0, text_color="#FFFFFF", command=self.request_full_console)
        self.btn_elevate.pack(side="right", fill="x", expand=True, padx=(5, 0))

        self.lbl_mini_foot = ctk.CTkLabel(self.body_mini, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria", height=16,
                                         font=(FONT_FAMILY, 9, "bold"), text_color="#64748B")
        self.lbl_mini_foot.pack(anchor="center", pady=(0, 3))

        # ===== الشريط السفلي: مجموعات معنونة + شريط حالة نحيف (Pack 1) =====
        self.b_bar = ctk.CTkFrame(self, corner_radius=0, height=76)

        self._bar_captions = []  # (label, ar, en) — بتتحدث مع تغيير اللغة والثيم

        bar_groups = ctk.CTkFrame(self.b_bar, fg_color="transparent")
        bar_groups.pack(anchor="center", pady=(4, 0))

        def _mk_group(cap_ar, cap_en):
            g = ctk.CTkFrame(bar_groups, fg_color="transparent")
            g.pack(side="left", padx=(10, 0))
            cap = ctk.CTkLabel(g, text=T2(cap_ar, cap_en), height=12,
                               font=(FONT_FAMILY, 8, "bold"), text_color="#64748B")
            cap.pack(anchor="center")
            row = ctk.CTkFrame(g, fg_color="transparent")
            row.pack(anchor="center", pady=(1, 0))
            self._bar_captions.append((cap, cap_ar, cap_en))
            return row

        _BAR_BTN_H = 30
        _BAR_FONT = (FONT_FAMILY, 10, "bold")

        row_view = _mk_group("العرض", "View")
        self.btn_view_rec = ctk.CTkButton(
            row_view, width=112, height=_BAR_BTN_H, corner_radius=9, font=_BAR_FONT,
            text_color="#FFFFFF", fg_color="#2563EB", hover_color="#1D4ED8",
            command=self.open_records_viewer
        )
        self.btn_view_rec.pack(side="left", padx=2)

        # النسخة المخففة: بدل زر المشرف (التقفيل/الدفع) فيه زر واحد بيفتح سجل الأرشيف الكامل (للمشرف فقط)
        self.btn_arch_full = ctk.CTkButton(row_view, fg_color="#4F46E5", hover_color="#4338CA", width=112,
                                           height=_BAR_BTN_H, corner_radius=9, font=_BAR_FONT, text_color="#FFFFFF", command=self.open_archive_history)

        self.btn_chrome = ctk.CTkButton(row_view, fg_color="#334155", hover_color="#475569", width=104,
                                        height=_BAR_BTN_H, corner_radius=9, font=_BAR_FONT, text_color="#FFFFFF", command=self.open_chrome_browser)

        row_reports = _mk_group("التقارير", "Reports")
        self.btn_pdf_export = ctk.CTkButton(row_reports, width=96, height=_BAR_BTN_H, corner_radius=9, font=_BAR_FONT,
                                           fg_color="#334155", hover_color="#475569", text_color="#FFFFFF", command=self.export_pdf_summary)
        self.btn_pdf_export.pack(side="left", padx=2)

        self.btn_excel = ctk.CTkButton(row_reports, fg_color="#059669", hover_color="#047857", width=96,
                                       height=_BAR_BTN_H, corner_radius=9, font=_BAR_FONT, text_color="#FFFFFF", command=self.open_excel)

        row_print = _mk_group("الطباعة", "Print")
        self.btn_print_slip = ctk.CTkButton(row_print, fg_color="#D97706", hover_color="#B45309", width=100,
                                           height=_BAR_BTN_H, corner_radius=9, font=_BAR_FONT, text_color="#FFFFFF", command=self.print_slip)
        self.btn_print_slip.pack(side="left", padx=2)

        # شريط حالة نحيف: عدادات اليوم لايف + سطر الإصدار
        status_row = ctk.CTkFrame(self.b_bar, fg_color="transparent", height=18)
        status_row.pack(fill="x", padx=12, pady=(2, 3))

        self.lbl_status_count = ctk.CTkLabel(status_row, text="", height=16,
                                             font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_status_count.pack(side="left")

        self.lbl_status_sum = ctk.CTkLabel(status_row, text="", height=16,
                                           font=(FONT_FAMILY, 9, "bold"), text_color="#00FF66")
        self.lbl_status_sum.pack(side="left", padx=(12, 0))

        self.lbl_foot = ctk.CTkLabel(status_row, text=f"A2R {APP_VERSION} • {APP_OWNER} • Alexandria", height=16,
                                font=(FONT_FAMILY, 9, "bold"), text_color="#FFFFFF")
        self.lbl_foot.pack(side="right")

        self._status_count_val = 0
        self._status_total_val = 0.0
        self._render_status_bar(0, 0.0)

        self.body_full = ctk.CTkFrame(self, fg_color="transparent")

        self.card_top = ctk.CTkFrame(self.body_full, corner_radius=8, border_width=1)
        self.card_top.pack(fill="x", pady=(2, 2))

        self.lbl_folder = ctk.CTkLabel(self.card_top, height=16, font=FONT_SECTION_LBL)
        self.lbl_folder.pack(anchor="w", padx=10, pady=(4, 1))

        f_dir = ctk.CTkFrame(self.card_top, fg_color="transparent")
        f_dir.pack(fill="x", padx=10, pady=(0, 2))

        self.e_path = ctk.CTkEntry(f_dir, font=FONT_ENTRY, height=30, text_color="#FFFFFF")
        self.e_path.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.e_path.bind("<FocusOut>", lambda e: self.validate_path_live())
        attach_context_menu(self.e_path)

        self.btn_browse = ctk.CTkButton(
            f_dir, width=74, height=30, corner_radius=9, font=FONT_BTN_SUB, text_color="#FFFFFF",
            fg_color="#2563EB", hover_color="#1D4ED8", command=self.browse_folder
        )
        self.btn_browse.pack(side="left", padx=(0, 4))

        self.btn_open_f = ctk.CTkButton(
            f_dir, width=64, height=30, corner_radius=9, font=FONT_BTN_SUB, text_color="#FFFFFF",
            fg_color="#059669", hover_color="#047857", command=self.open_current_folder
        )
        self.btn_open_f.pack(side="left")

        self.lbl_d = ctk.CTkLabel(self.card_top, height=16, font=FONT_SECTION_LBL)
        self.lbl_d.pack(anchor="w", padx=10, pady=(1, 1))

        f_date = ctk.CTkFrame(self.card_top, fg_color="transparent")
        f_date.pack(fill="x", padx=10, pady=(0, 4))

        today = datetime.date.today()
        self.cb_d = ctk.CTkComboBox(f_date, values=[f"{d:02d}" for d in range(1, 32)], width=56, height=30, font=FONT_REGULAR_BOLD)
        self.cb_d.set(f"{today.day:02d}")
        self.cb_d.pack(side="left", padx=(0, 3))

        self.cb_m = ctk.CTkComboBox(f_date, values=[f"{m:02d}" for m in range(1, 13)], width=56, height=30, font=FONT_REGULAR_BOLD)
        self.cb_m.set(f"{today.month:02d}")
        self.cb_m.pack(side="left", padx=(0, 3))

        self.cb_y = ctk.CTkComboBox(f_date, values=[str(y) for y in range(today.year - 3, today.year + 3)], width=70, height=30, font=FONT_REGULAR_BOLD)
        self.cb_y.set(str(today.year))
        self.cb_y.pack(side="left", padx=(0, 6))

        self.btn_today = ctk.CTkButton(f_date, width=58, height=30, corner_radius=8, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.set_today)
        self.btn_today.pack(side="left", padx=(0, 4))

        self.btn_yesterday = ctk.CTkButton(f_date, width=68, height=30, corner_radius=8, font=FONT_BTN_SUB, text_color="#FFFFFF",
                                           fg_color="#334155", hover_color="#475569", command=self.set_yesterday)
        self.btn_yesterday.pack(side="left", padx=(0, 8))

        f_switches = ctk.CTkFrame(f_date, fg_color="transparent")
        f_switches.pack(side="right")

        self.sw_autosync = ctk.CTkSwitch(f_switches, text="", width=38, height=22, command=self.toggle_autosync)
        self.sw_autosync.pack(side="left", padx=(0, 3))
        self.lbl_sw_sync = ctk.CTkLabel(f_switches, text="", font=(FONT_FAMILY, 9, "bold"))
        self.lbl_sw_sync.pack(side="left", padx=(0, 10))

        self.sw_autoprint = ctk.CTkSwitch(f_switches, text="", width=38, height=22, command=self.toggle_autoprint)
        self.sw_autoprint.pack(side="left", padx=(0, 3))
        self.lbl_sw_print = ctk.CTkLabel(f_switches, text="", font=(FONT_FAMILY, 9, "bold"))
        self.lbl_sw_print.pack(side="left")

        if self.auto_sync_enabled: self.sw_autosync.select()
        else: self.sw_autosync.deselect()
        if self.auto_print_enabled: self.sw_autoprint.select()
        else: self.sw_autoprint.deselect()

        self.card_dash = ctk.CTkFrame(self.body_full, corner_radius=8, border_width=1)
        self.card_dash.pack(fill="x", pady=(0, 2))

        dash_grid = ctk.CTkFrame(self.card_dash, fg_color="transparent")
        dash_grid.pack(fill="x", padx=10, pady=6)

        f_kpi = ctk.CTkFrame(dash_grid, fg_color="transparent")
        f_kpi.pack(side="left", fill="both", expand=True)

        self.pill_c1 = ctk.CTkFrame(f_kpi, fg_color="#07121E", corner_radius=10, border_width=1, border_color="#1E2E42")
        self.pill_c1.pack(side="left", padx=(0, 6), fill="both", expand=True)
        self.kpi1_bar = ctk.CTkFrame(self.pill_c1, width=4, height=28, corner_radius=2, fg_color="#38BDF8")
        self.kpi1_bar.pack(side="left", fill="y", padx=(6, 6), pady=6)
        f_kpi1_txt = ctk.CTkFrame(self.pill_c1, fg_color="transparent")
        f_kpi1_txt.pack(side="left", fill="both", expand=True, pady=4)
        self.lbl_kpi1_title = ctk.CTkLabel(f_kpi1_txt, height=16, font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_kpi1_title.pack(anchor="w")
        self.lbl_cnt = ctk.CTkLabel(f_kpi1_txt, text="0", height=22, font=(FONT_FAMILY, 16, "bold"), text_color="#FFFFFF")
        self.lbl_cnt.pack(anchor="w")

        self.pill_c2 = ctk.CTkFrame(f_kpi, fg_color="#07121E", corner_radius=10, border_width=1, border_color="#1E2E42")
        self.pill_c2.pack(side="left", padx=(0, 8), fill="both", expand=True)
        self.kpi2_bar = ctk.CTkFrame(self.pill_c2, width=4, height=28, corner_radius=2, fg_color="#34D399")
        self.kpi2_bar.pack(side="left", fill="y", padx=(6, 6), pady=6)
        f_kpi2_txt = ctk.CTkFrame(self.pill_c2, fg_color="transparent")
        f_kpi2_txt.pack(side="left", fill="both", expand=True, pady=4)
        self.lbl_kpi2_title = ctk.CTkLabel(f_kpi2_txt, height=16, font=(FONT_FAMILY, 9, "bold"), text_color="#38BDF8")
        self.lbl_kpi2_title.pack(anchor="w")
        self.lbl_sum = ctk.CTkLabel(f_kpi2_txt, text="0.00 EGP", height=22, font=(FONT_FAMILY, 16, "bold"), text_color="#00FF66")
        self.lbl_sum.pack(anchor="w")

        f_pos = ctk.CTkFrame(dash_grid, fg_color="transparent")
        f_pos.pack(side="right", fill="y")

        self.lbl_pos_title = ctk.CTkLabel(f_pos, height=16, font=FONT_SECTION_LBL)
        self.lbl_pos_title.pack(anchor="w", pady=(0, 2))

        f_pos_in = ctk.CTkFrame(f_pos, fg_color="transparent")
        f_pos_in.pack(fill="x")

        vcmd = (self.register(self.validate_numeric_input), '%P')
        self.e_pos = ctk.CTkEntry(f_pos_in, placeholder_text="POS / Cash Total", width=116, height=28,
                                  justify="center", font=FONT_ENTRY, text_color="#FFFFFF",
                                  validate="key", validatecommand=vcmd)
        self.e_pos.pack(side="left", padx=(0, 5))
        self.e_pos.bind("<Return>", lambda e: self.check_pos())
        attach_context_menu(self.e_pos)

        self.btn_pos_check = ctk.CTkButton(f_pos_in, width=62, height=28, corner_radius=9, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.check_pos)
        self.btn_pos_check.pack(side="left")

        self.lbl_diff = ctk.CTkLabel(f_pos, text="", height=15, font=(FONT_FAMILY, 10, "bold"))
        self.lbl_diff.pack(anchor="w", pady=(2, 0))

        self.card_actions = ctk.CTkFrame(self.body_full, corner_radius=8, border_width=1)
        self.card_actions.pack(fill="x", pady=(0, 2))

        self.btn_run = ctk.CTkButton(self.card_actions, font=(FONT_FAMILY, 13, "bold"), height=36, corner_radius=10,
                                     text_color="#FFFFFF", command=self.start_thread)
        self.btn_run.pack(fill="x", padx=10, pady=(7, 5))

        f_prog = ctk.CTkFrame(self.card_actions, fg_color="transparent")
        f_prog.pack(fill="x", padx=10, pady=(0, 1))

        self.progress_bar = ctk.CTkProgressBar(f_prog, orientation="horizontal", height=7, corner_radius=4, progress_color="#00FF66", fg_color="#064E3B")
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.lbl_progress_pct = ctk.CTkLabel(f_prog, text="0%", height=16, font=(FONT_FAMILY, 10, "bold"), text_color="#FFFFFF", width=36)
        self.lbl_progress_pct.pack(side="right")

        self.lbl_current_file = ctk.CTkLabel(self.card_actions, text="", height=16, font=(FONT_FAMILY, 9), text_color="#8FA3B8")
        self.lbl_current_file.pack(anchor="w", padx=12, pady=(0, 3))

        f_act = ctk.CTkFrame(self.card_actions, fg_color="transparent")
        f_act.pack(fill="x", padx=10, pady=(0, 7))

        self.btn_manual = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#059669", hover_color="#047857", height=32, corner_radius=9, width=82, command=self.open_manual)
        self.btn_manual.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_summary_reopen = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#4F46E5", hover_color="#4338CA", height=32, corner_radius=9, width=82, command=self.reopen_summary_modal)
        self.btn_summary_reopen.pack(side="left", fill="x", expand=True, padx=3)

        self.btn_cash = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#FFFFFF", fg_color="#059669", hover_color="#047857", height=32, corner_radius=9, width=72, command=self.open_cash_counter)
        self.btn_cash.pack(side="left", fill="x", expand=True, padx=3)

        self.btn_archive_downloads = ctk.CTkButton(f_act, font=FONT_BTN_SUB, fg_color="#4F46E5", hover_color="#4338CA", text_color="#FFFFFF", height=32, corner_radius=9, width=78, command=self.open_downloads_archiver_dialog)
        self.btn_archive_downloads.pack(side="left", fill="x", expand=True, padx=3)

        self.btn_reset = ctk.CTkButton(f_act, font=FONT_BTN_SUB, text_color="#EF4444", fg_color="transparent",
                                       hover_color="#2A1C22", border_width=1.5, border_color="#EF4444", height=32, corner_radius=9, width=62,
                                       command=self.confirm_and_reset)
        self.btn_reset.pack(side="right", fill="x", expand=True, padx=(3, 0))
        self._install_tooltips()

    def _render_status_bar(self, count, total):
        """شريط الحالة السفلي: عدد العمليات وإجمالي المبالغ (بيتحدث لايف مع كل فحص أو مسح)."""
        self._status_count_val = count
        self._status_total_val = total
        try:
            self.lbl_status_count.configure(text=T2("العمليات", "Ops") + f": {count:,}")
            self.lbl_status_sum.configure(text=T2("الإجمالي", "Total") + f": {total:,.2f} {tr('currency')}")
        except Exception as _e:
            _log_silent("status_bar#render", _e)

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
            "btn_mini_reprint":     (lambda: T2("إعادة طباعة آخر إيصال (في حالة نفاد الورق أو انحشاره)", "Reprint the last receipt (if paper ran out or jammed)")),
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
        _save_app_prefs(theme=selected_theme)

    def apply_theme(self, name):
        t = THEMES[name]
        if ctk.get_appearance_mode().lower() != t["mode"].lower():
            ctk.set_appearance_mode(t["mode"])
        self.configure(fg_color=t["bg"])
        self.header.configure(fg_color=t["sub_card"])
        self.lbl_logo.configure(text_color=t["accent"])
        self.header_line.configure(fg_color=t["primary"])
        try:
            self.kpi1_bar.configure(fg_color=t["primary"])
            self.kpi2_bar.configure(fg_color=t["success"])
            self.btn_reset.configure(text_color=t["danger"], border_color=t["danger"],
                                     hover_color=("#2A1B22" if t["mode"] == "Dark" else "#FEE2E2"))
        except Exception as _e: _log_silent("apply_theme#bars", _e)
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
        self.lbl_sum.configure(text_color=t["success"])
        try:
            self.lbl_cnt.configure(text_color=t["text"])
            for _p in (self.pill_c1, self.pill_c2):
                _p.configure(fg_color=t["input"], border_color=t["border"], corner_radius=10)
            self.progress_bar.configure(progress_color=t["success"], fg_color=t["border"])
            self.lbl_progress_pct.configure(text_color=t["text"])
            self.lbl_current_file.configure(text_color=t["text_muted"])
            self.lbl_foot.configure(text_color=t["text_muted"])
            self.lbl_mini_desc.configure(text_color=t["success"])
            self.lbl_mini_counter.configure(text_color=t["text_muted"])
            self.lbl_mini_archive.configure(text_color=t["text_muted"])
            self.lbl_mini_foot.configure(text_color=t["text_muted"])
            for _cap, _ar, _en in getattr(self, "_bar_captions", []):
                _cap.configure(text_color=t["text_muted"])
            self.lbl_status_count.configure(text_color=t["accent"])
            self.lbl_status_sum.configure(text_color=t["success"])
            self.lbl_clock.configure(text_color=t["accent"])
            self.f_role_btn.configure(fg_color=t["card"])
            for _e in (self.e_path, self.e_pos): style_entry(_e, t)
            for _c in (self.cb_d, self.cb_m, self.cb_y, self.cb_theme): style_combo(_c, t)
            apply_tree_style(t, 28)
        except Exception as _e: log_exception("apply_theme_extras", _e)
        self.btn_run.configure(fg_color=t["primary"], hover_color=t["primary_hover"])
        self.btn_pos_check.configure(fg_color=t["primary"], hover_color=t["primary_hover"])
        self._apply_button_roles(t)

        self.update_toggle_appearance()
        self._refresh_mini_archive_label()

    def _apply_button_roles(self, t):
        """تلوين كل الأزرار بحسب دورها من الثيم الحالي بنمط عصري مسطح (بدون إطار ذهبي)."""
        for role, attrs in BUTTON_ROLES.items():
            col, hov = t.get(role), t.get(role + "_hover")
            if not col:
                continue
            for a in attrs:
                b = getattr(self, a, None)
                if b is None:
                    continue
                try:
                    _tc = t.get(role + "_text")
                    if _tc:
                        b.configure(fg_color=t.get(role + "_fg", col),
                                    hover_color=t.get(role + "_hoverbg", hov), border_width=1,
                                    border_color=t.get(role + "_border", t["border"]), text_color=_tc,
                                    text_color_disabled=t["text_muted"])
                    elif role == "secondary":
                        b.configure(fg_color=col, hover_color=hov, border_width=1, border_color=t["border"])
                    else:
                        b.configure(fg_color=col, hover_color=hov, border_width=0)
                except Exception as e:
                    log_exception("apply_button_role:" + a, e)

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
        _save_app_prefs(lang=self.current_lang)

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
        self.btn_mini_reprint.configure(text=L["mini_reprint_last"])
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
        for _cap, _ar, _en in getattr(self, "_bar_captions", []):
            _cap.configure(text=_ar if lang == "ar" else _en)
        self._render_status_bar(getattr(self, "_status_count_val", 0), getattr(self, "_status_total_val", 0.0))
        self.btn_elevate.configure(text=L["btn_full_console"])
        self.btn_back_to_mini.configure(text=L["btn_back_mini"])
        self.lbl_mini_title.configure(text=L["mini_station_title"])
        self.lbl_mini_desc.configure(text=L["mini_status_active"])
        self.lbl_mini_counter.configure(text=tr("mini_printed_count", count=self.printed_count_today))
        self.btn_fix_printer.configure(text=self._paper_btn_text())
        self.update_toggle_appearance()
        self._refresh_mini_archive_label()
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
        self._render_status_bar(0, 0.0)
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
        def _scan_dir(folder):
            """قراءة سريعة لمجلد الإيصالات بـ os.scandir (بدون glob أو استدعاءات قرص مكررة).
            ترجّع: ([(path, name, size)], set_of_crdownload_base_names)."""
            pdfs, cr_bases = [], set()
            try:
                with os.scandir(folder) as it:
                    for ent in it:
                        name = ent.name
                        nl = name.lower()
                        if nl.endswith(".pdf"):
                            try:
                                if ent.is_file(follow_symlinks=False):
                                    pdfs.append((ent.path, name, ent.stat(follow_symlinks=False).st_size))
                            except OSError:
                                pass
                        elif nl.endswith(".crdownload"):
                            cr_bases.add(nl[:-11])
            except OSError:
                pass
            return pdfs, cr_bases

        def _routine():
            # استبعاد وتسكين الملفات الموجودة قبل تشغيل البرنامج
            initial_path = self._watch_path
            last_seeded = None   # آخر مجلد اتعلّمت ملفاته "اتطبعت"
            if initial_path and os.path.isdir(initial_path):
                try:
                    pdfs, _ = _scan_dir(initial_path)
                    for _, fn, _ in pdfs:
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
                    if not p or not os.path.isdir(p): continue

                    # تصفير عدّاد المطبوعات تلقائيًا عند بداية يوم جديد مع الحفاظ على منع إعادة طباعة الملفات القديمة
                    today_d = datetime.date.today()
                    if today_d != self._printed_count_day:
                        self._printed_count_day = today_d
                        self.printed_count_today = 0
                        self.last_printed_pdf = None
                        self.run_on_main(lambda: self.lbl_mini_counter.configure(
                            text=tr("mini_printed_count", count=0)))
                        pdfs_now, _ = _scan_dir(p)
                        keep = set()
                        for _, fn, _ in pdfs_now:
                            keep.add(fn)
                            keep.add(clean_download_filename(fn))
                        self.printed_receipts_set = keep

                    if p != last_seeded:
                        # مجلد جديد اتختار: الملفات اللي فيه دلوقتي قديمة، مش بتتطبع تلقائيًا.
                        # الطباعة التلقائية بتشتغل بس على الملفات اللي تظهر بعد كده.
                        pdfs_s, _ = _scan_dir(p)
                        for _, fn, _ in pdfs_s:
                            self.printed_receipts_set.add(fn)
                            self.printed_receipts_set.add(clean_download_filename(fn))
                        last_seeded = p
                        continue
                    if not (self.auto_print_enabled or self.auto_sync_enabled): continue

                    pdf_entries, cr_bases = _scan_dir(p)

                    if self.auto_print_enabled:
                        for pdf_file, fname, fsize in pdf_entries:
                            fl = fname.lower()
                            if fl.endswith("_cropped.pdf") or fl.endswith("_summary.pdf"):
                                continue
                            if not (fl.startswith("quote_receipt_") or MANUAL_NAME_RE.match(fname)):
                                continue
                            if fname.lstrip("_") in _VOID_KEYS:
                                continue
                            clean_fn = clean_download_filename(fname)
                            if clean_fn not in self.printed_receipts_set and fname not in self.printed_receipts_set:
                                if fl not in cr_bases and fsize > 1000 and _is_pdf_ready(pdf_file):
                                    self.printed_receipts_set.add(fname)
                                    self.printed_receipts_set.add(clean_fn)
                                    self._print_queue.put(pdf_file)   # الطباعة في thread مستقل، المراقبة تكمل فورًا

                    if (self.auto_sync_enabled and not self.is_processing
                            and time.time() - _last_sync[0] >= 2):
                        _last_sync[0] = time.time()
                        try:
                            valid = [(fn, sz) for _, fn, sz in pdf_entries
                                     if not fn.lower().endswith(("_summary.pdf", "_cropped.pdf"))]
                            current_sig = f"{len(valid)}_{sum(sz for _, sz in valid)}"
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
                self.last_printed_pdf = pdf
                try: ok = self.send_to_thermal_printer_57x90(pdf)
                except Exception as e:
                    log_exception(f"print_worker:{fname}", e)
                    ok = False
                if ok:
                    today_d = datetime.date.today()
                    if today_d != self._printed_count_day:
                        self._printed_count_day = today_d
                        self.printed_count_today = 0
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

    def send_to_thermal_printer_57x90(self, pdf_file_path, is_test=False):
        """يطبع إيصال على المقاس المختار. بيرجّع True لو الطباعة اتبعتت، False لو فشلت أو الطابعة معلّقة."""
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
                is_manual_pdf = bool(MANUAL_NAME_RE.match(clean_name))
                if not is_test and clean_name.lower().startswith("quote_receipt_"):
                    temp_copy = make_print_copy(pdf_file_path)
                    if temp_copy:
                        target = temp_copy

                if not is_test and not is_manual_pdf:
                    scaled_copy = scale_pdf_to_print_width(target)
                if scaled_copy:
                    target = scaled_copy

                use_noscale = bool(is_test or is_manual_pdf or scaled_copy)
                if os.path.exists(sumatra_path):
                    cmd = [
                        sumatra_path,
                        "-print-to-default",
                        "-print-settings", print_settings_arg(scaled=use_noscale),
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
            _set_win_alpha(win, 0.0)
            self._user_archive_win = win
            win.title(f"{tr('clean_downloads')} - A2R {APP_VERSION}")
            win.resizable(False, False)
            win.configure(fg_color=t["bg"])

            ctk.CTkLabel(win, text=T2("📦 أرشفة الجهاز", "📦 Device Archive"),
                         font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"]).pack(pady=(12, 2))
            ctk.CTkLabel(win, text=T2("بتنقل إيصالات الأيام السابقة للأرشيف وتعمل إكسيل وملخص (عدد المعاملات والإجمالي) لكل يوم",
                                      "Moves previous days' receipts to the archive and builds an Excel + summary (count & total) per day"),
                         font=(FONT_FAMILY, 9), text_color=t["text"], wraplength=410, justify="center").pack(padx=16, pady=(0, 8))

            card = ctk.CTkFrame(win, fg_color=t["card"], corner_radius=8, border_width=1, border_color=t["border"])
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
            s_lbl = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 9), text_color=t["text"], wraplength=410)
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

            btn_go = ctk.CTkButton(win, text="", font=FONT_BTN_MAIN, height=38, **_ghost(t, "primary"), command=_start)
            btn_go.pack(fill="x", padx=16, pady=(4, 6))

            if _show_hist:
                btn_hist = ctk.CTkButton(win, text=T2("📚 سجل الأرشيف", "📚 Archive History"), font=FONT_BTN_MAIN, height=38,
                                         **_ghost(t, "secondary"),
                                         command=self.open_archive_history)
                btn_hist.pack(fill="x", padx=16, pady=(0, 6))

            ctk.CTkLabel(win, text=(T2("المشرف: كل الأيام بتفاصيلها • المستخدم: آخر 7 أيام للقراءة فقط",
                                       "Supervisor: all days in full • User: last 7 days, read-only") if _show_hist else
                                    T2("📚 سجل الأرشيف متاح من زر سجل الأرشيف في الشريط السفلي",
                                       "📚 Archive history is available from the Archive History button below")),
                         font=(FONT_FAMILY, 9), text_color=t["text"], wraplength=410, justify="center").pack(padx=16, pady=(0, 8))

            refresh_state()
            fit_and_center(win, self, 430, min_height=280)
        except Exception as e: log_exception("open_archive_dialog", e)

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
                self._render_status_bar(info['total_count'], info['total_sum'])
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
        self._render_status_bar(info['total_count'], info['total_sum'])
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
        _set_win_alpha(win, 0.0)
        self._arch_win, self._arch_win_admin = win, is_admin
        win.title(T2("📚 سجل الأرشيف", "📚 Archive History"))
        win.resizable(True, True)
        _sw, _sh = win.winfo_screenwidth(), win.winfo_screenheight()
        center_window_on_screen(win, LOG_WIN_W, LOG_WIN_H, show=False)
        remember_window_geometry(win, "archive_history")
        try: win.transient(self)
        except Exception as _e: _log_silent("open_archive_history#transient", _e)
        _sc = _win_scale(win)
        win.minsize(min(LOG_WIN_MIN_W, int((_sw - 48) / _sc)), min(LOG_WIN_MIN_H, int((_sh - 100) / _sc)))
        win.configure(fg_color=t["bg"])

        ALL = T2("الكل", "All")
        st = {"stats": [], "debounce": None, "iso": None, "recs": [], "recs_iso": None,
              "load_id": 0, "cache": {}, "sel_job": None}

        # ---------- شريط الحالة والأدوات ----------
        bar = ctk.CTkFrame(win, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
        bar.pack(fill="x", padx=10, pady=(8, 4))
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
            ctk.CTkButton(dlg, text=T2("▶ ابدأ", "▶ Start"), font=FONT_BTN_MAIN, height=34, **_ghost(t, "primary"), command=go).pack(fill="x", padx=16, pady=(14, 0))

        # ---------- تكبير / ملء الشاشة / تصغير ----------
        fs = {"on": False}
        def toggle_fullscreen(event=None):
            fs["on"] = not fs["on"]
            try: win.attributes("-fullscreen", fs["on"])
            except Exception as _e: _log_silent("toggle_fullscreen#1", _e)
        def exit_fullscreen(event=None):
            if fs["on"]: toggle_fullscreen()
            else: close_toplevel_gracefully(win)      # Esc تاني (أو أول مرة لو مش fullscreen) = يقفل السجل
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
            def open_chrome_ext_folder():
                if not is_admin: return
                p_ext = ensure_chrome_extension_extracted()
                if p_ext and os.path.isdir(p_ext): os.startfile(p_ext)
            more_menu.add_command(label=T2("🧩 مجلد إضافة كروم", "🧩 Chrome extension folder"), command=open_chrome_ext_folder)
            more_menu.add_separator()
            more_menu.add_command(label=T2("⛶ ملء الشاشة (F11)", "⛶ Fullscreen (F11)"), command=toggle_fullscreen)
            def show_more():
                try: more_menu.tk_popup(btn_more.winfo_rootx(), btn_more.winfo_rooty() + btn_more.winfo_height())
                finally: more_menu.grab_release()

            btn_more = ctk.CTkButton(bar, text=T2("⚙️ المزيد ▾", "⚙️ More ▾"), font=FONT_BTN_SUB, width=110, height=30,
                                     **_ghost(t, "secondary"), command=show_more)
            btn_more.pack(side="right", padx=4, pady=6)
            ctk.CTkButton(bar, text=T2("🗖 تكبير", "🗖 Zoom"), font=FONT_BTN_SUB, width=90, height=30,
                          **_ghost(t, "secondary"),
                          command=toggle_zoom).pack(side="right", padx=4, pady=6)
            ctk.CTkButton(bar, text=T2("🔄 تحديث + نسخ", "🔄 Refresh + Backup"), font=FONT_BTN_SUB, width=150, height=30,
                          **_ghost(t, "primary"),
                          command=lambda: run_maintenance(True)).pack(side="right", padx=4, pady=6)
        else:
            ctk.CTkButton(bar, text=T2("🗖 تكبير", "🗖 Zoom"), font=FONT_BTN_SUB, width=90, height=30,
                          **_ghost(t, "secondary"),
                          command=toggle_zoom).pack(side="right", padx=4, pady=6)
            rb["btn"] = ctk.CTkButton(bar, text=T2("♻️ إعادة أرشفة الكل", "♻️ Re-archive all"), font=FONT_BTN_SUB, width=160,
                                      height=30, **_ghost(t, "primary"),
                                      command=lambda: run_rearchive(None, ask=False, silent=True))
            rb["btn"].pack(side="right", padx=4, pady=6)
            ctk.CTkLabel(bar, text=T2(f"📅 عرض آخر {USER_DAYS} أيام", f"📅 Last {USER_DAYS} days"),
                         font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(side="left", padx=8)

        # ---------- ستايل الجداول ----------
        apply_tree_style(t, 28)

        def make_tree(parent, columns, headers, widths):
            fr = ctk.CTkFrame(parent, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
            fr.pack(fill="both", expand=True, padx=2, pady=(4, 2))
            tree = ttk.Treeview(fr, columns=columns, show="headings", style="A2R.Treeview")
            for c in columns:
                tree.heading(c, text=headers[c])
                tree.column(c, width=widths.get(c, 90), anchor="center")
            for kind, (bg, fg) in TAG_COLORS[t["mode"]].items():
                tree.tag_configure(kind, background=bg, foreground=fg)
            vsb = ttk.Scrollbar(fr, orient="vertical", command=tree.yview)
            vsb.pack(side="right", fill="y", padx=2, pady=2)
            hsb = ttk.Scrollbar(fr, orient="horizontal", command=tree.xview)
            hsb.pack(side="bottom", fill="x", padx=2, pady=2)
            tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
            return tree

        tv = ctk.CTkTabview(win, fg_color=t["bg"], segmented_button_fg_color=t["card"],
                            segmented_button_selected_color=t["primary"], segmented_button_selected_hover_color=t["primary_hover"],
                            segmented_button_unselected_color=t["card"], segmented_button_unselected_hover_color=t["border"],
                            text_color="#FFFFFF")
        tv.pack(fill="both", expand=True, padx=10, pady=(0, 8))
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
        ctk.CTkButton(f1, text="✖", width=34, height=28, font=FONT_BTN_SUB, **_ghost(t, "secondary"), command=clear_filters).pack(side="left", padx=4)

        day_cols = ("date", "ops", "total")
        day_hdr = {"date": T2("التاريخ", "Date"), "ops": T2("المعاملات", "Tx"), "total": T2("إجمالي المبلغ", "Total")}
        day_tree = make_tree(left, day_cols, day_hdr, {"date": 120, "ops": 80, "total": 150})
        sum_lbl = ctk.CTkLabel(left, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"], justify="left")
        sum_lbl.pack(anchor="w", padx=8, pady=(2, 0))
        ctk.CTkLabel(left, text=T2("🟥 يوم فيه مكرر    🟨 يوم فيه ناقص", "🟥 has duplicates   🟨 has incomplete"),
                     font=(FONT_FAMILY, 9, "bold"), text_color=t["text"]).pack(anchor="w", padx=8, pady=(0, 2))

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
                tag = "dup" if s["dup"] else ("missing" if s["missing"] else ("odd" if len(day_tree.get_children()) % 2 else ""))
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
        hdr = ctk.CTkFrame(right, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["accent"])
        hdr.pack(fill="x", pady=(2, 0))
        day_title = ctk.CTkLabel(hdr, text=T2("👈 اختار يوم من القائمة لعرض معاملاته", "👈 Pick a day from the list"),
                                 font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"])
        day_title.pack(side="left", padx=14, pady=8)

        cards = ctk.CTkFrame(right, fg_color="transparent")
        cards.pack(fill="x", pady=(6, 2))
        card_lbls = {}
        def mk_card(key, title, color):
            f = ctk.CTkFrame(cards, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
            f.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkFrame(f, width=3, height=26, corner_radius=2, fg_color=color).pack(side="left", fill="y", padx=(6, 4), pady=4)
            inner = ctk.CTkFrame(f, fg_color="transparent")
            inner.pack(side="left", fill="both", expand=True, pady=2)
            ctk.CTkLabel(inner, text=title, font=(FONT_FAMILY, 9, "bold"), text_color=t["text"]).pack(anchor="w")
            lb = ctk.CTkLabel(inner, text="-", font=(FONT_FAMILY, 15, "bold"), text_color=color)
            lb.pack(anchor="w")
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
            make_themed_button(btn_row, t, kind, text=text, font=FONT_BTN_SUB, corner_radius=8,
                               width=w, height=32, command=cmd).pack(side="left", padx=(0, 6), pady=2)
        if is_admin: _b(T2("📊 إكسيل اليوم", "📊 Day Excel"), "success", d_excel, 125)
        _b(T2("📄 إيصال السمري", "📄 Summary receipt"), "primary", d_summary, 135)
        if is_admin:
            _b(T2("📂 فولدر اليوم", "📂 Day folder"), "quiet", d_folder, 115)
            _b(T2("♻️ إعادة أرشفة اليوم", "♻️ Re-archive day"), "danger",
               lambda: run_rearchive([st["iso"]] if st["iso"] else []), 145)

        # ---------- بحث وفلتر معاملات اليوم ----------
        search_row = ctk.CTkFrame(right, corner_radius=8, height=46, fg_color=t["card"], border_width=1, border_color=t["border"])
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
        tree_frame = ctk.CTkFrame(right, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
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

        ctk.CTkLabel(right, text=T2("🟥 مكرر   🟨 ناقص   🟧 وحدة أخرى   🟪 ملغي (مخصوم)   •   دبل كليك لفتح الإيصال",
                                    "🟥 Duplicate   🟨 Incomplete   🟧 Other unit   🟪 Void   •   double-click to open receipt"),
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
                tag = r["kind"] if r["kind"] in ("dup", "void", "missing", "wrong", "manual") else ("odd" if shown % 2 else "")
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

        # ================= تبويب البحث العام المتقدم (FTS5 + فلاتر) =================
        f2_card = ctk.CTkFrame(tab_search, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
        f2_card.pack(fill="x", pady=(2, 4))

        f2 = ctk.CTkFrame(f2_card, fg_color="transparent")
        f2.pack(fill="x", padx=10, pady=(8, 4))
        s_entry = ctk.CTkEntry(
            f2, placeholder_text=T2("اسم / لوحة / شاسيه / موتور / مبلغ أو نطاق (500-1000)...",
                                    "Name / plate / chassis / motor / amount or range (500-1000)..."),
            width=400, height=32, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"]
        )
        s_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        attach_context_menu(s_entry)

        ALL_S_ST = T2("كل الحالات", "All statuses")
        s_status_map = {
            ALL_S_ST: "all",
            T2("سليم", "OK"): "ok",
            T2("يدوي", "Manual"): "manual",
            T2("ملغي", "Void"): "void",
        }
        cb_s_status = ctk.CTkComboBox(f2, values=list(s_status_map.keys()), width=125, height=32, font=FONT_ENTRY,
                                      state="readonly", command=lambda v: do_search())
        cb_s_status.set(ALL_S_ST)
        style_combo(cb_s_status, t)
        cb_s_status.pack(side="left", padx=(0, 6))

        def clear_search_filters():
            s_entry.delete(0, "end")
            e_s_from.delete(0, "end")
            e_s_to.delete(0, "end")
            cb_s_unit.set(ALL_U)
            cb_s_status.set(ALL_S_ST)
            inc_void.select()
            do_search()

        ctk.CTkButton(f2, text=T2("✖ مسح", "✖ Clear"), width=74, height=32, corner_radius=8, font=FONT_BTN_SUB,
                      **_ghost(t, "secondary"),
                      command=clear_search_filters).pack(side="left")

        f2b = ctk.CTkFrame(f2_card, fg_color="transparent")
        f2b.pack(fill="x", padx=10, pady=(0, 8))

        ALL_U = T2("كل الوحدات", "All units")
        _u_vals = [ALL_U] + archive_units_list(cutoff_iso)
        cb_s_unit = SafeArabicComboBox(f2b, values=_u_vals, width=185, height=28, font=FONT_ENTRY,
                                       state="readonly", command=lambda v: do_search())
        cb_s_unit.set(ALL_U)
        style_combo(cb_s_unit, t)
        cb_s_unit.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(f2b, text=T2("من:", "From:"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left", padx=(0, 3))
        e_s_from = ctk.CTkEntry(f2b, placeholder_text="DD-MM-YYYY", width=105, height=28, font=FONT_ENTRY,
                                text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        e_s_from.pack(side="left", padx=(0, 8))
        attach_context_menu(e_s_from)

        ctk.CTkLabel(f2b, text=T2("إلى:", "To:"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left", padx=(0, 3))
        e_s_to = ctk.CTkEntry(f2b, placeholder_text="DD-MM-YYYY", width=105, height=28, font=FONT_ENTRY,
                              text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        e_s_to.pack(side="left", padx=(0, 10))
        attach_context_menu(e_s_to)

        inc_void = ctk.CTkCheckBox(f2b, text=T2("إظهار الملغي", "Include void"), font=FONT_SECTION_LBL, text_color=t["text"])
        inc_void.select()
        inc_void.pack(side="left", padx=(0, 8))

        s_count = ctk.CTkLabel(f2b, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        s_count.pack(side="right", padx=4)

        s_cols = ("date", "unit", "plate", "insured", "amount", "chassis", "time", "status", "file")
        s_hdr = {"date": T2("يوم الأرشيف", "Archive day"), "unit": T2("الوحدة", "Unit"), "plate": T2("اللوحة", "Plate"),
                 "insured": T2("المؤمن له", "Insured"), "amount": T2("المبلغ", "Amount"),
                 "chassis": T2("الشاسيه", "Chassis"), "time": T2("الوقت", "Time"),
                 "status": T2("الحالة", "Status"), "file": T2("الملف", "File")}
        s_tree = make_tree(tab_search, s_cols, s_hdr,
                           {"date": 98, "unit": 135, "plate": 100, "insured": 175, "amount": 88,
                            "chassis": 130, "time": 118, "status": 76, "file": 165})
        s_paths = {}
        s_days = {}

        def do_search(*_):
            q = s_entry.get().strip()
            d_from = parse_flex_date(e_s_from.get())
            d_to = parse_flex_date(e_s_to.get())
            min_d = d_from.isoformat() if d_from else ""
            if cutoff_iso and (not min_d or min_d < cutoff_iso):
                min_d = cutoff_iso
            max_d = d_to.isoformat() if d_to else ""
            u_sel = cb_s_unit.get()
            u_filt = "" if (not u_sel or u_sel == ALL_U) else u_sel
            st_filt = s_status_map.get(cb_s_status.get(), "all")

            s_tree.delete(*s_tree.get_children())
            s_paths.clear()
            s_days.clear()
            has_user_filter = bool(d_from or d_to or u_filt or st_filt != "all")
            if not q and not has_user_filter:
                s_count.configure(text="")
                return
            try:
                rows = archive_search(
                    q, include_void=bool(inc_void.get()), min_day=min_d, max_day=max_d,
                    unit_filter=u_filt, status_filter=st_filt
                )
            except Exception as e:
                log_exception("archive_search", e)
                rows = []
            tot = 0.0
            for i, row in enumerate(rows):
                path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void = row[:10]
                ch = row[10] if len(row) > 10 else "-"
                y, m, d = day.split("-")
                if is_void: status, tag = T2("ملغي", "Void"), "void"
                elif is_manual: status, tag = T2("يدوي", "Manual"), "manual"
                else: status, tag = T2("سليم", "OK"), ("odd" if i % 2 else "")
                if not is_void: tot += amount
                iid = str(i)
                s_paths[iid] = path
                s_days[iid] = day
                s_tree.insert("", "end", iid=iid, tags=(tag,) if tag else (),
                              values=(f"{d}-{m}-{y}", unit, plate, insured, f"{amount:,.2f}", ch, rtime, status, fname))
            s_count.configure(text=T2(f"النتائج: {len(rows):,}  |  الإجمالي (بدون الملغي): {tot:,.2f}",
                                      f"Results: {len(rows):,}  |  Total (excl. void): {tot:,.2f}"))

        def _debounced(*_):
            if st["debounce"]:
                try: win.after_cancel(st["debounce"])
                except Exception as _e: _log_silent("_debounced#1", _e)
            st["debounce"] = win.after(220, do_search)
        s_entry.bind("<KeyRelease>", _debounced)
        s_entry.bind("<Return>", do_search)
        e_s_from.bind("<KeyRelease>", _debounced)
        e_s_from.bind("<Return>", do_search)
        e_s_to.bind("<KeyRelease>", _debounced)
        e_s_to.bind("<Return>", do_search)
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

        # تشغيل: اعرض اللي في الفهرس فورًا، وبعدين ارفع النافذة للأمام وحدّث في الخلفية
        load_days()                       # اعرض الفهرس الموجود فورًا
        bring_window_to_front(win, focus_widget=day_q, delay=10)
        run_maintenance(light=True)       # فهرسة بس؛ النسخ الاحتياطي والإكسيلات بزرار "تحديث + نسخ" أو في الخلفية

    def open_records_viewer(self):
        if not self.last_detailed_records:
            messagebox.showinfo("Notice", tr("no_records_yet"))
            return
        self._records_window(self.last_detailed_records, live=True)

    def _records_window(self, records, live=True, day_iso=None, day_folder=None):
        """نافذة عرض السجلات: live=True لسجلات اليوم الحالي (فيها إلغاء/استرجاع)، live=False لأي يوم من الأرشيف."""
        if live:
            old_r = getattr(self, "_records_win", None)
            try:
                if old_r is not None and old_r.winfo_exists():
                    old_r.destroy()
            except Exception as _e: _log_silent("_records_window#old", _e)
        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        _set_win_alpha(win, 0.0)
        if live:
            self._records_win = win
        day_txt = ""
        if day_iso:
            yy, mm, dd_ = day_iso.split("-")
            day_txt = f"{dd_}-{mm}-{yy}"
        win.title(tr("records_viewer_title") + (f" — {day_txt}" if day_txt else ""))
        win.resizable(True, True)
        _sw, _sh = win.winfo_screenwidth(), win.winfo_screenheight()
        center_window_on_screen(win, LOG_WIN_W, LOG_WIN_H, show=False)
        remember_window_geometry(win, "records_viewer")
        try: win.transient(self)
        except Exception as _e: _log_silent("_records_window#transient", _e)
        _sc = _win_scale(win)
        win.minsize(min(LOG_WIN_MIN_W, int((_sw - 48) / _sc)), min(LOG_WIN_MIN_H, int((_sh - 100) / _sc)))
        win.configure(fg_color=t["bg"])

        if not live:
            hdr = ctk.CTkFrame(win, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["accent"])
            hdr.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(hdr, text=T2(f"📅 أرشيف يوم {day_txt}", f"📅 Archive day {day_txt}"),
                         font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"]).pack(side="left", padx=14, pady=8)

        # ---------- كروت الإحصائيات ----------
        cards = ctk.CTkFrame(win, fg_color="transparent")
        cards.pack(fill="x", padx=8, pady=(6, 2))
        card_lbls = {}

        def mk_card(key, title, color):
            f = ctk.CTkFrame(cards, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
            f.pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkFrame(f, width=3, height=26, corner_radius=2, fg_color=color).pack(side="left", fill="y", padx=(6, 4), pady=4)
            inner = ctk.CTkFrame(f, fg_color="transparent")
            inner.pack(side="left", fill="both", expand=True, pady=2)
            ctk.CTkLabel(inner, text=title, font=(FONT_FAMILY, 9, "bold"), text_color=t["text"]).pack(anchor="w")
            lb = ctk.CTkLabel(inner, text="0", font=(FONT_FAMILY, 15, "bold"), text_color=color)
            lb.pack(anchor="w")
            card_lbls[key] = lb

        mk_card("total", T2("إجمالي المبلغ (الصافي)", "Net total"), t["success"])
        mk_card("count", T2("عدد المعاملات", "Transactions"), t["accent"])
        mk_card("shown", T2("صافي المعروض", "Shown total"), t["text"])
        mk_card("void", T2("ملغي", "Void"), t["danger"])
        mk_card("dup", T2("مكرر", "Duplicates"), t["warning"])

        # ---------- البحث والفلاتر ----------
        search_row = ctk.CTkFrame(win, corner_radius=8, height=52, fg_color=t["card"], border_width=1, border_color=t["border"])
        search_row.pack(fill="x", padx=10, pady=(4, 2))

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
        btn_row.pack(fill="x", padx=10, pady=(0, 2))

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
            make_themed_button(btn_row, t, kind, text=text, font=FONT_BTN_SUB, corner_radius=8,
                               width=w, height=30, command=cmd).pack(side="left", padx=(0, 6), pady=2)

        _b(tr("open_pdf_btn"), "primary", open_selected)
        _b(tr("btn_reprint"), "warn", reprint_selected, 105)
        _b(T2("📂 فتح الفولدر", "📂 Open folder"), "quiet", open_folder, 125)
        if live:
            _b(tr("btn_void_sel"), "danger", cancel_selected, 110)
            _b(tr("btn_restore_sel"), "success", restore_selected_void)
        else:
            _b(T2("📄 ملخص اليوم", "📄 Day summary"), "tool", open_day_summary, 125)
            _b(T2("📊 إكسيل اليوم", "📊 Day Excel"), "success", export_day_excel, 125)

        ctk.CTkLabel(win, text=T2("🟥 مكرر   🟨 ناقص   🟧 وحدة أخرى   🟪 ملغي (مخصوم)   •   دبل كليك لفتح الإيصال",
                                  "🟥 Duplicate   🟨 Incomplete   🟧 Other unit   🟪 Void   •   double-click to open receipt"),
                     font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(anchor="w", padx=16)

        tree_frame = ctk.CTkFrame(win, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))

        columns = ("idx", "unit", "plate", "insured", "amount", "time", "make", "model", "chassis", "motor", "period", "file", "status")
        headers = {
            "idx": tr("col_idx"), "unit": tr("col_unit"), "plate": tr("col_plate"),
            "insured": tr("col_insured"), "amount": tr("col_amount"), "time": tr("col_time"),
            "make": tr("col_make"), "model": tr("col_model"), "chassis": tr("col_chassis"),
            "motor": tr("col_motor"), "period": tr("col_period"), "file": tr("col_file"), "status": tr("col_status")
        }

        apply_tree_style(t, 30)

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
                tag = r["kind"] if r["kind"] in ("dup", "void", "missing", "wrong", "manual") else ("odd" if shown % 2 else "")
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
        bring_window_to_front(win, focus_widget=search_entry, delay=10)

    def show_custom_summary(self, unit_display_name, total_sum, total_cnt, pdf_count, manual_count, date_label, duplicates=0, wrong=0, missing=0):
        old = getattr(self, "_summary_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.destroy()
        except Exception as _e: _log_silent("show_custom_summary#old", _e)

        t = THEMES[self.current_theme_name]
        modal = ctk.CTkToplevel(self)
        _set_win_alpha(modal, 0.0)
        self._summary_win = modal
        modal.title(tr("summary_title"))
        modal.resizable(False, False)
        set_window_icon_safe(modal)
        modal.configure(fg_color=t["bg"])

        hdr = ctk.CTkFrame(modal, corner_radius=0, height=44, fg_color=t["sub_card"])
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=f"📊  {tr('summary_title')}", font=(FONT_FAMILY, 13, "bold"), text_color=t["accent"]).pack(side="left", padx=14, pady=8)
        ctk.CTkFrame(modal, height=2, corner_radius=0, fg_color=t["primary"]).pack(fill="x")

        card_box = ctk.CTkFrame(modal, corner_radius=14, fg_color=t["card"], border_width=1, border_color=t["border"])
        card_box.pack(fill="both", expand=True, padx=14, pady=(12, 8))

        row_u = ctk.CTkFrame(card_box, fg_color="transparent")
        row_u.pack(fill="x", padx=14, pady=(10, 6))
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

        cb_unit = SafeArabicComboBox(row_u, values=clean_opts, width=215, height=32, font=FONT_REGULAR_BOLD,
                                     command=_unit_changed, state="readonly")
        style_combo(cb_unit, t)
        cb_unit.set(_sel_unit)
        cb_unit.pack(side="right")
        _unit_changed(_sel_unit)

        ctk.CTkFrame(card_box, height=1, fg_color=t["border"]).pack(fill="x", padx=14, pady=(2, 6))

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

        for lbl_t, val_t, val_c, val_sz in details:
            row = ctk.CTkFrame(card_box, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(row, text=lbl_t, font=(FONT_FAMILY, 11, "bold"), text_color=t["text"]).pack(side="left")
            ctk.CTkLabel(row, text=val_t, font=(FONT_FAMILY, val_sz, "bold"), text_color=val_c).pack(side="right")

        tot_box = ctk.CTkFrame(card_box, corner_radius=10, fg_color=t["input"], border_width=1, border_color=t["border"])
        tot_box.pack(fill="x", padx=14, pady=(10, 12))
        ctk.CTkFrame(tot_box, width=4, height=28, corner_radius=2, fg_color=t["success"]).pack(side="left", fill="y", padx=(6, 8), pady=6)
        ctk.CTkLabel(tot_box, text=tr("total_amt_lbl"), font=(FONT_FAMILY, 12, "bold"), text_color=t["text"]).pack(side="left", pady=8)
        ctk.CTkLabel(tot_box, text=f"{total_sum:,.2f} {tr('currency')}", font=(FONT_FAMILY, 17, "bold"),
                     text_color=t["success"]).pack(side="right", padx=12, pady=8)

        b_bar = ctk.CTkFrame(modal, fg_color="transparent")
        b_bar.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(b_bar, text=T2("إغلاق", "Close"), width=80, height=34, corner_radius=9, font=FONT_BTN_SUB,
                      **_ghost(t, "secondary"),
                      command=modal.destroy).pack(side="right", padx=(6, 0))

        ctk.CTkButton(b_bar, text=tr("export_pdf"), width=110, height=34, corner_radius=9, font=FONT_BTN_SUB,
                      **_ghost(t, "primary"),
                      command=lambda: self.export_pdf_summary(parent=modal)).pack(side="right", padx=6)

        if self.is_supervisor:
            ctk.CTkButton(b_bar, text=tr("open_excel"), width=110, height=34, corner_radius=9, font=FONT_BTN_SUB,
                          fg_color=t["success_btn"], hover_color=t["success_btn_hover"], text_color="#FFFFFF",
                          command=lambda: [modal.destroy(), self.open_excel()]).pack(side="right")

        modal.update_idletasks()
        _sc = _win_scale(modal)
        _rh = max(340, int(modal.winfo_reqheight() / _sc) + 8)
        center_window_relative(modal, self, 420, _rh)

    def reopen_summary_modal(self):
        if not self.last_summary_info:
            messagebox.showinfo("Notice", tr("no_summary_yet"))
            return
        info = self.last_summary_info
        self.show_custom_summary(info["unit"], info["total_sum"], info["total_count"],
                                 info["pdf_count"], info["manual_count"], info["date_label"], info["duplicates"],
                                 info.get("wrong_count", 0), info.get("missing_count", 0))

    def open_manual(self):
        old = getattr(self, "_manual_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift(); old.focus_force(); return
        except Exception as _e: _log_silent("open_manual#exists", _e)

        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        _set_win_alpha(win, 0.0)
        self._manual_win = win
        win.title(tr("manual_win_title"))
        win.resizable(False, False)
        win.configure(fg_color=t["bg"])

        ctk.CTkFrame(win, height=3, corner_radius=0, fg_color=t["success_btn"]).pack(fill="x")
        card = ctk.CTkFrame(win, corner_radius=14, fg_color=t["card"], border_width=1, border_color=t["border"])
        card.pack(fill="both", expand=True, padx=14, pady=(12, 8))

        ctk.CTkLabel(card, text=tr("manual_amt_lbl"), font=FONT_SECTION_LBL, text_color=t["warning"]).pack(anchor="w", padx=14, pady=(12, 2))
        e_a = ctk.CTkEntry(card, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"], height=34)
        e_a.pack(fill="x", padx=14)
        attach_context_menu(e_a)

        ctk.CTkLabel(card, text=tr("manual_name_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=14, pady=(8, 2))
        e_name = ctk.CTkEntry(card, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"], height=34)
        e_name.pack(fill="x", padx=14)
        attach_context_menu(e_name)

        ctk.CTkLabel(card, text=tr("manual_plate_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=14, pady=(8, 2))
        e_p = ctk.CTkEntry(card, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"], height=34)
        e_p.pack(fill="x", padx=14)
        attach_context_menu(e_p)

        ctk.CTkLabel(card, text=tr("manual_unit_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=14, pady=(8, 2))
        cb_u = SafeArabicComboBox(card, values=[""] + UNITS_LIST, font=FONT_REGULAR_BOLD, height=34)
        style_combo(cb_u, t)
        cb_u.set("")
        cb_u.pack(fill="x", padx=14, pady=(0, 12))
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

        for _ent in (e_a, e_name, e_p):
            _ent.bind("<Return>", save)
        f_btns = ctk.CTkFrame(win, fg_color="transparent")
        f_btns.pack(fill="x", padx=14, pady=(0, 12))
        btn_gen = ctk.CTkButton(f_btns, text=tr("manual_generate_btn"), font=FONT_BTN_MAIN,
                                fg_color=t["success_btn"], hover_color=t["success_btn_hover"],
                                text_color="#FFFFFF", height=38, corner_radius=10, command=save)
        btn_gen.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(f_btns, text=T2("إلغاء", "Cancel"), font=FONT_BTN_SUB, width=82, height=38, corner_radius=10,
                      **_ghost(t, "secondary"),
                      command=win.destroy).pack(side="right")
        fit_and_center(win, self, 370, min_height=320, focus_widget=e_a)

    def print_slip(self):
        old = getattr(self, "_slip_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift(); old.focus_force(); return
        except Exception as _e: _log_silent("print_slip#exists", _e)

        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        _set_win_alpha(win, 0.0)
        self._slip_win = win
        win.title(tr("slip_dialog_title"))
        win.resizable(False, False)
        win.configure(fg_color=t["bg"])

        ctk.CTkFrame(win, height=3, corner_radius=0, fg_color=t["warn_btn"]).pack(fill="x")
        card = ctk.CTkFrame(win, corner_radius=14, fg_color=t["card"], border_width=1, border_color=t["border"])
        card.pack(fill="both", expand=True, padx=14, pady=(12, 8))

        ctk.CTkLabel(card, text=tr("slip_name_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=14, pady=(12, 2))
        cb_employee = SafeArabicComboBox(card, values=[""] + EMPLOYEES_LIST, font=FONT_REGULAR_BOLD, height=34)
        style_combo(cb_employee, t)
        cb_employee.set("")
        cb_employee.pack(fill="x", padx=14)
        attach_context_menu(cb_employee)

        ctk.CTkLabel(card, text=tr("slip_unit_lbl"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=14, pady=(8, 2))
        cb_u = SafeArabicComboBox(card, values=[""] + UNITS_LIST, font=FONT_REGULAR_BOLD, height=34)
        style_combo(cb_u, t)
        cb_u.set("")
        cb_u.pack(fill="x", padx=14)
        attach_context_menu(cb_u)

        tid_pill = ctk.CTkFrame(card, corner_radius=8, fg_color=t["input"], border_width=1, border_color=t["border"])
        tid_pill.pack(fill="x", padx=14, pady=(10, 12))
        lbl_tid = ctk.CTkLabel(tid_pill, text=T2("رقم الماكينة: —", "Terminal ID: —"),
                               font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        lbl_tid.pack(pady=6)

        def _update_tid(*_):
            tid = UNIT_TERMINALS.get(cb_u.get().strip(), "")
            lbl_tid.configure(text=f"Terminal ID: {tid}" if tid else T2("رقم الماكينة: —", "Terminal ID: —"))

        cb_u._user_command = lambda raw: _update_tid()
        cb_u.bind("<KeyRelease>", _update_tid)

        def do_p(event=None):
            emp_val = cb_employee.get().strip()
            unit_val = cb_u.get().strip()
            tid_val = UNIT_TERMINALS.get(unit_val, "")
            date_val = datetime.date.today().strftime('%d/%m/%Y')
            win.destroy()

            def _print_bg():
                try:
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
                except Exception as e:
                    log_exception("print_slip_bg", e)

            threading.Thread(target=_print_bg, daemon=True).start()

        cb_employee.bind("<Return>", do_p)
        f_btns = ctk.CTkFrame(win, fg_color="transparent")
        f_btns.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(f_btns, text=tr("slip_btn_print"), font=FONT_BTN_MAIN, height=36, corner_radius=10,
                      fg_color=t["warn_btn"], hover_color=t["warn_btn_hover"], text_color="#FFFFFF",
                      command=do_p).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(f_btns, text=T2("إلغاء", "Cancel"), font=FONT_BTN_SUB, width=80, height=36, corner_radius=10,
                      **_ghost(t, "secondary"),
                      command=win.destroy).pack(side="right")
        fit_and_center(win, self, 355, min_height=260, focus_widget=cb_employee)

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
                     font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", padx=16, pady=(14, 4))
        cb = SafeArabicComboBox(win, values=UNITS_LIST, font=FONT_REGULAR_BOLD, height=34, state="readonly")
        style_combo(cb, t)
        cb.set("")
        cb.pack(fill="x", padx=16)
        lbl_tid = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        lbl_tid.pack(anchor="w", padx=16, pady=(8, 0))
        msg = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 10, "bold"), text_color=t["danger"])
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
                      **_ghost(t, "primary"),
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
        old = getattr(self, "_cash_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift(); old.focus_force(); return
        except Exception as _e: _log_silent("open_cash_counter#exists", _e)

        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        _set_win_alpha(win, 0.0)
        self._cash_win = win
        win.title(tr("cash_win_title"))
        win.resizable(False, False)
        win.configure(fg_color=t["bg"])

        ctk.CTkFrame(win, height=3, corner_radius=0, fg_color=t["success_btn"]).pack(fill="x")
        hdr = ctk.CTkFrame(win, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(hdr, text=tr("cash_hdr"), font=(FONT_FAMILY, 15, "bold"), text_color=t["accent"]).pack(side="left")
        if self.system_total_sum > 0:
            sys_badge = ctk.CTkFrame(hdr, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
            sys_badge.pack(side="right")
            ctk.CTkLabel(sys_badge, text=T2(f"السيستم: {self.system_total_sum:,.2f}", f"Sys: {self.system_total_sum:,.2f}"),
                         font=(FONT_FAMILY, 10, "bold"), text_color=t["success"], padx=8, pady=3).pack()

        f_quick = ctk.CTkFrame(win, corner_radius=14, fg_color=t["card"], border_width=1, border_color=t["border"])
        f_quick.pack(fill="x", padx=16, pady=(4, 8))

        r_c = ctk.CTkFrame(f_quick, fg_color="transparent")
        r_c.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(r_c, text=tr("cash_manual_lbl"), width=165, anchor="w", font=(FONT_FAMILY, 11, "bold"), text_color=t["warning"]).pack(side="left")
        e_manual_cash = ctk.CTkEntry(r_c, width=140, height=32, justify="center", font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        e_manual_cash.pack(side="right")
        attach_context_menu(e_manual_cash)

        r_p = ctk.CTkFrame(f_quick, fg_color="transparent")
        r_p.pack(fill="x", padx=12, pady=(4, 8))
        ctk.CTkLabel(r_p, text=tr("cash_pos_lbl"), width=165, anchor="w", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"]).pack(side="left")
        e_pos_in = ctk.CTkEntry(r_p, width=140, height=32, justify="center", font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        e_pos_in.pack(side="right")
        attach_context_menu(e_pos_in)

        frame_box = ctk.CTkFrame(win, corner_radius=14, fg_color=t["card"], border_width=1, border_color=t["border"])
        frame_box.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        denoms = [200, 100, 50, 20, 10, 5, 1]
        entries = {}
        sub_lbls = {}

        sum_card = ctk.CTkFrame(win, corner_radius=8, fg_color=t["card"], border_width=1, border_color=t["border"])
        sum_card.pack(fill="x", padx=16, pady=(0, 8))
        lbl_tot_cash = ctk.CTkLabel(sum_card, text=tr("cash_tot_lbl", sum=0), font=(FONT_FAMILY, 11, "bold"), text_color=t["success"])
        lbl_combined_total = ctk.CTkLabel(sum_card, text=tr("cash_comb_lbl", sum=0), font=(FONT_FAMILY, 13, "bold"), text_color=t["text"])
        lbl_diff_sys = ctk.CTkLabel(sum_card, text="", font=(FONT_FAMILY, 11, "bold"))
        current_calculated = [0.0, 0.0]

        def recalc(*_):
            c_sum = 0.0
            for d, ent in entries.items():
                v = ent.get().strip()
                sub = int(v) * d if v.isdigit() else 0
                c_sum += sub
                sub_lbls[d].configure(text=f"= {sub:,}" if sub else "= 0",
                                      text_color=t["success"] if sub else t["text_muted"])

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

        for idx_d, d in enumerate(denoms):
            r = ctk.CTkFrame(frame_box, fg_color="transparent")
            r.pack(fill="x", padx=12, pady=(8 if idx_d == 0 else 2, 8 if idx_d == len(denoms) - 1 else 2))
            ctk.CTkLabel(r, text=tr("cash_denom_lbl", d=d), width=95, anchor="w", font=(FONT_FAMILY, 11, "bold"), text_color=t["text"]).pack(side="left")
            lbl_s = ctk.CTkLabel(r, text="= 0", width=95, anchor="e", font=(FONT_FAMILY, 10, "bold"), text_color=t["text"])
            lbl_s.pack(side="right", padx=(6, 0))
            sub_lbls[d] = lbl_s
            e = ctk.CTkEntry(r, width=90, height=28, justify="center", font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
            e.pack(side="right")
            e.bind("<KeyRelease>", recalc)
            attach_context_menu(e)
            entries[d] = e

        lbl_tot_cash.pack(pady=(8, 1))
        lbl_combined_total.pack(pady=(1, 1))
        lbl_diff_sys.pack(pady=(1, 8))

        def clear_cash():
            e_manual_cash.delete(0, "end")
            e_pos_in.delete(0, "end")
            for ent in entries.values():
                ent.delete(0, "end")
            recalc()
            e_manual_cash.focus_set()

        def apply_and_close(event=None):
            if current_calculated[1] > 0:
                self.e_pos.delete(0, 'end')
                self.e_pos.insert(0, f"{current_calculated[1]:.2f}")
                self.check_pos()
            win.destroy()

        f_btns = ctk.CTkFrame(win, fg_color="transparent")
        f_btns.pack(fill="x", padx=16, pady=(0, 12))
        btn_apply = ctk.CTkButton(f_btns, text=tr("cash_apply_btn"), font=FONT_BTN_MAIN, corner_radius=10,
                                  fg_color=t["success_btn"], hover_color=t["success_btn_hover"], text_color="#FFFFFF",
                                  height=38, command=apply_and_close)
        btn_apply.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(f_btns, text=T2("تصفير", "Reset"), font=FONT_BTN_SUB, width=80, height=38, corner_radius=10,
                      **_ghost(t, "secondary"),
                      command=clear_cash).pack(side="right")
        win.bind("<Return>", apply_and_close)
        fit_and_center(win, self, 405, min_height=470, focus_widget=e_manual_cash)

if __name__ == "__main__":
    app = CustomTkinterApp()
    app.mainloop()
