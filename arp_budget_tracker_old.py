# -*- coding: utf-8 -*-
"""
ARP Budget Tracker - v4 clean
Windows / Python 3.13  |  stdlib only (matplotlib optional)
"""

import os
import sys
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
except Exception:
    HAS_MPL = False

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
APP_TITLE  = "ARP Budget Tracker"
CURR       = "\u20b9"
CATEGORIES = ["Income", "Bills", "Variable", "Savings", "Debt"]
MONTHS     = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]

CAT_BG = {
    "Income":   "#d4edda",
    "Bills":    "#ffe8cc",
    "Variable": "#e9e9e9",
    "Savings":  "#d0e8ff",
    "Debt":     "#f8d7da",
}
CAT_FG = {
    "Income":   "#155724",
    "Bills":    "#7d3c00",
    "Variable": "#333333",
    "Savings":  "#0c3762",
    "Debt":     "#721c24",
}
DIFF_POS = "#1a6e2e"   # green  — under budget (good)
DIFF_NEG = "#b71c1c"   # red    — over budget  (bad)

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
        c.execute("""CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS entries (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     year INTEGER NOT NULL, month INTEGER NOT NULL,
                     category TEXT NOT NULL, name TEXT NOT NULL,
                     budget REAL DEFAULT 0, actual REAL DEFAULT 0,
                     created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                     entry_date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     entry_id INTEGER NOT NULL, amount REAL NOT NULL,
                     txn_date TEXT, note TEXT,
                     created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.commit()

    def get_setting(self, k):
        r = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return r["value"] if r else None

    def set_setting(self, k, v):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))
        self.conn.commit()

    def get_entries(self, year, month):
        return self.conn.execute(
            """SELECT id, year, month, category, name, budget, actual, entry_date
               FROM entries WHERE year=? AND month=?
               ORDER BY
                 CASE category
                   WHEN 'Income'   THEN 1 WHEN 'Bills'    THEN 2
                   WHEN 'Variable' THEN 3 WHEN 'Savings'  THEN 4
                   WHEN 'Debt'     THEN 5 ELSE 6 END, id""",
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
            "SELECT id, entry_id, amount, txn_date, note FROM transactions"
            " WHERE entry_id=? ORDER BY txn_date, id", (eid,)).fetchall()

    def add_transaction(self, eid, amount, tdate, note):
        self.conn.execute(
            "INSERT INTO transactions(entry_id,amount,txn_date,note)"
            " VALUES(?,?,?,?)", (eid, amount, tdate, note))
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
            "SELECT SUM(amount) s FROM transactions WHERE entry_id=?",
            (eid,)).fetchone()
        total = r["s"] or 0.0
        self.conn.execute("UPDATE entries SET actual=? WHERE id=?", (total, eid))
        self.conn.commit()
        return total

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def sha256(pw):  return hashlib.sha256(pw.encode("utf-8")).hexdigest()
def fmt(v):      return "{}{:,.2f}".format(CURR, v)
def today():     return datetime.now().strftime("%Y-%m-%d")
def strip_fmt(s):
    return float(str(s).replace(CURR,"").replace(",","").strip() or 0)

# ═══════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════
class LoginWindow:
    def __init__(self, db, on_success):
        self.db = db
        self.on_success = on_success
        r = tk.Tk()
        self.root = r
        r.title(APP_TITLE + " - Login")
        r.geometry("380x290")
        r.resizable(False, False)
        r.configure(bg="#f5f7fa")
        r.lift()
        r.attributes("-topmost", True)
        r.after(400, lambda: r.attributes("-topmost", False))

        tk.Label(r, text="ARP", font=("Segoe UI", 36, "bold"),
                 bg="#f5f7fa", fg="#1e2a3a").pack(pady=(22,0))
        tk.Label(r, text="Budget Tracker", font=("Segoe UI", 12),
                 bg="#f5f7fa", fg="#78909c").pack()
        tk.Label(r, text="DB: " + os.path.basename(DB_PATH),
                 font=("Segoe UI", 8), bg="#f5f7fa", fg="#aaa").pack()

        frm = tk.Frame(r, bg="#f5f7fa")
        frm.pack(pady=14)
        has = db.get_setting("password_hash") is not None

        def ef(label, row, show=""):
            tk.Label(frm, text=label, bg="#f5f7fa",
                     font=("Segoe UI", 10)).grid(
                     row=row, column=0, sticky="e", padx=8, pady=5)
            e = tk.Entry(frm, show=show, width=22,
                         font=("Segoe UI", 10), relief="solid", bd=1)
            e.grid(row=row, column=1, padx=8, pady=5)
            return e

        if has:
            self.pw = ef("Password:", 0, "*")
            self.pw.bind("<Return>", lambda e: self._login())
            tk.Button(r, text="Login", command=self._login,
                      bg="#1565c0", fg="white",
                      font=("Segoe UI", 10, "bold"),
                      padx=28, pady=6, relief="flat").pack(pady=6)
        else:
            tk.Label(frm, text="Set a password to protect your data:",
                     bg="#f5f7fa", font=("Segoe UI", 9)
                     ).grid(row=0, columnspan=2, pady=(0,6))
            self.pw  = ef("Password:", 1, "*")
            self.pw2 = ef("Confirm:",  2, "*")
            tk.Button(r, text="Create Account", command=self._create,
                      bg="#2e7d32", fg="white",
                      font=("Segoe UI", 10, "bold"),
                      padx=20, pady=6, relief="flat").pack(pady=6)

        self.pw.focus_set()
        r.mainloop()

    def _login(self):
        if sha256(self.pw.get()) == self.db.get_setting("password_hash"):
            self.root.destroy()
            self.on_success()
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
        self.root.destroy()
        self.on_success()

# ═══════════════════════════════════════════════════════════════
# ENTRY DIALOG
# ═══════════════════════════════════════════════════════════════
class EntryDialog(tk.Toplevel):
    def __init__(self, parent, title, initial=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#ffffff")
        self.transient(parent); self.grab_set()
        self.result = None

        now = datetime.now()
        iv = initial or {"year": now.year, "month": now.month,
                         "category": "Income", "name": "",
                         "budget": 0.0, "actual": 0.0,
                         "entry_date": today()}

        f = tk.Frame(self, bg="#ffffff", padx=20, pady=14)
        f.pack(fill="both", expand=True)

        def lbl(text, r):
            tk.Label(f, text=text, bg="#ffffff",
                     font=("Segoe UI", 10)).grid(
                     row=r, column=0, sticky="e", pady=5, padx=6)

        def ent(r, var, w=20):
            e = tk.Entry(f, textvariable=var, width=w,
                         font=("Segoe UI", 10), relief="solid", bd=1)
            e.grid(row=r, column=1, pady=5, padx=6, sticky="w")
            return e

        lbl("Year:",  0); self.vy = tk.StringVar(value=str(iv["year"]))
        ent(0, self.vy, 8)

        lbl("Month:", 1); self.vm = tk.StringVar(value=str(iv["month"]))
        ttk.Combobox(f, textvariable=self.vm,
                     values=[str(i) for i in range(1,13)],
                     width=6, state="readonly",
                     font=("Segoe UI", 10)).grid(
                     row=1, column=1, pady=5, padx=6, sticky="w")

        lbl("Category:", 2); self.vc = tk.StringVar(value=iv["category"])
        ttk.Combobox(f, textvariable=self.vc, values=CATEGORIES,
                     width=14, state="readonly",
                     font=("Segoe UI", 10)).grid(
                     row=2, column=1, pady=5, padx=6, sticky="w")

        lbl("Name:", 3); self.vn = tk.StringVar(value=iv["name"])
        ent(3, self.vn, 26)

        lbl("Budget ({})".format(CURR), 4)
        self.vb = tk.StringVar(value=str(iv["budget"])); ent(4, self.vb, 16)

        lbl("Actual ({})".format(CURR), 5)
        self.va = tk.StringVar(value=str(iv["actual"])); ent(5, self.va, 16)

        lbl("Date (YYYY-MM-DD):", 6)
        self.vd = tk.StringVar(value=iv.get("entry_date") or today())
        ent(6, self.vd, 14)

        btns = tk.Frame(f, bg="#ffffff")
        btns.grid(row=7, column=0, columnspan=2, pady=12)
        tk.Button(btns, text="Save", command=self._save,
                  bg="#2e7d32", fg="white", padx=22, relief="flat",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=self.destroy,
                  padx=16, relief="flat").pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        parent.wait_window(self)

    def _save(self):
        name = self.vn.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Name is required.", parent=self)
            return
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
        self.configure(bg="#ffffff")
        self.transient(parent); self.grab_set()
        self.result = None

        iv = initial or {"amount": 0.0, "txn_date": today(), "note": ""}

        f = tk.Frame(self, bg="#ffffff", padx=20, pady=14)
        f.pack(fill="both", expand=True)

        def lbl(text, r):
            tk.Label(f, text=text, bg="#ffffff",
                     font=("Segoe UI", 10)).grid(
                     row=r, column=0, sticky="e", pady=6, padx=6)

        lbl("Amount ({})".format(CURR), 0)
        self.va = tk.StringVar(value=str(iv["amount"]))
        tk.Entry(f, textvariable=self.va, width=18,
                 font=("Segoe UI", 10), relief="solid", bd=1
                 ).grid(row=0, column=1, pady=6, padx=6, sticky="w")

        lbl("Date (YYYY-MM-DD):", 1)
        self.vd = tk.StringVar(value=iv["txn_date"] or today())
        tk.Entry(f, textvariable=self.vd, width=14,
                 font=("Segoe UI", 10), relief="solid", bd=1
                 ).grid(row=1, column=1, pady=6, padx=6, sticky="w")

        lbl("Note:", 2)
        self.vn = tk.StringVar(value=iv["note"] or "")
        tk.Entry(f, textvariable=self.vn, width=28,
                 font=("Segoe UI", 10), relief="solid", bd=1
                 ).grid(row=2, column=1, pady=6, padx=6, sticky="w")

        btns = tk.Frame(f, bg="#ffffff")
        btns.grid(row=3, column=0, columnspan=2, pady=12)
        tk.Button(btns, text="Save", command=self._save,
                  bg="#1565c0", fg="white", padx=22, relief="flat",
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", command=self.destroy,
                  padx=16, relief="flat").pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        parent.wait_window(self)

    def _save(self):
        try:
            amount = float(self.va.get())
        except ValueError:
            messagebox.showerror("Invalid", "Amount must be a number.", parent=self)
            return
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

        self.title("Transactions  —  {}".format(self.ename))
        self.geometry("680x460")
        self.configure(bg="#f5f7fa")
        self.transient(parent)

        # toolbar
        tb = tk.Frame(self, bg="#1e2a3a", height=44)
        tb.pack(fill="x"); tb.pack_propagate(False)

        def btn(text, cmd, color):
            tk.Button(tb, text=text, command=cmd, bg=color, fg="white",
                      font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                      relief="flat", cursor="hand2",
                      activebackground="#37474f",
                      activeforeground="white"
                      ).pack(side="left", padx=6, pady=5)

        btn("+ Add",              self._add,    "#2e7d32")
        btn("Edit",               self._edit,   "#1565c0")
        btn("Delete",             self._delete, "#b71c1c")
        btn("Sync Actual \u2190 Sum", self._sync,  "#e65100")

        # status at bottom — pack before tree
        self.status = tk.Label(self, text="", anchor="w",
                               bg="#1e2a3a", fg="#b0bec5",
                               font=("Segoe UI", 9), padx=10, pady=3)
        self.status.pack(fill="x", side="bottom")

        # tree
        cols = ("id", "amount", "txn_date", "note")
        self.tree = ttk.Treeview(self, columns=cols,
                                 show="headings", height=14)
        self.tree.heading("id",       text="ID",     anchor="center")
        self.tree.heading("amount",   text="Amount", anchor="e")
        self.tree.heading("txn_date", text="Date",   anchor="center")
        self.tree.heading("note",     text="Note",   anchor="w")
        self.tree.column("id",       width=55,  anchor="center", stretch=False)
        self.tree.column("amount",   width=140, anchor="e",      stretch=False)
        self.tree.column("txn_date", width=110, anchor="center", stretch=False)
        self.tree.column("note",     width=360, anchor="w")

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
            bg = "#f8f9fa" if i % 2 else "#ffffff"
            self.tree.insert("", "end", iid=str(r["id"]),
                             values=(r["id"], fmt(r["amount"]),
                                     r["txn_date"] or "", r["note"] or ""),
                             tags=("row",))
            self.tree.tag_configure("row", background=bg)
            total += r["amount"] or 0
        self.status.config(
            text="  {}  transactions     Total: {}".format(len(rows), fmt(total)))

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showinfo("Select", "Click a row first.", parent=self)
            return None
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
        d = TxnDialog(self, initial={"amount":   strip_fmt(v[1]),
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
        messagebox.showinfo("Synced",
            "Actual updated to {}".format(fmt(total)), parent=self)
        self._load(); self.refresh_cb()

# ═══════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════
class MainApp:
    def __init__(self, db):
        self.db = db

        r = tk.Tk(); self.root = r
        r.title(APP_TITLE)
        r.geometry("1340x780")
        r.minsize(960, 580)
        r.configure(bg="#f5f7fa")
        r.lift()
        r.attributes("-topmost", True)
        r.after(400, lambda: r.attributes("-topmost", False))

        now = datetime.now()
        self.sel_year  = tk.IntVar(value=now.year)
        self.sel_month = tk.IntVar(value=now.month)

        self._build()
        self._load()
        self._keys()
        r.mainloop()

    # ─── BUILD UI ──────────────────────────────────────────────
    def _build(self):
        r = self.root

        # ── Top bar ──────────────────────────────────────────
        top = tk.Frame(r, bg="#1e2a3a", height=52)
        top.pack(fill="x"); top.pack_propagate(False)

        tk.Label(top, text="ARP  Budget Tracker",
                 bg="#1e2a3a", fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=18)

        pf = tk.Frame(top, bg="#1e2a3a"); pf.pack(side="right", padx=16)

        def lbl(text, parent=pf):
            tk.Label(parent, text=text, bg="#1e2a3a", fg="white",
                     font=("Segoe UI", 10)).pack(side="left")

        lbl("Year: ")
        year_cb = ttk.Combobox(pf, textvariable=self.sel_year,
                               values=list(range(2020, 2036)),
                               width=6, state="readonly",
                               font=("Segoe UI", 10))
        year_cb.pack(side="left")
        year_cb.bind("<<ComboboxSelected>>", lambda e: self._load())

        lbl("   Month: ")
        self.month_cb = ttk.Combobox(pf, values=MONTHS,
                                     width=6, state="readonly",
                                     font=("Segoe UI", 10))
        self.month_cb.current(self.sel_month.get() - 1)
        self.month_cb.pack(side="left")
        self.month_cb.bind("<<ComboboxSelected>>", self._on_month)

        # ── Toolbar ───────────────────────────────────────────
        tb = tk.Frame(r, bg="#263238", height=42)
        tb.pack(fill="x"); tb.pack_propagate(False)

        def tbtn(text, cmd, color, hint=""):
            label = "{} {}".format(text, hint) if hint else text
            tk.Button(tb, text=label, command=cmd,
                      bg=color, fg="white",
                      font=("Segoe UI", 9),
                      padx=12, pady=4, relief="flat", cursor="hand2",
                      activebackground="#546e7a",
                      activeforeground="white"
                      ).pack(side="left", padx=5, pady=6)

        tbtn("Refresh",       self._load,       "#37474f", "[F5]")
        tbtn("+ Add Entry",   self._add,        "#2e7d32", "[Ctrl+N]")
        tbtn("Edit",          self._edit,       "#1565c0", "[Ctrl+E]")
        tbtn("Delete",        self._delete,     "#b71c1c", "[Del]")
        tbtn("Transactions",  self._open_txns,  "#6a1b9a", "[Enter]")

        self.lbl_year = tk.Label(tb, text="", bg="#263238", fg="#80cbc4",
                                 font=("Segoe UI", 9, "bold"))
        self.lbl_year.pack(side="right", padx=16)

        # ── Status bar — pack BEFORE content so it anchors to bottom ──
        self.status = tk.Label(r, text="", anchor="w",
                               bg="#1e2a3a", fg="#b0bec5",
                               font=("Segoe UI", 9), padx=12, pady=4)
        self.status.pack(fill="x", side="bottom")

        # ── Content area: tree + optional chart side panel ────
        content = tk.Frame(r, bg="#f5f7fa")
        content.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        # Chart panel (right side, only if matplotlib available)
        if HAS_MPL:
            self.chart_frame = tk.Frame(content, bg="#f5f7fa", width=250)
            self.chart_frame.pack(side="right", fill="y", padx=(4, 2))
            self.chart_frame.pack_propagate(False)

        # Tree frame (left / fills remaining space)
        tree_frame = tk.Frame(content, bg="#f5f7fa")
        tree_frame.pack(side="left", fill="both", expand=True)

        # ── Treeview style ─────────────────────────────────────
        style = ttk.Style()
        style.configure("B.Treeview",
                        rowheight=26, font=("Segoe UI", 9),
                        background="#ffffff", fieldbackground="#ffffff",
                        foreground="#212121")
        style.configure("B.Treeview.Heading",
                        font=("Segoe UI", 9, "bold"),
                        background="#37474f", foreground="white",
                        relief="flat")
        style.map("B.Treeview",
                  background=[("selected", "#1565c0")],
                  foreground=[("selected", "#ffffff")])

        cols = ("id", "category", "name", "budget", "actual", "diff", "date")
        self.tree = ttk.Treeview(tree_frame, columns=cols,
                                 show="headings", style="B.Treeview",
                                 selectmode="browse")

        hdrs = [("ID","center",48,False), ("Category","w",112,False),
                ("Name","w",280,True),    ("Budget","e",140,False),
                ("Actual","e",140,False), ("Diff","e",140,False),
                ("Date","center",110,False)]
        for (h, anc, w, stretch), col in zip(hdrs, cols):
            self.tree.heading(col, text=h, anchor=anc)
            self.tree.column(col, width=w, anchor=anc, stretch=stretch)

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._open_txns())

    # ─── HANDLERS ──────────────────────────────────────────────
    def _on_month(self, _=None):
        self.sel_month.set(MONTHS.index(self.month_cb.get()) + 1)
        self._load()

    def _keys(self):
        r = self.root
        r.bind("<Control-n>", lambda e: self._add())
        r.bind("<Control-e>", lambda e: self._edit())
        r.bind("<Delete>",    lambda e: self._delete())
        r.bind("<F5>",        lambda e: self._load())
        r.bind("<Return>",    lambda e: self._open_txns())

    # ─── LOAD ──────────────────────────────────────────────────
    def _load(self, _=None):
        self.month_cb.current(self.sel_month.get() - 1)
        y = self.sel_year.get()
        m = self.sel_month.get()

        rows = self.db.get_entries(y, m)

        for ch in self.tree.get_children(): self.tree.delete(ch)

        tot_b = tot_a = 0.0
        for i, r in enumerate(rows):
            b = r["budget"] or 0
            a = r["actual"] or 0
            d = b - a
            cat = r["category"]

            # Unique tag per (category, diff_direction) — encodes both bg & fg
            sign    = "p" if d >= 0 else "n"
            tag     = "t_{}_{}".format(cat, sign)
            cat_bg  = CAT_BG.get(cat, "#ffffff")
            # Use alternating shades within the same category
            bg      = cat_bg if i % 2 == 0 else self._darken(cat_bg)
            diff_fg = DIFF_POS if d >= 0 else DIFF_NEG
            self.tree.tag_configure(tag, background=bg, foreground=diff_fg)

            self.tree.insert("", "end", iid=str(r["id"]),
                             values=(r["id"], cat, r["name"],
                                     fmt(b), fmt(a), fmt(d),
                                     r["entry_date"] or ""),
                             tags=(tag,))
            tot_b += b; tot_a += a

        rem = tot_b - tot_a
        mn  = MONTHS[m - 1]
        self.status.config(
            text="  {}-{}    {} entries    "
                 "Budget: {}    Actual: {}    Remaining: {}".format(
                     y, mn, len(rows),
                     fmt(tot_b), fmt(tot_a), fmt(rem)))

        yb, ya = self.db.get_year_totals(y)
        self.lbl_year.config(
            text="Year {}   Budget: {}   Actual: {}".format(
                y, fmt(yb), fmt(ya)))

        if HAS_MPL:
            self._draw_chart(y, m)

    @staticmethod
    def _darken(hex_color, amount=12):
        """Slightly darken a hex colour for zebra effect."""
        h = hex_color.lstrip("#")
        rgb = [int(h[i:i+2], 16) for i in (0, 2, 4)]
        rgb = [max(0, c - amount) for c in rgb]
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    # ─── CHART ─────────────────────────────────────────────────
    def _draw_chart(self, y, m):
        for w in self.chart_frame.winfo_children(): w.destroy()
        cat_rows = self.db.get_cat_totals(y, m)
        if not cat_rows: return

        # Sort chart in same order as table
        order = {c: i for i, c in enumerate(CATEGORIES)}
        cat_rows = sorted(cat_rows, key=lambda r: order.get(r["category"], 99))

        cats  = [r["category"] for r in cat_rows]
        bvals = [r["b"] or 0   for r in cat_rows]
        avals = [r["a"] or 0   for r in cat_rows]

        fig = Figure(figsize=(2.5, 5.0), facecolor="#f5f7fa")
        ax  = fig.add_subplot(1, 1, 1)
        ax.set_facecolor("#f5f7fa")
        x = range(len(cats)); h = 0.35
        ax.barh([i + h/2 for i in x], bvals, h,
                label="Budget", color="#90caf9", alpha=0.9)
        ax.barh([i - h/2 for i in x], avals, h,
                label="Actual",
                color=[CAT_BG.get(c, "#cccccc") for c in cats])
        ax.set_yticks(list(x))
        ax.set_yticklabels(cats, fontsize=8)
        ax.set_title("{}-{}\nBudget vs Actual".format(
            MONTHS[m-1], y), fontsize=8, pad=4)
        ax.legend(fontsize=7)
        ax.tick_params(axis="x", labelsize=7)
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout(pad=1.0)

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().configure(bg="#f5f7fa")
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ─── CRUD ──────────────────────────────────────────────────
    def _add(self):
        d = EntryDialog(self.root, "Add Entry",
                        initial={"year": self.sel_year.get(),
                                 "month": self.sel_month.get(),
                                 "category": "Income", "name": "",
                                 "budget": 0.0, "actual": 0.0,
                                 "entry_date": today()})
        if d.result:
            self.db.add_entry(d.result["year"], d.result["month"],
                              d.result["category"], d.result["name"],
                              d.result["budget"], d.result["actual"],
                              d.result["entry_date"])
            self._load()

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showinfo("Select", "Click a row first.", parent=self.root)
            return None
        return s[0]

    def _edit(self):
        iid = self._sel()
        if iid is None: return
        v = self.tree.item(iid)["values"]
        d = EntryDialog(self.root, "Edit Entry",
                        initial={"year": self.sel_year.get(),
                                 "month": self.sel_month.get(),
                                 "category": v[1], "name": v[2],
                                 "budget": strip_fmt(v[3]),
                                 "actual": strip_fmt(v[4]),
                                 "entry_date": v[6]})
        if d.result:
            self.db.update_entry(int(iid), d.result["year"],
                                 d.result["month"], d.result["category"],
                                 d.result["name"], d.result["budget"],
                                 d.result["actual"], d.result["entry_date"])
            self._load()

    def _delete(self):
        iid = self._sel()
        if iid is None: return
        name = self.tree.item(iid)["values"][2]
        if messagebox.askyesno(
                "Delete", "Delete '{}' and all its transactions?".format(name),
                parent=self.root):
            self.db.delete_entry(int(iid)); self._load()

    def _open_txns(self):
        iid = self._sel()
        if iid is None: return
        rows = self.db.get_entries(self.sel_year.get(), self.sel_month.get())
        row  = next((r for r in rows if str(r["id"]) == iid), None)
        if row: TxnWindow(self.root, self.db, row, self._load)

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
