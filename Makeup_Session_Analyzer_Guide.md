# Makeup Session Analyzer — User Guide

> *A tool for tracking student attendance, calculating makeup hours, and identifying students who need extra sessions.*

---

## Quick Start

**Double-click** `MakeupAnalyzer.exe` (Windows).

The window has **two file pickers**:

---

### 1. Attendance sheet (`.xlsx`) — *Required*

Your normal monthly attendance export from Radius.
**Make sure to set the start date to the first day of the month that is 2 months prior to the current month.**

**Example:**

- The current date is June 11
- Select the date range of the attendance sheet to be from **4/1** to **6/11**
- Click "Export to Excel"

---

### 2. Configuration workbook (`.xlsx`) — *Optional*

A single workbook that can contain **any combination** of the tabs below. The tool finds them automatically by name — no need to name them exactly.

#### Tab: Reduced-Hour Students

Students who only need **4 hours/month** instead of the standard 8.

| First Name | Last Name |
|------------|-----------|
| Jane       | Doe       |
| John       | Smith     |

*Or a single column:*

| Full Name   |
|-------------|
| Jane Doe    |
| John Smith  |

Leave this tab out if all students use the 8-hour standard.

---

#### Tab: Extra-Hours Students

Students who require **12 hours/month** instead of the standard 8.

| First Name | Last Name |
|------------|-----------|
| Jane       | Doe       |
| John       | Smith     |

*Or a single column:*

| Full Name   |
|-------------|
| Jane Doe    |
| John Smith  |

Leave this tab out if all students use the 8-hour standard.

---

#### Tab: Schedule Changes

Records students who **permanently switched** their session days partway through a month.

| First Name | Last Name | Effective Date | New Session Days |
|------------|-----------|----------------|------------------|
| Jane       | Doe       | 04/15/2026     | Mon, Wed         |
| John       | Smith     | 03/10/2026     | Tue, Thu         |

*Or with a single name column:*

| Full Name   | Effective Date | New Session Days |
|-------------|----------------|------------------|
| Jane Doe    | 04/15/2026     | Mon, Wed         |

**Effective Date** — The first day the new schedule applies.  
Any date format works: `04/15/2026`, `4/15/2026`, `April 15, 2026`.

**New Session Days** — Separate multiple days with a comma.  

Accepted days: `Mon` `Tue` `Wed` `Thu` `Fri` `Sat`

Leave this tab out if no students changed their schedule.

---

#### Tab: On-Hold Students

Records students who are temporarily on hold (sick leave, vacation, suspension, etc.).

| First Name | Last Name | Hold Start |
|------------|-----------|------------|
| Jane       | Doe       | 04/15/2026 |

*Or with a single name column:*

| Full Name   | Hold Start |
|-------------|------------|
| Jane Doe    | 04/15/2026 |

**Hold Start** — The first day the hold begins (inclusive).

The hold **automatically ends** on the first attendance date on or after the
hold start date — no end date column is needed. If no attendance is recorded
after the start date, the hold remains indefinite (still on hold).

---

#### Tab: Dropped Students

Records students who have stopped attending. They are **completely excluded** from
the make-up report and schedule-conflict popups once their Last Attendance Date has passed.

| First Name | Last Name | Last Attendance Date |
|------------|-----------|----------------------|
| Jane       | Doe       | 04/15/2026           |

*Or with a single name column:*

| Full Name   | Last Attendance Date |
|-------------|----------------------|
| Jane Doe    | 04/15/2026           |

**Last Attendance Date** — The last date the student attended. Once this date is
in the past, the student is excluded from all results and popups.

If a student's Last Attendance Date is today or in the future, they will still
appear in results until that date passes.

> ⚠️ If a student is listed on **both** the Dropped Students tab and the On-Hold
> Students tab, the On-Hold status takes precedence — the student is treated as
> on-hold, not dropped.

---

#### Tab: New Students

Records students who recently started the program. They do **not** owe makeup hours for sessions before their start date.

| First Name | Last Name | Start Date  |
|------------|-----------|-------------|
| Jane       | Doe       | 05/15/2026  |

*Or with a single name column:*

| Full Name   | Start Date  |
|-------------|-------------|
| Jane Doe    | 05/15/2026  |

Months entirely before the start date are skipped. In the month containing the start date, only sessions from the start date onward are counted.

---

## Running the Analysis

Click **Run Analysis**.

> If a student's schedule can't be determined from their history, a pop-up will ask you to pick the correct day(s).

---

## Reading the Results

> Click any row to see full details at the bottom of the window.

### Status Flags

| Status                  | Meaning                                                              |
|-------------------------|----------------------------------------------------------------------|
| `_ hr(s) still needed`  | Total makeup hours the student still owes                            |
| `At risk`               | Currently on track, but missing one more session = makeup needed     |
| `On Hold`               | Student is on hold — hours are tracked but status overridden         |
| `Fully made up`         | All required hours met                                               |

---

## Exporting to Excel

Click **Export to Excel** to save a report.

The exported file includes only rows where students need action or are on hold.

Exported columns:

| Column                   | Description                             |
|--------------------------|-----------------------------------------|
| Student                  | Full name                               |
| Schedule                 | Their regular session day(s)            |
| Month                    | The month being analyzed                |
| Status                   | Current status (see table above)        |
| On Hold                  | Whether the row is affected by a hold   |
| Hold Start               | Start of hold period                    |
| Hold End                 | End of hold period                      |
| Makeups completed (hrs)  | Hours fulfilled by makeup sessions      |
| Makeups completed (dates)| Dates of makeup sessions                |
| Still needed (hrs)       | Hours still outstanding                 |
| Missed regular sessions  | Dates of missed regular sessions        |

---

## How the Analyzer Calculates Makeup Hours

### 1. Monthly Requirement

Most students need **8 hours per month**.

Students on the **Reduced-Hour Students** list need **4 hours per month**.

Students on the **Extra-Hours Students** list need **12 hours per month**.

### 2. Regular Hours

Each student has one or more **regularly scheduled session days** (e.g. Tuesday and Thursday).

Only attendance on those scheduled days counts toward the monthly total.

### 3. Bonus Sessions

If a month has **more scheduled sessions** than the minimum required to meet the goal, those extra sessions act as a buffer.

**Example:**

- Requirement: **8 hours**
- Available scheduled hours this month: **9 hours**
- Student attends **8 of those 9 hours**

**Result:** ✅ No makeup hours needed.

### 4. Makeup Hours

Any attendance on a **non-scheduled day** counts as a makeup session.

**Example:**

- Student's schedule: Tuesday and Thursday
- Student attends on **Wednesday**

The Wednesday attendance is counted as **makeup time** for that month.

> Makeup hours only apply to the **month they were attended**. They cannot be moved to a different month.

### 5. Extra Time During a Regular Session

If a student attends **longer than their normal session length**, the extra time is treated as makeup credit.

**Example:**

- Student normally attends **1-hour sessions**
- Student attends a regular Tuesday session for **2 hours**

The first **1 hour** counts as the regular session.  
The additional **1 hour** is automatically treated as makeup time.

### 6. Shortage Calculation

1. The analyzer counts **regular attendance hours** for the month.
2. It compares them to the student's **required monthly minimum**.
3. It **applies any makeup hours** completed in that same month.

**Example:**

| Step                     | Hours |
|--------------------------|-------|
| Required monthly minimum | 8     |
| Regular attendance       | 6     |
| Raw shortage             | 2     |
| Makeup hours completed   | −1    |
| **Still needed**         | **1** |

### 7. Schedule Changes and Rescheduling

When a student permanently changes their schedule mid-month, the analyzer uses the **old schedule** before the effective date and the **new schedule** on and after that date.

**Example:**

- Original schedule: Tuesday and Thursday
- New schedule effective **April 15**: Monday and Wednesday

April contains:

| Period               | Scheduled Days                    |
|----------------------|-----------------------------------|
| Apr 1 – Apr 14       | 2 Tuesdays + 2 Thursdays = 4     |
| Apr 15 – Apr 30      | 2 Mondays + 2 Wednesdays = 4     |
| **Total**            | **8 regular sessions**            |

The analyzer uses all 8 sessions when checking if the student had enough available hours.

### 8. Missed Sessions

A regular session is considered **missed** when:

1. The student was **scheduled** for that day, **and**
2. **No attendance** was recorded for that date.

> The current day is **never** counted as missed — attendance is entered end-of-day.

### 9. Current Month Projections

For the current month, the analyzer **assumes the student attends all remaining scheduled sessions**.

This allows the tool to estimate whether the student is on track.

Students who **cannot reach the required hours** even with perfect attendance are flagged.

### 10. At-Risk Students

A student may be marked **"At risk"** — meaning they are currently on track, but **missing one future scheduled session** would create a shortage.

Common examples:

- No remaining bonus sessions available
- Already used their bonus session for the month
- Projected attendance reaches the requirement **exactly**

> "At risk" does **not** mean the student currently owes makeup hours.

### 11. On-Hold Students

Students on hold have their **required hours prorated** — only scheduled sessions outside the hold period count toward the minimum.

**Example:**

- Student normally needs **8 hours/month**
- On hold **Apr 15 – May 9**
- In April, only sessions **before Apr 15** count toward the requirement
- If there are only 2 scheduled sessions before Apr 15 (2 hours each), their prorated requirement = **4 hours**

While a student is on hold:

| Scenario                                 | Behavior                                                      |
|------------------------------------------|---------------------------------------------------------------|
| Current month is within hold             | Status shows "On Hold" — shortage is tracked but overridden   |
| Past month owes hours, still on hold now | Status also shows "On Hold" — they still owe, can't act yet   |
| Hold ends, past month still owes         | Status reverts to "N hr(s) still needed"                      |

### 12. New Students

Students on the **New Students** tab don't owe makeup hours for sessions **before their start date**.

**Example:**

- Jane Doe's start date: **September 15**
- Needed: 8 hours/month, attends 1-hour sessions twice a week (Tue/Thu)
- The analyzer will **skip July and August entirely**
- In September, sessions **before September 15** are deducted from her requirement:
  - Scheduled sessions before Sep 15: 2 Tuesdays + 1 Thursday = **3 sessions**
  - Deduction: 3 sessions × 1 hour = **3 hours**
  - Prorated requirement for September: 8 − 3 = **5 hours**

### 13. Grace Period (Deadline)

Students have **two calendar months** from the missed session date to complete makeup hours.

| Missed Session | Deadline    |
|----------------|-------------|
| March 12       | May 12      |
| April 23       | June 23     |

After the grace period expires, the shortage is **no longer included** in the report.

---

## Summary: Step by Step

The analyzer follows this process for each student:

1. Determine the student's **regular schedule**
2. Calculate how many **scheduled hours** were available
3. Count **attendance on scheduled days** toward the monthly requirement
4. Count **attendance on non-scheduled days** as makeup hours
5. **Apply makeup hours** to shortages from the same month
6. Determine whether the student:
   - Still needs makeup hours
   - Is at risk of needing makeup hours
   - Has fully satisfied the requirement
   - Is currently on hold

---

## Taking Attendance for Makeups

When a student comes in for a makeup session, here's how to record it:

| Scenario                                                              | What to do                                                               |
|-----------------------------------------------------------------------|--------------------------------------------------------------------------|
| Student is **redeeming a makeup from a previous month**               | Add a **1-hour attendance entry** in the previous month's date. Do **not** log it on today's date. |
| Student is **redeeming a makeup from this month**                     | Mark attendance for the day like usual.                                  |
| Student came for a **2-hour session: 1 regular + 1 makeup from last month** | Mark **1 hour** in last month's date + **1 hour** on today's date like usual. |
| Student came for a **2-hour session: 2 makeups from last month**      | Mark a **2-hour attendance** in last month. Do **not** log today's date. |

---

## Known Limitations & Notes

| Issue | Details |
|-------|---------|
| **8-session limit** | Radius currently does not allow attendance logging for more than 8 sessions. |
| **Hours, not sessions** | Cannot track using number of sessions — must use total hours. |
| **Extra summer sessions** | Cannot track extra summer sessions through this tool. |
| **Accidental makeup sessions** | Cannot take attendance when extra makeup sessions were given by accident. |
| **Schedule inference** | A student's schedule is inferred from the 1–2 days they attended the most in the last 2 months. If a student is new or has been rescheduling frequently, the inference may be incorrect. Use the **New Students** tab to set a start date. |
| **Current day not included** | Attendance doesn't include the current day. If a student has a makeup scheduled today, the tool won't mark it complete until the next day. |
| **Sync / duplicate sessions** | If someone calls for a makeup and you didn't know the student already scheduled some or all of their makeups, you could accidentally give them extra sessions. To avoid duplicates, a centralized platform that tracks scheduled vs. completed makeup hours is recommended. |

---

