# UPDATED FOR:
# - On-Hold Students tab
# - Hold Start Date required
# - Hold End Date optional (blank = indefinite)
# - Status overridden to 'On Hold' while preserving calculated shortage

"""
analyzer_core.py
=================
All non-GUI logic for the Makeup Session Analyzer.
Imported by both makeup_analyzer_app.py and makeup_analyzer_cli.py.
"""

import math
import calendar
from datetime import date, timedelta
from collections import defaultdict

import pandas as pd


# ---------------------------------------------------------------------------
# Config  (mutated at runtime by callers)
# ---------------------------------------------------------------------------
REDUCED_REQUIREMENT: set = set()
DEFAULT_REQUIRED_HRS = 8
REDUCED_REQUIRED_HRS = 4


def required_hrs(student: str) -> int:
    return REDUCED_REQUIRED_HRS if student in REDUCED_REQUIREMENT else DEFAULT_REQUIRED_HRS


# ---------------------------------------------------------------------------
# Day lookups
# ---------------------------------------------------------------------------
DAY_MAP = {
    "mo": 0, "mon": 0, "monday": 0,
    "tu": 1, "tue": 1, "tues": 1, "tuesday": 1,
    "we": 2, "wed": 2, "wednesday": 2,
    "th": 3, "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fr": 4, "fri": 4, "friday": 4,
    "sa": 5, "sat": 5, "saturday": 5,
}
DAY_FULL = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday",
}
DAY_SHORT = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat"}


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def month_offset(year: int, month: int, delta: int):
    m, y = month + delta, year
    while m > 12: m -= 12; y += 1
    while m < 1:  m += 12; y -= 1
    return y, m


def add_months(d: date, n: int) -> date:
    yr, mo = month_offset(d.year, d.month, n)
    last = calendar.monthrange(yr, mo)[1]
    return date(yr, mo, min(d.day, last))


def last_day_of(yr: int, mo: int) -> date:
    return date(yr, mo, calendar.monthrange(yr, mo)[1])


def month_label(yr: int, mo: int) -> str:
    return f"{calendar.month_name[mo]} {yr}"


def grace_window(ref: date):
    """
    window_end   = yesterday  (attendance recorded end-of-day; today not yet counted)
    window_start = exactly 2 months before ref, same day, clamped to month end
    Example: ref = Apr 28  →  start = Feb 28,  end = Apr 27
    """
    window_end = ref - timedelta(days=1)
    yr, mo = month_offset(ref.year, ref.month, -2)
    last = calendar.monthrange(yr, mo)[1]
    window_start = date(yr, mo, min(ref.day, last))
    return window_start, window_end


# ---------------------------------------------------------------------------
# Schedule-change helpers
# ---------------------------------------------------------------------------
def effective_schedule(student: str, d: date,
                        base_schedule: list, changes: list) -> list:
    """Most recent change with effective_date <= d, else base_schedule."""
    if not changes:
        return base_schedule
    applicable = [
        (c["effective_date"], c["schedule"])
        for c in changes
        if c["student"] == student and c["effective_date"] <= d
    ]
    if not applicable:
        return base_schedule
    return max(applicable, key=lambda x: x[0])[1]


def scheduled_sessions_in_month(yr: int, mo: int,
                                  student: str, base_schedule: list,
                                  changes: list) -> list:
    """All dates in (yr, mo) that are scheduled for this student,
    accounting for mid-month schedule changes."""
    first_d, last_d = date(yr, mo, 1), last_day_of(yr, mo)
    results, d = [], first_d
    while d <= last_d:
        if d.weekday() in effective_schedule(student, d, base_schedule, changes):
            results.append(d)
        d += timedelta(days=1)
    return results


def is_makeup_session(student: str, d: date,
                       base_schedule: list, changes: list) -> bool:
    """True if `d` is outside the student's effective schedule on that date."""
    return d.weekday() not in effective_schedule(student, d, base_schedule, changes)


# ---------------------------------------------------------------------------
# Column finder / schedule parser
# ---------------------------------------------------------------------------
def find_col(columns, *keywords):
    for kw in keywords:
        for col in columns:
            if kw.lower() in col.lower():
                return col
    return None


def parse_session_days(raw) -> list:
    if pd.isna(raw) or not str(raw).strip():
        return []
    result = []
    for tok in str(raw).replace("/", ",").replace(";", ",").split(","):
        key = tok.strip().lower()
        if key in DAY_MAP:
            wday = DAY_MAP[key]
            if wday not in result:
                result.append(wday)
    return sorted(result)


# ---------------------------------------------------------------------------
# Schedule inference
# ---------------------------------------------------------------------------
def _ok(schedule, hrs):
    return {"schedule": schedule, "hrs_per_session": hrs,
            "needs_dialog": False, "dialog_reason": None,
            "tie_days": [], "fixed_days": [], "known_day": None,
            "pick_count": None}


def infer_schedule(student: str, sdf, hours_col: str, sched_col,
                   reduced_set: set = None,
                   reference_date: date = None) -> dict:
    """
    Infer a student's regular schedule from their full attendance history.
    Returns a dict; if needs_dialog is True the caller must resolve it.

    reduced_set    : set of reduced-hours student names — pass explicitly so
                     the caller controls which set is used at inference time.
    reference_date : used to restrict hrs_per_session estimation to prior months,
                     since the current month may have irregular makeup sessions.
    """
    if reduced_set is None:
        reduced_set = REDUCED_REQUIREMENT
    if reference_date is None:
        reference_date = date.today()

    def _req():
        return REDUCED_REQUIRED_HRS if student in reduced_set else DEFAULT_REQUIRED_HRS

    # 1. Explicit schedule column takes priority — cell values only.
    # The column-header fallback ("Session days: Tu, Thu" in the name) is
    # intentionally NOT used: it would apply the same schedule to every
    # student whose cells are empty, which is wrong when students differ.
    if sched_col:
        vals = sdf[sched_col].dropna()
        raw  = vals.mode().iloc[0] if not vals.empty else None
        if raw is not None:
            schedule = parse_session_days(raw)
            if schedule:
                reg = sdf[sdf["_wday"].isin(schedule)]
                # Use mode() so a single outlier session doesn't inflate hrs.
                mode_vals = reg[hours_col].mode() if len(reg) > 0 else None
                hrs = float(mode_vals.iloc[0]) if mode_vals is not None and len(mode_vals) > 0 else 1.0
                hrs = max(hrs, 1.0)
                # Validate completeness: if the column only gives 1 day but
                # this student needs 2 (non-reduced, 1-hr), fall through to
                # attendance inference so the second day can be resolved.
                needs_two = len(schedule) < 2 and student not in reduced_set and (hrs * 4) < _req()
                if not needs_two:
                    return _ok(schedule, hrs)
                # else fall through to attendance-based inference below

    # 2. Infer from attendance history (excluding Sunday)
    wday_counts = sdf["_wday"].value_counts().sort_values(ascending=False)
    days  = [d for d in wday_counts.index.tolist() if d != 6]
    freqs = [wday_counts[d] for d in days]

    if not days:
        return _ok([], 1.0)

    # hrs_per_session: use mode on candidate schedule days from PRIOR months
    # only.  The current month may have irregular 2hr makeup sessions on the
    # student's regular days that would inflate hrs_mode and make projected
    # hours overshoot 8, masking an at-risk condition.
    # Falls back to all history only when no prior-month data exists.
    candidate_days = days[:2]
    prior_rows = sdf[
        (sdf["_year"] < reference_date.year) |
        ((sdf["_year"] == reference_date.year) &
         (sdf["_month"] < reference_date.month))
    ]
    cand_rows = prior_rows[prior_rows["_wday"].isin(candidate_days)]
    if len(cand_rows) == 0:
        # No prior history — fall back to all available sessions
        cand_rows = sdf[sdf["_wday"].isin(candidate_days)]
    if len(cand_rows) > 0:
        mode_vals = cand_rows[hours_col].mode()
        hrs_mode  = float(mode_vals.iloc[0]) if len(mode_vals) > 0 else 1.0
    else:
        hrs_mode  = 1.0
    hrs_mode = max(hrs_mode, 1.0)

    # Reduced-hours students only need 1 session day per week (4 hrs/month).
    # All other students need 2 days — even if their sessions are 2 hrs each,
    # because a non-reduced student who genuinely comes once a week for 2 hrs
    # will always have a single clear top day in their history and will never
    # reach the tie logic below.
    is_reduced = student in reduced_set

    if is_reduced:
        # Only needs 1 day. If the top day is a clear winner, use it directly.
        if len(days) == 1 or freqs[0] > freqs[1]:
            return _ok(days[:1], hrs_mode)
        # Tie at the top — ask the user to pick the 1 correct day.
        tied = sorted(d for d, f in zip(days, freqs) if f == freqs[0])
        return {"schedule": None, "hrs_per_session": hrs_mode,
                "needs_dialog": True, "dialog_reason": "tie",
                "tie_days": tied, "fixed_days": [],
                "known_day": None, "pick_count": 1}
    else:
        # Needs 2 days per week — unless one day alone already covers the
        # monthly requirement AND is a clear attendance winner.
        # Check this first, before any tie logic, so that a 2-hr student
        # with sporadic makeup appearances on other days isn't pulled into
        # a false tie (e.g. Wed×8 plus Mon×1 and Fri×1 from makeups).
        top_day_sufficient = (hrs_mode * 4) >= _req()
        top_day_clear      = len(days) == 1 or freqs[0] > freqs[1]
        if top_day_sufficient and top_day_clear:
            return _ok(days[:1], hrs_mode)

        # Only 1 day found — ask for the second day (1-hr student who needs 2).
        if len(days) == 1:
            return {"schedule": None, "hrs_per_session": hrs_mode,
                    "needs_dialog": True, "dialog_reason": "single_day",
                    "tie_days": [], "fixed_days": [], "known_day": days[0],
                    "pick_count": 2}

        # Tie at the 2nd/3rd boundary — can't tell which 2 days are the schedule.
        if len(days) >= 3 and freqs[1] == freqs[2]:
            fixed = [d for d, f in zip(days, freqs) if f > freqs[1]]
            tied  = sorted(set([d for d, f in zip(days, freqs)
                                if f >= freqs[1]] + fixed))
            return {"schedule": None, "hrs_per_session": hrs_mode,
                    "needs_dialog": True, "dialog_reason": "tie",
                    "tie_days": tied, "fixed_days": fixed,
                    "known_day": None, "pick_count": 2}

        # Clear top 2.
        schedule  = sorted(days[:2])
        reg       = sdf[sdf["_wday"].isin(schedule)]
        if len(reg) > 0:
            m   = reg[hours_col].mode()
            hrs = float(m.iloc[0]) if len(m) > 0 else hrs_mode
        else:
            hrs = hrs_mode
        return _ok(schedule, max(hrs, 1.0))


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------
def load_reduced_students(filepath: str, sheet_name=0) -> set:
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]
    first_col = find_col(df.columns, "first name", "first")
    last_col  = find_col(df.columns, "last name",  "last")
    name_col  = find_col(df.columns, "full name",  "name")
    names = set()
    if first_col and last_col:
        for _, row in df.iterrows():
            f, l = str(row[first_col]).strip(), str(row[last_col]).strip()
            if f not in ("", "nan") and l not in ("", "nan"):
                names.add(f"{f} {l}")
    elif name_col:
        for val in df[name_col].dropna():
            n = str(val).strip()
            if n:
                names.add(n)
    else:
        for val in df[df.columns[0]].dropna():
            n = str(val).strip()
            if n:
                names.add(n)
    return names


def load_schedule_changes(filepath: str, sheet_name=0) -> list:
    """
    Load schedule changes from Excel.
    Required columns:
      - Name: "First Name" + "Last Name"  OR  "Full Name" / "Name"
      - "Effective Date"  (any date-parseable format)
      - "New Session Days"  (e.g. "Mon, Wed")
    Returns: [{"student": str, "effective_date": date, "schedule": [int,...]}, ...]
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]

    first_col = find_col(df.columns, "first name", "first")
    last_col  = find_col(df.columns, "last name",  "last")
    name_col  = find_col(df.columns, "full name",  "name")
    date_col  = find_col(df.columns, "effective date", "date")
    days_col  = find_col(df.columns, "new session days", "session days", "session")

    if not date_col:
        raise ValueError("Schedule-changes sheet must have an 'Effective Date' column.")
    if not days_col:
        raise ValueError("Schedule-changes sheet must have a 'New Session Days' column.")

    results = []
    for _, row in df.iterrows():
        if first_col and last_col:
            f, l = str(row[first_col]).strip(), str(row[last_col]).strip()
            if f in ("", "nan") or l in ("", "nan"):
                continue
            name = f"{f} {l}"
        elif name_col:
            name = str(row[name_col]).strip()
            if not name or name == "nan":
                continue
        else:
            continue

        try:
            eff_date = pd.to_datetime(row[date_col]).date()
        except Exception:
            continue

        schedule = parse_session_days(str(row[days_col]))
        if not schedule:
            continue

        results.append({"student": name, "effective_date": eff_date,
                         "schedule": schedule})
    return results


def load_attendance(filepath: str, sheet_name=0):
    """
    Auto-detects the header row to handle blank rows above the real headers.
    Returns (df, hours_col_name, sched_col_name_or_None).
    """
    raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    header_row = 0
    for i, row_data in raw.iterrows():
        vals = [str(v).strip().lower() for v in row_data.values]
        if any(kw in v for v in vals
               for kw in ("attendance date", "first name", "last name")):
            header_row = i
            break

    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    date_col  = find_col(df.columns, "attendance date", "date")
    first_col = find_col(df.columns, "first name",       "first")
    last_col  = find_col(df.columns, "last name",        "last")
    hours_col = find_col(df.columns, "duration (hours)", "hours")
    sched_col = find_col(df.columns, "session day",      "session")

    missing = [n for n, c in [
        ("Attendance Date", date_col), ("First Name", first_col),
        ("Last Name", last_col),       ("Duration (Hours)", hours_col),
    ] if c is None]
    if missing:
        raise ValueError(
            f"Could not find required columns in the attendance sheet.\n"
            f"Missing: {missing}\nColumns found: {list(df.columns)}"
        )

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, first_col, last_col])
    df["_student"] = df[first_col].str.strip() + " " + df[last_col].str.strip()
    df["_date"]    = df[date_col].dt.date
    df["_year"]    = df[date_col].dt.year
    df["_month"]   = df[date_col].dt.month
    df["_wday"]    = df["_date"].apply(lambda d: d.weekday())
    df[hours_col]  = pd.to_numeric(df[hours_col], errors="coerce").fillna(0)

    return df, hours_col, sched_col



def load_hold_students(filepath: str, sheet_name=0) -> list:
    """
    Load hold periods from Excel.
    Accepted columns:
      - Name: "First Name" + "Last Name"  OR  "Full Name" / "Name"
      - Start date: "Effective Date", "Start Date", "Hold Start Date", etc.
      - End date:   "End Date", "Hold End Date", etc.
    Returns: [{"student": str, "start_date": date, "end_date": date}, ...]
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]

    first_col = find_col(df.columns, "first name", "first")
    last_col  = find_col(df.columns, "last name",  "last")
    name_col  = find_col(df.columns, "full name",  "name")

    start_col = find_col(
        df.columns,
        "effective date", "start date", "hold start", "begin date", "begin"
    )
    end_col = find_col(
        df.columns,
        "end date", "hold end", "end", "through", "until"
    )

    if not start_col:
        raise ValueError(
            "On-hold sheet must have a start date column "
            "(for example 'Effective Date' or 'Start Date')."
        )
    # end_col is optional — a blank or missing end date means indefinite hold.

    results = []
    for _, row in df.iterrows():
        if first_col and last_col:
            f, l = str(row[first_col]).strip(), str(row[last_col]).strip()
            if f in ("", "nan") or l in ("", "nan"):
                continue
            name = f"{f} {l}"
        elif name_col:
            name = str(row[name_col]).strip()
            if not name or name == "nan":
                continue
        else:
            continue

        try:
            start_date = pd.to_datetime(row[start_col]).date()
        except Exception:
            continue

        # Parse end date — blank/missing means indefinite (None).
        end_date = None
        if end_col:
            try:
                raw_end = row[end_col]
                if pd.notna(raw_end) and str(raw_end).strip() not in ("", "nan"):
                    end_date = pd.to_datetime(raw_end).date()
            except Exception:
                pass   # treat unparseable end date as indefinite

        if end_date is not None and end_date < start_date:
            continue   # skip invalid rows where end is before start

        results.append({
            "student":    name,
            "start_date": start_date,
            "end_date":   end_date,   # None = indefinite
        })
    return results


def load_new_students(filepath: str, sheet_name=0) -> dict:
    """
    Load new students with their start date from Excel.
    Required columns:
      - Name: "First Name" + "Last Name"  OR  "Full Name" / "Name"
      - "Start Date" (any date-parseable format)
    Returns: {student_name: start_date}
    Students don't owe makeup hours for sessions before their start date.
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]

    first_col = find_col(df.columns, "first name", "first")
    last_col  = find_col(df.columns, "last name",  "last")
    name_col  = find_col(df.columns, "full name",  "name")
    date_col  = find_col(df.columns, "start date", "date")

    if not date_col:
        raise ValueError("New Students sheet must have a 'Start Date' column.")

    results = {}
    for _, row in df.iterrows():
        if first_col and last_col:
            f, l = str(row[first_col]).strip(), str(row[last_col]).strip()
            if f in ("", "nan") or l in ("", "nan"):
                continue
            name = f"{f} {l}"
        elif name_col:
            name = str(row[name_col]).strip()
            if not name or name == "nan":
                continue
        else:
            continue

        try:
            start_date = pd.to_datetime(row[date_col]).date()
        except Exception:
            continue

        results[name] = start_date
    return results


def hold_active_for_month(student: str, yr: int, mo: int, hold_periods: list):
    """Return (is_on_hold, start_date, end_date) if any hold overlaps month.
    end_date of None means the hold is indefinite."""
    if not hold_periods:
        return False, None, None

    month_start = date(yr, mo, 1)
    month_end   = last_day_of(yr, mo)
    overlaps = [
        h for h in hold_periods
        if h["student"] == student
        and h["start_date"] <= month_end
        and (h["end_date"] is None or h["end_date"] > month_start)
    ]
    if not overlaps:
        return False, None, None

    start = min(h["start_date"] for h in overlaps)
    # If any overlapping hold has no end date, the combined hold is indefinite.
    ends = [h["end_date"] for h in overlaps]
    end  = None if any(e is None for e in ends) else max(ends)
    return True, start, end

def compute_prorated_requirement(student: str, yr: int, mo: int,
                                  base_schedule: list, changes: list,
                                  hrs_per_session: float,
                                  hold_periods: list) -> float:
    """
    Return the prorated required hours for (yr, mo), counting only scheduled
    sessions that fall outside any active hold periods.

    A hold spans [start_date, end_date) — the student is on hold from
    start_date through the day BEFORE end_date, and back on end_date.
    """
    month_start = date(yr, mo, 1)
    month_end   = last_day_of(yr, mo)

    all_sessions = scheduled_sessions_in_month(yr, mo, student, base_schedule, changes)

    count = 0
    for d in all_sessions:
        on_hold_on_this_day = False
        for h in hold_periods:
            if h["student"] != student:
                continue
            if h["start_date"] <= d and (h["end_date"] is None or d < h["end_date"]):
                on_hold_on_this_day = True
                break
        if not on_hold_on_this_day:
            count += 1

    return count * hrs_per_session


# ---------------------------------------------------------------------------
# Schedule description helper
# ---------------------------------------------------------------------------
def _schedule_desc_for_month(student, yr, mo, base_sched, changes):
    first_d, last_d = date(yr, mo, 1), last_day_of(yr, mo)
    segments, cur, seg_start = [], effective_schedule(student, first_d, base_sched, changes), first_d
    d = first_d + timedelta(days=1)
    while d <= last_d:
        s = effective_schedule(student, d, base_sched, changes)
        if s != cur:
            segments.append((seg_start, d - timedelta(days=1), cur))
            cur, seg_start = s, d
        d += timedelta(days=1)
    segments.append((seg_start, last_d, cur))

    if len(segments) == 1:
        return " & ".join(DAY_FULL[w] for w in segments[0][2])

    parts = []
    for start, end, sched in segments:
        ds = " & ".join(DAY_FULL[w] for w in sched)
        parts.append(f"{ds} (until {end.strftime('%b %d')})"
                     if end != last_d else f"{ds} (from {start.strftime('%b %d')})")
    return " → ".join(parts)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------
def analyze(df, hours_col: str, schedules: dict,
            schedule_changes: list = None,
            hold_periods: list = None,
            new_students: dict = None,
            reference_date: date = None):
    """
    schedules        : { student: {"schedule": [int,...], "hrs_per_session": float} }
    schedule_changes : [ {"student": str, "effective_date": date, "schedule": [int,...]} ]
    hold_periods     : [ {"student": str, "start_date": date, "end_date": date}, ... ]
    new_students     : { student_name: start_date } — months before start_date are skipped
    Returns (results, skipped) where:
      results : list of result dicts
      skipped : { student_name: reason_string } for students in the attendance
                sheet who produced no results (so the UI can warn about them)
    """
    if reference_date is None:
        reference_date = date.today()
    if schedule_changes is None:
        schedule_changes = []
    if hold_periods is None:
        hold_periods = []
    if new_students is None:
        new_students = {}

    win_start, window_end = grace_window(reference_date)
    cur_y, cur_m = reference_date.year, reference_date.month

    months_in_scope = [
        (y, m) for y, m in [
            month_offset(cur_y, cur_m, -2),
            month_offset(cur_y, cur_m, -1),
            (cur_y, cur_m),
        ]
        if last_day_of(y, m) >= win_start
    ]

    all_results = []
    skipped     = {}   # { student: reason } for students producing no results

    for student in sorted(df["_student"].unique()):
        s_info      = schedules.get(student, {})
        base_sched  = s_info.get("schedule", [])
        hrs_per_ses = s_info.get("hrs_per_session", 1.0)
        if not base_sched:
            skipped[student] = (
                "Schedule could not be determined. "
                "The dialog may have been closed without confirming, "
                "or no attendance history was found."
            )
            continue

        sdf             = df[df["_student"] == student].copy()
        student_changes = [c for c in schedule_changes if c["student"] == student]
        raw_shortfalls  = []
        reg_extra_by_month    = defaultdict(list)
        reg_extra_dates_month = defaultdict(list)

        new_student_deduction = 0.0

        for (yr, mo) in months_in_scope:
            is_current   = (yr == cur_y and mo == cur_m)
            all_sched    = scheduled_sessions_in_month(yr, mo, student, base_sched, schedule_changes)
            # past_sched  : sessions strictly before today — used only to
            #               determine which sessions were missed (today is not
            #               yet missed since attendance is end-of-day).
            # future_sched : sessions today and later — used for both shortage
            #               projection and at-risk.  Including today means the
            #               hours-needed number never jumps on a scheduled day
            #               just because attendance hasn't been recorded yet.
            past_sched   = [d for d in all_sched if d <  reference_date]
            future_sched = [d for d in all_sched if d >= reference_date]

            # New students: skip months entirely before their start date.
            if student in new_students:
                start_d = new_students[student]
                if last_day_of(yr, mo) < start_d:
                    continue
                # In the month containing the start date, only count
                # sessions from the start date onward as scheduled.
                # Deduct the hours they could not have attended.
                if date(yr, mo, 1) <= start_d <= last_day_of(yr, mo):
                    sessions_before       = len([d for d in all_sched if d < start_d])
                    new_student_deduction = sessions_before * hrs_per_ses
                    all_sched             = [d for d in all_sched      if d >= start_d]
                    past_sched            = [d for d in past_sched     if d >= start_d]
                    future_sched          = [d for d in future_sched   if d >= start_d]

            month_rows = sdf[(sdf["_year"] == yr) & (sdf["_month"] == mo)]

            # Regular sessions: fast path when no changes, slow path otherwise
            if not student_changes:
                reg_mask = month_rows["_wday"].isin(base_sched)
            else:
                reg_mask = pd.Series(
                    [not is_makeup_session(student, row["_date"], base_sched, schedule_changes)
                     for _, row in month_rows.iterrows()],
                    index=month_rows.index, dtype=bool,
                )

            # Only count sessions that have actually occurred (strictly before
            # reference_date).  Sessions on or after reference_date belong to
            # future_sched and are already projected forward.  Counting them in
            # reg_hrs too would inflate projected by one session and cause the
            # at-risk check to silently fail for students who attended today.
            past_mask          = month_rows["_date"].apply(lambda d: d < reference_date)
            reg_rows           = month_rows[reg_mask & past_mask]

            # Count regular-session hours toward projected attendance,
            # but only up to the student's normal hrs_per_session.
            # Any excess hours beyond the regular session length are treated
            # as same-month makeup credit.
            reg_session_hours = reg_rows[hours_col]

            # Regular attendance contribution
            reg_hrs = float(
                reg_session_hours.clip(upper=hrs_per_ses).sum()
            )

            # Extra hours from oversized regular sessions become same-month makeup credit.
            extra_makeup_hrs = float(
                (reg_session_hours - hrs_per_ses).clip(lower=0).sum()
            )
            extra_makeup_dates = reg_rows.loc[
                reg_rows[hours_col] > hrs_per_ses, "_date"
            ].tolist()
            if extra_makeup_hrs > 0:
                reg_extra_by_month[(yr, mo)].append(extra_makeup_hrs)
                reg_extra_dates_month[(yr, mo)].extend(extra_makeup_dates)

            reg_attended_dates = set(reg_rows["_date"].tolist())
            missed             = [d for d in past_sched if d not in reg_attended_dates]

            on_hold, hold_start, hold_end = hold_active_for_month(
                student, yr, mo, hold_periods
            )

            if on_hold:
                req = compute_prorated_requirement(
                    student, yr, mo, base_sched, schedule_changes,
                    hrs_per_ses, hold_periods
                )
                # No scheduled sessions outside the hold — nothing required.
                if req <= 0:
                    continue
            else:
                req = required_hrs(student)

            # New student in their start month: deduct sessions before start date.
            if new_student_deduction > 0:
                req = max(0.0, req - new_student_deduction)
                new_student_deduction = 0.0
                if req <= 0:
                    continue

            if is_current:
                # future_sched includes today, so projected never drops on a
                # day the student is scheduled — hours needed stays stable.
                projected    = reg_hrs + len(future_sched) * hrs_per_ses
                shortage     = max(0.0, req - projected)
                display_proj = projected
            else:
                total_possible = len(all_sched) * hrs_per_ses
                if total_possible < req:
                    continue
                display_proj = total_possible
                shortage     = max(0.0, req - reg_hrs)
                if past_sched and add_months(max(past_sched), 2) < reference_date:
                    continue

            if shortage <= 0 and not on_hold and not is_current:
                continue

            raw_shortfalls.append({
                "yr": yr, "mo": mo, "is_current": is_current,
                "display_proj": round(display_proj, 2),
                "shortage":     round(shortage, 2),
                "at_risk":      False,
                "on_hold":      on_hold,
                "hold_start":   hold_start,
                "hold_end":     hold_end,
                "missed":       missed,
                "sched_desc":   _schedule_desc_for_month(
                    student, yr, mo, base_sched, schedule_changes),
            })

        if not raw_shortfalls:
            continue

        # Off-schedule (makeup) sessions, same month only, up to window_end
        off_by_month    = defaultdict(list)
        off_dates_month = defaultdict(list)
        for _, row in sdf.iterrows():
            d = row["_date"]
            if d > window_end:
                continue
            is_off = (is_makeup_session(student, d, base_sched, schedule_changes)
                      if student_changes else d.weekday() not in base_sched)
            if is_off:
                key = (d.year, d.month)
                off_by_month[key].append(float(row[hours_col]))
                off_dates_month[key].append(d)

        for sf in raw_shortfalls:
            key = (sf["yr"], sf["mo"])

            makeup_credit = sum(off_by_month.get(key, [])) + sum(reg_extra_by_month.get(key, []))
            applied = min(makeup_credit, sf["shortage"])

            sf["applied_hrs"] = round(applied, 2)
            sf["applied_dates"] = sorted(set(
                off_dates_month.get(key, []) + reg_extra_dates_month.get(key, [])
            ))

            remaining_after_makeups = max(0.0, sf["shortage"] - applied)
            sf["remaining"] = math.floor(remaining_after_makeups)

            # Recalculate at-risk after makeup credit has been applied.
            # A student can still be at risk even if they are fully made up
            # today, because one missed future session would drop them below
            # the required total.
            if sf["is_current"]:
                projected_after_makeups = sf["display_proj"] + applied
                sf["at_risk"] = (
                    len(future_sched) > 0
                    and (projected_after_makeups - hrs_per_ses) < req
                )
            else:
                sf["at_risk"] = False

        # If student is on hold in the CURRENT month, that overrides
        # the status of any past-month shortfalls — they still owe hours
        # but cannot act on them until the hold is lifted.
        currently_on_hold, cur_hold_start, cur_hold_end = hold_active_for_month(
            student, cur_y, cur_m, hold_periods
        )

        for sf in raw_shortfalls:
            if sf["missed"]:
                deadline = add_months(max(sf["missed"]), 2)
            else:
                deadline = add_months(reference_date, 2)

            # Determine effective on-hold status for this row.
            # A past-month shortfall for a student currently on hold
            # gets the hold override even if the hold did not exist
            # during that specific month.
            effective_on_hold = sf["on_hold"] or (currently_on_hold and not sf["is_current"])

            if not effective_on_hold and not sf["at_risk"] and sf["remaining"] <= 0:
                continue

            if effective_on_hold:
                status = "On Hold"
            elif sf["remaining"] > 0:
                # Outstanding hours > at-risk warning.
                status = f"{sf['remaining']} hr(s) still needed"
            elif sf["at_risk"]:
                status = "At risk — 1 missed session away from needing makeup"
            else:
                status = "Fully made up"

            # Use the actual hold dates for the current hold when
            # overriding a past-month row.
            display_on_hold = effective_on_hold
            display_hold_start = (str(cur_hold_start.strftime("%m/%d")) if effective_on_hold and not sf["on_hold"]
                                    else str(sf["hold_start"]) if sf["hold_start"] else "")
            display_hold_end   = (str(cur_hold_end.strftime("%m/%d")) if effective_on_hold and not sf["on_hold"] and cur_hold_end
                                    else (str(sf["hold_end"]) if sf["hold_end"] else
                                          ("Indefinite" if effective_on_hold and not cur_hold_end else "")))

            all_results.append({
                "Student":                   student,
                "Schedule":                  sf["sched_desc"],
                "Month":                     month_label(sf["yr"], sf["mo"]),
                "Status":                    status,
                "On Hold":                   display_on_hold,
                "Hold Start":                display_hold_start,
                "Hold End":                  display_hold_end,
                "Makeups completed (hrs)":   sf["applied_hrs"],
                "Makeups completed (dates)":
                    ", ".join(d.strftime("%m/%d") for d in sf["applied_dates"]) or "none",
                "Still needed (hrs)":        sf["remaining"],
                "_at_risk":                  sf["at_risk"],
                "Missed regular sessions":
                    ", ".join(d.strftime("%m/%d") for d in sf["missed"]) or "none yet",
            })

    return all_results, skipped
# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_excel(results: list, out_path: str) -> int:
    needs = [
        r for r in results
        if r["Still needed (hrs)"] > 0 or r["_at_risk"] or r.get("On Hold")
    ]
    if not needs:
        return 0
    export_df = pd.DataFrame(needs)
    cols = [c for c in export_df.columns if c not in ("_at_risk", "On Hold")]
    export_df[cols].to_excel(out_path, index=False)
    return len(needs)
