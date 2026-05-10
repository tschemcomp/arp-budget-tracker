# ARP Budget Tracker

A clean, password-protected Python desktop app for tracking monthly and annual personal finances. Built with Tkinter and SQLite — no internet, no accounts, your data stays on your machine.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-green.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

---

## Features

- **Five categories** to mirror a real-world budget — Income, Bills, Variable Expenses, Savings, Extra Debt
- **Budget vs Actual** tracking for every line item, with monthly and annual rollups
- **Quick Add** for cumulative bills (groceries, fuel, etc.) — enter individual spends and they sum into a running total
- **Transaction log** — every Quick Add entry is timestamped with an optional note
- **Charts dashboard** — pie chart for budget composition, bar chart for Budget vs Actual
- **Annual report** — 12-month summary table plus a trend line for every category
- **Export to CSV** — month summary, full year, or transaction log — opens cleanly in Excel or Google Sheets
- **Password protection** — set on first run, hashed with SHA-256
- **Local SQLite database** — single file you can sync via OneDrive / Google Drive / Dropbox
- **Auto cloud detection** — the app automatically picks your OneDrive / Google Drive folder if available

---

## Screenshots

> _Add screenshots here once you've taken a few — for example a screenshot of the main monthly view, the dashboard, and the annual report._

---

## Requirements

- **Python 3.8 or newer** ([download here](https://www.python.org/downloads/))
- **Windows 10 / 11** (currently the only fully-supported platform)
- The following Python packages:
  - `matplotlib`
  - `tkcalendar`

`tkinter` and `sqlite3` come pre-bundled with the standard Python installer — no extra install needed for those.

---

## Installation

### 1. Install Python

Download Python from [python.org/downloads](https://www.python.org/downloads/) and **make sure to tick "Add Python to PATH"** during installation.

### 2. Install dependencies

Open PowerShell or Command Prompt and run:

```powershell
pip install matplotlib tkcalendar
```

### 3. Download the app

Either clone this repository:

```powershell
git clone https://github.com/YOUR_USERNAME/arp-budget-tracker.git
cd arp-budget-tracker
```

Or just download `arp_budget_tracker.py` directly from the repo.

---

## Running the app

From the folder containing `arp_budget_tracker.py`:

```powershell
python arp_budget_tracker.py
```

On first run:
1. The app picks a sensible folder for your data (auto-detects OneDrive / Google Drive if present, else uses the script folder)
2. You'll be asked to **create a password** — pick something memorable
3. The main window opens — start adding entries with the **+ Add** button on each category panel

---

## Creating a Desktop shortcut (Windows)

So you don't have to use PowerShell every time:

1. Right-click the Desktop → **New → Shortcut**
2. Paste the following as the location (replace the path with the actual path to your Python install and script):

   ```
   C:\Users\YOUR_USERNAME\AppData\Local\Programs\Python\Python313\python.exe C:\Users\YOUR_USERNAME\Desktop\arp_budget_tracker.py
   ```

3. Click **Next**, name it **ARP Budget**, click **Finish**
4. Optionally right-click the shortcut → **Properties → Change Icon** to give it a nice icon

Now you can launch the app with one double-click.

---

## How to use

### Adding entries

Click **+ Add** on any category panel. Enter:

- **Item name** (e.g. "Rent", "Salary", "Grocery")
- **Budget** — what you plan to spend / earn
- **Actual** — what you've actually spent / earned (can be 0 if just planning)
- **Date** — defaults to today, change with the calendar widget

### Tracking cumulative spends (groceries, fuel, etc.)

For items where you spend multiple times in a month:

1. Create the item once with **+ Add** — set the **Budget** (e.g. 8000 for Grocery), leave Actual at 0
2. Each time you spend, click the row, then press **Quick Add**
3. Enter the amount (e.g. 450 at D-Mart) with date and optional note
4. The actual auto-increments and each spend is logged separately

### Viewing the transaction log

Click any row, then press the green **Log** button to see every individual Quick Add transaction with date, amount, and note.

### Exporting data

Click **Export CSV** in the top bar. Pick:

- **Month summary** — Budget vs Actual for the current month
- **Full year** — 12-month table for all categories
- **Transaction log** — every individual Quick Add entry

The exported CSV opens directly in Excel or Google Sheets.

### Sync across multiple computers

The app stores everything in a single `arp_budget.db` file. To sync between machines:

1. The first time you run it, it auto-creates the file in OneDrive / Google Drive if available
2. On the second machine, point the app to the same file via **Settings → Change data location**
3. **Important:** never run the app on two machines at the same instant — close it on one before opening on the other so the cloud has time to sync

---

## Data storage

All data lives in **one SQLite file**: `arp_budget.db`

It contains three tables:

- `settings` — your hashed password and config
- `entries` — your monthly budget items
- `transactions` — individual Quick Add events tied to entries

You can open this file with any SQLite viewer (e.g. [DB Browser for SQLite](https://sqlitebrowser.org/)) for a direct look at your data.

---

## Known limitations / notes

- **Windows only (for now)** — Tkinter on recent macOS versions has a known rendering bug that turns dialogs black. The app technically runs on Mac but the UI is unusable. A web-based version is planned to support Mac, iPhone, and iPad.
- The app is single-user. Multiple computers writing to the same `.db` file simultaneously can corrupt it — coordinate which machine has the app open.
- Currency is displayed using the prefix defined in the `CURR` constant near the top of the script. Change it to suit your locale.

---

## Roadmap

- [ ] Web app version (Flask) for true cross-platform / mobile access
- [ ] Multiple budget profiles (e.g. Personal vs Business)
- [ ] Recurring entry templates (auto-create monthly bills)
- [ ] Backup / restore from CSV
- [ ] Localization for currency and date formats

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Built as a personal-finance tool inspired by traditional Excel budget templates, with the goal of being simple, offline, and private.
