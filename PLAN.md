# RCJ Schedule Planner CLI

## Context
RoboCupJunior events require each team to complete one scoring run per arena and one technical interview. Scheduling these manually is error-prone and time-consuming. This CLI automates the process: given teams, arenas, time parameters, and available day/timeframes, it produces a valid conflict-free schedule exported as per-day CSVs.

---

## Project Structure

```
/Users/captain/src/rcj-schedule-planner/
├── pyproject.toml               # PEP 621, entry point: rcj-planner
├── rcj_planner/
│   ├── __init__.py
│   ├── cli.py                   # Click command group (generate, show, validate)
│   ├── models.py                # Dataclasses: Team, TimeSlot, Resource, Assignment, Schedule
│   ├── loader.py                # Parse teams CSV + day specs
│   ├── scheduler.py             # Greedy scheduler + constraint helpers
│   ├── persistence.py           # JSON save/load
│   └── exporter.py              # Write per-day CSVs
└── tests/
    ├── test_models.py
    ├── test_scheduler.py
    └── test_exporter.py
```

Packaging: `pip install -e .` (standard pip/venv, no uv).

---

## Data Models (`models.py`)

- **`Team`**: `name: str`, `division: str = ""`
- **`TimeSlot`** (frozen dataclass): `day: str`, `start: time`, `end: time`
  - `overlaps(other)` — true if intervals intersect
  - `buffer_conflict(other, gap_minutes)` — true if gap between slots < `gap_minutes`
- **`Resource`** (frozen dataclass): `kind: Literal["arena","interview"]`, `name: str`
- **`Assignment`**: `slot: TimeSlot`, `resource: Resource`, `teams: list[Team]`
- **`Schedule`**: `assignments: list[Assignment]`, `meta: dict`
  - `assignments_for_team(team)`, `assignments_for_resource(resource)`

---

## CLI Interface (`cli.py`)

Tool: **Click**, entry point `rcj-planner`.

### `generate` command
```
rcj-planner generate \
  --teams teams.csv \
  --arenas 4 \
  --run-time 10 \
  --interview-time 20 \
  --interview-group-size 3 \
  --day "Day1:09:00-17:00" \
  --day "Day2:09:00-13:00" \
  --output-dir ./output \
  --save schedule.json
```

| Flag | Required | Default | Notes |
|---|---|---|---|
| `--teams` | yes | — | CSV path |
| `--arenas` | yes | — | integer |
| `--run-time` | yes | — | minutes per run slot |
| `--interview-time` | yes | — | minutes per interview slot |
| `--interview-group-size` | yes | — | teams per slot |
| `--day` | yes (multi) | — | `Label:HH:MM-HH:MM` |
| `--output-dir` | no | `./output` | |
| `--save` | no | `schedule.json` | |
| `--buffer` | no | = `--run-time` | enforced gap between a team's consecutive assignments |

### `show` command
```
rcj-planner show schedule.json [--day Day1]
```
Prints a formatted table per day to stdout.

### `validate` command
```
rcj-planner validate schedule.json
```
Re-checks all constraints on a saved schedule; reports violations.

---

## Input/Output Formats

### `teams.csv`
```
team_name,division
Warp Drive,Soccer Open
SkyBot,Rescue Maze
```
`division` column is used to auto-group teams for interviews (teams in the same division share slots). `team_name` is required.

### Output `Day1.csv`
```
time_slot,resource,teams
09:00-09:10,Arena 1,Warp Drive
09:10-09:20,Arena 2,SkyBot
09:00-09:20,Interview,"Warp Drive, SkyBot, Thunderbots"
```
Sorted by `time_slot` then `resource`.

### `schedule.json` (persistence)
```json
{
  "meta": { "arenas": 4, "run_time_minutes": 10, "interview_time_minutes": 20, ... },
  "assignments": [
    { "day": "Day1", "start": "09:00", "end": "09:10",
      "resource_kind": "arena", "resource_name": "Arena 1", "teams": ["Warp Drive"] }
  ]
}
```

---

## Scheduling Algorithm (`scheduler.py`)

### Slot generation
For each day, enumerate fixed-width slots starting at `day_start`, stepping by `slot_duration`, until `day_end`.
Run slots and interview slots are on **separate grids** (different durations).

### Constraints
1. Each team: exactly 1 run per arena.
2. Each team: exactly 1 interview assignment.
3. Same team: no two assignments overlap in time.
4. Same team: gap between any two consecutive assignments ≥ `buffer_minutes`.
5. Same resource: no two assignments overlap in time.

Buffer math (fixed-grid): `|slot_a.start − slot_b.start| < (slot_duration + buffer_minutes)`.

### Phase 1 — Arena runs (greedy round-robin)
```
for each arena:
    for each team:
        find earliest run-slot s where constraints 3–5 are satisfied
        assign (s, arena, [team])
```
Per-arena cursor advances past the last assigned slot to spread load.

### Phase 2 — Interviews (grouped by division)
```
groups = { division: [teams…] }
for each division:
    chunk teams into groups of interview_group_size
    for each group:
        find earliest interview-slot s satisfying constraints 3–5 for all members
        assign (s, interview_resource, group)
```
If a division's team count is not a multiple of `interview_group_size`, the last group is smaller.

### Error handling
If no valid slot is found, raise `SchedulingError` with a clear message (team name, resource, reason). No backtracking in v1 — the user adjusts parameters.

---

## Implementation Steps

1. **Scaffold** — `pyproject.toml` (Click dependency, entry point), package dirs, `__init__.py` files.
2. **`models.py`** — dataclasses + `overlaps` / `buffer_conflict` helpers; unit tests.
3. **`loader.py`** — `load_teams(path)`, `parse_day_spec(spec)`, `generate_slots(days, minutes)`; unit tests.
4. **`scheduler.py`** — slot generator, constraint helpers, phase 1 & 2 algorithm, `SchedulingError`; unit tests with small cases (4 teams, 2 arenas, 1 day).
5. **`persistence.py`** — `save(schedule, path)` / `load(path)` with round-trip test.
6. **`exporter.py`** — `export_day_csvs(schedule, output_dir)` sorted output; unit tests.
7. **`cli.py`** — `generate`, `show`, `validate` commands wiring all modules.
8. **Integration test** — `CliRunner` end-to-end: generate → validate → check CSV row count.

---

## Verification

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Run tests
python -m pytest tests/

# Generate a schedule
rcj-planner generate \
  --teams teams.csv --arenas 3 \
  --run-time 10 --interview-time 15 --interview-group-size 3 \
  --day "Day1:09:00-17:00" \
  --save schedule.json --output-dir ./out

# Validate
rcj-planner validate schedule.json

# Inspect
rcj-planner show schedule.json
cat out/Day1.csv
```

Expected: no `SchedulingError`, each team appears in exactly N arena rows + 1 interview row across all CSVs, `validate` exits 0.

---

## Critical Files
- `rcj_planner/models.py` — core data structures
- `rcj_planner/scheduler.py` — algorithm (highest complexity)
- `rcj_planner/cli.py` — user-facing interface
- `rcj_planner/loader.py` — input parsing
- `pyproject.toml` — entry point wiring
