"""
demo_setup.py — creates the files needed to run all three demo flows.
Run once from the project root:
    python demo_setup.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HOME = Path.home()


def create_demo_files() -> None:
    print("Creating demo files...")

    # ── Demo 1: file the search/read flow will find ───────────────────────────
    docs = HOME / "Documents"
    docs.mkdir(exist_ok=True)

    budget = docs / "budget_report_2024.txt"
    budget.write_text(
        "Q4 Budget Report — FY 2024\n\n"
        "Total Revenue: ₹42,00,000\n"
        "Total Expenses: ₹31,50,000\n"
        "Net Profit: ₹10,50,000\n\n"
        "Top expense categories:\n"
        "  1. Infrastructure  ₹12,00,000\n"
        "  2. Salaries        ₹16,00,000\n"
        "  3. Marketing        ₹3,50,000\n\n"
        "This report was generated automatically by the Finance team.\n",
        encoding="utf-8",
    )
    print(f"  Created: {budget}")

    # ── Demo 2: file to copy ──────────────────────────────────────────────────
    notes = docs / "notes.txt"
    notes.write_text(
        "Meeting notes — 2024-01-15\n\n"
        "- Reviewed Q4 budget\n"
        "- Discussed roadmap for 2025\n"
        "- Action items assigned to team leads\n",
        encoding="utf-8",
    )
    print(f"  Created: {notes}")

    # ── Demo 3: ensure Desktop exists (Notepad demo) ──────────────────────────
    desktop = HOME / "Desktop"
    desktop.mkdir(exist_ok=True)
    print(f"  Desktop folder: {desktop}")

    print()
    print("Demo files ready. Suggested demo flows:")
    print()
    print("  Demo 1 — Read-only (no confirmation, auto-executes):")
    print('    Find my budget report and summarize it')
    print()
    print("  Demo 2 — File copy with confirmation gate:")
    notes_escaped = str(notes).replace("\\", "\\\\")
    dest_escaped  = str(desktop / "notes_backup.txt").replace("\\", "\\\\")
    print(f'    Copy "{notes_escaped}" to "{dest_escaped}"')
    print()
    print("  Demo 3 — Screen inspect + hotkey:")
    print("    1. Open Notepad (Win+R, notepad, Enter)")
    print("    2. What is on my screen right now?")
    print('    3. press "ctrl+s"')
    print()
    print("  ⛓  Demo 4 — Find then read (2-step chain, no confirmation):")
    print('    Find my budget report, then read it')
    print()
    print("  ⛓  Demo 5 — Open → Type → Save (3-step chain, requires confirmation):")
    print('    Open Notepad, then type "Hello World from Desktop Assistant", then save it')
    print()
    print("  ⛓  Demo 6 — Copy then open (2-step chain with context passing):")
    print(f'    Copy "{notes_escaped}" to "{dest_escaped}", then open it')
    print()


if __name__ == "__main__":
    create_demo_files()
