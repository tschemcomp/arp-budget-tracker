# -*- coding: utf-8 -*-
# ARP Budget Tracker v3
# Requirements: pip install matplotlib tkcalendar
# Run: python arp_budget_tracker.py

import os
import sys
import sqlite3
import hashlib
import calendar
import csv
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Windows DPI fix
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    from tkcalendar import DateEntry
    HAS_CAL = True
except ImportError:
    HAS_CAL = False

# ============================================================
# CONFIG
# ============================================================
APP_TITLE  = "ARP Budget Tracker"
CURR       = "Rs."
CATEGORIES = ["Income", "Bills", "Variable", "Savings", "Debt"]
MONTHS     = [calendar.month_abbr[m] for m in range(1, 13)]

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_SCRIPT_DIR, "arp_config.txt")
DEFAULT_DB  = os.path.join(_SCRIPT_DIR, "arp_budget.db")

# Light theme colors - explicit so Windows dark mode cannot override
BG_WIN   = "#F0F4F8"
BG_CARD  = "#FFFFFF"
BG_TOTAL = "#FFFDE7"
FG_DARK  = "#212121"
FG_MUTED = "#78909C"
TOP_BG   = "#1E2A3A"

CAT = {
    "Income":   {"hdr": "#2E7D32", "light": "#E8F5E9", "fg": "#1B5E20"},
    "Bills":    {"hdr": "#1565C0", "light": "#E3F2FD", "fg": "#0D47A1"},
    "Variable": {"hdr": "#E65100", "light": "#FFF3E0", "fg": "#BF360C"},
    "Savings":  {"hdr": "#6A1B9A", "light": "#F3E5F5", "fg": "#4A148C"},
    "Debt":     {"hdr": "#B71C1C", "light": "#FFEBEE", "fg": "#7F0000"},
}


# ============================================================
# DB PATH
# ============================================================
def load_db_path():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            p = f.read().strip()
        if p and os.path.exists(os.path.dirname(p) or "."):
            return p
    return None


def save_db_path(path):
    with open(CONFIG_FILE, "w") as f:
        f.write(path)


def pick_db_location(root):
    dlg = tk.Toplevel(root)
    dlg.title("Choose data location")
    dlg.geometry("500x260")
    dlg.resizable(False, False)
    dlg.configure(bg=BG_WIN)
    dlg.transient(root)
    dlg.grab_set()

    result = {"path": None}

    tk.Label(dlg, text="Where should ARP store your budget data?",
             bg=BG_WIN, fg=FG_DARK,
             font=("Helvetica", 12, "bold")).pack(pady=(20, 4))
    tk.Label(dlg,
             text="Pick a cloud-synced folder to share data across Mac and Windows.",
             bg=BG_WIN, fg=FG_MUTED, font=("Helvetica", 10)).pack(pady=(0, 14))

    bf = tk.Frame(dlg, bg=BG_WIN)
    bf.pack(pady=4)

    def _pick(title, suggested_name):
        path = filedialog.asksaveasfilename(
            parent=dlg, title=title,
            initialdir=os.path.expanduser("~"),
            initialfile="arp_budget.db",
            defaultextension=".db",
            filetypes=[("Database", "*.db")])
        if path:
            result["path"] = path
            dlg.destroy()

    def _btn(text, sub, cmd, color):
        f = tk.Frame(bf, bg=BG_CARD,
                     highlightbackground="#C8D0DC", highlightthickness=1)
        f.pack(side="left", padx=8, ipadx=4, ipady=4)
        tk.Label(f, text=text, bg=BG_CARD, fg=color,
                 font=("Helvetica", 10, "bold")).pack(padx=14, pady=(8, 2))
        tk.Label(f, text=sub, bg=BG_CARD, fg=FG_MUTED,
                 font=("Helvetica", 8)).pack(padx=14, pady=(0, 8))
        for w in [f] + list(f.winfo_children()):
            w.bind("<Button-1>", lambda e: cmd())

    _btn("iCloud Drive",  "Mac to Mac/Win sync",  lambda: _pick("Save in iCloud Drive", "iCloud"), "#1565C0")
    _btn("Google Drive",  "Mac + Windows sync",   lambda: _pick("Save in Google Drive",  "GDrive"), "#2E7D32")
    _btn("Local only",    "This computer only",   lambda: _pick("Save locally",          "Local"),  "#555555")

    tk.Label(dlg, text="Change anytime via Settings in the app.",
             bg=BG_WIN, fg=FG_MUTED, font=("Helvetica", 8)).pack(pady=(12, 0))

    root.wait_window(dlg)
    return result["path"]


# ============================================================
# DATABASE
# ============================================================
class Database:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS entries (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     year INTEGER NOT NULL,
                     month INTEGER NOT NULL,
                     category TEXT NOT NULL,
                     name TEXT NOT NULL,
                     budget REAL DEFAULT 0,
                     actual REAL DEFAULT 0,
                     entry_date TEXT,
                     created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     entry_id INTEGER NOT NULL,
                     amount REAL NOT NULL,
                     txn_date TEXT,
                     note TEXT,
                     created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        try:
            c.execute("ALTER TABLE entries ADD COLUMN entry_date TEXT")
        except Exception:
            pass
        self.conn.commit()

    def get_setting(self, k):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return r["value"] if r else None

    def set_setting(self, k, v):
        self.conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))
        self.conn.commit()

    def add_entry(self, year, month, cat, name, budget, actual, edate=None):
        c = self.conn.cursor()
        c.execute("INSERT INTO entries(year,month,category,name,budget,actual,entry_date) VALUES(?,?,?,?,?,?,?)",
                  (year, month, cat, name, budget, actual, edate))
        self.conn.commit()
        return c.lastrowid

    def update_entry(self, eid, name, budget, actual, edate=None):
        self.conn.execute(
            "UPDATE entries SET name=?,budget=?,actual=?,entry_date=? WHERE id=?",
            (name, budget, actual, edate, eid))
        self.conn.commit()

    def delete_entry(self, eid):
        self.conn.execute("DELETE FROM transactions WHERE entry_id=?", (eid,))
        self.conn.execute("DELETE FROM entries WHERE id=?", (eid,))
        self.conn.commit()

    def get_entries(self, year, month, cat=None):
        if cat:
            return self.conn.execute(
                "SELECT * FROM entries WHERE year=? AND month=? AND category=? ORDER BY id",
                (year, month, cat)).fetchall()
        return self.conn.execute(
            "SELECT * FROM entries WHERE year=? AND month=? ORDER BY category,id",
            (year, month)).fetchall()

    def quick_add(self, eid, amount, txn_date=None, note=""):
        txn_date = txn_date or date.today().strftime("%Y-%m-%d")
        self.conn.execute(
            "INSERT INTO transactions(entry_id,amount,txn_date,note) VALUES(?,?,?,?)",
            (eid, amount, txn_date, note))
        self.conn.execute("UPDATE entries SET actual=actual+? WHERE id=?", (amount, eid))
        self.conn.commit()

    def get_transactions(self, eid):
        return self.conn.execute(
            "SELECT * FROM transactions WHERE entry_id=? ORDER BY txn_date,id",
            (eid,)).fetchall()

    def annual_summary(self, year):
        rows = self.conn.execute(
            "SELECT month,category,SUM(budget) b,SUM(actual) a "
            "FROM entries WHERE year=? GROUP BY month,category", (year,)).fetchall()
        r = {c: {m: (0.0, 0.0) for m in range(1, 13)} for c in CATEGORIES}
        for row in rows:
            r[row["category"]][row["month"]] = (row["b"] or 0, row["a"] or 0)
        return r

    def export_month_csv(self, year, month, filepath):
        entries = self.get_entries(year, month)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Category", "Item", "Budget", "Actual", "Difference", "Date"])
            for e in entries:
                diff = (e["actual"] or 0) - (e["budget"] or 0)
                w.writerow([e["category"], e["name"],
                            e["budget"] or 0, e["actual"] or 0,
                            round(diff, 2), e["entry_date"] or ""])

    def export_year_csv(self, year, filepath):
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            header = ["Category"]
            for m in range(1, 13):
                header += [MONTHS[m-1] + " Budget", MONTHS[m-1] + " Actual"]
            header += ["Annual Budget", "Annual Actual"]
            w.writerow(header)
            sm = self.annual_summary(year)
            for cat in CATEGORIES:
                row = [cat]
                ab = aa = 0
                for m in range(1, 13):
                    b, a = sm[cat][m]
                    row += [round(b, 2), round(a, 2)]
                    ab += b; aa += a
                row += [round(ab, 2), round(aa, 2)]
                w.writerow(row)

    def export_transactions_csv(self, year, month, filepath):
        entries = self.get_entries(year, month)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Category", "Item", "Date", "Amount", "Note"])
            for e in entries:
                txns = self.get_transactions(e["id"])
                if txns:
                    for t in txns:
                        w.writerow([e["category"], e["name"],
                                    t["txn_date"], t["amount"], t["note"] or ""])
                else:
                    w.writerow([e["category"], e["name"],
                                e["entry_date"] or "", e["actual"] or 0, ""])


# ============================================================
# HELPERS
# ============================================================
def _hash(pw):
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _fmt(v):
    return "{} {:,.2f}".format(CURR, v)


def _strip(s):
    return float(str(s).replace(CURR, "").replace(",", "").strip() or 0)


def _apply_theme(root):
    try:
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=BG_WIN, foreground=FG_DARK,
                        fieldbackground=BG_CARD)
    except Exception:
        pass
    root.configure(bg=BG_WIN)
    root.option_add("*Background",       BG_WIN)
    root.option_add("*background",       BG_WIN)
    root.option_add("*Foreground",       FG_DARK)
    root.option_add("*foreground",       FG_DARK)
    root.option_add("*Entry.Background", BG_CARD)
    root.option_add("*Entry.Foreground", FG_DARK)


def _entry_field(parent, label, row, val="", show=""):
    tk.Label(parent, text=label, bg=BG_CARD, fg=FG_DARK).grid(
        row=row, column=0, sticky="e", padx=8, pady=5)
    e = tk.Entry(parent, width=22, show=show, relief="solid", bd=1,
                 bg=BG_CARD, fg=FG_DARK, insertbackground=FG_DARK)
    e.insert(0, str(val))
    e.grid(row=row, column=1, padx=8, pady=5, sticky="w")
    return e


def _date_field(parent, row, init=""):
    tk.Label(parent, text="Date:", bg=BG_CARD, fg=FG_DARK).grid(
        row=row, column=0, sticky="e", padx=8, pady=5)
    if HAS_CAL:
        try:
            d0 = datetime.strptime(init, "%Y-%m-%d").date()
        except Exception:
            d0 = date.today()
        cal = DateEntry(parent, width=16,
                        background="#1565C0", foreground="white",
                        borderwidth=1, date_pattern="yyyy-mm-dd",
                        selectbackground="#1565C0")
        cal.set_date(d0)
        cal.grid(row=row, column=1, padx=8, pady=5, sticky="w")
        return lambda: cal.get_date().strftime("%Y-%m-%d")
    else:
        e = tk.Entry(parent, width=16, relief="solid", bd=1,
                     bg=BG_CARD, fg=FG_DARK, insertbackground=FG_DARK)
        e.insert(0, init or date.today().strftime("%Y-%m-%d"))
        e.grid(row=row, column=1, padx=8, pady=5, sticky="w")
        tk.Label(parent, text="yyyy-mm-dd", bg=BG_CARD, fg=FG_MUTED,
                 font=("Helvetica", 8)).grid(row=row, column=2, sticky="w")
        return lambda: e.get()


# ============================================================
# LOGIN
# ============================================================
class LoginWindow:
    def __init__(self, db, on_success):
        self.db = db
        self.on_success = on_success
        r = tk.Tk()
        self.root = r
        r.title(APP_TITLE + " - Login")
        r.geometry("420x320")
        r.resizable(False, False)
        _apply_theme(r)
        r.lift()
        r.attributes("-topmost", True)
        r.after(400, lambda: r.attributes("-topmost", False))

        first = db.get_setting("password_hash") is None

        tk.Label(r, text="ARP", font=("Helvetica", 40, "bold"),
                 bg=BG_WIN, fg=TOP_BG).pack(pady=(22, 0))
        tk.Label(r, text="Budget Tracker", font=("Helvetica", 12),
                 bg=BG_WIN, fg=FG_MUTED).pack()

        frm = tk.Frame(r, bg=BG_WIN)
        frm.pack(pady=16)

        if first:
            tk.Label(frm, text="Create a password:", bg=BG_WIN, fg=FG_DARK).grid(
                row=0, columnspan=2, pady=(0, 8))
            self.pw  = _entry_field(frm, "Password:", 1, show="*")
            self.pw2 = _entry_field(frm, "Confirm:",  2, show="*")
            tk.Button(r, text="Create Account", command=self._create,
                      bg="#2E7D32", fg="white", font=("Helvetica", 10, "bold"),
                      padx=22, pady=7, relief="flat", cursor="hand2").pack(pady=10)
        else:
            tk.Label(frm, text="Enter your password:", bg=BG_WIN, fg=FG_DARK).grid(
                row=0, columnspan=2, pady=(0, 8))
            self.pw = _entry_field(frm, "Password:", 1, show="*")
            self.pw.bind("<Return>", lambda e: self._login())
            tk.Button(r, text="Login", command=self._login,
                      bg="#1565C0", fg="white", font=("Helvetica", 10, "bold"),
                      padx=30, pady=7, relief="flat", cursor="hand2").pack(pady=10)

        db_short = db.path[-55:] if len(db.path) > 55 else db.path
        tk.Label(r, text="Data: " + db_short, bg=BG_WIN, fg=FG_MUTED,
                 font=("Helvetica", 8)).pack()

        self.pw.focus_set()
        r.mainloop()

    def _create(self):
        pw, pw2 = self.pw.get(), self.pw2.get()
        if len(pw) < 4:
            messagebox.showwarning("Too short", "Use at least 4 characters.")
            return
        if pw != pw2:
            messagebox.showerror("Mismatch", "Passwords do not match.")
            return
        self.db.set_setting("password_hash", _hash(pw))
        messagebox.showinfo("Done", "Account created!")
        self.root.destroy()
        self.on_success()

    def _login(self):
        if _hash(self.pw.get()) == self.db.get_setting("password_hash"):
            self.root.destroy()
            self.on_success()
        else:
            messagebox.showerror("Wrong password", "Try again.")
            self.pw.delete(0, tk.END)


# ============================================================
# MAIN APP
# ============================================================
class BudgetApp:
    def __init__(self, db):
        self.db = db
        r = tk.Tk()
        self.root = r
        r.title(APP_TITLE)
        r.geometry("1280x860")
        r.minsize(1060, 700)
        _apply_theme(r)
        r.lift()
        r.attributes("-topmost", True)
        r.after(400, lambda: r.attributes("-topmost", False))

        now = datetime.now()
        self.cur_year  = tk.IntVar(value=now.year)
        self.cur_month = tk.IntVar(value=now.month)
        self.panels    = {}

        self._build_ui()
        self._refresh_all()
        r.mainloop()

    # ----------------------------------------------------------
    def _build_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg=TOP_BG, height=56)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="ARP", bg=TOP_BG, fg="white",
                 font=("Helvetica", 22, "bold")).pack(side="left", padx=18)
        tk.Label(top, text="Budget Tracker", bg=TOP_BG, fg="#90CAF9",
                 font=("Helvetica", 11)).pack(side="left")

        ctrl = tk.Frame(top, bg=TOP_BG)
        ctrl.pack(side="right", padx=14)

        def top_btn(text, cmd, fg):
            tk.Button(ctrl, text=text, command=cmd,
                      bg="#263238", fg=fg,
                      font=("Helvetica", 9, "bold"),
                      padx=10, pady=4, relief="flat", cursor="hand2",
                      activebackground="#37474F", activeforeground=fg
                      ).pack(side="left", padx=4)

        top_btn("Export CSV", self._export_dialog,   "#80CBC4")
        top_btn("Settings",   self._settings_dialog, "#B0BEC5")

        period = tk.Frame(top, bg=TOP_BG)
        period.pack(side="right", padx=10)
        tk.Label(period, text="Month:", bg=TOP_BG, fg="white",
                 font=("Helvetica", 10)).pack(side="left", padx=(0, 4))
        self.month_cb = ttk.Combobox(period, values=MONTHS, width=6,
                                     state="readonly", font=("Helvetica", 10))
        self.month_cb.set(MONTHS[self.cur_month.get() - 1])
        self.month_cb.pack(side="left")
        self.month_cb.bind("<<ComboboxSelected>>", self._on_month)

        tk.Label(period, text="  Year:", bg=TOP_BG, fg="white",
                 font=("Helvetica", 10)).pack(side="left", padx=(10, 4))
        year_cb = ttk.Combobox(period, textvariable=self.cur_year,
                               values=list(range(2020, 2036)), width=6,
                               state="readonly", font=("Helvetica", 10))
        year_cb.pack(side="left")
        year_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_all())

        # Notebook
        style = ttk.Style()
        style.configure("TNotebook", background=BG_WIN, borderwidth=0)
        style.configure("TNotebook.Tab", background="#DDE3EC", foreground=FG_DARK,
                        padding=[14, 6], font=("Helvetica", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", BG_CARD)],
                  foreground=[("selected", TOP_BG)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=10)

        self.tab_monthly = tk.Frame(nb, bg=BG_WIN)
        self.tab_charts  = tk.Frame(nb, bg=BG_WIN)
        self.tab_annual  = tk.Frame(nb, bg=BG_WIN)
        nb.add(self.tab_monthly, text="  Monthly Entries  ")
        nb.add(self.tab_charts,  text="  Dashboard  ")
        nb.add(self.tab_annual,  text="  Annual Report  ")

        self._build_monthly()
        self._build_charts()
        self._build_annual()

    def _on_month(self, _=None):
        self.cur_month.set(MONTHS.index(self.month_cb.get()) + 1)
        self._refresh_all()

    # ----------------------------------------------------------
    def _build_monthly(self):
        sf = tk.Frame(self.tab_monthly, bg=BG_WIN)
        sf.pack(fill="x", padx=10, pady=(8, 4))
        self.lbl_inc  = self._sum_box(sf, "Income",        "#2E7D32")
        self.lbl_exp  = self._sum_box(sf, "Expenses",      "#B71C1C")
        self.lbl_sav  = self._sum_box(sf, "Savings",       "#6A1B9A")
        self.lbl_left = self._sum_box(sf, "Left to Spend", "#1565C0")

        grid = tk.Frame(self.tab_monthly, bg=BG_WIN)
        grid.pack(fill="both", expand=True, padx=10, pady=4)
        pos = {"Income":(0,0), "Bills":(0,1), "Variable":(1,0),
               "Savings":(1,1), "Debt":(2,0)}
        for cat, (r, c) in pos.items():
            self._build_panel(grid, cat, r, c)
        for r in range(3): grid.rowconfigure(r, weight=1)
        for c in range(2): grid.columnconfigure(c, weight=1)

    def _sum_box(self, parent, title, color):
        box = tk.Frame(parent, bg=BG_CARD,
                       highlightbackground="#C8D0DC", highlightthickness=1)
        box.pack(side="left", fill="both", expand=True, padx=5, pady=4)
        tk.Label(box, text=title, bg=BG_CARD, fg=FG_MUTED,
                 font=("Helvetica", 9)).pack(anchor="w", padx=12, pady=(6, 0))
        lbl = tk.Label(box, text=CURR + " 0.00", bg=BG_CARD, fg=color,
                       font=("Helvetica", 15, "bold"))
        lbl.pack(anchor="w", padx=12, pady=(0, 6))
        return lbl

    def _build_panel(self, parent, cat, row, col):
        t = CAT[cat]
        card = tk.Frame(parent, bg=BG_CARD,
                        highlightbackground="#C8D0DC", highlightthickness=1)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        hdr = tk.Frame(card, bg=t["hdr"], height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=cat, bg=t["hdr"], fg="white",
                 font=("Helvetica", 11, "bold")).pack(side="left", padx=10)

        bf = tk.Frame(hdr, bg=t["hdr"])
        bf.pack(side="right", padx=5)

        def fb(text, cmd, bg, fg):
            return tk.Button(bf, text=text, command=cmd,
                             bg=bg, fg=fg, bd=0, padx=7, pady=2,
                             font=("Helvetica", 8, "bold"), relief="flat",
                             cursor="hand2", activebackground=bg, activeforeground=fg)

        fb("+ Add",     lambda c=cat: self._add(c),       "#FFFFFF", t["hdr"]).pack(side="left", padx=2)
        fb("Quick Add", lambda c=cat: self._quick_add(c), "#FFF9C4", "#5D4037").pack(side="left", padx=2)
        fb("Log",       lambda c=cat: self._show_log(c),  "#E8F5E9", "#2E7D32").pack(side="left", padx=2)
        fb("Edit",      lambda c=cat: self._edit(c),      "#E3F2FD", "#1565C0").pack(side="left", padx=2)
        fb("Delete",    lambda c=cat: self._delete(c),    "#FFEBEE", "#B71C1C").pack(side="left", padx=2)

        sn = cat + ".Treeview"
        style = ttk.Style()
        style.configure(sn, background=BG_CARD, fieldbackground=BG_CARD,
                        foreground=FG_DARK, rowheight=25, font=("Helvetica", 9))
        style.configure(sn + ".Heading", background=t["light"],
                        foreground=t["fg"], font=("Helvetica", 9, "bold"), relief="flat")
        style.map(sn,
                  background=[("selected", t["hdr"])],
                  foreground=[("selected", "#FFFFFF")])

        cols = ("name", "budget", "actual", "date")
        tree = ttk.Treeview(card, columns=cols, show="headings",
                            height=5, style=sn)
        tree.heading("name",   text="Item")
        tree.heading("budget", text="Budget")
        tree.heading("actual", text="Actual")
        tree.heading("date",   text="Date")
        tree.column("name",   width=140, anchor="w")
        tree.column("budget", width=90,  anchor="e")
        tree.column("actual", width=90,  anchor="e")
        tree.column("date",   width=85,  anchor="center")
        tree.tag_configure("odd",  background=BG_CARD)
        tree.tag_configure("even", background=t["light"])

        sb = ttk.Scrollbar(card, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tot = tk.Frame(card, bg=BG_TOTAL)
        tot.pack(fill="x")
        tk.Label(tot, text="Total", bg=BG_TOTAL,
                 font=("Helvetica", 9, "bold"), fg=FG_DARK).pack(side="left", padx=10, pady=4)
        lbl_a = tk.Label(tot, text=CURR + " 0.00", bg=BG_TOTAL,
                         font=("Helvetica", 9, "bold"), fg=t["hdr"])
        lbl_a.pack(side="right", padx=14, pady=4)
        lbl_b = tk.Label(tot, text=CURR + " 0.00", bg=BG_TOTAL,
                         font=("Helvetica", 9), fg=FG_MUTED)
        lbl_b.pack(side="right", padx=14, pady=4)

        self.panels[cat] = {"tree": tree, "tb": lbl_b, "ta": lbl_a}

    def _build_charts(self):
        self.charts_wrap = tk.Frame(self.tab_charts, bg=BG_WIN)
        self.charts_wrap.pack(fill="both", expand=True, padx=10, pady=10)

    def _build_annual(self):
        self.annual_wrap = tk.Frame(self.tab_annual, bg=BG_WIN)
        self.annual_wrap.pack(fill="both", expand=True, padx=10, pady=10)

    # ----------------------------------------------------------
    def _add(self, cat):
        dlg = EntryDialog(self.root, "Add to " + cat)
        if dlg.result:
            n, b, a, d = dlg.result
            self.db.add_entry(self.cur_year.get(), self.cur_month.get(),
                              cat, n, b, a, d)
            self._refresh_all()

    def _quick_add(self, cat):
        tree = self.panels[cat]["tree"]
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Select a row first",
                "Click on an item row first, then press Quick Add.")
            return
        item = tree.item(sel[0])
        eid  = int(item["tags"][0])
        name = item["values"][0]
        dlg  = QuickAddDialog(self.root, name)
        if dlg.result:
            amount, txn_date, note = dlg.result
            self.db.quick_add(eid, amount, txn_date, note)
            self._refresh_all()

    def _show_log(self, cat):
        tree = self.panels[cat]["tree"]
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Click on an item to see its log.")
            return
        item = tree.item(sel[0])
        eid  = int(item["tags"][0])
        name = item["values"][0]
        txns = self.db.get_transactions(eid)
        TransactionLogDialog(self.root, name, txns)

    def _edit(self, cat):
        tree = self.panels[cat]["tree"]
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Click on a row first.")
            return
        item = tree.item(sel[0])
        eid  = int(item["tags"][0])
        v    = item["values"]
        dlg  = EntryDialog(self.root, "Edit " + cat,
                           initial=(v[0], _strip(v[1]), _strip(v[2]),
                                    v[3] if len(v) > 3 else ""))
        if dlg.result:
            n, b, a, d = dlg.result
            self.db.update_entry(eid, n, b, a, d)
            self._refresh_all()

    def _delete(self, cat):
        tree = self.panels[cat]["tree"]
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Click on a row first.")
            return
        name = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Delete", "Delete '" + name + "' and all its transactions?"):
            self.db.delete_entry(int(tree.item(sel[0])["tags"][0]))
            self._refresh_all()

    # ----------------------------------------------------------
    def _refresh_all(self):
        self.month_cb.set(MONTHS[self.cur_month.get() - 1])
        self._refresh_monthly()
        self._refresh_charts()
        self._refresh_annual()

    def _refresh_monthly(self):
        y, m   = self.cur_year.get(), self.cur_month.get()
        totals = {c: [0.0, 0.0] for c in CATEGORIES}

        for cat in CATEGORIES:
            p    = self.panels[cat]
            tree = p["tree"]
            for ch in tree.get_children():
                tree.delete(ch)
            tb = ta = 0.0
            for i, e in enumerate(self.db.get_entries(y, m, cat)):
                tag = "even" if i % 2 == 0 else "odd"
                tree.insert("", "end",
                            values=(e["name"], _fmt(e["budget"]),
                                    _fmt(e["actual"]), e["entry_date"] or ""),
                            tags=(str(e["id"]), tag))
                tb += e["budget"] or 0
                ta += e["actual"] or 0
            totals[cat] = [tb, ta]
            p["tb"].config(text=_fmt(tb))
            p["ta"].config(text=_fmt(ta))

        inc  = totals["Income"][1]
        exp  = totals["Bills"][1] + totals["Variable"][1] + totals["Debt"][1]
        sav  = totals["Savings"][1]
        left = inc - exp - sav
        self.lbl_inc.config(text=_fmt(inc))
        self.lbl_exp.config(text=_fmt(exp))
        self.lbl_sav.config(text=_fmt(sav))
        self.lbl_left.config(text=_fmt(left),
                             fg="#2E7D32" if left >= 0 else "#B71C1C")
        self._totals = totals

    def _refresh_charts(self):
        for w in self.charts_wrap.winfo_children():
            w.destroy()
        tot = getattr(self, "_totals", {c: [0, 0] for c in CATEGORIES})
        fig = Figure(figsize=(11, 6.5), facecolor=BG_WIN)

        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor(BG_WIN)
        pc = ["Bills", "Variable", "Savings", "Debt"]
        vals = [tot[c][0] for c in pc]
        if any(v > 0 for v in vals):
            data = [(l, v, CAT[l]["hdr"]) for l, v in zip(pc, vals) if v > 0]
            ax1.pie([d[1] for d in data], labels=[d[0] for d in data],
                    colors=[d[2] for d in data], autopct="%1.0f%%",
                    startangle=90, textprops={"fontsize": 10},
                    wedgeprops={"edgecolor": "white", "linewidth": 2})
        else:
            ax1.text(0.5, 0.5, "No budget data yet",
                     ha="center", va="center", fontsize=12, color=FG_MUTED)
            ax1.set_xticks([]); ax1.set_yticks([])
        ax1.set_title("Budget Composition", fontsize=13, fontweight="bold", pad=14)

        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor("#FAFAFA")
        bc = ["Bills", "Variable", "Savings", "Debt"]
        bv = [tot[c][0] for c in bc]
        av = [tot[c][1] for c in bc]
        yp = range(len(bc)); h = 0.35
        ax2.barh([p + h/2 for p in yp], bv, h, label="Budget",
                 color=[CAT[c]["hdr"] for c in bc], alpha=0.45)
        ax2.barh([p - h/2 for p in yp], av, h, label="Actual",
                 color=[CAT[c]["hdr"] for c in bc])
        ax2.set_yticks(list(yp))
        ax2.set_yticklabels(bc)
        ax2.set_title("Budget vs Actual", fontsize=13, fontweight="bold", pad=14)
        ax2.legend(); ax2.grid(axis="x", alpha=0.3)
        ax2.set_xlabel("Amount (" + CURR + ")")
        fig.tight_layout(pad=2)

        canvas = FigureCanvasTkAgg(fig, master=self.charts_wrap)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=BG_WIN)
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _refresh_annual(self):
        for w in self.annual_wrap.winfo_children():
            w.destroy()
        y  = self.cur_year.get()
        sm = self.db.annual_summary(y)

        tk.Label(self.annual_wrap, text="Annual Report - " + str(y),
                 bg=BG_WIN, fg=TOP_BG,
                 font=("Helvetica", 15, "bold")).pack(pady=(0, 8))

        tbl = tk.Frame(self.annual_wrap, bg=BG_WIN)
        tbl.pack(fill="x", padx=14)
        headers = ["Category"] + list(MONTHS) + ["Total"]
        for i, h in enumerate(headers):
            tk.Label(tbl, text=h, bg=TOP_BG, fg="white",
                     font=("Helvetica", 9, "bold"),
                     padx=6, pady=5
                     ).grid(row=0, column=i, sticky="nsew", padx=1, pady=1)

        for r, cat in enumerate(CATEGORIES, 1):
            tk.Label(tbl, text=cat,
                     bg=CAT[cat]["hdr"], fg="white",
                     font=("Helvetica", 9, "bold"), padx=8, pady=4
                     ).grid(row=r, column=0, sticky="nsew", padx=1, pady=1)
            row_total = 0
            for m in range(1, 13):
                a = sm[cat][m][1]; row_total += a
                bg = CAT[cat]["light"] if r % 2 == 0 else BG_CARD
                tk.Label(tbl, text=("{:,.0f}".format(a) if a else "-"),
                         bg=bg, fg=FG_DARK, font=("Helvetica", 9), padx=4, pady=4
                         ).grid(row=r, column=m, sticky="nsew", padx=1, pady=1)
            tk.Label(tbl, text=CURR + "{:,.0f}".format(row_total),
                     bg=BG_TOTAL, fg=CAT[cat]["hdr"],
                     font=("Helvetica", 9, "bold"), padx=6, pady=4
                     ).grid(row=r, column=13, sticky="nsew", padx=1, pady=1)

        for c in range(14):
            tbl.columnconfigure(c, weight=1)

        fig = Figure(figsize=(11, 4), facecolor=BG_WIN)
        ax  = fig.add_subplot(1, 1, 1)
        ax.set_facecolor("#FAFAFA")
        for cat in CATEGORIES:
            ax.plot(MONTHS, [sm[cat][m][1] for m in range(1, 13)],
                    marker="o", label=cat,
                    color=CAT[cat]["hdr"], linewidth=2, markersize=5)
        ax.set_title("Monthly Trend - " + str(y), fontsize=12, fontweight="bold")
        ax.set_ylabel("Amount (" + CURR + ")")
        ax.legend(ncol=5); ax.grid(alpha=0.25)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.annual_wrap)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=BG_WIN)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=14, pady=10)

    # ----------------------------------------------------------
    def _export_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Export to CSV")
        dlg.geometry("420x240")
        dlg.resizable(False, False)
        dlg.configure(bg=BG_WIN)
        dlg.transient(self.root); dlg.grab_set()

        y, m = self.cur_year.get(), self.cur_month.get()
        mn   = MONTHS[m - 1]

        tk.Label(dlg, text="Export to CSV", bg=BG_WIN, fg=FG_DARK,
                 font=("Helvetica", 13, "bold")).pack(pady=(18, 4))
        tk.Label(dlg, text="Opens in Excel, Google Sheets, etc.",
                 bg=BG_WIN, fg=FG_MUTED, font=("Helvetica", 9)).pack()

        def export(mode):
            names = {"month": "ARP_" + str(y) + "_" + mn + "_summary.csv",
                     "year":  "ARP_" + str(y) + "_annual.csv",
                     "txns":  "ARP_" + str(y) + "_" + mn + "_transactions.csv"}
            path = filedialog.asksaveasfilename(
                parent=dlg, title="Save CSV",
                initialfile=names[mode], defaultextension=".csv",
                filetypes=[("CSV", "*.csv")])
            if not path: return
            try:
                if mode == "month": self.db.export_month_csv(y, m, path)
                elif mode == "year": self.db.export_year_csv(y, path)
                else: self.db.export_transactions_csv(y, m, path)
                dlg.destroy()
                messagebox.showinfo("Exported", "Saved to:\n" + path)
            except Exception as ex:
                messagebox.showerror("Export failed", str(ex))

        bf = tk.Frame(dlg, bg=BG_WIN); bf.pack(pady=18)

        def cbtn(text, sub, cmd, color):
            f = tk.Frame(bf, bg=BG_CARD,
                         highlightbackground="#C8D0DC", highlightthickness=1)
            f.pack(side="left", padx=6, ipadx=2, ipady=2)
            tk.Label(f, text=text, bg=BG_CARD, fg=color,
                     font=("Helvetica", 10, "bold")).pack(padx=12, pady=(8, 2))
            tk.Label(f, text=sub, bg=BG_CARD, fg=FG_MUTED,
                     font=("Helvetica", 8)).pack(padx=12, pady=(0, 8))
            for w in [f] + list(f.winfo_children()):
                w.bind("<Button-1>", lambda e: cmd())

        cbtn(mn + " " + str(y), "Budget & Actual",    lambda: export("month"), "#1565C0")
        cbtn("Full year " + str(y), "12-month table", lambda: export("year"),  "#2E7D32")
        cbtn(mn + " log", "Every transaction",        lambda: export("txns"),  "#E65100")

        tk.Button(dlg, text="Cancel", command=dlg.destroy,
                  bg=BG_WIN, fg=FG_MUTED, relief="flat").pack(pady=4)

    def _settings_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Settings")
        dlg.geometry("500x200")
        dlg.resizable(False, False)
        dlg.configure(bg=BG_WIN)
        dlg.transient(self.root); dlg.grab_set()

        tk.Label(dlg, text="Settings", bg=BG_WIN, fg=FG_DARK,
                 font=("Helvetica", 13, "bold")).pack(pady=(18, 4))
        short = ("..." + self.db.path[-58:]) if len(self.db.path) > 60 else self.db.path
        tk.Label(dlg, text="Data file:\n" + short,
                 bg=BG_WIN, fg=FG_MUTED, font=("Helvetica", 9),
                 justify="center").pack(pady=4)

        bf = tk.Frame(dlg, bg=BG_WIN); bf.pack(pady=14)

        def change_loc():
            new_path = pick_db_location(dlg)
            if new_path:
                import shutil
                try:
                    if os.path.exists(self.db.path) and self.db.path != new_path:
                        shutil.copy2(self.db.path, new_path)
                except Exception:
                    pass
                save_db_path(new_path)
                dlg.destroy()
                messagebox.showinfo("Restart required",
                    "Data location updated.\nPlease restart the app.")

        tk.Button(bf, text="Change data location", command=change_loc,
                  bg="#1565C0", fg="white", font=("Helvetica", 9, "bold"),
                  padx=14, pady=6, relief="flat", cursor="hand2").pack(side="left", padx=8)
        tk.Button(bf, text="Close", command=dlg.destroy,
                  bg=BG_WIN, fg=FG_MUTED, relief="flat", padx=12).pack(side="left", padx=8)


# ============================================================
# DIALOGS
# ============================================================
class EntryDialog:
    def __init__(self, parent, title, initial=("", 0.0, 0.0, "")):
        self.result = None
        top = tk.Toplevel(parent)
        top.title(title)
        top.geometry("400x250")
        top.transient(parent); top.grab_set()
        top.resizable(False, False)
        top.configure(bg=BG_CARD)

        f = tk.Frame(top, bg=BG_CARD, padx=20, pady=14)
        f.pack(fill="both", expand=True)

        self.name_e   = _entry_field(f, "Item Name:",         0, initial[0])
        self.budget_e = _entry_field(f, "Budget (" + CURR + "):", 1, initial[1])
        self.actual_e = _entry_field(f, "Actual (" + CURR + "):", 2, initial[2])
        self._get_date = _date_field(f, 3, initial[3] if len(initial) > 3 else "")

        btns = tk.Frame(f, bg=BG_CARD)
        btns.grid(row=4, column=0, columnspan=3, pady=14)
        tk.Button(btns, text="Save", command=self._save,
                  bg="#2E7D32", fg="white", padx=22, relief="flat",
                  font=("Helvetica", 9, "bold"), cursor="hand2").pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=top.destroy,
                  padx=16, relief="flat", cursor="hand2").pack(side="left", padx=6)

        self.top = top
        self.name_e.focus_set()
        top.bind("<Return>", lambda e: self._save())
        parent.wait_window(top)

    def _save(self):
        name = self.name_e.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Item name is required.")
            return
        try:
            b = float(self.budget_e.get() or 0)
            a = float(self.actual_e.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid", "Budget and Actual must be numbers.")
            return
        self.result = (name, b, a, self._get_date())
        self.top.destroy()


class QuickAddDialog:
    def __init__(self, parent, item_name):
        self.result = None
        top = tk.Toplevel(parent)
        top.title("Quick Add")
        top.geometry("360x230")
        top.transient(parent); top.grab_set()
        top.resizable(False, False)
        top.configure(bg=BG_CARD)

        f = tk.Frame(top, bg=BG_CARD, padx=22, pady=16)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Adding to: " + item_name,
                 bg=BG_CARD, fg=FG_MUTED,
                 font=("Helvetica", 9)).grid(row=0, column=0, columnspan=2, sticky="w")

        self.amt_e     = _entry_field(f, "Amount (" + CURR + "):", 1)
        self._get_date = _date_field(f, 2, "")

        tk.Label(f, text="Note (optional):", bg=BG_CARD, fg=FG_DARK).grid(
            row=3, column=0, sticky="e", pady=4, padx=8)
        self.note_e = tk.Entry(f, width=22, relief="solid", bd=1,
                               bg=BG_CARD, fg=FG_DARK, insertbackground=FG_DARK)
        self.note_e.grid(row=3, column=1, pady=4, padx=8, sticky="w")

        btns = tk.Frame(f, bg=BG_CARD)
        btns.grid(row=4, column=0, columnspan=2, pady=14)
        tk.Button(btns, text="Add", command=self._save,
                  bg="#E65100", fg="white", padx=20, relief="flat",
                  font=("Helvetica", 9, "bold"), cursor="hand2").pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=top.destroy,
                  padx=14, relief="flat", cursor="hand2").pack(side="left", padx=6)

        self.top = top
        self.amt_e.focus_set()
        top.bind("<Return>", lambda e: self._save())
        parent.wait_window(top)

    def _save(self):
        try:
            v = float(self.amt_e.get())
            if v <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Enter a positive number.")
            return
        self.result = (v, self._get_date(), self.note_e.get().strip())
        self.top.destroy()


class TransactionLogDialog:
    def __init__(self, parent, item_name, txns):
        top = tk.Toplevel(parent)
        top.title("Log - " + item_name)
        top.geometry("520x340")
        top.transient(parent); top.grab_set()
        top.configure(bg=BG_WIN)

        tk.Label(top, text="Transactions: " + item_name,
                 bg=BG_WIN, fg=FG_DARK,
                 font=("Helvetica", 12, "bold")).pack(pady=(14, 6), padx=16, anchor="w")

        cols = ("date", "amount", "note")
        tree = ttk.Treeview(top, columns=cols, show="headings", height=10)
        tree.heading("date",   text="Date")
        tree.heading("amount", text="Amount (" + CURR + ")")
        tree.heading("note",   text="Note")
        tree.column("date",   width=110, anchor="center")
        tree.column("amount", width=130, anchor="e")
        tree.column("note",   width=240, anchor="w")

        total = 0.0
        for t in txns:
            tree.insert("", "end",
                        values=(t["txn_date"] or "", _fmt(t["amount"]),
                                t["note"] or ""))
            total += t["amount"] or 0
        tree.pack(fill="both", expand=True, padx=14, pady=4)

        bot = tk.Frame(top, bg=BG_TOTAL)
        bot.pack(fill="x")
        tk.Label(bot, text="Total: " + _fmt(total),
                 bg=BG_TOTAL, fg="#1565C0",
                 font=("Helvetica", 10, "bold")).pack(side="right", padx=18, pady=6)

        if not txns:
            tk.Label(top, text="No transactions yet. Use Quick Add to log spends.",
                     bg=BG_WIN, fg=FG_MUTED, font=("Helvetica", 9)).pack(pady=10)

        tk.Button(top, text="Close", command=top.destroy,
                  bg=BG_WIN, fg=FG_MUTED, relief="flat").pack(pady=8)


# ============================================================
# ENTRY POINT
# ============================================================
def main():
    print("Starting ARP Budget Tracker...")

    root = tk.Tk()
    root.geometry("1x1+0+0")  # tiny visible window so dialogs have a parent
    root.lift()
    root.attributes("-topmost", True)
    _apply_theme(root)

    db_path = load_db_path()
    if db_path is None:
        chosen = pick_db_location(root)
        if chosen is None:
            chosen = DEFAULT_DB
        save_db_path(chosen)
        db_path = chosen

    root.destroy()

    db = Database(db_path)
    LoginWindow(db, on_success=lambda: BudgetApp(db))


if __name__ == "__main__":
    main()
