MAKEUP SESSION ANALYZER
========================

WHAT'S IN THIS FOLDER
----------------------
  analyzer_core.py            — shared logic (required for build)
  makeup_analyzer_app.py      — the program (source code, required for build)
  build_windows.bat           — builds MakeupAnalyzer.exe  (run this on Windows)
  build_mac.sh                — builds MakeupAnalyzer app  (run this on Mac)
  README.txt                  — this file


FOR THE PERSON SETTING THIS UP (one-time only)
-----------------------------------------------
You only need to do this ONCE on any computer that will build the .exe.
After that, the .exe can be copied to any Windows computer and just works —
no Python, no setup, nothing needed on the target computer.

Step 1 — Install Python (if not already installed)
  • Go to https://www.python.org/downloads/
  • Download the latest Python 3 installer
  • During installation, CHECK THE BOX that says "Add Python to PATH"

Step 2 — Build the executable
  Windows:  Double-click  build_windows.bat  and follow the prompts.
  Mac:      Open Terminal, drag build_mac.sh into it, press Enter.

Step 3 — Find your executable
  Windows:  Look in the  dist\  folder → MakeupAnalyzer.exe
  Mac:      Look in the  dist/  folder → MakeupAnalyzer

Step 4 — Distribute
  Copy MakeupAnalyzer.exe (or MakeupAnalyzer on Mac) to any shared drive
  or desktop. That single file is all your coworkers need.

  NOTE: If you ever rebuild after changes, delete the old  dist\  and
  build\  folders first before running the build script again.


FOR COWORKERS USING THE PROGRAM
---------------------------------
Just double-click MakeupAnalyzer.exe (Windows) or MakeupAnalyzer (Mac).

The window has three file pickers:

  1. Attendance sheet (.xlsx)
     Your normal monthly attendance export. Required.

  2. Configuration workbook (.xlsx)   <- OPTIONAL
     A single workbook that can contain any of these tabs (tab names are
     detected automatically — exact name does not matter):

     a) Reduced-Hour Students tab
        Lists students who only need 4 hours/month instead of the
        standard 8. Two formats are accepted:

          Format A (two columns):        Format B (one column):
          +------------+-----------+     +------------------+
          | First Name | Last Name |     | Full Name        |
          +------------+-----------+     +------------------+
          | Jane       | Doe       |     | Jane Doe         |
          | John       | Smith     |     | John Smith       |
          +------------+-----------+     +------------------+

        Leave this out if all students use the standard 8-hour requirement.
        
              b) Extra-Hours Students tab   <- OPTIONAL
                 Lists students who need 12 hours/month instead of the standard 8.
                 Same formats as the Reduced-Hour Students tab.
        
                   Format A (two columns):        Format B (one column):
                   +------------+-----------+     +------------------+
                   | First Name | Last Name |     | Full Name        |
                   +------------+-----------+     +------------------+
                   | Jane       | Doe       |     | Jane Doe         |
                   +------------+-----------+     +------------------+
        
                 Leave this out if all students use the standard 8-hour requirement.
        
              c) Schedule Changes tab   <- OPTIONAL
        Records students who permanently switched session days partway
        through a month. The tool uses the old schedule before the
        effective date and the new schedule on and after it.

        Required columns (names must match exactly, spelling and spacing):

          +------------+-----------+----------------+------------------+
          | First Name | Last Name | Effective Date | New Session Days |
          +------------+-----------+----------------+------------------+
          | Jane       | Doe       | 04/15/2026     | Mon, Wed         |
          | John       | Smith     | 03/10/2026     | Tue, Thu         |
          +------------+-----------+----------------+------------------+

          OR if you prefer a single name column:

          +------------+----------------+------------------+
          | Full Name  | Effective Date | New Session Days |
          +------------+----------------+------------------+
          | Jane Doe   | 04/15/2026     | Mon, Wed         |
          | John Smith | 03/10/2026     | Tue, Thu         |
          +------------+----------------+------------------+

        EFFECTIVE DATE — the first day the new schedule applies.
          Any date format Excel recognises works (04/15/2026, 4/15/2026, etc.)

        NEW SESSION DAYS — the days of the week after the change.
          Separate multiple days with a comma. Accepted abbreviations:

            Mon  Tue  Wed  Thu  Fri  Sat
            Mo   Tu   We   Th   Fr
            Monday  Tuesday  Wednesday  Thursday  Friday  Saturday

          NOTE: Sunday is NOT accepted. Session days run Mon–Sat only.

          Examples:  "Mon, Wed"   "Tue, Thu"   "Friday"

        Leave this out if no students changed their schedule this month.

     c) On-Hold Students tab   <- OPTIONAL
        Records students who are temporarily on hold (e.g. sick leave,
        vacation, suspension). During a hold, the student's required
        hours are prorated — only scheduled sessions outside the hold
        period count toward the monthly minimum.

        The hold automatically ends on the first attendance date on or
        after the hold start date — no end date column is needed.
        Example: hold starts April 15, student attends April 22 →
        hold spans April 15 through April 21.

        If no attendance is recorded after the hold start, the hold is
        indefinite (still on hold).

        If a student is currently on hold (hold overlaps the current
        month), any past-month shortfalls are shown with status "On Hold"
        — they still owe the hours but cannot act on them until the hold
        is lifted.

        Columns:

          +------------+-----------+------------+
          | First Name | Last Name | Hold Start |
          +------------+-----------+------------+
          | Jane       | Doe       | 04/15/2026 |
          +------------+-----------+------------+

          OR single name column:

          +------------+------------+
          | Full Name  | Hold Start |
          +------------+------------+
          | Jane Doe   | 04/15/2026 |
          +------------+------------+

        HOLD START — the first day the hold begins (inclusive).

     d) Dropped Students tab   <- OPTIONAL
        Records students who have stopped attending. They are completely
        excluded from the make-up report and schedule-conflict popups once
        their Last Attendance Date has passed.

        If a student is on BOTH the Dropped and On-Hold lists, on-hold wins
        and the student is treated as on-hold, not dropped.

        Columns:

          +------------+-----------+----------------------+
          | First Name | Last Name | Last Attendance Date |
          +------------+-----------+----------------------+
          | Jane       | Doe       | 04/15/2026           |
          +------------+-----------+----------------------+

          OR single name column:

          +------------+----------------------+
          | Full Name  | Last Attendance Date |
          +------------+----------------------+
          | Jane Doe   | 04/15/2026           |
          +------------+----------------------+

        LAST ATTENDANCE DATE — the last date the student attended.
          Once this date is in the past, the student is excluded entirely.

     e) New Students tab   <- OPTIONAL
        Records students who recently started and have a start date.
        They do not owe makeup hours for sessions that occurred before
        their start date. Months entirely before the start date are
        skipped; in the month containing the start date, only sessions
        from the start date onward are counted.

        Columns:

          +------------+-----------+----------------+
          | First Name | Last Name | Start Date     |
          +------------+-----------+----------------+
          | Jane       | Doe       | 05/15/2026     |
          +------------+-----------+----------------+

          OR single name column:

          +------------+----------------+
          | Full Name  | Start Date     |
          +------------+----------------+
          | Jane Doe   | 05/15/2026     |
          +------------+----------------+

Then click Run Analysis.

Results appear in the table:
  • Red rows    = student still needs a makeup session
  • Yellow rows = student is one missed session away from needing a makeup
  • Blue rows   = student is on hold
  • Green rows  = shortfall has been fully made up
  • Click any row to see full details at the bottom of the window

Click Export to Excel to save a report containing only rows where students
need action or are on hold. The exported Excel includes these columns:
  Student, Schedule, Month, Status, On Hold, Hold Start, Hold End,
  Makeups completed (hrs), Makeups completed (dates), Still needed (hrs),
  Missed regular sessions


HOURS RULES (for reference)
-----------------------------
  • Students need 8 hours/month minimum (or 4 hrs for reduced-hours students,
    or 12 hrs for extra-hours students)
  • Only sessions on their regular scheduled days count toward the monthly total
  • Attendance on a non-scheduled day = a makeup session for that month
  • A makeup session only counts toward the month it was attended, not a
    different month's shortfall
  • Grace period: exactly 2 calendar months from the missed session date.
    Example: missed March 12 → deadline is May 12.
  • Today's session is never counted as missed (attendance is taken
    end-of-day, so it has not happened yet when the tool is run)
  • If a student's projected hours for the rest of the month still can't
    reach the minimum even with perfect attendance, they are flagged
    as at risk
  • Students on hold have their required hours prorated — only scheduled
    sessions outside the hold period count toward the minimum
  • New students do not owe makeup hours for sessions before their start
    date. In their start month, sessions before the start date are
    deducted from their total required hours for that month
