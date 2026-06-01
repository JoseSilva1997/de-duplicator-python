# Guest List Cleaner

Removes people from a guests list if they are already on your confirmed attendees list, even when their email or company has changed.

## What it does

You give it two files:

- **Guest list** — your full list of candidates.
- **Attendee list** — the people already confirmed.

It compares them and writes out a cleaned guest list with the duplicates removed.

## Running it

If you have the packaged app, just open it. Otherwise, from the project folder:

```
pip install -e .
guest-list-dedup
```

Then:

1. Upload your **guest list** and your **attendee list** (`.xlsx`, `.xls`, or `.csv`).
2. If a file has more than one sheet, pick which sheets to use.
3. Click **Remove duplicates**.

Each guest sheet is checked against all the attendee sheets combined.

## Input files

Column headers are matched automatically. Common variations are recognised (for example `First Name`, `firstname`, and `first_name` are all understood). The fields it looks for:

- First name / Last name (or a single Full name column)
- Email
- Company / Organisation
- Job title
- Country

## How matching works

Each guest is checked against the attendees using five rules, in order. A guest is removed as soon as one rule finds a match:

1. **Exact email** — same email address.
2. **Email username** — the part before the `@` matches (handles a changed company domain).
3. **Name and company** — first name, last name, and company all match exactly.
4. **Fuzzy key** — name and company match approximately (handles small spelling differences).
5. **Fuzzy name** — names are similar enough to match on their own, even without a company.

A second pass then re-checks remaining guests against everyone removed by the high-confidence rules, catching chains of duplicates.

## Output

Two Excel files are saved to your **Desktop**:

- **Updated guests list from `<file>`** — the cleaned guest list.
- **People removed from `<file>`** — every removed guest, with the reason, a confidence score, and the attendee they matched. Not written if no one was removed.

If you selected multiple sheets, the output keeps the same one-sheet-per-sheet structure. Sheets with no removals are left out of the "People removed" file.

## Settings

Open the gear icon (top right):

- **Remove guests with no email address** — on by default. Drops guest rows that have no email before matching.
