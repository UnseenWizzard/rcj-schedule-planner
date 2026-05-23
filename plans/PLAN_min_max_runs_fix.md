# Plan: Fix underfill / SchedulingError with `day_run_minimums`

## Problem summary

Commit `abea07d` ("Add possibility to define min/max runs per day")
introduced day-min/day-max balancing in the general scheduling path of
`build_schedule` ([rcj_planner/scheduler.py:233-246](rcj_planner/scheduler.py#L233-L246) and
the sort key at [rcj_planner/scheduler.py:255](rcj_planner/scheduler.py#L255)).
The logic is buggy and causes two symptoms when `day_run_minimums` is set:

1. **Schedules that should succeed fail** with `SchedulingError: Team 'TXX'
   was assigned 8 runs, expected 9`.
2. **Schedules that succeed pack into the morning of each day**, leaving the
   afternoon empty (e.g. both days end ~15:00 with run_time=12 / runs=2 /
   30 teams).

### Verified reproduction

30 teams, one division, 3 arenas, 2 days `09:00–18:00`, no interviews,
buffer=5min:

| Scenario                                                | Current code                | Expected           |
| ------------------------------------------------------- | --------------------------- | ------------------ |
| runs=2, min/max 3:3 each day, run_time=12               | OK; days end 15:00 (corr.) | Same (correct)     |
| runs=3, min/max 4:5 each day, run_time=12               | **`SchedulingError` "T24 assigned 8 runs, expected 9"** | OK, both days full |
| runs=3, min/max 3:6 each day, run_time=12               | **SchedulingError**         | OK                 |
| runs=3, min/max 4:6 Day1 + 3:5 Day2, run_time=12        | **SchedulingError**         | OK                 |
| runs=3, min=0/max=9 each day, run_time=12               | OK (min logic inert)        | OK                 |

The third row through fifth row are all genuinely **feasible** at run_time=12
(Day1 demand = 30×4.5 = 135 = capacity 45 slots × 3 arenas; the range allows
half the teams to do 5 and half to do 4) — the planner *should* produce a
schedule but raises `SchedulingError`.

### Root causes (in [rcj_planner/scheduler.py:233-238](rcj_planner/scheduler.py#L233-L238))

```python
day_min = div.day_run_minimums.get(slot.day,0)
days = div.day_specs if div.day_specs is not None else day_specs
runsNeededOnOtherDays = sum(d != slot.day and team_day_runs[team][d.split(":")[0]] < day_min for d in days)
runsNeededToday = div.day_run_minimums.get(slot.day, 0) - team_day_runs[team][slot.day]
if runsNeededToday < 0 and runsNeededOnOtherDays > 0:
    continue # deprioritize teams that have already met today's minimum if they still need runs on other days
```

- **Bug A** — `d` is a full day-spec string like `"Day1:09:00-18:00"`,
  but `slot.day` is just `"Day1"`. The comparison `d != slot.day` is
  therefore **always True**, so `runsNeededOnOtherDays` counts the current
  day as well as other days.
- **Bug B** — `day_min` is **today's** minimum, but it is compared against
  **other days'** run counts. The correct comparison uses each day's
  own minimum.
- **Bug C** — the `continue` is a **hard exclusion**, not a deprioritization
  (despite the comment). Combined with bugs A/B it removes teams that the
  greedy still needs in order to satisfy total-run requirements, producing
  `SchedulingError` even when the scenario is feasible.
- **Bug D** — `runsNeededOnOtherDays` is the **primary** key in the sort
  ([scheduler.py:255](rcj_planner/scheduler.py#L255)). Because of bugs A/B
  it is **lower** for teams that have already met today's minimum, so those
  teams are *preferred* for additional runs today — the opposite of the
  intent (which is to save remaining runs for under-min days).
- **Bug E (cleanup)** — leftover commented-out debug `print` blocks at
  [scheduler.py:260-264](rcj_planner/scheduler.py#L260-L264) and
  [scheduler.py:300-302](rcj_planner/scheduler.py#L300-L302).

### Design (confirmed by experiment)

A patched scheduler tested against the same scenario succeeds on all
feasible configs **and** keeps all 40 existing scheduler tests passing.
The fix has three parts:

1. **Hard correctness skip.** Before adding a team to the candidate list,
   compute the minimum runs the team still owes on *other days* and skip
   if assigning here would make those minimums unreachable:
   ```python
   other_day_min_need = sum(
       max(0, div.day_run_minimums.get(dl, 0) - team_day_runs[team][dl])
       for dl in day_labels if dl != slot.day
   )
   if total_runs_per_team - team_runs[team] - 1 < other_day_min_need:
       continue
   ```
   This is the only hard skip; it is provably safe (it never excludes a
   team unless that team must save the run for another day's minimum).

2. **Soft priority via a coherent sort key.** Compute a 3-level
   `min_priority` per candidate:
   - `0` if the team is below **today's** minimum (catch up today)
   - `2` if the team has met today's minimum but other days are still
     below their own minimum (save runs for those days)
   - `1` otherwise (everything is balanced; no preference)

   Use `min_priority` as the **primary** sort term, replacing the broken
   `runsNeededOnOtherDays`.

3. **Fix `runsNeededOnOtherDays` calculation** for correctness even though
   it becomes a non-decisive sort term: compare `dl != slot.day` on day
   labels (after `split(":")[0]`) and use each day's own minimum.

### Out of scope

- The simplified single-arena path (`num_arenas == 1 and arena_reset > 0`)
  is untouched — it already gates `day_run_limits` correctly and does not
  use `day_run_minimums` in candidate selection.
- `validate_schedule` is untouched; min/max constraints are enforced
  inside `build_schedule` already.
- No CLI or model changes — only the general scheduling path and tests.
- Tight configs that are **genuinely infeasible** at a given run_time
  (e.g. `5:5 / 4:4` at run_time=12 demands 150 runs on a day with 135
  capacity) continue to raise `SchedulingError` — that is correct.

## Tasks

- [x] **Task 1 — Add regression tests and apply the fix**

  All edits in [rcj_planner/scheduler.py](rcj_planner/scheduler.py) and
  new tests in [tests/test_scheduler.py](tests/test_scheduler.py) and
  [tests/test_integration.py](tests/test_integration.py). One commit at
  the end.

  1. **Add the unit regression test** in `tests/test_scheduler.py` (after
     the existing `test_day_run_minimum_impossible_raises` near
     [tests/test_scheduler.py:568](tests/test_scheduler.py#L568)). Use
     `DAYS_2_LONG = ["Day1:09:00-18:00", "Day2:09:00-18:00"]` (define
     locally — it is longer than the file's existing `DAYS_2`):

     ```python
     def test_day_run_min_max_large_two_day_schedule_balances():
         """30 teams, 3 arenas, runs=3, two 9-18 days, range min/max should succeed.

         Regression: commit abea07d's candidate logic raised
         SchedulingError on this feasible scenario.
         """
         DAYS_LONG = ["Day1:09:00-18:00", "Day2:09:00-18:00"]
         teams = [Team(f"T{i:02d}", "Maze") for i in range(30)]
         divisions = [Division(label="Maze", teams=teams, num_arenas=3,
                               runs_per_arena=3, no_interviews=True,
                               day_run_minimums={"Day1": 4, "Day2": 4},
                               day_run_limits={"Day1": 5, "Day2": 5})]
         s = build_schedule(divisions, DAYS_LONG, run_time=12,
                            interview_time=20, interview_group_size=3,
                            buffer_minutes=5)
         assert validate_schedule(s) == []
         # Each team got all required runs and per-day counts within range
         for t in teams:
             arena_assignments = [a for a in s.assignments
                                  if a.resource.kind == "arena" and t in a.teams]
             assert len(arena_assignments) == 9, f"{t.name}: expected 9 runs"
             for d in ("Day1", "Day2"):
                 c = sum(1 for a in arena_assignments if a.slot.day == d)
                 assert 4 <= c <= 5, f"{t.name} on {d}: {c} runs not in [4,5]"
     ```

  2. **Add a second smaller regression test** that pins the priority
     behaviour broken by Bug A/B (the day-label comparison and per-day
     minimum). This is the *small* analogue of the same bug:

     ```python
     def test_day_run_minimum_uses_per_day_value_not_today_min():
         """Day1 min=1, Day2 min=2: per-day minimums must be respected
         independently — the original buggy logic compared other days
         against today's minimum.
         """
         DAYS = ["Day1:09:00-17:00", "Day2:09:00-17:00"]
         teams = [Team(f"Team{i}", "Maze") for i in range(4)]
         divisions = [Division(label="Maze", teams=teams, num_arenas=1,
                               runs_per_arena=4,
                               day_run_minimums={"Day1": 1, "Day2": 2},
                               day_run_limits={"Day1": 3, "Day2": 2})]
         s = build_schedule(divisions, DAYS, run_time=10, interview_time=20,
                            interview_group_size=2, buffer_minutes=10)
         assert validate_schedule(s) == []
         for t in teams:
             arena = [a for a in s.assignments
                      if a.resource.kind == "arena" and t in a.teams]
             d1 = sum(1 for a in arena if a.slot.day == "Day1")
             d2 = sum(1 for a in arena if a.slot.day == "Day2")
             assert d1 == 2, f"{t.name}: expected 2 Day1 runs, got {d1}"
             assert d2 == 2, f"{t.name}: expected 2 Day2 runs, got {d2}"
     ```

  3. **Add a CLI integration test** in `tests/test_integration.py`,
     modeled on `test_generate_division_day_runs_multi_day_minimum`
     ([tests/test_integration.py:255](tests/test_integration.py#L255)):

     ```python
     def test_generate_division_day_runs_large_two_day_balances(tmp_path):
         """30 teams + range min/max on two 9-18 days runs=3 via CLI must succeed."""
         maze_csv = tmp_path / "maze.csv"
         maze_csv.write_text("team_name\n" + "\n".join(f"T{i:02d}" for i in range(30)) + "\n")
         schedule_file = tmp_path / "schedule.json"
         output_dir = tmp_path / "out"

         runner = CliRunner()
         result = runner.invoke(cli, [
             "generate",
             "--division", f"Maze:{maze_csv}:arenas=3:runs=3:no_interviews",
             "--division-day-runs", "Maze:Day1:4:5",
             "--division-day-runs", "Maze:Day2:4:5",
             "--run-time", "12",
             "--interview-time", "20",
             "--interview-group-size", "3",
             "--buffer", "5",
             "--day", "Day1:09:00-18:00",
             "--day", "Day2:09:00-18:00",
             "--save", str(schedule_file),
             "--output-dir", str(output_dir),
         ])
         assert result.exit_code == 0, result.output
         result = runner.invoke(cli, ["validate", str(schedule_file)])
         assert result.exit_code == 0, result.output
     ```

     Note: confirm `--buffer` (or the equivalent flag name) exists in
     [rcj_planner/cli.py](rcj_planner/cli.py) — if not, omit it (the
     default is acceptable).

  4. **Run the new tests against the unfixed scheduler first** to confirm
     they reproduce the bug (`python -m pytest tests/test_scheduler.py::test_day_run_min_max_large_two_day_schedule_balances -v`
     should fail with `SchedulingError`). This step is verification only;
     do not commit yet.

  5. **Apply the scheduler fix.** In
     [rcj_planner/scheduler.py:233-246](rcj_planner/scheduler.py#L233-L246),
     replace the buggy candidate block:

     ```python
                             day_min = div.day_run_minimums.get(slot.day,0)
                             days = div.day_specs if div.day_specs is not None else day_specs
                             runsNeededOnOtherDays = sum(d != slot.day and team_day_runs[team][d.split(":")[0]] < day_min for d in days)
                             runsNeededToday = div.day_run_minimums.get(slot.day, 0) - team_day_runs[team][slot.day]
                             if runsNeededToday < 0 and runsNeededOnOtherDays > 0:
                                 continue # deprioritize teams that have already met today's minimum if they still need runs on other days

                             candidates.append({
                                 "index": i,
                                 "team": team,
                                 "runsNeededToday": runsNeededToday,
                                 "runsNeededOnOtherDays": runsNeededOnOtherDays,
                                 "repeats_arena": 1 if (apply_no_repeat and team_last_arena.get(team) == arena) else 0,
                             })
     ```

     with:

     ```python
                             days = div.day_specs if div.day_specs is not None else day_specs
                             day_labels = [d.split(":")[0] for d in days]
                             today_min = div.day_run_minimums.get(slot.day, 0)
                             runsNeededToday = today_min - team_day_runs[team][slot.day]
                             other_day_min_need = sum(
                                 max(0, div.day_run_minimums.get(dl, 0) - team_day_runs[team][dl])
                                 for dl in day_labels if dl != slot.day
                             )
                             # Hard skip: assigning here would leave too few remaining runs to meet other days' minimums.
                             if total_runs_per_team - team_runs[team] - 1 < other_day_min_need:
                                 continue
                             runsNeededOnOtherDays = sum(
                                 1 for dl in day_labels
                                 if dl != slot.day
                                 and team_day_runs[team][dl] < div.day_run_minimums.get(dl, 0)
                             )
                             if runsNeededToday > 0:
                                 min_priority = 0
                             elif runsNeededOnOtherDays > 0:
                                 min_priority = 2
                             else:
                                 min_priority = 1
                             candidates.append({
                                 "index": i,
                                 "team": team,
                                 "runsNeededToday": runsNeededToday,
                                 "runsNeededOnOtherDays": runsNeededOnOtherDays,
                                 "min_priority": min_priority,
                                 "repeats_arena": 1 if (apply_no_repeat and team_last_arena.get(team) == arena) else 0,
                             })
     ```

  6. **Update the sort key** at
     [rcj_planner/scheduler.py:255](rcj_planner/scheduler.py#L255).
     Replace:

     ```python
                         key=lambda x: (x["runsNeededOnOtherDays"], -x["runsNeededToday"], x["repeats_arena"], team_day_runs[x["team"]][slot.day], team_runs[x["team"]], x["index"])
     ```

     with:

     ```python
                         key=lambda x: (x["min_priority"], -x["runsNeededToday"], x["repeats_arena"], team_day_runs[x["team"]][slot.day], team_runs[x["team"]], x["index"])
     ```

     Also update the comment one line above
     ([scheduler.py:252](rcj_planner/scheduler.py#L252)) to reflect the
     new key ordering: e.g. *"lowest min-priority (catch-up first, save-for-others
     last) → max runs still needed today → avoid repeating arena → fewest
     runs on this day → fewest total runs → original order"*.

  7. **Remove the dead commented-out debug prints** at
     [scheduler.py:260-264](rcj_planner/scheduler.py#L260-L264) and
     [scheduler.py:300-302](rcj_planner/scheduler.py#L300-L302) (the
     `# print(f"...")` blocks left over from commit abea07d). Delete
     the comment-only block lines.

  8. **Run the full test suite** (`python -m pytest tests/`). The three
     new tests plus all existing 40+ scheduler tests and the integration
     suite must pass. Fix any regressions before continuing.

  9. **Commit** the change with a message like:

     ```
     fix(scheduler): correctly balance day_run_minimums across days

     The candidate logic in build_schedule's general path had two bugs:
     a day-label comparison that never excluded the current day, and a
     hard `continue` that excluded teams the greedy still needed. Replace
     the broken filter with a feasibility-preserving hard skip (do not
     assign if the team can no longer meet other days' minimums) and a
     three-level soft priority in the sort key. Also drop leftover
     commented debug prints.

     Fixes scheduler failure on feasible configs like 30 teams / 3 arenas
     / runs=3 / per-day min:max 4:5 over two 9-18 days.
     ```
