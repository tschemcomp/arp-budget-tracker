# -*- coding: utf-8 -*-
"""
ARP Budget Tracker - Card Layout
Matches the original screenshot exactly with light background.
Windows / Python 3.13 | stdlib only (matplotlib optional)
"""

import os
import sqlite3
import hashlib
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
    print("matplotlib OK, version:", matplotlib.__version__)
except Exception as _mpl_err:
    HAS_MPL = False
    print("matplotlib FAILED:", _mpl_err)

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
APP_TITLE  = "ARP Budget Tracker"
CURR       = "\u20b9"
CATEGORIES = ["Income", "Bills", "Variable", "Savings", "Debt"]
MONTHS     = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]

# Card header colours (matching screenshot)
CAT_HDR = {
    "Income":   "#4CAF50",
    "Bills":    "#2196F3",
    "Variable": "#FF9800",
    "Savings":  "#9C27B0",
    "Debt":     "#F44336",
}
# Light tint for card body / table rows
CAT_LIGHT = {
    "Income":   "#F1F8F1",
    "Bills":    "#E3F2FD",
    "Variable": "#FFF8F0",
    "Savings":  "#F8F0FF",
    "Debt":     "#FFF0F0",
}

BG_WIN   = "#F0F0F0"
BG_CARD  = "#FFFFFF"
BG_TOTAL = "#FFFDE7"
FG_DARK  = "#212121"
FG_MUTED = "#757575"
TOP_BG   = "#1E2A3A"

# ═══════════════════════════════════════════════════════════════
# DB PATH
# ═══════════════════════════════════════════════════════════════
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = None
for _c in [
    os.path.join(SCRIPT_DIR, "arp_budget.db"),
    os.path.join(os.path.expanduser("~"), "Desktop", "arp_budget.db"),
]:
    if os.path.exists(_c):
        DB_PATH = _c
        break
if DB_PATH is None:
    DB_PATH = os.path.join(SCRIPT_DIR, "arp_budget.db")

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
class DB:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._ensure()

    def _ensure(self):
        c = self.conn
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("""CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL, month INTEGER NOT NULL,
            category TEXT NOT NULL, name TEXT NOT NULL,
            budget REAL DEFAULT 0, actual REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, entry_date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL, amount REAL NOT NULL,
            txn_date TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.commit()

    def get_setting(self, k):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return r["value"] if r else None

    def set_setting(self, k, v):
        self.conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))
        self.conn.commit()

    def get_entries(self, year, month, category=None):
        if category:
            return self.conn.execute(
                "SELECT * FROM entries WHERE year=? AND month=? AND category=? ORDER BY id",
                (year, month, category)).fetchall()
        return self.conn.execute(
            "SELECT * FROM entries WHERE year=? AND month=? ORDER BY category,id",
            (year, month)).fetchall()

    def add_entry(self, year, month, cat, name, budget, actual, edate):
        c = self.conn.cursor()
        c.execute("INSERT INTO entries(year,month,category,name,budget,actual,entry_date)"
                  " VALUES(?,?,?,?,?,?,?)",
                  (year, month, cat, name, budget, actual, edate))
        self.conn.commit()
        return c.lastrowid

    def update_entry(self, eid, year, month, cat, name, budget, actual, edate):
        self.conn.execute(
            "UPDATE entries SET year=?,month=?,category=?,name=?,"
            "budget=?,actual=?,entry_date=? WHERE id=?",
            (year, month, cat, name, budget, actual, edate, eid))
        self.conn.commit()

    def delete_entry(self, eid):
        self.conn.execute("DELETE FROM transactions WHERE entry_id=?", (eid,))
        self.conn.execute("DELETE FROM entries WHERE id=?", (eid,))
        self.conn.commit()

    def get_year_totals(self, year):
        r = self.conn.execute(
            "SELECT SUM(budget) b, SUM(actual) a FROM entries WHERE year=?",
            (year,)).fetchone()
        return (r["b"] or 0, r["a"] or 0)

    def get_cat_totals(self, year, month):
        return self.conn.execute(
            "SELECT category, SUM(budget) b, SUM(actual) a "
            "FROM entries WHERE year=? AND month=? GROUP BY category",
            (year, month)).fetchall()

    def get_transactions(self, eid):
        return self.conn.execute(
            "SELECT * FROM transactions WHERE entry_id=? ORDER BY txn_date, id",
            (eid,)).fetchall()

    def add_transaction(self, eid, amount, tdate, note):
        self.conn.execute(
            "INSERT INTO transactions(entry_id,amount,txn_date,note) VALUES(?,?,?,?)",
            (eid, amount, tdate, note))
        self.conn.commit()

    def update_transaction(self, tid, amount, tdate, note):
        self.conn.execute(
            "UPDATE transactions SET amount=?,txn_date=?,note=? WHERE id=?",
            (amount, tdate, note, tid))
        self.conn.commit()

    def delete_transaction(self, tid):
        self.conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
        self.conn.commit()

    def sync_actual(self, eid):
        r = self.conn.execute(
            "SELECT SUM(amount) s FROM transactions WHERE entry_id=?", (eid,)).fetchone()
        total = r["s"] or 0.0
        self.conn.execute("UPDATE entries SET actual=? WHERE id=?", (total, eid))
        self.conn.commit()
        return total

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def sha256(pw):   return hashlib.sha256(pw.encode("utf-8")).hexdigest()
def fmt(v):       return "{}{:,.2f}".format(CURR, v)
def today():      return datetime.now().strftime("%Y-%m-%d")
def strip_fmt(s): return float(str(s).replace(CURR,"").replace(",","").strip() or 0)

# ═══════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════
class LoginWindow:
    def __init__(self, db, on_success):
        self.db = db
        self.on_success = on_success
        r = tk.Tk(); self.root = r
        r.title(APP_TITLE + " - Login")
        r.geometry("400x300")
        r.resizable(False, False)
        r.configure(bg=BG_WIN)
        r.lift()
        r.attributes("-topmost", True)
        r.after(400, lambda: r.attributes("-topmost", False))

        tk.Label(r, text="ARP", font=("Segoe UI", 40, "bold"),
                 bg=BG_WIN, fg=TOP_BG).pack(pady=(24, 0))
        tk.Label(r, text="Budget Tracker", font=("Segoe UI", 13),
                 bg=BG_WIN, fg=FG_MUTED).pack()
        tk.Label(r, text="DB: " + os.path.basename(DB_PATH),
                 font=("Segoe UI", 8), bg=BG_WIN, fg="#aaa").pack(pady=(2,0))

        frm = tk.Frame(r, bg=BG_WIN); frm.pack(pady=16)
        has = db.get_setting("password_hash") is not None

        def ef(label, row, show=""):
            tk.Label(frm, text=label, bg=BG_WIN, fg=FG_DARK,
                     font=("Segoe UI", 10)).grid(
                     row=row, column=0, sticky="e", padx=8, pady=5)
            e = tk.Entry(frm, show=show, width=22,
                         font=("Segoe UI", 10),
                         bg=BG_CARD, fg=FG_DARK,
                         insertbackground=FG_DARK,
                         relief="solid", bd=1)
            e.grid(row=row, column=1, padx=8, pady=5)
            return e

        if has:
            self.pw = ef("Password:", 0, "*")
            self.pw.bind("<Return>", lambda e: self._login())
            tk.Button(r, text="Login", command=self._login,
                      bg="#1565C0", fg="white",
                      font=("Segoe UI", 10, "bold"),
                      padx=30, pady=7, relief="flat",
                      cursor="hand2").pack(pady=8)
        else:
            tk.Label(frm, text="Create a password:",
                     bg=BG_WIN, fg=FG_DARK,
                     font=("Segoe UI", 10)).grid(
                     row=0, columnspan=2, pady=(0, 6))
            self.pw  = ef("Password:", 1, "*")
            self.pw2 = ef("Confirm:",  2, "*")
            tk.Button(r, text="Create Account", command=self._create,
                      bg="#2E7D32", fg="white",
                      font=("Segoe UI", 10, "bold"),
                      padx=22, pady=7, relief="flat",
                      cursor="hand2").pack(pady=8)

        self.pw.focus_set()
        r.mainloop()

    def _login(self):
        if sha256(self.pw.get()) == self.db.get_setting("password_hash"):
            self.root.destroy(); self.on_success()
        else:
            messagebox.showerror("Wrong password", "Try again.", parent=self.root)
            self.pw.delete(0, tk.END)

    def _create(self):
        pw, pw2 = self.pw.get(), self.pw2.get()
        if len(pw) < 4:
            messagebox.showwarning("Too short", "Use at least 4 characters.",
                                   parent=self.root); return
        if pw != pw2:
            messagebox.showerror("Mismatch", "Passwords do not match.",
                                 parent=self.root); return
        self.db.set_setting("password_hash", sha256(pw))
        messagebox.showinfo("Done", "Account created!", parent=self.root)
        self.root.destroy(); self.on_success()

# ═══════════════════════════════════════════════════════════════
# ENTRY DIALOG
# ═══════════════════════════════════════════════════════════════
class EntryDialog(tk.Toplevel):
    def __init__(self, parent, title, category="Income", initial=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=BG_CARD)
        self.transient(parent); self.grab_set()
        self.result = None

        now = datetime.now()
        iv = initial or {"year": now.year, "month": now.month,
                         "category": category, "name": "",
                         "budget": 0.0, "actual": 0.0,
                         "entry_date": today()}

        f = tk.Frame(self, bg=BG_CARD, padx=20, pady=14)
        f.pack(fill="both", expand=True)

        def row(label, r):
            tk.Label(f, text=label, bg=BG_CARD, fg=FG_DARK,
                     font=("Segoe UI", 10)).grid(
                     row=r, column=0, sticky="e", pady=5, padx=8)

        def entry(r, var, w=22):
            e = tk.Entry(f, textvariable=var, width=w,
                         font=("Segoe UI", 10),
                         bg=BG_CARD, fg=FG_DARK,
                         insertbackground=FG_DARK,
                         relief="solid", bd=1)
            e.grid(row=r, column=1, pady=5, padx=8, sticky="w")
            return e

        row("Year:",  0)
        self.vy = tk.StringVar(value=str(iv["year"])); entry(0, self.vy, 8)

        row("Month:", 1)
        self.vm = tk.StringVar(value=str(iv["month"]))
        ttk.Combobox(f, textvariable=self.vm,
                     values=[str(i) for i in range(1, 13)],
                     width=6, state="readonly",
                     font=("Segoe UI", 10)).grid(
                     row=1, column=1, pady=5, padx=8, sticky="w")

        row("Category:", 2)
        self.vc = tk.StringVar(value=iv["category"])
        ttk.Combobox(f, textvariable=self.vc, values=CATEGORIES,
                     width=14, state="readonly",
                     font=("Segoe UI", 10)).grid(
                     row=2, column=1, pady=5, padx=8, sticky="w")

        row("Name:", 3)
        self.vn = tk.StringVar(value=iv["name"]); entry(3, self.vn, 26)

        row("Budget ({})".format(CURR), 4)
        self.vb = tk.StringVar(value=str(iv["budget"])); entry(4, self.vb, 16)

        row("Actual ({})".format(CURR), 5)
        self.va = tk.StringVar(value=str(iv["actual"])); entry(5, self.va, 16)

        row("Date (YYYY-MM-DD):", 6)
        self.vd = tk.StringVar(value=iv.get("entry_date") or today())
        entry(6, self.vd, 14)

        btns = tk.Frame(f, bg=BG_CARD); btns.grid(row=7, column=0, columnspan=2, pady=12)
        tk.Button(btns, text="Save", command=self._save,
                  bg="#2E7D32", fg="white", padx=22, relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=self.destroy,
                  padx=16, relief="flat", cursor="hand2",
                  bg="#EEEEEE", fg=FG_DARK).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        parent.wait_window(self)

    def _save(self):
        name = self.vn.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Name is required.", parent=self); return
        try:
            year = int(self.vy.get()); month = int(self.vm.get())
            budget = float(self.vb.get() or 0)
            actual = float(self.va.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid", "Year/Month/Budget/Actual must be numbers.",
                                 parent=self); return
        self.result = {"year": year, "month": month,
                       "category": self.vc.get(), "name": name,
                       "budget": budget, "actual": actual,
                       "entry_date": self.vd.get().strip() or today()}
        self.destroy()

# ═══════════════════════════════════════════════════════════════
# TRANSACTION DIALOG
# ═══════════════════════════════════════════════════════════════
class TxnDialog(tk.Toplevel):
    def __init__(self, parent, initial=None):
        super().__init__(parent)
        self.title("Transaction")
        self.resizable(False, False)
        self.configure(bg=BG_CARD)
        self.transient(parent); self.grab_set()
        self.result = None

        iv = initial or {"amount": 0.0, "txn_date": today(), "note": ""}

        f = tk.Frame(self, bg=BG_CARD, padx=20, pady=14)
        f.pack(fill="both", expand=True)

        def row(label, r):
            tk.Label(f, text=label, bg=BG_CARD, fg=FG_DARK,
                     font=("Segoe UI", 10)).grid(
                     row=r, column=0, sticky="e", pady=6, padx=8)

        row("Amount ({})".format(CURR), 0)
        self.va = tk.StringVar(value=str(iv["amount"]))
        tk.Entry(f, textvariable=self.va, width=18,
                 font=("Segoe UI", 10), bg=BG_CARD, fg=FG_DARK,
                 insertbackground=FG_DARK, relief="solid", bd=1
                 ).grid(row=0, column=1, pady=6, padx=8, sticky="w")

        row("Date (YYYY-MM-DD):", 1)
        self.vd = tk.StringVar(value=iv["txn_date"] or today())
        tk.Entry(f, textvariable=self.vd, width=14,
                 font=("Segoe UI", 10), bg=BG_CARD, fg=FG_DARK,
                 insertbackground=FG_DARK, relief="solid", bd=1
                 ).grid(row=1, column=1, pady=6, padx=8, sticky="w")

        row("Note:", 2)
        self.vn = tk.StringVar(value=iv["note"] or "")
        tk.Entry(f, textvariable=self.vn, width=28,
                 font=("Segoe UI", 10), bg=BG_CARD, fg=FG_DARK,
                 insertbackground=FG_DARK, relief="solid", bd=1
                 ).grid(row=2, column=1, pady=6, padx=8, sticky="w")

        btns = tk.Frame(f, bg=BG_CARD); btns.grid(row=3, column=0, columnspan=2, pady=12)
        tk.Button(btns, text="Save", command=self._save,
                  bg="#1565C0", fg="white", padx=22, relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=self.destroy,
                  padx=16, relief="flat", cursor="hand2",
                  bg="#EEEEEE", fg=FG_DARK).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        parent.wait_window(self)

    def _save(self):
        try:
            amount = float(self.va.get())
        except ValueError:
            messagebox.showerror("Invalid", "Amount must be a number.", parent=self); return
        self.result = {"amount": amount,
                       "txn_date": self.vd.get().strip() or today(),
                       "note": self.vn.get().strip()}
        self.destroy()

# ═══════════════════════════════════════════════════════════════
# TRANSACTIONS WINDOW
# ═══════════════════════════════════════════════════════════════
class TxnWindow(tk.Toplevel):
    def __init__(self, parent, db, entry_row, refresh_cb):
        super().__init__(parent)
        self.db = db
        self.eid = entry_row["id"]
        self.ename = entry_row["name"]
        self.refresh_cb = refresh_cb

        self.title("Transactions — {}".format(self.ename))
        self.geometry("700x460")
        self.configure(bg=BG_WIN)
        self.transient(parent)

        tb = tk.Frame(self, bg=TOP_BG, height=44)
        tb.pack(fill="x"); tb.pack_propagate(False)

        def btn(text, cmd, color):
            tk.Button(tb, text=text, command=cmd,
                      bg=color, fg="white",
                      font=("Segoe UI", 9, "bold"),
                      padx=12, pady=4, relief="flat", cursor="hand2",
                      activebackground="#37474F",
                      activeforeground="white"
                      ).pack(side="left", padx=6, pady=6)

        btn("+ Add",              self._add,    "#2E7D32")
        btn("Edit",               self._edit,   "#1565C0")
        btn("Delete",             self._delete, "#B71C1C")
        btn("Sync Actual \u2190 Sum", self._sync, "#E65100")

        # status — bottom first
        self.status = tk.Label(self, text="", anchor="w",
                               bg="#ECEFF1", fg=FG_DARK,
                               font=("Segoe UI", 9), padx=10, pady=4)
        self.status.pack(fill="x", side="bottom")

        # tree
        cols = ("id", "amount", "txn_date", "note")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        self.tree.heading("id",       text="ID",     anchor="center")
        self.tree.heading("amount",   text="Amount", anchor="e")
        self.tree.heading("txn_date", text="Date",   anchor="center")
        self.tree.heading("note",     text="Note",   anchor="w")
        self.tree.column("id",       width=55,  anchor="center", stretch=False)
        self.tree.column("amount",   width=150, anchor="e",      stretch=False)
        self.tree.column("txn_date", width=110, anchor="center", stretch=False)
        self.tree.column("note",     width=380, anchor="w")

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8,0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0,6))

        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Delete>",   lambda e: self._delete())
        self._load()

    def _load(self):
        for ch in self.tree.get_children(): self.tree.delete(ch)
        rows = self.db.get_transactions(self.eid)
        total = 0.0
        for i, r in enumerate(rows):
            bg = "#F5F5F5" if i % 2 else BG_CARD
            self.tree.insert("", "end", iid=str(r["id"]),
                             values=(r["id"], fmt(r["amount"]),
                                     r["txn_date"] or "", r["note"] or ""),
                             tags=("r",))
            self.tree.tag_configure("r", background=bg)
            total += r["amount"] or 0
        self.status.config(
            text="  {} transactions     Total: {}".format(len(rows), fmt(total)))

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showinfo("Select", "Click a row first.", parent=self); return None
        return int(s[0])

    def _add(self):
        d = TxnDialog(self)
        if d.result:
            self.db.add_transaction(self.eid, d.result["amount"],
                                    d.result["txn_date"], d.result["note"])
            self._load()

    def _edit(self):
        tid = self._sel()
        if tid is None: return
        v = self.tree.item(str(tid))["values"]
        d = TxnDialog(self, initial={"amount": strip_fmt(v[1]),
                                     "txn_date": v[2], "note": v[3]})
        if d.result:
            self.db.update_transaction(tid, d.result["amount"],
                                       d.result["txn_date"], d.result["note"])
            self._load()

    def _delete(self):
        tid = self._sel()
        if tid is None: return
        if messagebox.askyesno("Delete", "Delete this transaction?", parent=self):
            self.db.delete_transaction(tid); self._load()

    def _sync(self):
        total = self.db.sync_actual(self.eid)
        messagebox.showinfo("Synced", "Actual updated to {}".format(fmt(total)), parent=self)
        self._load(); self.refresh_cb()

# ═══════════════════════════════════════════════════════════════
# MAIN APP  — card layout
# ═══════════════════════════════════════════════════════════════
class MainApp:
    def __init__(self, db):
        self.db = db
        self.panels = {}   # cat -> {tree, lbl_tot_b, lbl_tot_a}

        r = tk.Tk(); self.root = r
        r.title(APP_TITLE)
        r.geometry("1400x860")
        r.minsize(1100, 650)
        r.configure(bg=BG_WIN)
        r.lift()
        r.attributes("-topmost", True)
        r.after(400, lambda: r.attributes("-topmost", False))

        now = datetime.now()
        self.sel_year  = tk.IntVar(value=now.year)
        self.sel_month = tk.IntVar(value=now.month)

        self._build()
        self._refresh()
        self._keys()
        r.mainloop()

    # ─── TOP BAR ───────────────────────────────────────────────
    def _build(self):
        r = self.root

        top = tk.Frame(r, bg=TOP_BG, height=56)
        top.pack(fill="x"); top.pack_propagate(False)

        tk.Label(top, text="ARP", bg=TOP_BG, fg="white",
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=14)
        tk.Label(top, text="Budget Tracker", bg=TOP_BG, fg="#90CAF9",
                 font=("Segoe UI", 11)).pack(side="left")

        pf = tk.Frame(top, bg=TOP_BG); pf.pack(side="right", padx=14)

        tk.Label(pf, text="Month:", bg=TOP_BG, fg="white",
                 font=("Segoe UI", 10)).pack(side="left", padx=(0,4))
        self.month_cb = ttk.Combobox(pf, values=MONTHS, width=6,
                                     state="readonly", font=("Segoe UI", 10))
        self.month_cb.current(self.sel_month.get() - 1)
        self.month_cb.pack(side="left")
        self.month_cb.bind("<<ComboboxSelected>>", self._on_month)

        tk.Label(pf, text="  Year:", bg=TOP_BG, fg="white",
                 font=("Segoe UI", 10)).pack(side="left", padx=(10,4))
        year_cb = ttk.Combobox(pf, textvariable=self.sel_year,
                               values=list(range(2020, 2036)),
                               width=6, state="readonly",
                               font=("Segoe UI", 10))
        year_cb.pack(side="left")
        year_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh())

        # ─── NOTEBOOK ──────────────────────────────────────────
        style = ttk.Style()
        style.configure("TNotebook", background=BG_WIN, borderwidth=0)
        style.configure("TNotebook.Tab", background="#D0D5DD", foreground=FG_DARK,
                        padding=[16, 6], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", BG_CARD)],
                  foreground=[("selected", TOP_BG)])

        nb = ttk.Notebook(r)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        self.tab_monthly  = tk.Frame(nb, bg=BG_WIN)
        self.tab_dashboard = tk.Frame(nb, bg=BG_WIN)
        self.tab_annual   = tk.Frame(nb, bg=BG_WIN)
        nb.add(self.tab_monthly,   text="  Monthly Entries  ")
        nb.add(self.tab_dashboard, text="  Dashboard  ")
        nb.add(self.tab_annual,    text="  Annual Report  ")

        self._build_monthly()
        self._build_dashboard()
        self._build_annual()

    # ─── MONTHLY TAB ───────────────────────────────────────────
    def _build_monthly(self):
        tab = self.tab_monthly

        # Summary strip
        sf = tk.Frame(tab, bg=BG_WIN)
        sf.pack(fill="x", padx=14, pady=(10, 4))
        self.lbl_income   = self._sum_card(sf, "Income",        "#2E7D32")
        self.lbl_expenses = self._sum_card(sf, "Expenses",      "#C62828")
        self.lbl_savings  = self._sum_card(sf, "Savings",       "#6A1B9A")
        self.lbl_left     = self._sum_card(sf, "Left to Spend", "#1565C0")

        # Category grid
        grid = tk.Frame(tab, bg=BG_WIN)
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        positions = {
            "Income":   (0, 0),
            "Bills":    (0, 1),
            "Variable": (1, 0),
            "Savings":  (1, 1),
            "Debt":     (2, 0),
        }
        for cat, (row, col) in positions.items():
            self._build_card(grid, cat, row, col)

        for r in range(3): grid.rowconfigure(r, weight=1)
        for c in range(2): grid.columnconfigure(c, weight=1)

    def _sum_card(self, parent, title, color):
        box = tk.Frame(parent, bg=BG_CARD, bd=0,
                       highlightbackground="#CCCCCC", highlightthickness=1)
        box.pack(side="left", fill="both", expand=True, padx=5, pady=2)
        tk.Label(box, text=title, bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(6,0))
        lbl = tk.Label(box, text=fmt(0), bg=BG_CARD, fg=color,
                       font=("Segoe UI", 15, "bold"))
        lbl.pack(anchor="w", padx=12, pady=(0,6))
        return lbl

    def _build_card(self, parent, cat, row, col):
        hdr_color   = CAT_HDR.get(cat, "#607D8B")
        light_color = CAT_LIGHT.get(cat, "#FAFAFA")

        card = tk.Frame(parent, bg=BG_CARD, bd=0,
                        highlightbackground="#CCCCCC", highlightthickness=1)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        # Header
        hdr = tk.Frame(card, bg=hdr_color, height=36)
        hdr.pack(fill="x"); hdr.pack_propagate(False)

        tk.Label(hdr, text=cat, bg=hdr_color, fg="white",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12)

        bf = tk.Frame(hdr, bg=hdr_color); bf.pack(side="right", padx=6)

        def hbtn(text, cmd, bg=BG_CARD, fg=None):
            fg = fg or hdr_color
            tk.Button(bf, text=text, command=cmd,
                      bg=bg, fg=fg, bd=0,
                      font=("Segoe UI", 8, "bold"),
                      padx=8, pady=2, relief="flat",
                      cursor="hand2",
                      activebackground=bg,
                      activeforeground=fg
                      ).pack(side="left", padx=2)

        hbtn("+ Add",  lambda c=cat: self._add(c))
        hbtn("Edit",   lambda c=cat: self._edit(c),   bg="#E3F2FD", fg="#1565C0")
        hbtn("Delete", lambda c=cat: self._delete(c), bg="#FFEBEE", fg="#B71C1C")

        # Treeview
        sn = "C{}.Treeview".format(cat)
        style = ttk.Style()
        style.configure(sn, background=BG_CARD, fieldbackground=BG_CARD,
                        foreground=FG_DARK, rowheight=24,
                        font=("Segoe UI", 9))
        style.configure(sn + ".Heading",
                        background=light_color, foreground=FG_DARK,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map(sn,
                  background=[("selected", hdr_color)],
                  foreground=[("selected", "white")])

        cols = ("name", "budget", "actual")
        tree = ttk.Treeview(card, columns=cols, show="headings",
                            style=sn, height=5)
        tree.heading("name",   text="Item",   anchor="w")
        tree.heading("budget", text="Budget", anchor="e")
        tree.heading("actual", text="Actual", anchor="e")
        tree.column("name",   anchor="w", width=180)
        tree.column("budget", anchor="e", width=110, stretch=False)
        tree.column("actual", anchor="e", width=110, stretch=False)

        tree.tag_configure("odd",  background=BG_CARD)
        tree.tag_configure("even", background=light_color)

        sb = ttk.Scrollbar(card, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Double-click opens transactions
        tree.bind("<Double-1>", lambda e, c=cat: self._open_txns(c))

        # Total row
        tot = tk.Frame(card, bg=BG_TOTAL)
        tot.pack(fill="x")
        tk.Label(tot, text="Total", bg=BG_TOTAL, fg=FG_DARK,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=10, pady=3)
        lbl_a = tk.Label(tot, text=fmt(0), bg=BG_TOTAL, fg=hdr_color,
                         font=("Segoe UI", 9, "bold"))
        lbl_a.pack(side="right", padx=12, pady=3)
        lbl_b = tk.Label(tot, text=fmt(0), bg=BG_TOTAL, fg=FG_MUTED,
                         font=("Segoe UI", 9))
        lbl_b.pack(side="right", padx=12, pady=3)

        self.panels[cat] = {"tree": tree, "lbl_b": lbl_b, "lbl_a": lbl_a}

    # ─── DASHBOARD TAB ─────────────────────────────────────────
    def _build_dashboard(self):
        self.dash_wrap = tk.Frame(self.tab_dashboard, bg=BG_WIN)
        self.dash_wrap.pack(fill="both", expand=True, padx=10, pady=10)

    # ─── ANNUAL TAB ────────────────────────────────────────────
    def _build_annual(self):
        self.annual_wrap = tk.Frame(self.tab_annual, bg=BG_WIN)
        self.annual_wrap.pack(fill="both", expand=True, padx=10, pady=10)

    # ─── REFRESH ───────────────────────────────────────────────
    def _refresh(self, _=None):
        self.month_cb.current(self.sel_month.get() - 1)
        y = self.sel_year.get()
        m = self.sel_month.get()

        tot_income = tot_expense = tot_savings = 0.0

        for cat in CATEGORIES:
            p    = self.panels[cat]
            tree = p["tree"]
            for ch in tree.get_children(): tree.delete(ch)

            rows = self.db.get_entries(y, m, cat)
            tot_b = tot_a = 0.0
            for i, r in enumerate(rows):
                b = r["budget"] or 0
                a = r["actual"] or 0
                tag = "even" if i % 2 == 0 else "odd"
                tree.insert("", "end", iid=str(r["id"]),
                            values=(r["name"], fmt(b), fmt(a)),
                            tags=(tag,))
                tot_b += b; tot_a += a

            p["lbl_b"].config(text=fmt(tot_b))
            p["lbl_a"].config(text=fmt(tot_a))

            if cat == "Income":
                tot_income = tot_a
            elif cat == "Savings":
                tot_savings = tot_a
            elif cat in ("Bills", "Variable", "Debt"):
                tot_expense += tot_a

        left = tot_income - tot_expense - tot_savings
        self.lbl_income.config(text=fmt(tot_income))
        self.lbl_expenses.config(text=fmt(tot_expense))
        self.lbl_savings.config(text=fmt(tot_savings))
        self.lbl_left.config(text=fmt(left),
                             fg="#1565C0" if left >= 0 else "#C62828")

        self._refresh_dashboard(y, m)
        self._refresh_annual(y)

    def _refresh_dashboard(self, y, m):
        try:
            self._draw_dashboard(y, m)
        except Exception as e:
            for w in self.dash_wrap.winfo_children(): w.destroy()
            tk.Label(self.dash_wrap,
                     text="Chart error: {}".format(e),
                     bg=BG_WIN, fg="#B71C1C",
                     font=("Segoe UI", 10)).pack(pady=40)

    def _draw_dashboard(self, y, m):
        for w in self.dash_wrap.winfo_children(): w.destroy()
        if not HAS_MPL:
            tk.Label(self.dash_wrap,
                     text="Install matplotlib for charts:\n  pip install matplotlib",
                     bg=BG_WIN, fg=FG_MUTED, font=("Segoe UI", 12)).pack(pady=40)
            return

        cat_rows = self.db.get_cat_totals(y, m)
        order = {c: i for i, c in enumerate(CATEGORIES)}
        cat_rows = sorted(cat_rows, key=lambda r: order.get(r["category"], 99))

        cats  = [r["category"] for r in cat_rows]
        bvals = [r["b"] or 0   for r in cat_rows]
        avals = [r["a"] or 0   for r in cat_rows]
        colors = [CAT_HDR.get(c, "#607D8B") for c in cats]

        fig = Figure(figsize=(11, 5.5), facecolor=BG_WIN)

        # Pie
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor(BG_WIN)
        non_zero = [(c, b, cl) for c, b, cl in zip(cats, bvals, colors) if b > 0]
        if non_zero:
            ax1.pie([x[1] for x in non_zero],
                    labels=[x[0] for x in non_zero],
                    colors=[x[2] for x in non_zero],
                    autopct="%1.0f%%", startangle=90,
                    textprops={"fontsize": 10},
                    wedgeprops={"edgecolor": "white", "linewidth": 2})
        ax1.set_title("Budget Composition", fontsize=12, fontweight="bold")

        # Bar
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor("#FAFAFA")
        x = range(len(cats)); h = 0.35
        ax2.barh([i + h/2 for i in x], bvals, h,
                 label="Budget", color=colors, alpha=0.45)
        ax2.barh([i - h/2 for i in x], avals, h,
                 label="Actual", color=colors, alpha=0.9)
        ax2.set_yticks(list(x)); ax2.set_yticklabels(cats)
        ax2.set_title("Budget vs Actual", fontsize=12, fontweight="bold")
        ax2.legend(); ax2.grid(axis="x", alpha=0.3)
        ax2.set_xlabel("Amount ({})".format(CURR))
        fig.tight_layout(pad=2)

        canvas = FigureCanvasTkAgg(fig, master=self.dash_wrap)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=BG_WIN)
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _refresh_annual(self, y):
        for w in self.annual_wrap.winfo_children(): w.destroy()

        tk.Label(self.annual_wrap,
                 text="Annual Report — {}".format(y),
                 bg=BG_WIN, fg=TOP_BG,
                 font=("Segoe UI", 14, "bold")).pack(pady=(0, 8))

        tbl = tk.Frame(self.annual_wrap, bg=BG_WIN)
        tbl.pack(fill="x", padx=10)

        headers = ["Category"] + MONTHS + ["Total"]
        for i, h in enumerate(headers):
            tk.Label(tbl, text=h, bg=TOP_BG, fg="white",
                     font=("Segoe UI", 8, "bold"),
                     padx=6, pady=5
                     ).grid(row=0, column=i, sticky="nsew", padx=1, pady=1)

        rows = self.conn_annual(y)
        for r_idx, cat in enumerate(CATEGORIES, 1):
            tk.Label(tbl, text=cat,
                     bg=CAT_HDR.get(cat, "#607D8B"), fg="white",
                     font=("Segoe UI", 8, "bold"), padx=8, pady=4
                     ).grid(row=r_idx, column=0, sticky="nsew", padx=1, pady=1)
            row_total = 0
            for m_idx, m in enumerate(range(1, 13), 1):
                a = rows.get(cat, {}).get(m, 0)
                row_total += a
                bg = CAT_LIGHT.get(cat, BG_CARD) if r_idx % 2 == 0 else BG_CARD
                tk.Label(tbl, text="{:,.0f}".format(a) if a else "-",
                         bg=bg, fg=FG_DARK,
                         font=("Segoe UI", 8), padx=4, pady=4
                         ).grid(row=r_idx, column=m_idx, sticky="nsew", padx=1, pady=1)
            tk.Label(tbl, text=fmt(row_total),
                     bg=BG_TOTAL, fg=CAT_HDR.get(cat, "#333"),
                     font=("Segoe UI", 8, "bold"), padx=6, pady=4
                     ).grid(row=r_idx, column=13, sticky="nsew", padx=1, pady=1)

        for c in range(14): tbl.columnconfigure(c, weight=1)

        # ── Trend line chart below the table ──────────────────
        if HAS_MPL:
            try:
                rows_data = self.conn_annual(y)
                chart_frame = tk.Frame(self.annual_wrap, bg=BG_WIN)
                chart_frame.pack(fill="both", expand=True, padx=10, pady=(10, 4))

                fig = Figure(figsize=(12, 3.8), facecolor=BG_WIN)
                ax  = fig.add_subplot(1, 1, 1)
                ax.set_facecolor("#FAFAFA")

                for cat in CATEGORIES:
                    actuals = [rows_data.get(cat, {}).get(m, 0) for m in range(1, 13)]
                    ax.plot(MONTHS, actuals,
                            marker="o", linewidth=2, markersize=5,
                            label=cat, color=CAT_HDR.get(cat, "#607D8B"))

                ax.set_title("Monthly Trend — {}".format(y),
                             fontsize=11, fontweight="bold", pad=8)
                ax.set_ylabel("Amount ({})".format(CURR))
                ax.legend(ncol=5, loc="upper right", fontsize=8)
                ax.grid(alpha=0.25)
                ax.tick_params(axis="both", labelsize=8)
                fig.tight_layout(pad=1.5)

                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.draw()
                canvas.get_tk_widget().configure(bg=BG_WIN)
                canvas.get_tk_widget().pack(fill="both", expand=True)
            except Exception as e:
                tk.Label(self.annual_wrap,
                         text="Chart error: {}".format(e),
                         bg=BG_WIN, fg="#B71C1C",
                         font=("Segoe UI", 9)).pack()

    def conn_annual(self, year):
        rows = self.db.conn.execute(
            "SELECT month, category, SUM(actual) a FROM entries "
            "WHERE year=? GROUP BY month, category", (year,)).fetchall()
        result = {cat: {m: 0 for m in range(1, 13)} for cat in CATEGORIES}
        for r in rows:
            if r["category"] in result:
                result[r["category"]][r["month"]] = r["a"] or 0
        return result

    # ─── MONTH COMBOBOX ────────────────────────────────────────
    def _on_month(self, _=None):
        self.sel_month.set(MONTHS.index(self.month_cb.get()) + 1)
        self._refresh()

    # ─── KEYS ──────────────────────────────────────────────────
    def _keys(self):
        pass  # Category-specific shortcuts not needed in card layout

    # ─── CRUD ──────────────────────────────────────────────────
    def _add(self, cat):
        d = EntryDialog(self.root, "Add to {}".format(cat), category=cat,
                        initial={"year": self.sel_year.get(),
                                 "month": self.sel_month.get(),
                                 "category": cat, "name": "",
                                 "budget": 0.0, "actual": 0.0,
                                 "entry_date": today()})
        if d.result:
            self.db.add_entry(d.result["year"], d.result["month"],
                              d.result["category"], d.result["name"],
                              d.result["budget"], d.result["actual"],
                              d.result["entry_date"])
            self._refresh()

    def _sel(self, cat):
        tree = self.panels[cat]["tree"]
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Click an item in {} first.".format(cat),
                                parent=self.root)
            return None
        return sel[0]   # iid = str(entry id)

    def _edit(self, cat):
        iid = self._sel(cat)
        if iid is None: return
        tree = self.panels[cat]["tree"]
        vals = tree.item(iid)["values"]
        # vals: name, budget_str, actual_str
        d = EntryDialog(self.root, "Edit {} entry".format(cat), category=cat,
                        initial={"year": self.sel_year.get(),
                                 "month": self.sel_month.get(),
                                 "category": cat,
                                 "name": vals[0],
                                 "budget": strip_fmt(vals[1]),
                                 "actual": strip_fmt(vals[2]),
                                 "entry_date": today()})
        if d.result:
            self.db.update_entry(int(iid), d.result["year"], d.result["month"],
                                 d.result["category"], d.result["name"],
                                 d.result["budget"], d.result["actual"],
                                 d.result["entry_date"])
            self._refresh()

    def _delete(self, cat):
        iid = self._sel(cat)
        if iid is None: return
        name = self.panels[cat]["tree"].item(iid)["values"][0]
        if messagebox.askyesno("Delete",
                               "Delete '{}' and all its transactions?".format(name),
                               parent=self.root):
            self.db.delete_entry(int(iid)); self._refresh()

    def _open_txns(self, cat):
        iid = self._sel(cat)
        if iid is None: return
        rows = self.db.get_entries(self.sel_year.get(),
                                   self.sel_month.get(), cat)
        row = next((r for r in rows if str(r["id"]) == iid), None)
        if row: TxnWindow(self.root, self.db, row, self._refresh)

# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════
def main():
    print("ARP Budget Tracker starting...")
    print("DB:", DB_PATH)
    db = DB(DB_PATH)
    LoginWindow(db, on_success=lambda: MainApp(db))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\n*** Crash — press Enter to close ***")
