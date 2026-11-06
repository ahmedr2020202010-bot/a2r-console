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

APP_VERSION = "v4.30.0"
APP_OWNER = "Ahmed Ramadan"

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
            except Exception:
                pass

    _apply()
    try:
        # customtkinter يعيد وضع أيقونته الافتراضية بعد لحظات، فنعيد تطبيق أيقونتنا
        window.after(300, _apply)
        window.after(1000, _apply)
    except Exception:
        pass
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
    except Exception:
        pass
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
MANUAL_NAME_RE = re.compile(r"^[_]?\d+(?:\.\d{2})?_\d{6}\.pdf$", re.IGNORECASE)

SOUND_MUTED = True

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def log_exception(context, exc):
    try: logging.error(f"[{context}] {exc}")
    except: pass

def init_local_database():
    try:
        conn = sqlite3.connect(DB_FILE)
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
        conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("INSERT OR REPLACE INTO voids (file_key, amount, plate, reason, voided_at, voided_by) VALUES (?,?,?,?,?,?)",
                     (file_key, float(amount), plate or "-", reason or "", at, by))
        conn.commit()
    finally:
        conn.close()
    _VOID_KEYS[file_key] = {"reason": reason or "", "at": at, "by": by}

def remove_void(file_key):
    conn = sqlite3.connect(DB_FILE)
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
        "manual": "➕ Manual", "summary_btn": "📊 Summary", "print_slip": "🖨️ Photocopy", "view_records": "🔍 Records Viewer",
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
        "manual": "➕ إضافة يدوي", "summary_btn": "📊 ملخص الفحص", "print_slip": "🖨️ إيصال تصوير", "view_records": "🔍 عرض السجلات",
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
        except Exception: pass
    return text

def format_arabic_for_dropdown(text):
    if not text: return ""
    if REPORTLAB_AVAILABLE and re.search(r"[\u0621-\u064A]", text):
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            pass
    return text

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
        except: pass
    threading.Thread(target=_tone, daemon=True).start()

def play_sound_diff():
    if SOUND_MUTED: return
    def _tone():
        try:
            winsound.Beep(520, 150)
            winsound.Beep(440, 200)
        except: pass
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
            except: pass
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
            except: pass
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
            except: pass

    def _ar(t):
        try: return get_display(arabic_reshaper.reshape(str(t)))
        except: return str(t)

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

def create_photocopy_slip_pdf(filepath, emp_name, unit_name, date_str, terminal_id=""):
    if not REPORTLAB_AVAILABLE:
        return False
    PAGE_W, PAGE_H = 160, 95
    c = canvas.Canvas(filepath, pagesize=(PAGE_W, PAGE_H))
    font_name = "Helvetica-Bold"
    for f_cand in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\seguiemj.ttf"]:
        if os.path.exists(f_cand):
            try:
                pdfmetrics.registerFont(TTFont("SlipArabic", f_cand))
                font_name = "SlipArabic"
                break
            except: pass

    def _ar(t):
        try: return get_display(arabic_reshaper.reshape(str(t)))
        except: return str(t)

    c.setFillColorRGB(0, 0, 0)
    c.setFont(font_name, 17)
    y = PAGE_H - 20
    c.drawCentredString(PAGE_W / 2, y, _ar(emp_name))
    if unit_name:
        y -= 20
        c.setFont(font_name, 14)
        c.drawCentredString(PAGE_W / 2, y, _ar(unit_name))
    if terminal_id:
        y -= 17
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(PAGE_W / 2, y, f"TID: {terminal_id}")
    y -= 19
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(PAGE_W / 2, y, date_str)
    c.save()
    return True

SUPERVISOR_HASHES = {hashlib.sha256("a2r1000".encode('utf-8')).hexdigest()}
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
                             encoding='utf-8', errors='ignore', creationflags=flags)
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

def run_pdftotext_bbox(path):
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        res = subprocess.run([PDFTOTEXT_EXE, "-bbox", path, "-"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore",
                             creationflags=flags)
    except Exception as e:
        log_exception(f"bbox:{os.path.basename(path)}", e)
        return None, None, []
    out = res.stdout or ""
    pm = re.search(r'<page\s+width="([\d.]+)"\s+height="([\d.]+)"', out)
    if not pm:
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

    if method != "bbox":
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
        conn = sqlite3.connect(DB_FILE)
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
        _PARSE_CACHE[key] = dict(rec)
        return rec

    key = (path, st.st_mtime, st.st_size)
    if key in _PARSE_CACHE:
        cached = _PARSE_CACHE[key]
        return dict(cached) if cached else None
    txt = run_pdftotext(path)
    if not is_receipt_text(txt):
        _PARSE_CACHE[key] = None
        return None
    f = parse_receipt(path, txt)
    rec = make_record(path, f["unit"], f["plate"], f["insured"], f["amount"], f["dt"], mdate, False,
                      chassis=f["chassis"], motor=f["motor"], make=f["make"],
                      model=f["model"], period=f["period"])
    if not f["dt"]:
        rec["time"] = f["time"]
    _PARSE_CACHE[key] = dict(rec)
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
        tx_sig = (r["plate"], r["time"], round(r["amount"], 2))
        if r["plate"] != "-" and tx_sig in dup_sig_seen:
            browser_dup[id(r)] = True
        else:
            browser_dup[id(r)] = False
            if r["plate"] != "-":
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

def build_summary(records, device_unit, date_label):
    units_summary = {}
    valid_total_sum = 0.0
    valid_count = 0
    void_count = 0
    void_sum = 0.0
    seen_sigs = set()

    for r in records:
        if r.get("is_void"):
            void_count += 1
            void_sum += r["amount"]
            continue

        u = units_summary.setdefault(r["unit"], {"count": 0, "total": 0.0, "pdf_cnt": 0, "manual_cnt": 0})
        u["count"] += 1
        u["total"] += r["amount"]
        u["manual_cnt" if r["is_manual"] else "pdf_cnt"] += 1

        tx_sig = (r["plate"], r["time"], round(r["amount"], 2))
        if tx_sig not in seen_sigs or r["plate"] == "-":
            valid_total_sum += r["amount"]
            valid_count += 1
            if r["plate"] != "-":
                seen_sigs.add(tx_sig)

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
               "الطراز", "المدة التأمينية", "اسم الملف", "نوع المعاملة"]

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
                    rec['model'], rec['period'], rec['file'], rec['status_text']]
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
    ws.auto_filter.ref = f"A1:M{last_data}"
    ws.freeze_panes = "A2"

    current_r += 1
    tot_label = ws.cell(row=current_r, column=2, value="الصافي الفعلي العام")
    tot_label.font, tot_label.fill, tot_label.border = Font(name="Arial", size=12, bold=True), fill_total, thin_border
    
    valid_count = sum(1 for r in records if not r.get('is_void'))
    cnt_cell = ws.cell(row=current_r, column=4, value=valid_count)
    cnt_cell.font, cnt_cell.fill, cnt_cell.alignment, cnt_cell.border = Font(name="Arial", size=12, bold=True), fill_total, center, thin_border
    sum_cell = ws.cell(row=current_r, column=5, value=f"=SUM(E2:E{last_data})")
    sum_cell.font, sum_cell.fill, sum_cell.alignment, sum_cell.border = Font(name="Arial", size=12, bold=True, color="C00000"), fill_total, center, thin_border
    sum_cell.number_format = '#,##0.00'

    for col_i in range(1, 14): ws.column_dimensions[get_column_letter(col_i)].width = 20
    ws.column_dimensions['D'].width = 32
    ws.column_dimensions['L'].width = 30
    ws.column_dimensions['M'].width = 28
    
    try:
        wb.save(out_file)
    except Exception:
        alt_path = out_file.replace(".xlsx", f"_{int(time.time())}.xlsx")
        try: wb.save(alt_path)
        except: pass
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
                             creationflags=flags)
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
        val = self.e_pwd.get().strip().lower()
        h_val = hashlib.sha256(val.encode('utf-8')).hexdigest()
        if h_val in SUPERVISOR_HASHES:
            self.destroy()
            self.on_success(is_supervisor=True)
        elif h_val in EMPLOYEE_HASHES:
            self.destroy()
            self.on_success(is_supervisor=False)
        else:
            self.lbl_err.configure(text=tr("access_denied"))
            self.e_pwd.delete(0, 'end')
            try: winsound.MessageBeep(winsound.MB_ICONHAND)
            except: pass

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
            val = self.e.get().strip().lower()
            if hashlib.sha256(val.encode('utf-8')).hexdigest() in SUPERVISOR_HASHES:
                self.destroy()
                on_success()
            else:
                try: winsound.MessageBeep(winsound.MB_ICONHAND)
                except: pass
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
            conn = sqlite3.connect(DB_FILE)
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

    def _silent_archive_all_historical(self, folder_path):
        try:
            archive_root = ensure_archive_root(folder_path)
            manual_map = load_manual_map()
            all_pdf_files = [f for f in glob.glob(os.path.join(folder_path, "*.pdf")) if not f.endswith("_Summary.pdf") and not f.endswith("_cropped.pdf")]
            today_date = datetime.date.today()
            days_records_map = {}
            load_void_map()
            _void = lambda n: n.startswith("_") or n.lstrip("_") in _VOID_KEYS

            for pdf in all_pdf_files:
                fname = os.path.basename(pdf)
                try: mdate = datetime.date.fromtimestamp(os.path.getmtime(pdf))
                except Exception: mdate = today_date

                file_date = None
                rec_info = None
                if MANUAL_NAME_RE.match(fname):
                    row = manual_map.get(fname)
                    clean_b = fname.lstrip("_")
                    m_amt = re.match(r"^(\d+(?:\.\d{2})?)", clean_b)
                    if row:
                        dt_m = parse_vault_dt(row[4])
                        file_date = dt_m.date() if dt_m else mdate
                        rec_info = {"unit": detect_unit_from_text(row[0]) or UNSPEC, "amount": float(row[3]), "is_manual": True, "is_void": _void(fname)}
                    else:
                        file_date = mdate
                        rec_info = {"unit": UNSPEC, "amount": float(m_amt.group(1)) if m_amt else 0.0, "is_manual": True, "is_void": _void(fname)}
                else:
                    raw_txt = run_pdftotext(pdf)
                    if is_receipt_text(raw_txt):
                        f = parse_receipt(pdf, raw_txt)
                        file_date = f["dt"].date() if f["dt"] else mdate
                        rec_info = {"unit": f["unit"], "amount": f["amount"], "is_manual": False, "is_void": _void(fname)}
                    else:
                        file_date = extract_date_from_text(raw_txt) or mdate

                if file_date and file_date < today_date:
                    year_folder = os.path.join(archive_root, str(file_date.year))
                    month_folder = os.path.join(year_folder, f"{file_date.month:02d}-{file_date.strftime('%B')}")
                    day_folder = os.path.join(month_folder, f"{file_date.day:02d}")
                    os.makedirs(day_folder, exist_ok=True)
                    target_dest = os.path.join(day_folder, fname)
                    try:
                        shutil.move(pdf, target_dest)
                        cropped_version = pdf.replace(".pdf", "_cropped.pdf")
                        if os.path.exists(cropped_version):
                            try: os.remove(cropped_version)
                            except Exception: pass
                        if rec_info:
                            days_records_map.setdefault(day_folder, []).append(rec_info)
                    except Exception:
                        pass

            for d_folder, recs in days_records_map.items():
                d_name = os.path.basename(d_folder)
                parent_m = os.path.basename(os.path.dirname(d_folder))
                parent_y = os.path.basename(os.path.dirname(os.path.dirname(d_folder)))
                date_str_tag = f"{d_name}-{parent_m.split('-')[0]}-{parent_y}"
                self._generate_day_summary_pdf(d_folder, date_str_tag, recs)
        except Exception as ex:
            log_exception("silent_archive_historical", ex)

    def _cancel_auto_minimize(self):
        if self._auto_minimize_timer:
            try:
                self.after_cancel(self._auto_minimize_timer)
            except Exception:
                pass
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
        except Exception:
            pass

    def _create_tray_image(self):
        ico_path = get_app_icon_path()
        if ico_path:
            try:
                return Image.open(ico_path).convert("RGBA")
            except Exception:
                pass
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
                except Exception:
                    pass
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
            except Exception:
                pass
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
            self.send_to_thermal_printer_57x90(fpath)
            play_sound_matched()
            messagebox.showinfo(tr("done"), tr("reprint_success"))
        else:
            messagebox.showerror("Error", f"File not found: {rec.get('file', '')}")

    def _sync_watch_path(self):
        try: self._watch_path = self.get_clean_path()
        except Exception: pass
        try: self.after(1000, self._sync_watch_path)
        except Exception: pass

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
        self.btn_chrome.pack_forget()
        if is_supervisor:
            self.badge_role.configure(text="● ADMIN", text_color="#EF4444")
            self.f_role_btn.configure(border_color="#EF4444")
            self.btn_excel.pack(side="left", padx=2)
        else:
            self.badge_role.configure(text="● USER", text_color="#10B981")
            self.f_role_btn.configure(border_color="#10B981")
        self.btn_chrome.pack(side="left", padx=2)

        self.switch_to_full_view()
        # أرشفة تلقائية لكل الأيام السابقة فور الدخول (مستخدم أو مشرف) مع إظهار نافذة التقدم
        self.after(400, self.auto_archive_on_login)

    def _archive_done_today(self):
        today_tag = datetime.date.today().strftime("%Y-%m-%d")
        try:
            conn = sqlite3.connect(DB_FILE)
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
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS system_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT)")
            c.execute("INSERT OR REPLACE INTO system_meta (meta_key, meta_value) VALUES ('last_full_archive_date', ?)", (today_tag,))
            conn.commit()
            conn.close()
        except Exception as e:
            log_exception("mark_archive_done_today", e)

    def auto_archive_on_login(self):
        folder = self.get_clean_path() or DEFAULT_RECEIPTS_DIR
        if not folder or not os.path.isdir(folder):
            return
        # الأرشفة التلقائية مرة واحدة فقط في اليوم
        if self._archive_done_today():
            return
        try:
            t = THEMES[self.current_theme_name]
            win = ctk.CTkToplevel(self)
            win.title(f"{tr('clean_downloads')} - A2R {APP_VERSION}")
            win.resizable(False, False)
            set_window_icon_safe(win)
            center_window_relative(win, self, 430, 170)
            win.configure(fg_color=t["bg"])
            try: win.attributes("-topmost", True)
            except Exception: pass
            win.protocol("WM_DELETE_WINDOW", lambda: None)  # منع الإغلاق أثناء الأرشفة

            ctk.CTkLabel(win, text=tr("arch_title"), font=(FONT_FAMILY, 13, "bold"),
                         text_color=t["accent"]).pack(pady=(14, 2))
            s_lbl = ctk.CTkLabel(win, text="Scanning files...", font=(FONT_FAMILY, 9, "bold"),
                                 text_color=t["text"], wraplength=390)
            s_lbl.pack(pady=(4, 6))

            f_prog = ctk.CTkFrame(win, fg_color="transparent")
            f_prog.pack(fill="x", padx=20, pady=(4, 4))
            f_prog.grid_columnconfigure(0, weight=1)
            p_bar = ctk.CTkProgressBar(f_prog, orientation="horizontal", height=8, progress_color=t["success"])
            p_bar.set(0)
            p_bar.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            p_lbl = ctk.CTkLabel(f_prog, text="0%", font=(FONT_FAMILY, 10, "bold"), width=36, text_color=t["text"])
            p_lbl.grid(row=0, column=1)

            threading.Thread(target=self._process_archive_worker,
                             args=(False, win, p_bar, p_lbl, s_lbl, folder, True), daemon=True).start()
        except Exception as e:
            log_exception("auto_archive_on_login", e)

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

        
