# UPDATED FOR:
# - Separate Attendance workbook
# - Separate Configuration workbook containing tabs:
#   Reduced-Hour Students
#   Schedule Changes
#   On-Hold Students
# - On-Hold end date optional (blank = indefinite hold)

"""
Makeup Session Analyzer — Desktop App
======================================
Run with:  python makeup_analyzer_app.py
Requires:  pip install pandas openpyxl
Tkinter is included with standard Python (no install needed).

Attendance is a separate workbook.
Additional Configuration Workbook format:
  Tabs expected (names can vary):
    • Attendance
    • Reduced-hours students (optional)
    • Schedule changes (optional)
    • On hold (optional)

  Example hold row:
    Jane | Doe | 2026-04-15 | 2026-05-31
"""

import sys
import traceback
import threading
from datetime import date
from tkinter import (
    Tk, Toplevel, Frame, Label, Button, Text, Scrollbar,
    StringVar, IntVar, BooleanVar, Checkbutton, Radiobutton,
    filedialog, messagebox, ttk,
    END, WORD, BOTH, RIGHT, Y, X, LEFT, W, N, S, E, DISABLED, NORMAL,
)

import pandas as pd

import sys as _sys, os as _os
# When running as a PyInstaller .exe, bundled files land in sys._MEIPASS.
# Add that folder to the path so `import analyzer_core` works.
if getattr(_sys, "frozen", False):
    _sys.path.insert(0, _sys._MEIPASS)
else:
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import analyzer_core as core
from analyzer_core import (
    DAY_FULL,
    load_reduced_students, load_schedule_changes, load_attendance,
    load_hold_students, load_new_students,
    infer_schedule, analyze, export_excel,
)


# ---------------------------------------------------------------------------
# Dialog: resolve tied schedule days
# ---------------------------------------------------------------------------
class TieResolverDialog(Toplevel):
    """
    Shown when attendance history is ambiguous about which day(s) form the
    regular schedule.  pick_count=1 for once-a-week students (reduced-hours
    or 2-hr standard); pick_count=2 for twice-a-week students.
    """
    def __init__(self, parent, student: str, all_days: list,
                 fixed_days: list, pick_count: int = 2):
        super().__init__(parent)
        self.title("Resolve Schedule Ambiguity")
        self.resizable(False, False)
        self.result = None
        self._pick  = pick_count
        self._vars  = {}
        pad = {"padx": 24}

        Label(self, text="Schedule ambiguity for:",
              font=("Helvetica", 10)).pack(**pad, pady=(18, 2))
        Label(self, text=student,
              font=("Helvetica", 12, "bold")).pack(**pad)

        if pick_count == 1:
            msg = ("The days below were attended an equal number of times.\n"
                   "Select the 1 day that is their regular session day:")
        else:
            msg = ("The days below were attended an equal number of times.\n"
                   "Select exactly 2 that are their regular schedule days:")
        Label(self, text=msg, wraplength=340, justify="left",
              font=("Helvetica", 10)).pack(**pad, pady=(10, 6))

        box = Frame(self, relief="groove", bd=1)
        box.pack(**pad, pady=(0, 8), fill=X)
        for wday in sorted(all_days):
            var   = BooleanVar(value=(wday in fixed_days))
            state = DISABLED if wday in fixed_days else NORMAL
            Checkbutton(box, text=f"  {DAY_FULL[wday]}", variable=var,
                        font=("Helvetica", 11), state=state,
                        command=self._update).pack(anchor=W, padx=8, pady=2)
            self._vars[wday] = var

        self._status = Label(self, text="", fg="#b45309", font=("Helvetica", 9))
        self._status.pack()
        self._btn = Button(self, text="Confirm", command=self._confirm,
                           bg="#2563eb", fg="white", font=("Helvetica", 11, "bold"),
                           relief="flat", padx=14, pady=6, state=DISABLED, cursor="hand2")
        self._btn.pack(pady=(6, 18))

        self._update()
        self._center(parent)
        self.transient(parent)
        self.grab_set()
        # Prevent closing without confirming — would silently drop the student.
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        parent.wait_window(self)

    def _on_close_attempt(self):
        messagebox.showwarning(
            "Selection required",
            "Please select the correct day(s) before closing.\n\n"
            "Closing without selecting will exclude this student from results.",
            parent=self,
        )

    def _update(self):
        n = sum(1 for v in self._vars.values() if v.get())
        if n == self._pick:
            self._btn.config(state=NORMAL); self._status.config(text="")
        elif n < self._pick:
            self._btn.config(state=DISABLED)
            self._status.config(text=f"Select {self._pick - n} more day(s)")
        else:
            self._btn.config(state=DISABLED)
            self._status.config(text=f"Too many — uncheck {n - self._pick}")

    def _confirm(self):
        self.result = sorted(d for d, v in self._vars.items() if v.get())
        self.destroy()

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# ---------------------------------------------------------------------------
# Dialog: resolve single-day ambiguity
# ---------------------------------------------------------------------------
class SingleDayResolverDialog(Toplevel):
    def __init__(self, parent, student: str, known_day: int):
        super().__init__(parent)
        self.title("Incomplete Schedule Data")
        self.resizable(False, False)
        self.result = None
        pad = {"padx": 24}

        Label(self, text="Incomplete schedule data for:",
              font=("Helvetica", 10)).pack(**pad, pady=(18, 2))
        Label(self, text=student,
              font=("Helvetica", 12, "bold")).pack(**pad)
        Label(self,
              text=(f"Only {DAY_FULL[known_day]} was found in their history.\n"
                    "What is their second session day?"),
              wraplength=340, justify="left",
              font=("Helvetica", 10)).pack(**pad, pady=(10, 6))

        box = Frame(self, relief="groove", bd=1)
        box.pack(**pad, pady=(0, 8), fill=X)
        self._var = IntVar(value=-99)

        for wday in range(6):
            if wday == known_day:
                continue
            Radiobutton(box, text=f"  {DAY_FULL[wday]}",
                        variable=self._var, value=wday,
                        font=("Helvetica", 11),
                        command=self._update).pack(anchor=W, padx=8, pady=1)
        Radiobutton(box, text="  They only come once a week",
                    variable=self._var, value=-1,
                    font=("Helvetica", 10, "italic"),
                    command=self._update).pack(anchor=W, padx=8, pady=(8, 4))

        self._btn = Button(self, text="Confirm", command=self._confirm,
                           bg="#2563eb", fg="white", font=("Helvetica", 11, "bold"),
                           relief="flat", padx=14, pady=6, state=DISABLED, cursor="hand2")
        self._btn.pack(pady=(6, 18))

        self._center(parent)
        self.transient(parent)
        self.grab_set()
        # Prevent closing without confirming — would silently drop the student.
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        parent.wait_window(self)

    def _on_close_attempt(self):
        messagebox.showwarning(
            "Selection required",
            "Please select a day (or 'once a week') before closing.\n\n"
            "Closing without selecting will exclude this student from results.",
            parent=self,
        )

    def _update(self):
        self._btn.config(state=NORMAL if self._var.get() != -99 else DISABLED)

    def _confirm(self):
        self.result = self._var.get()
        self.destroy()

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
class App(Tk):
    def __init__(self):
        super().__init__()
        self.title("Makeup Session Analyzer")
        self.resizable(True, True)
        self.minsize(720, 580)
        self.configure(bg="#f0f0f0")

        self.attendance_path = StringVar()
        self.config_path     = StringVar()
        self._results          = []
        self._skipped_students = []

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # Two file pickers: attendance sheet + configuration workbook
        picker = Frame(self, bg="#f0f0f0")
        picker.pack(fill=X, **pad)
        self._file_row(picker, "Attendance sheet (.xlsx):",
                       self.attendance_path, self._pick_attendance, row=0)
        self._file_row(picker, "Configuration workbook (.xlsx):",
                       self.config_path, self._pick_config, row=1)
        Label(picker,
              text=("Configuration workbook is optional. "
                    "Expected tabs: Reduced-Hour Students, Schedule Changes, On-Hold Students."),
              bg="#f0f0f0", fg="#777", font=("Helvetica", 9)).grid(
              row=2, column=1, sticky=W, pady=(0, 4))

        # Buttons
        btn_frame = Frame(self, bg="#f0f0f0")
        btn_frame.pack(fill=X, padx=12, pady=(0, 8))

        self.run_btn = Button(
            btn_frame, text="Run Analysis", command=self._run,
            bg="#2563eb", fg="white", font=("Helvetica", 11, "bold"),
            relief="flat", padx=16, pady=6, cursor="hand2",
            activebackground="#1d4ed8", activeforeground="white")
        self.run_btn.pack(side=LEFT)

        self.export_btn = Button(
            btn_frame, text="Export to Excel", command=self._export,
            bg="#16a34a", fg="white", font=("Helvetica", 11, "bold"),
            relief="flat", padx=16, pady=6, cursor="hand2",
            activebackground="#15803d", activeforeground="white",
            state=DISABLED)
        self.export_btn.pack(side=LEFT, padx=(10, 0))

        self.status_lbl = Label(btn_frame, text="", bg="#f0f0f0",
                                fg="#555", font=("Helvetica", 10))
        self.status_lbl.pack(side=LEFT, padx=(14, 0))

        # Results table
        tbl = Frame(self, bg="#f0f0f0")
        tbl.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        cols = ("Student", "Month", "Status",
                "Makeups done", "Still needed")
        self.tree = ttk.Treeview(tbl, columns=cols,
                                 show="headings", selectmode="browse")
        widths = {"Student": 180, "Month": 120, "Status": 180,
                  "Makeups done": 110, "Still needed": 90}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c], anchor=W, stretch=True)
        self.tree.tag_configure("open",    background="#fee2e2")
        self.tree.tag_configure("at_risk", background="#fef9c3")
        self.tree.tag_configure("on_hold", background="#dbeafe")
        self.tree.tag_configure("done",    background="#dcfce7")

        vsb = Scrollbar(tbl, orient="vertical",   command=self.tree.yview)
        hsb = Scrollbar(tbl, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky=N+S+E+W)
        vsb.grid(row=0, column=1, sticky=N+S)
        hsb.grid(row=1, column=0, sticky=E+W)
        tbl.rowconfigure(0, weight=1)
        tbl.columnconfigure(0, weight=1)

        # Detail panel
        det = Frame(self, bg="#f0f0f0")
        det.pack(fill=X, padx=12, pady=(0, 12))
        Label(det, text="Details:", bg="#f0f0f0",
              font=("Helvetica", 10, "bold")).pack(anchor=W)
        dscroll = Scrollbar(det)
        dscroll.pack(side=RIGHT, fill=Y)
        self.detail = Text(det, height=5, wrap=WORD, state=DISABLED,
                           yscrollcommand=dscroll.set, font=("Courier", 10),
                           bg="#1e1e1e", fg="#d4d4d4", relief="flat", padx=8, pady=6)
        self.detail.pack(fill=X)
        dscroll.config(command=self.detail.yview)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _file_row(self, parent, label, var, cmd, row):
        Label(parent, text=label, bg="#f0f0f0",
              font=("Helvetica", 10)).grid(row=row, column=0, sticky=W, pady=3)
        Label(parent, textvariable=var, bg="white", relief="sunken",
              width=52, anchor=W, font=("Helvetica", 10)).grid(
              row=row, column=1, sticky=W+E, padx=(8, 6), pady=3)
        Button(parent, text="Browse…", command=cmd,
               font=("Helvetica", 10), cursor="hand2").grid(
               row=row, column=2, sticky=W, pady=3)
        parent.columnconfigure(1, weight=1)

    def _pick_attendance(self):
        p = filedialog.askopenfilename(
            title="Select attendance sheet",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if p:
            self.attendance_path.set(p)

    def _pick_config(self):
        p = filedialog.askopenfilename(
            title="Select configuration workbook (Reduced-Hour Students, Schedule Changes, On-Hold Students)",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if p:
            self.config_path.set(p)

    # ── Run flow ─────────────────────────────────────────────────────────────

    def _run(self):
        if not self.attendance_path.get():
            messagebox.showwarning("No file", "Please select an attendance sheet first.")
            return
        self.run_btn.config(state=DISABLED, text="Loading…")
        self.export_btn.config(state=DISABLED)
        self.status_lbl.config(text="")
        self._clear_table()
        self.after(60, self._phase1_load)

    def _phase1_load(self):
        try:
            attendance = self.attendance_path.get()
            config     = self.config_path.get()

            # Load optional configuration tabs from the config workbook.
            # If no config workbook was provided, all defaults are used.
            core.REDUCED_REQUIREMENT = set()
            changes      = []
            hold_periods = []
            new_students = {}

            if config:
                core.REDUCED_REQUIREMENT = self._load_optional_component(
                    config,
                    load_reduced_students,
                    preferred_terms=("reduced", "reduced-hours", "reduced hours"),
                    default=set(),
                )
                changes = self._load_optional_component(
                    config,
                    load_schedule_changes,
                    preferred_terms=("schedule change", "schedule changes", "change"),
                    default=[],
                )
                hold_periods = self._load_optional_component(
                    config,
                    load_hold_students,
                    preferred_terms=("hold", "on hold", "holds"),
                    default=[],
                )
                new_students = self._load_optional_component(
                    config,
                    load_new_students,
                    preferred_terms=("new student", "new students", "new"),
                    default={},
                )

            # Load attendance from its own separate file.
            df, hours_col, sched_col = load_attendance(attendance)

            self.run_btn.config(text="Resolving schedules…")
            self.update_idletasks()

            schedules = self._resolve_schedules(df, hours_col, sched_col)

            self.run_btn.config(text="Analyzing…")
            threading.Thread(
                target=self._phase2_analyze,
                args=(df, hours_col, schedules, changes, hold_periods, new_students),
                daemon=True,
            ).start()

        except Exception:
            self.run_btn.config(state=NORMAL, text="Run Analysis")
            messagebox.showerror("Error", traceback.format_exc())

    def _resolve_schedules(self, df, hours_col, sched_col) -> dict:
        # Capture the reduced set once here so every infer_schedule call
        # uses the same set that was loaded moments ago, with no reliance
        # on the module global being read at the right moment.
        reduced_set = set(core.REDUCED_REQUIREMENT)
        schedules   = {}
        self._skipped_students = []   # students whose schedule couldn't be resolved

        for student in sorted(df["_student"].unique()):
            sdf  = df[df["_student"] == student]
            info = infer_schedule(student, sdf, hours_col, sched_col,
                                  reduced_set=reduced_set,
                                  reference_date=date.today())

            if info["needs_dialog"]:
                if info["dialog_reason"] == "tie":
                    dlg = TieResolverDialog(self, student,
                                            all_days=info["tie_days"],
                                            fixed_days=info["fixed_days"],
                                            pick_count=info.get("pick_count", 2))
                    info["schedule"] = dlg.result or []
                elif info["dialog_reason"] == "single_day":
                    dlg = SingleDayResolverDialog(self, student,
                                                  known_day=info["known_day"])
                    if dlg.result is None or dlg.result == -1:
                        info["schedule"] = [info["known_day"]]
                        if dlg.result == -1:   # "only once a week" → reduced hours
                            core.REDUCED_REQUIREMENT.add(student)
                    else:
                        info["schedule"] = sorted([info["known_day"], dlg.result])

            final_schedule = info.get("schedule") or []
            if not final_schedule:
                # Schedule is empty — student will be excluded from analysis.
                # Record them so the UI can warn the user.
                self._skipped_students.append(student)

            schedules[student] = {
                "schedule":        final_schedule,
                "hrs_per_session": info["hrs_per_session"],
            }
        return schedules

    def _phase2_analyze(self, df, hours_col, schedules, changes, hold_periods, new_students):
        try:
            results, skipped = analyze(
                df, hours_col, schedules,
                schedule_changes=changes,
                hold_periods=hold_periods,
                new_students=new_students,
            )
            self.after(0, self._populate_table, results, skipped)
        except Exception:
            self.after(0, self._show_exc, traceback.format_exc())

    def _load_required_component(self, workbook, loader, preferred_terms=()):
        result, sheet = self._load_component(
            workbook, loader, preferred_terms=preferred_terms, required=True
        )
        return result

    def _load_optional_component(self, workbook, loader, preferred_terms=(), default=None):
        result, sheet = self._load_component(
            workbook, loader, preferred_terms=preferred_terms, required=False
        )
        return default if result is None else result

    def _load_component(self, workbook, loader, preferred_terms=(), required=False):
        xl = pd.ExcelFile(workbook)
        sheet_names = list(xl.sheet_names)
        preferred_terms = tuple(t.lower() for t in preferred_terms)

        preferred = [
            s for s in sheet_names
            if any(term in s.lower() for term in preferred_terms)
        ]
        candidates = preferred + [s for s in sheet_names if s not in preferred]

        last_error = None
        for sheet in candidates:
            try:
                return loader(workbook, sheet_name=sheet), sheet
            except Exception as e:
                last_error = e

        if required:
            raise ValueError(
                f"Could not find a valid sheet for {loader.__name__}. "
                f"Last error: {last_error}"
            )
        return None, None

    # ── Table ─────────────────────────────────────────────────────────────────

    def _clear_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._set_detail("")

    def _populate_table(self, results, skipped=None):
        self._results = results
        self.run_btn.config(state=NORMAL, text="Run Analysis")
        self._clear_table()

        if skipped:
            names = "\n".join(f"  \u2022 {n}:\n    {r}" for n, r in skipped.items())
            messagebox.showwarning(
                "Schedule not determined for some students",
                "The following student(s) were excluded because their regular "
                "session days could not be determined. Re-run and complete the "
                "schedule dialog for each:\n\n" + names
            )

        if not results:
            self.status_lbl.config(text="No students need makeups.", fg="#16a34a")
            # If there are also no skipped students, something unexpected happened.
            # Show a diagnostic so the user knows the tool ran and found nothing.
            if not skipped:
                ref = date.today()
                win_start, win_end = __import__('analyzer_core').grace_window(ref)
                messagebox.showinfo(
                    "Analysis complete",
                    f"Analysis ran successfully as of {ref}.\n"
                    f"Grace window: {win_start} → {win_end}\n\n"
                    f"No students were found to need makeups or be at risk "
                    f"within this window."
                )
            return

        outstanding = [r for r in results if r["Still needed (hrs)"] > 0 and r["Status"] != "On Hold"]
        on_hold = [r for r in results if r["Status"] == "On Hold"]
        status_text = (
            f"{len(outstanding)} open makeup(s) across "
            f"{len(set(r['Student'] for r in outstanding))} student(s)."
        )
        if on_hold:
            status_text += f"  {len(on_hold)} on hold."
        self.status_lbl.config(text=status_text, fg="#b45309")

        for i, r in enumerate(results):
            if r["Status"] == "On Hold":
                tag = "on_hold"
            elif r["Still needed (hrs)"] > 0:
                tag = "open"
            elif r["_at_risk"]:
                tag = "at_risk"
            else:
                tag = "done"
            self.tree.insert("", END, iid=str(i), tags=(tag,), values=(
                r["Student"], r["Month"], r["Status"],
                r["Makeups completed (hrs)"], r["Still needed (hrs)"],
            ))
        self.export_btn.config(state=NORMAL)

        if self._skipped_students:
            names = "\n".join(f"  • {s}" for s in self._skipped_students)
            messagebox.showwarning(
                "Students excluded from results",
                "The following student(s) were excluded because their regular "
                "session days could not be determined.\n\n"
                + names +
                "\n\nTo include them, re-run the analysis and complete the "
                "schedule dialog when it appears for each student.",
            )

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        r     = self._results[int(sel[0])]
        still = r["Still needed (hrs)"]
        done  = r["Makeups completed (hrs)"]
        hold_info = ""
        if r.get("On Hold"):
            hold_info = (
                f"\nOn hold      : {r['Hold Start']} to {r['Hold End']}"
                if r.get("Hold Start") or r.get("Hold End") else ""
            )

        self._set_detail(
            f"Student : {r['Student']}\nSchedule: {r['Schedule']}\n"
            f"Month   : {r['Month']}\n"
            f"Makeups done    : {done} hrs"
            + (f"  on {r['Makeups completed (dates)']}" if done > 0 else "") + "\n"
            f"Status          : {r['Status']}"
            + hold_info + "\n"
            f"Missed sessions : {r['Missed regular sessions']}"
        )

    def _set_detail(self, txt):
        self.detail.config(state="normal")
        self.detail.delete("1.0", END)
        self.detail.insert(END, txt)
        self.detail.config(state=DISABLED)

    def _export(self):
        if not self._results:
            return
        path = filedialog.asksaveasfilename(
            title="Save results as…", defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="makeup_report.xlsx")
        if not path:
            return
        try:
            count = export_excel(self._results, path)
            if count == 0:
                messagebox.showinfo("Nothing to export",
                                    "No students have outstanding makeups.")
            else:
                messagebox.showinfo("Saved", f"Exported {count} record(s) to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _show_exc(self, tb_str: str):
        self.run_btn.config(state=NORMAL, text="Run Analysis")
        messagebox.showerror("Error", tb_str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        messagebox.showerror(
            "Unexpected Error",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

    sys.excepthook = handle_exception
    App().mainloop()
