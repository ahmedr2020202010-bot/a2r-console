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

APP_VERSION = "v4.60.0"
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
        "btn_advanced_tools": "🛠️ Advanced Tools", "adv_login_prompt": "🔒 Enter Password for Advanced Tools", "adv_win_title": "Advanced Batching & Receipts", "adv_pick_folder": "Select Directory (Required)", "adv_btn_batch": "التقفيل (Batching)", "adv_btn_receipts": "إيصالات الدفع (Payment Receipts)", "adv_err_dir": "Please select a directory first!", "adv_placeholder": "Algorithm will be integrated here...", "btn_full_console": "🖥️ Full Console", "btn_back_mini": "⚡ Mini Mode",
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
        "btn_advanced_tools": "🛠️ أدوات التقفيل", "adv_login_prompt": "🔒 أدخل كلمة المرور المتقدمة (للمشرف فقط)", "adv_win_title": "أدوات التقفيل وإيصالات الدفع", "adv_pick_folder": "تحديد مسار المجلد (إجباري)", "adv_btn_batch": "عملية التقفيل", "adv_btn_receipts": "فحص إيصالات الدفع", "adv_err_dir": "الرجاء اختيار المجلد أولاً!", "adv_placeholder": "سيتم دمج خوارزمية المعالجة (OpenCV/OCR) هنا في الخطوة القادمة...", "btn_full_console": "🖥️ النسخة الكاملة", "btn_back_mini": "⚡ وضع الميني",
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
    conn = sqlite3.connect(DB_FILE)
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
        s_conn = sqlite3.connect(DB_FILE)
        d_conn = sqlite3.connect(os.path.join(db_dir, "a2r_vault_backup.db"))
        try: s_conn.backup(d_conn)
        finally:
            d_conn.close(); s_conn.close()
    except Exception as e:
        log_exception("archive_backup_db", e)
    return copied

def archive_maintenance(folder_path, progress=None):
    """فهرسة + نسخ احتياطي. لو في عملية شغالة بالفعل بترجع None ومش بتتكرر."""
    if not _ARCHIVE_LOCK.acquire(blocking=False): return None
    try:
        n = archive_index_update(folder_path, progress)
        b = archive_backup(folder_path)
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

def archive_search(query, include_void=True, limit=3000):
    q = _norm_search(query)
    if not q: return []
    amt = None
    try: amt = float(str(query).strip().replace(",", ""))
    except Exception: pass
    out = []
    for r in archive_load_rows():
        path, day, fname, unit, plate, insured, amount, rtime, is_manual, is_void = r
        if is_void and not include_void: continue
        hit = q in _norm_search(plate) or q in _norm_search(insured) or q in _norm_search(fname)
        if not hit and amt is not None and abs(amount - amt) < 0.005: hit = True
        if hit: out.append(r)
    out.sort(key=lambda r: (r[1], r[7]), reverse=True)
    return out[:limit]

def parse_flex_date(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try: return datetime.datetime.strptime(s, fmt).date()
        except Exception: pass
    return None

# ================= كنس الأرشيف: أي ملف مش بتاع النهارده يتنقل للأرشيف =================
_SWEEP_CACHE = {}
_SWEEP_LOCK = threading.Lock()

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
            _SWEEP_CACHE[ck] = file_date
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
                    except Exception: pass
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

SUPERVISOR_HASHES = {hashlib.sha256("a2r1000".encode('utf-8')).hexdigest()}
ADVANCED_ADMIN_HASH = hashlib.sha256("Ahmed@A2r460".encode("utf-8")).hexdigest()

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


class AdvancedLoginGate(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.parent = parent
        self.on_success = on_success
        self.title("Advanced Authorization")
        self.resizable(False, False)
        set_window_icon_safe(self)
        center_window_relative(self, parent, 360, 205)

        t = THEMES[parent.current_theme_name]
        self.configure(fg_color=t["bg"])

        ctk.CTkLabel(self, text="A2R ADVANCED TOOLS", font=(FONT_FAMILY, 15, "bold"), text_color=t["accent"]).pack(pady=(12, 1))
        ctk.CTkLabel(self, text=tr("adv_login_prompt"), font=(FONT_FAMILY, 10, "bold"), text_color=t["text_muted"]).pack(pady=(0, 6))

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

        btn_enter = ctk.CTkButton(self, text=tr("done"), font=FONT_BTN_MAIN,
                                  fg_color="#4F46E5", hover_color="#4338CA", text_color="#FFFFFF", command=self.check_pwd)
        btn_enter.pack(fill="x", padx=24, pady=(6, 4))

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
        val = self.e_pwd.get().strip()
        import hashlib
        h_val = hashlib.sha256(val.encode('utf-8')).hexdigest()
        if h_val == ADVANCED_ADMIN_HASH:
            self.destroy()
            self.on_success()
        else:
            self.lbl_err.configure(text=tr("access_denied"))
            self.e_pwd.delete(0, 'end')
            try: winsound.MessageBeep(winsound.MB_ICONHAND)
            except: pass

class AdvancedToolsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(tr("adv_win_title"))
        self.resizable(False, False)
        set_window_icon_safe(self)
        center_window_relative(self, parent, 460, 240)
        
        t = THEMES[parent.current_theme_name]
        self.configure(fg_color=t["bg"])

        ctk.CTkLabel(self, text=tr("adv_win_title"), font=(FONT_FAMILY, 14, "bold"), text_color=t["accent"]).pack(pady=(14, 8))

        f_dir = ctk.CTkFrame(self, fg_color="transparent")
        f_dir.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(f_dir, text=tr("adv_pick_folder"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(anchor="w", pady=(0, 4))
        
        f_in = ctk.CTkFrame(f_dir, fg_color="transparent")
        f_in.pack(fill="x")
        
        self.e_path = ctk.CTkEntry(f_in, font=FONT_ENTRY, height=30, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        self.e_path.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        btn_browse = ctk.CTkButton(f_in, text=tr("browse"), width=70, height=30, font=FONT_BTN_SUB, fg_color=t["primary"], command=self.browse_folder)
        btn_browse.pack(side="left")

        f_btns = ctk.CTkFrame(self, fg_color="transparent")
        f_btns.pack(fill="x", padx=20, pady=15)
        
        btn_batch = ctk.CTkButton(f_btns, text=tr("adv_btn_batch"), height=40, font=FONT_BTN_MAIN, fg_color="#0F766E", hover_color="#115E59", text_color="#FFFFFF", command=lambda: self.run_action("batch"))
        btn_batch.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        btn_receipts = ctk.CTkButton(f_btns, text=tr("adv_btn_receipts"), height=40, font=FONT_BTN_MAIN, fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF", command=lambda: self.run_action("receipts"))
        btn_receipts.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.lbl_status = ctk.CTkLabel(self, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["text_muted"])
        self.lbl_status.pack(pady=(0, 10))

    def browse_folder(self):
        f = filedialog.askdirectory()
        if f:
            self.e_path.delete(0, 'end')
            self.e_path.insert(0, f)

    def run_action(self, action_type):
        path = self.e_path.get().strip()
        if not path or not os.path.exists(path):
            self.lbl_status.configure(text=tr("adv_err_dir"), text_color="#EF4444")
            try: winsound.MessageBeep(winsound.MB_ICONHAND)
            except: pass
            return
            
        self.lbl_status.configure(text=tr("adv_placeholder"), text_color="#10B981")
\nclass CustomTkinterApp(ctk.CTk):
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

    def _run_archive_sweep(self, folder_path, progress=None):
        """كنس + تحديث ملخصات الأيام اللي اتغيّرت. آمنة لو اتنادت من أكتر من مكان."""
        if not _SWEEP_LOCK.acquire(blocking=False): return 0
        moved = 0
        try:
            moved, touched = archive_sweep(folder_path, progress)
            for d_folder in touched:
                d_name = os.path.basename(d_folder)
                parent_m = os.path.basename(os.path.dirname(d_folder))
                parent_y = os.path.basename(os.path.dirname(os.path.dirname(d_folder)))
                tag = f"{d_name}-{parent_m.split('-')[0]}-{parent_y}"
                self._generate_day_summary_pdf(d_folder, tag, archive_day_records(d_folder))
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

    def request_advanced_tools(self):
        AdvancedLoginGate(self, self.open_advanced_window)

    def open_advanced_window(self):
        AdvancedToolsWindow(self)

    def unlock_full_console(self, is_supervisor):
        self.is_supervisor = is_supervisor

        # كل الصلاحيات متاحة للجميع (مستخدم أو مشرف) ما عدا زر الإكسل: حصري للمشرف
        for w in (self.cb_d, self.cb_m, self.cb_y):
            w.configure(state="normal")
        for w in (self.btn_yesterday, self.btn_browse, self.btn_open_f):
            w.configure(state="normal")

        self.btn_excel.pack_forget()
        self.btn_arch_hist.pack_forget()
        self.btn_chrome.pack_forget()
        if is_supervisor:
            self.badge_role.configure(text="● ADMIN", text_color="#EF4444")
            self.f_role_btn.configure(border_color="#EF4444")
            self.btn_excel.pack(side="left", padx=2)
            self.btn_arch_hist.pack(side="left", padx=2)
            if not hasattr(self, 'btn_advanced_tools'):
                self.btn_advanced_tools = ctk.CTkButton(self.btn_center_box, text=tr("btn_advanced_tools"), fg_color="#4F46E5", hover_color="#4338CA", width=105, height=25, font=FONT_BTN_SUB, text_color="#FFFFFF", command=self.request_advanced_tools)
            self.btn_advanced_tools.pack(side="left", padx=2)
        else:
            self.badge_role.configure(text="● USER", text_color="#10B981")
            self.f_role_btn.configure(border_color="#10B981")
            if hasattr(self, 'btn_advanced_tools'):
                self.btn_advanced_tools.pack_forget()
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

        self.update_toggle_appearance()

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
        self.btn_chrome.configure(text=L["open_chrome"])
        self.btn_elevate.configure(text=L["btn_full_console"])
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
        except:
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
            if initial_path and os.path.exists(initial_path):
                try:
                    for f in glob.glob(os.path.join(initial_path, "*.pdf")):
                        fn = os.path.basename(f)
                        self.printed_receipts_set.add(fn)
                        self.printed_receipts_set.add(clean_download_filename(fn))
                except Exception as e:
                    log_exception("init_watchdogs_seed", e)

            while True:
                time.sleep(2)
                p = self._watch_path
                if not p or not os.path.exists(p): continue

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
                                        self.send_to_thermal_printer_57x90(pdf_file)
                                        self.printed_count_today += 1
                                        self.run_on_main(lambda: self.lbl_mini_counter.configure(
                                            text=tr("mini_printed_count", count=self.printed_count_today)))
                                except: pass

                if self.auto_sync_enabled and not self.is_processing and not self.is_mini_mode:
                    try:
                        valid_pdfs = [f for f in pdf_files if not f.endswith("_Summary.pdf") and not f.endswith("_cropped.pdf")]
                        current_sig = f"{len(valid_pdfs)}_{sum(os.path.getsize(f) for f in valid_pdfs if os.path.exists(f))}"
                        if self.last_pdf_state_sig == "":
                            self.last_pdf_state_sig = current_sig
                        elif current_sig != self.last_pdf_state_sig:
                            self.last_pdf_state_sig = current_sig
                            self.run_on_main(self.start_thread)
                    except: pass

        threading.Thread(target=_routine, daemon=True).start()

    def send_to_thermal_printer_57x90(self, pdf_file_path):
        temp_copy = None
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

            if os.path.exists(sumatra_path):
                cmd = [
                    sumatra_path,
                    "-print-to-default",
                    "-print-settings", "paper=57 x 90 mm,fit",
                    "-silent",
                    target
                ]
                subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            else:
                if sys.platform == "win32": os.startfile(target, "print")
        except Exception as e:
            log_exception(f"auto_print:{os.path.basename(pdf_file_path)}", e)
        finally:
            if temp_copy:
                time.sleep(1.0)
                try: os.remove(temp_copy)
                except Exception: pass

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
                d = filedialog.askdirectory(initialdir=e_arch_dir.get().strip())
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
                    except Exception:
                        pass
                return None

            def _open_selected_day_summary():
                try:
                    s_d = int(cb_arch_d.get())
                    s_m = int(cb_arch_m.get())
                    s_y = int(cb_arch_y.get())
                    target_dt = datetime.date(s_y, s_m, s_d)
                except Exception:
                    messagebox.showerror("Error", tr("invalid_date"))
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

                messagebox.showinfo("Not Found", f"No summary report or archived receipts found for: {date_tag}")

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
                    messagebox.showerror("Error", tr("dir_missing"))
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
            total_sum = sum(r['amount'] for r in records_list if not r.get('is_void'))
            total_cnt = sum(1 for r in records_list if not r.get('is_void'))
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
                    except: pass

            def _ar(txt):
                try: return get_display(arabic_reshaper.reshape(str(txt)))
                except: return str(txt)

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

        moved_count = self._run_archive_sweep(folder_path, prog)
        if auto: self._mark_archive_done_today()
        self._start_archive_maintenance(folder_path)

        def _complete():
            if auto:
                p_bar.set(1.0)
                p_lbl.configure(text="100%")
                s_lbl.configure(text=f"✓ Archive complete — {moved_count} file(s) archived.")
                try: win.after(1500, win.destroy)
                except Exception: pass
                return
            try: win.destroy()
            except: pass
            play_sound_matched()
            messagebox.showinfo(tr("done"), f"Successfully archived {moved_count} files.\nSummary PDFs updated for all affected days.")

        self.run_on_main(_complete)

    def start_thread(self):
        L = LANGUAGES[self.current_lang]
        if not self.processing_lock.acquire(blocking=False): return

        try:
            target_date = datetime.date(int(self.cb_y.get()), int(self.cb_m.get()), int(self.cb_d.get()))
        except:
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
        center_window_relative(win, self, 1100, 650)
        win.configure(fg_color=t["bg"])
        try: win.lift(); win.focus_force()
        except Exception: pass

        ALL = T2("الكل", "All")
        st = {"stats": [], "debounce": None}

        # ---------- شريط الحالة والأدوات ----------
        bar = ctk.CTkFrame(win, corner_radius=10, fg_color=t["card"], border_width=1, border_color=t["border"])
        bar.pack(fill="x", padx=14, pady=(12, 6))
        status_lbl = ctk.CTkLabel(bar, text="", font=(FONT_FAMILY, 10, "bold"), text_color=t["accent"])
        status_lbl.pack(side="left", padx=12, pady=8)

        def _set_status(txt):
            try:
                if win.winfo_exists(): status_lbl.configure(text=txt)
            except Exception: pass

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
                    load_days()
                self.after(0, fin)
            _set_status(T2("جاري الفحص...", "Scanning..."))
            threading.Thread(target=work, daemon=True).start()

        def open_backup_folder():
            if os.path.isdir(ARCHIVE_BACKUP_DIR): os.startfile(ARCHIVE_BACKUP_DIR)
            else: messagebox.showinfo(T2("تنبيه", "Notice"), T2("لا توجد نسخة احتياطية بعد. اضغط (تحديث + نسخ).", "No backup yet. Press Refresh + Backup."))

        ctk.CTkButton(bar, text=T2("🔄 تحديث + نسخ احتياطي", "🔄 Refresh + Backup"), font=FONT_BTN_SUB, width=160, height=30,
                      fg_color=t["primary"], hover_color=t["primary_hover"], text_color="#FFFFFF",
                      command=lambda: run_maintenance(True)).pack(side="right", padx=4, pady=6)
        ctk.CTkButton(bar, text=T2("🗄️ فتح النسخة الاحتياطية", "🗄️ Open Backup"), font=FONT_BTN_SUB, width=160, height=30,
                      fg_color="#4338CA", hover_color="#3730A3", text_color="#FFFFFF",
                      command=open_backup_folder).pack(side="right", padx=4, pady=6)

        # ---------- ستايل الجداول ----------
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
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
        tab_days = tv.add(T2("📅 الأيام", "📅 Days"))
        tab_search = tv.add(T2("🔎 بحث عام في الأرشيف", "🔎 Global Search"))

        # ================= تبويب الأيام =================
        f1 = ctk.CTkFrame(tab_days, fg_color="transparent")
        f1.pack(fill="x", pady=(2, 2))
        day_q = ctk.CTkEntry(f1, placeholder_text=T2("ابحث عن يوم (مثال: 15-10-2026 أو 2026-10)", "Find a day (e.g. 2026-10-15)"),
                             width=270, font=FONT_ENTRY, text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        day_q.pack(side="left", padx=(0, 6))
        attach_context_menu(day_q)
        ctk.CTkLabel(f1, text=T2("الشهر:", "Month:"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left", padx=(6, 2))
        cb_month = ctk.CTkComboBox(f1, values=[ALL], width=110, font=FONT_ENTRY, fg_color=t["input"], border_color=t["border"],
                                   command=lambda v: apply_days())
        cb_month.set(ALL)
        cb_month.pack(side="left", padx=2)
        ctk.CTkLabel(f1, text=T2("من:", "From:"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left", padx=(8, 2))
        from_e = ctk.CTkEntry(f1, placeholder_text="YYYY-MM-DD", width=105, font=FONT_ENTRY, text_color=t["text"],
                              fg_color=t["input"], border_color=t["border"])
        from_e.pack(side="left", padx=2)
        ctk.CTkLabel(f1, text=T2("إلى:", "To:"), font=FONT_SECTION_LBL, text_color=t["text"]).pack(side="left", padx=(6, 2))
        to_e = ctk.CTkEntry(f1, placeholder_text="YYYY-MM-DD", width=105, font=FONT_ENTRY, text_color=t["text"],
                            fg_color=t["input"], border_color=t["border"])
        to_e.pack(side="left", padx=2)

        def clear_filters():
            for e in (day_q, from_e, to_e): e.delete(0, "end")
            cb_month.set(ALL)
            apply_days()
        ctk.CTkButton(f1, text=T2("مسح الفلاتر", "Clear"), width=80, height=28, font=FONT_BTN_SUB,
                      fg_color="#64748B", hover_color="#475569", text_color="#FFFFFF",
                      command=clear_filters).pack(side="left", padx=8)

        day_cols = ("date", "ops", "total", "manual", "void", "dup", "missing")
        day_hdr = {"date": T2("التاريخ", "Date"), "ops": T2("عدد المعاملات", "Transactions"),
                   "total": T2("إجمالي المبلغ", "Total Amount"), "manual": T2("يدوي", "Manual"),
                   "void": T2("ملغي", "Void"), "dup": T2("مكرر", "Duplicates"), "missing": T2("ناقص", "Incomplete")}
        day_tree = make_tree(tab_days, day_cols, day_hdr,
                             {"date": 140, "ops": 120, "total": 160, "manual": 80, "void": 80, "dup": 90, "missing": 90})
        sum_lbl = ctk.CTkLabel(tab_days, text="", font=(FONT_FAMILY, 12, "bold"), text_color=t["accent"])
        sum_lbl.pack(anchor="w", padx=8, pady=(2, 0))
        ctk.CTkLabel(tab_days, text=T2("🟥 يوم فيه مكرر    🟨 يوم فيه ناقص    •  دبل كليك لفتح ملخص اليوم",
                                       "🟥 has duplicates   🟨 has incomplete  •  double-click to open day summary"),
                     font=(FONT_FAMILY, 9, "bold"), text_color=t["text_muted"]).pack(anchor="w", padx=8)

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
            d_from, d_to = parse_flex_date(from_e.get()), parse_flex_date(to_e.get())
            items = []
            for s in st["stats"]:
                day = s["day"]
                if mval != ALL and not day.startswith(mval): continue
                if d_from and day < d_from.isoformat(): continue
                if d_to and day > d_to.isoformat(): continue
                if q:
                    y, m, d = day.split("-")
                    hay = f"{day} {d}-{m}-{y} {d}/{m}/{y}"
                    if q.replace("/", "-") not in hay.replace("/", "-"): continue
                items.append(s)
            key = sort_state["col"]
            items.sort(key=lambda s: s["day"] if key == "date" else s[key], reverse=sort_state["rev"])
            day_tree.delete(*day_tree.get_children())
            for s in items:
                y, m, d = s["day"].split("-")
                tag = "dup" if s["dup"] else ("missing" if s["missing"] else "")
                day_tree.insert("", "end", iid=s["day"], tags=(tag,) if tag else (),
                                values=(f"{d}-{m}-{y}", f"{s['ops']:,}", f"{s['total']:,.2f}",
                                        s["manual"], s["void"], s["dup"], s["missing"]))
            tot_ops = sum(s["ops"] for s in items)
            tot_amt = sum(s["total"] for s in items)
            sum_lbl.configure(text=T2(f"الأيام: {len(items)}   |   إجمالي المعاملات: {tot_ops:,}   |   إجمالي المبلغ: {tot_amt:,.2f} جنيه",
                                      f"Days: {len(items)}  |  Transactions: {tot_ops:,}  |  Total: {tot_amt:,.2f} EGP"))

        def load_days():
            try: st["stats"] = archive_day_stats(archive_load_rows())
            except Exception as e:
                log_exception("archive_history_load", e)
                st["stats"] = []
            months = sorted({s["day"][:7] for s in st["stats"]}, reverse=True)
            cb_month.configure(values=[ALL] + months)
            if cb_month.get() not in [ALL] + months: cb_month.set(ALL)
            apply_days()

        def open_selected_day(event=None, folder_only=False):
            sel = day_tree.selection()
            if not sel: return
            try: dd = datetime.date.fromisoformat(sel[0])
            except Exception: return
            dfolder = archive_day_dir(folder, dd)
            if not os.path.isdir(dfolder):
                messagebox.showerror(T2("غير موجود", "Not found"), dfolder)
                return
            pdfs = sorted(glob.glob(os.path.join(dfolder, "Samary_*.pdf")))
            if pdfs and not folder_only: os.startfile(pdfs[0])
            else: os.startfile(dfolder)

        day_tree.bind("<Double-1>", open_selected_day)
        dmenu = tk.Menu(day_tree, tearoff=0)
        dmenu.add_command(label=T2("📄 فتح ملخص اليوم", "📄 Open day summary"), command=open_selected_day)
        dmenu.add_command(label=T2("📂 فتح فولدر اليوم", "📂 Open day folder"), command=lambda: open_selected_day(folder_only=True))
        def _dpop(ev):
            it = day_tree.identify_row(ev.y)
            if it:
                day_tree.selection_set(it)
                dmenu.tk_popup(ev.x_root, ev.y_root)
        day_tree.bind("<Button-3>", _dpop)
        for e in (day_q, from_e, to_e): e.bind("<KeyRelease>", apply_days)

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

        def do_search(*_):
            q = s_entry.get().strip()
            s_tree.delete(*s_tree.get_children())
            s_paths.clear()
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
                s_tree.insert("", "end", iid=iid, tags=(tag,) if tag else (),
                              values=(f"{d}-{m}-{y}", unit, plate, insured, f"{amount:,.2f}", rtime, status, fname))
            s_count.configure(text=T2(f"النتائج: {len(rows):,}  |  الإجمالي (بدون الملغي): {tot:,.2f}",
                                      f"Results: {len(rows):,}  |  Total (excl. void): {tot:,.2f}"))

        def _debounced(*_):
            if st["debounce"]:
                try: win.after_cancel(st["debounce"])
                except Exception: pass
            st["debounce"] = win.after(300, do_search)
        s_entry.bind("<KeyRelease>", _debounced)
        s_entry.bind("<Return>", do_search)
        inc_void.configure(command=do_search)

        def open_result(event=None, folder_only=False):
            sel = s_tree.selection()
            if not sel: return
            p = s_paths.get(sel[0], "")
            if not p or not os.path.exists(p):
                messagebox.showerror(T2("غير موجود", "Not found"), os.path.basename(p or ""))
                return
            if folder_only: os.startfile(os.path.dirname(p))
            else: os.startfile(p)
        s_tree.bind("<Double-1>", open_result)
        smenu = tk.Menu(s_tree, tearoff=0)
        smenu.add_command(label=T2("📄 فتح الإيصال", "📄 Open receipt"), command=open_result)
        smenu.add_command(label=T2("📂 فتح فولدر اليوم", "📂 Open day folder"), command=lambda: open_result(folder_only=True))
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

    def open_records_viewer(self):
        if not self.last_detailed_records:
            messagebox.showinfo("Notice", tr("no_records_yet"))
            return

        t = THEMES[self.current_theme_name]
        win = ctk.CTkToplevel(self)
        win.title(tr("records_viewer_title"))
        win.resizable(True, True)
        set_window_icon_safe(win)
        center_window_relative(win, self, 1260, 580)
        win.configure(fg_color=t["bg"])

        search_row = ctk.CTkFrame(win, corner_radius=10, height=52, fg_color=t["card"], border_width=1, border_color=t["border"])
        search_row.pack(fill="x", padx=14, pady=(12, 6))

        search_entry = ctk.CTkEntry(search_row, placeholder_text=tr("search_placeholder"), font=FONT_ENTRY, width=280,
                                    text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        search_entry.pack(side="left", padx=8, pady=8)
        search_entry.focus_set()
        attach_context_menu(search_entry)

        amt_entry = ctk.CTkEntry(search_row, placeholder_text=tr("amt_filter_placeholder"), font=FONT_ENTRY, width=95,
                                 text_color=t["text"], fg_color=t["input"], border_color=t["border"])
        amt_entry.pack(side="left", padx=(0, 6), pady=8)
        attach_context_menu(amt_entry)

        def open_selected():
            sel = tree.selection()
            if not sel: return
            try:
                rec = self.last_detailed_records[int(sel[0])]
            except Exception: return
            fpath = rec.get("path", "")
            if fpath and os.path.exists(fpath): os.startfile(fpath)
            else: messagebox.showerror("Not Found", f"File not found: {rec.get('file', '')}")

        def reprint_selected():
            sel = tree.selection()
            if not sel: return
            try:
                rec = self.last_detailed_records[int(sel[0])]
                self.reprint_receipt_record(rec)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        btn_open = ctk.CTkButton(search_row, text=tr("open_pdf_btn"), font=FONT_BTN_SUB, fg_color=t["primary"],
                                 hover_color=t["primary_hover"], text_color="#FFFFFF", width=115, height=30, command=open_selected)
        btn_open.pack(side="left", padx=2)

        btn_reprint_toolbar = ctk.CTkButton(search_row, text=tr("btn_reprint"), font=FONT_BTN_SUB, fg_color="#D97706",
                                            hover_color="#B45309", text_color="#FFFFFF", width=105, height=30, command=reprint_selected)
        btn_reprint_toolbar.pack(side="left", padx=2)

        def cancel_selected():
            sel = tree.selection()
            if not sel: return
            idx = int(sel[0])
            rec = self.last_detailed_records[idx]
            if rec.get("is_void"):
                messagebox.showinfo(tr("done"), tr("void_already"))
                return
            msg = tr("void_confirm_msg", idx=idx+1, amt=rec['amount'])
            if messagebox.askyesno(tr("void_confirm_title"), msg):
                self.void_selected_record(rec, refresh)

        btn_cancel_row = ctk.CTkButton(search_row, text=tr("btn_void_sel"), font=FONT_BTN_SUB, fg_color="#991B1B",
                                       hover_color="#7F1D1D", text_color="#FFFFFF", width=110, height=30, command=cancel_selected)
        btn_cancel_row.pack(side="left", padx=2)

        def restore_selected_void():
            sel = tree.selection()
            if not sel: return
            idx = int(sel[0])
            rec = self.last_detailed_records[idx]
            if not rec.get("is_void"):
                messagebox.showinfo(tr("done"), tr("restore_already"))
                return
            msg = tr("restore_confirm_msg", idx=idx+1, amt=rec['amount'])
            if messagebox.askyesno(tr("restore_confirm_title"), msg):
                self.unvoid_selected_record(rec, refresh)

        btn_restore_void = ctk.CTkButton(search_row, text=tr("btn_restore_sel"), font=FONT_BTN_SUB, fg_color="#0F766E",
                                         hover_color="#115E59", text_color="#FFFFFF", width=115, height=30, command=restore_selected_void)
        btn_restore_void.pack(side="left", padx=2)

        count_lbl = ctk.CTkLabel(search_row, text="", font=(FONT_FAMILY, 11, "bold"), text_color=t["accent"])
        count_lbl.pack(side="right", padx=14)

        ctk.CTkLabel(win, text=tr("legend_text"), font=(FONT_FAMILY, 10, "bold"), text_color=t["text"]).pack(anchor="w", padx=16)

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
        except: pass
        style.configure("A2R.Treeview", background=t["input"], foreground=t["text"],
                        fieldbackground=t["input"], font=(FONT_FAMILY, 10, "bold"), rowheight=28)
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
            if col in ("idx", "amount"):
                self.last_detailed_records.sort(key=lambda r: float(r["amount"]) if col=="amount" else 0, reverse=reverse)
            else:
                self.last_detailed_records.sort(key=lambda r: str(r.get(col, "")), reverse=reverse)
            refresh()

        for col in columns:
            tree.heading(col, text=headers.get(col, col), command=lambda c=col: sort_by(c))
            w = 38 if col == "idx" else (140 if col in ("insured", "file", "status", "period") else 85)
            tree.column(col, width=w, anchor="center")

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
        row_menu.add_separator()
        row_menu.add_command(label=tr("menu_void_tx"), command=cancel_selected)
        row_menu.add_command(label=tr("menu_restore_tx"), command=restore_selected_void)

        def show_row_menu(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                row_menu.entryconfigure(0, label=tr("menu_open_file"))
                row_menu.entryconfigure(1, label=tr("menu_reprint"))
                row_menu.entryconfigure(3, label=tr("menu_void_tx"))
                row_menu.entryconfigure(4, label=tr("menu_restore_tx"))
                row_menu.tk_popup(event.x_root, event.y_root)

        tree.bind("<Button-3>", show_row_menu)

        def refresh(*_):
            q = search_entry.get().strip().lower()
            aq = amt_entry.get().strip().replace(",", "")
            tree.delete(*tree.get_children())
            shown = 0
            shown_valid_sum = 0.0

            for i, r in enumerate(self.last_detailed_records):
                amt_str = f"{r['amount']:.2f}"
                vals = (i + 1, r["unit"], r["plate"], r["insured"], amt_str, r["time"],
                        r["make"], r["model"], r["chassis"], r["motor"], r["period"], r["file"], r["status_text"])

                if aq and aq not in amt_str: continue
                if q:
                    full_s = f"{r['unit']} {r['plate']} {r['insured']} {r['time']} {r['chassis']} {r['motor']} {r['make']} {r['model']} {r['file']} {r['status_text']}".lower()
                    if q not in full_s: continue

                tag = r["kind"] if r["kind"] in ("dup", "void") else ""
                tree.insert("", "end", iid=str(i), values=vals, tags=(tag,) if tag else ())
                shown += 1
                if not r.get("is_void"):
                    shown_valid_sum += r["amount"]

            count_lbl.configure(text=tr("records_stats", shown=shown, net=shown_valid_sum, total=self.last_summary_info.get('total_sum', 0)))

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
                      hover_color=t["primary_hover"], text_color="#FFFFFF", command=self.export_pdf_summary).pack(side="right", padx=4)

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

        def save(event=None):
            raw = e_a.get().strip().replace(",", "")
            if not raw: return
            try:
                amt = float(raw)
                if amt <= 0: return
                dest = self.get_clean_path()
                now_dt = datetime.datetime.now()
                t_stamp = now_dt.strftime("%H%M%S")
                date_tag = now_dt.strftime("%d-%m-%Y")
                file_base = f"{amt:.2f}_{t_stamp}.pdf"
                full_path = os.path.join(dest, file_base)

                u_val = cb_u.get().strip() or "-"
                p_val = e_p.get().strip() or "-"
                n_val = e_name.get().strip() or "-"

                if not REPORTLAB_AVAILABLE:
                    messagebox.showerror("Error", "ReportLab is not installed!")
                    return

                self.printed_receipts_set.add(file_base)
                create_manual_receipt_pdf(full_path, u_val, p_val, n_val, amt, op_dt=now_dt)
                try:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("INSERT INTO manual_tx (unit, plate, insured, amount, created_at, file_name) VALUES (?, ?, ?, ?, ?, ?)",
                              (u_val, p_val, n_val, amt, f"{date_tag} {t_stamp}", file_base))
                    conn.commit()
                    conn.close()
                except Exception as ex_db: log_exception("insert_vault", ex_db)

                if self.auto_print_enabled:
                    self.send_to_thermal_printer_57x90(full_path)

                try: os.startfile(full_path)
                except: pass
                win.destroy()
            except Exception as ex_save:
                messagebox.showerror("Error", f"Failed to generate manual receipt:\n{str(ex_save)}")

        e_a.bind("<Return>", save)
        ctk.CTkButton(win, text=tr("manual_generate_btn"), font=FONT_BTN_MAIN, fg_color=t["success"],
                      hover_color=t["primary_hover"], text_color="#FFFFFF", height=36, command=save).pack(fill="x", padx=18, pady=16)
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
                        "-print-settings", "paper=57 x 90 mm,fit",
                        "-silent",
                        pdf_path
                    ]
                    subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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

    def export_pdf_summary(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error", "ReportLab library required for PDF generation.")
            return
        if not self.last_summary_info or not self.last_generated_file:
            messagebox.showinfo("Notice", "No records available yet. Run extraction first!")
            return

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
                    except: pass

            def _ar(txt):
                try: return get_display(arabic_reshaper.reshape(str(txt)))
                except: return str(txt)

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
                except: pass

            current_calculated[0] = c_sum
            lbl_tot_cash.configure(text=tr("cash_tot_lbl", sum=c_sum))

            pos_val = 0.0
            pos_str = e_pos_in.get().strip().replace(",", "")
            if pos_str:
                try: pos_val = float(pos_str)
                except: pass

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
