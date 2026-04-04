# Plan: Extended Interview Slots

## Requirements

1. **Separate interview timeframes per day** — Interviews can optionally have a different time window than runs for each day (e.g., runs 09:00–17:00 but interviews only 13:00–17:00).
2. **Configurable parallel interview rooms** — Allow specifying the number of concurrent interview resources (e.g., `--interview-rooms 2` creates "Interview 1" and "Interview 2").
3. **Schedule viewer: inline interviews in By Day view** — In the By Day view, show interviews not as a standalone division group but inline alongside the arenas of whichever division(s) are currently visible.

---

## Task 1: Add `--interview-day` CLI option for per-day interview timeframes

Currently, interview slots are generated from the same `day_specs` as run slots (`generate_slots(day_specs, interview_time)`). This task adds an optional `--interview-day` parameter that overrides the time window used for interview slot generation on specific days.

**UX**: Follows the same `Label:HH:MM-HH:MM` format as `--day`. The label must reference an existing `--day` label. Days without an `--interview-day` override fall back to their `--day` window. Example:

```bash
rcj-planner generate \
  --day "Day1:09:00-17:00" \
  --day "Day2:09:00-13:00" \
  --interview-day "Day1:13:00-17:00" \
  ...
```

Here Day1 interviews are restricted to 13:00–17:00, while Day2 interviews use the full 09:00–13:00 window.

- [x] **1.1** In `cli.py`, add a new `--interview-day` option (multiple, optional):
  - Format: `Label:HH:MM-HH:MM` (same as `--day`).
  - Validate that each label matches an existing `--day` label; error if not.
  - Build resolved interview day specs: for each `--day`, use the matching `--interview-day` if provided, otherwise use the `--day` spec itself.
  - Pass the resolved list to `build_schedule()` as a new `interview_day_specs` parameter.

- [x] **1.2** In `scheduler.py` `build_schedule()`:
  - Add `interview_day_specs: list[str] | None = None` parameter.
  - If provided, use `generate_slots(interview_day_specs, interview_time)` for `all_interview_slots` instead of `generate_slots(day_specs, interview_time)`.
  - This also affects Phase 1 simplified-mode gap interviews: the gap interview slots must come from the interview-specific slot list.

- [x] **1.3** Store `interview_days` in `schedule.meta` (alongside existing `days`) so the viewer and persistence layer have the information.

- [x] **1.4** Add tests in `tests/test_scheduler.py`:
  - Test that when `interview_day_specs` restricts the timeframe, no interviews are scheduled outside that window.
  - Test that omitting `interview_day_specs` preserves current behavior (interviews use run day specs).

- [x] **1.5** Run `python -m pytest tests/` and fix any failures. Commit.

---

## Task 2: Add `--interview-rooms` CLI option for parallel interview resources

Currently there is a single `Resource("interview", "Interview")`. This task allows multiple parallel interview resources. The flag is named `--interview-rooms` (not `--interview-slots`) to avoid ambiguity with time slots, and to mirror how `arenas=N` names the run venues.

- [x] **2.1** In `cli.py`, add `--interview-rooms` option (int, default 1):
  - Pass to `build_schedule()` as `num_interview_rooms`.

- [x] **2.2** In `scheduler.py` `build_schedule()`:
  - Add `num_interview_rooms: int = 1` parameter.
  - Create `num_interview_rooms` interview resources: when 1, use `Resource("interview", "Interview")` (backward-compatible); when >1, use `Resource("interview", "Interview 1")`, `Resource("interview", "Interview 2")`, etc.
  - In Phase 1 (simplified gap interviews) and Phase 2 (main interview scheduling), try each interview resource in order when looking for a free slot — assign each chunk to the first available interview resource with no conflict at that time.

- [x] **2.3** Store `interview_rooms` count in `schedule.meta`.

- [x] **2.4** Add tests in `tests/test_scheduler.py`:
  - Test that with `num_interview_rooms=2`, two interview groups can be scheduled at the same time on different resources.
  - Test that with `num_interview_rooms=1`, behavior is unchanged.

- [x] **2.5** Run `python -m pytest tests/` and fix any failures. Commit.

---

## Task 3: Update schedule viewer — show interviews inline in By Day view

Currently the By Day view groups "Interview" as its own division column at the end of the table. Instead, interview columns should appear alongside the arenas of the division whose teams are being interviewed, and should follow the division filter toggles.

- [x] **3.1** In `schedule_viewer.html` `renderDayView()`, change the resource grouping logic:
  - For each division group, after its arena columns, append the interview resource column(s) that have assignments containing teams from that division on the current day.
  - If an interview slot contains teams from multiple divisions (mixed group), show it in each relevant division group.
  - Remove "Interview" as a standalone division in the filter pills — interviews are now shown within their parent division.

- [x] **3.2** Update `divisionOf()` helper or add a separate mapping: build a lookup from interview resources to divisions based on team membership for the current day, so interview columns can be placed in the right division group.

- [x] **3.3** Handle multiple interview resources (`Interview 1`, `Interview 2`): `shortName()` should display them distinctly, and they should be grouped under the correct division.

- [x] **3.4** Update `resourcesForDay()` so interview resources are sorted after arenas within each division group, not pushed to the end.

- [x] **3.5** Ensure the division filter pills still work: toggling a division on/off should also show/hide its interview columns. The standalone "Interview" pill should no longer appear.

- [x] **3.6** Verify mobile card layout (`mobileCards` section) also shows interviews inline with their division rather than as a separate group.

- [x] **3.7** Manually test by loading `ui/schedule_viewer.html` with the sample schedule. Commit.

---

## Task 4: Update Interview view and wallboard for multi-room support

- [x] **4.1** In `renderInterviewView()`, update to handle multiple interview resources — show the resource name (e.g., "Interview 1") in the table when there is more than one interview resource.

- [x] **4.2** In `renderWallboardView()`, the interview section already filters by team membership so it should largely work, but verify that multiple interview resources are handled correctly (no duplicate rows, each resource's assignments shown).

- [x] **4.3** Manually test both views. Commit.

---

## Task 5: Update README, integration tests, and sample scripts

- [x] **5.1** Update `README.md`:
  - Add `--interview-day` and `--interview-rooms` to the flag table with descriptions and defaults.
  - Update the example `generate` command to show `--interview-day` usage.
  - Update scheduling rules section: adjust "All divisions share a single interview schedule" to account for multiple rooms.
  - Update the output format section if interview resource naming changes (e.g., "Interview 1").

- [x] **5.2** Update `tests/integration/test_should_work.sh` if the generated output format changes (e.g., interview resource naming).

- [x] **5.3** Update `sample/generate_ao2026.sh` to demonstrate the new options if appropriate.

- [x] **5.4** Run `bash tests/integration/test_should_work.sh` and fix any failures. Commit.
