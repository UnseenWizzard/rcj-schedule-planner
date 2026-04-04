# Plan: Load schedule.json in the Schedule Viewer

## Context

`schedule_viewer.html` currently only accepts CSV files (one per day, rows with
`time_slot`, `resource`, `teams`).  The planner now outputs `schedule.json`
whose relevant part is an `assignments` array.  Each assignment looks like:

```json
{
  "day": "Day1",
  "start": "11:00",
  "end": "11:10",
  "resource_kind": "arena",
  "resource_name": "Line \u2013 Arena 1",
  "teams": ["Team A"]
}
```

The viewer's internal `state.days` shape is:
```js
{ "Day1": [ { time_slot, resource, teams }, … ] }
```

Mapping:
- `time_slot` → `assignment.start + "\u2013" + assignment.end`  (en-dash)
- `resource`  → `assignment.resource_name`
- `teams`     → `assignment.teams.join(", ")`

---

## Step 1 – Add JSON file parsing and file-upload support

**File:** `schedule_viewer.html`

### What to do

1. Add a `parseScheduleJSON(text)` function in the `<script>` block (near the
   existing `parseCSV` function) that:
   - `JSON.parse(text)`, reads `.assignments`
   - Groups by `day`
   - Maps each entry to `{ time_slot, resource, teams }` using the mapping above
   - Returns a `state.days`-compatible object: `{ Day1: [...], Day2: [...] }`

2. Update `loadFiles(files)` so that when a file ends in `.json` it calls
   `parseScheduleJSON` on the text content and merges the returned days into
   `state.days`.  CSV files continue to use `parseCSV` as before.
   A single JSON file replaces/merges all days at once.

3. Update both `<input type="file">` elements:
   - Change `accept=".csv"` → `accept=".csv,.json"`

4. Update the dropzone body text to mention JSON alongside CSV:
   - e.g. "Drag & drop **schedule.json** or **Day1.csv**, **Day2.csv**, … here"

### Acceptance criteria
- Dropping `schedule.json` on the dropzone loads all days and all four views
  render correctly (day, division, interview, team).
- Dropping CSV files still works unchanged.
- No regressions in existing behaviour.

---

## Step 2 – Load schedule JSON from a URL

**File:** `schedule_viewer.html`

**Depends on:** Step 1 (`parseScheduleJSON` must exist and work)

### What to do

1. Add a second load option beneath the dropzone in `#loader-screen` — a card
   with:
   - A label: "Or load from URL"
   - A `<input type="url" id="url-input">` with placeholder
     `https://example.com/schedule.json`
   - A `<button id="url-load-btn">Load</button>`
   - An empty `<p id="url-error">` for inline error messages (hidden by default)

2. Wire up the button (and Enter keypress on the input):
   - Show a loading state on the button ("Loading…", disabled) while fetching
   - `fetch(url)` → `.text()` → `parseScheduleJSON(text)`
   - On success: merge days into `state.days`, hide loader, show app, call `render()`
   - On any error (network, non-ok status, JSON parse): display a human-readable
     message in `#url-error`; re-enable the button

3. Style the URL panel to fit the existing design language:
   - Same CSS variables (`--primary`, `--border`, `--radius`, `--muted`, etc.)
   - Visually separated from the dropzone (e.g. a small card or a simple
     "— or —" divider + compact form below)
   - Error text in a red/warning colour; keep it subtle

### Acceptance criteria
- Entering a valid URL pointing to a `schedule.json` and clicking Load renders
  the schedule correctly.
- A bad URL or non-JSON response shows an inline error message without crashing.
- File upload (CSV and JSON) still works unchanged.
- CORS errors produce a readable message ("Could not fetch – check CORS headers
  or try downloading the file directly").
