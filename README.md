# rcj-schedule-planner

A CLI tool for generating conflict-free schedules for RoboCupJunior events. Given divisions (each with their own teams file and arena count), time parameters, and available day/timeframes, it produces a valid schedule exported as per-day CSVs.

Each division gets its own independent arena run schedule. All divisions share the interview schedule, which supports one or more parallel interview rooms.

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Usage

### Generate a schedule

```bash
rcj-planner generate \
  --division "Maze:soccer.csv:arenas=3" \
  --division "Rescue Maze:rescue.csv:arenas=2:runs=2" \
  --run-time 10 \
  --interview-time 20 \
  --interview-group-size 3 \
  --day "Day1:09:00-17:00" \
  --day "Day2:09:00-13:00" \
  --interview-day "Day1:13:00-17:00" \
  --interview-rooms 2 \
  --break "Day1:12:00-13:00" \
  --break "Day2:Rescue Maze:10:00-10:30" \
  --output-dir ./output \
  --save schedule.json
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--division` | yes (repeatable) | — | Division spec (see below) |
| `--run-time` | yes | — | Minutes per arena run slot |
| `--interview-time` | yes | — | Minutes per interview slot |
| `--interview-group-size` | yes | — | Teams per interview slot |
| `--day` | yes (repeatable) | — | Day spec: `Label:HH:MM-HH:MM` |
| `--output-dir` | no | `./output` | Directory for CSV output |
| `--save` | no | `schedule.json` | Path for saved schedule |
| `--buffer` | no | = `--run-time` | Minimum gap (minutes) between a team's consecutive assignments |
| `--break` | no (repeatable) | — | Break spec: `Day:HH:MM-HH:MM` (global) or `Day:Division:HH:MM-HH:MM` (division-specific) |
| `--interview-day` | no (repeatable) | — | Override interview time window for a day: `Label:HH:MM-HH:MM`. Label must match an existing `--day` label. Days without an override use their `--day` window. |
| `--interview-rooms` | no | `1` | Number of parallel interview resources. When `1`, the resource is named `"Interview"`; when `>1`, resources are named `"Interview 1"`, `"Interview 2"`, etc. |

#### Division spec

```
Label:path/to/teams.csv:arenas=N[:runs=M][:arena_reset=R]
```

| Key | Required | Default | Description |
|---|---|---|---|
| `Label` | yes | — | Display name for the division (e.g. `Soccer Open`) |
| `path/to/teams.csv` | yes | — | Path to the CSV file listing team names |
| `arenas=N` | yes | — | Number of arenas available to this division |
| `runs=M` | no | `1` | Number of runs each team must complete on each arena |
| `arena_reset=R` | no | `0` | Minutes to block an arena after each complete round (one run per team) before the next round can begin |

Example:

```bash
--division "Rescue Maze:input/maze.csv:arenas=2:runs=3:arena_reset=15"
```

This schedules the Rescue Maze division with 2 arenas, 3 runs per team per arena, and a 15-minute reset gap between rounds on each arena.

### Inspect a schedule

```bash
rcj-planner show schedule.json
rcj-planner show schedule.json --day Day1
```

### Validate a saved schedule

```bash
rcj-planner validate schedule.json
```

## Input format

Each division requires its own CSV file:

### `soccer.csv` / `rescue.csv` / …

```csv
team_name
Warp Drive
SkyBot
Thunderbots
```

Only `team_name` is required. The division label comes from the `--division` spec, not from the file.

## Output format

### Per-day CSVs (`Day1.csv`, `Day2.csv`, …)

```csv
time_slot,resource,teams
09:00-09:10,Soccer Open – Arena 1,Warp Drive
09:10-09:20,Soccer Open – Arena 2,SkyBot
09:00-09:10,Rescue Maze – Arena 1,Gamma
09:00-09:20,Interview,"Warp Drive, SkyBot, Thunderbots"
```

Arena resources are namespaced by division (`"Soccer Open – Arena 1"`). The interview resource is shared across all divisions and named `"Interview"` by default. With `--interview-rooms 2` the resources are named `"Interview 1"`, `"Interview 2"`, etc. Rows are sorted by `time_slot` then `resource`.

### `schedule.json`

Saved schedule for use with `show` and `validate` commands.

## Scheduling rules

1. Each team gets one run per arena per run in their division (configurable via `runs=N` in the division spec, default 1).
2. Each team gets exactly one interview assignment.
3. No team has two assignments that overlap in time.
4. No team has two consecutive assignments closer than `--buffer` minutes apart.
5. No resource (arena or interview room) is double-booked.
6. Arena resources are isolated per division — teams only run on their division's arenas.
   Interview resources are shared across divisions; the number of parallel rooms is set with `--interview-rooms` (default 1).

7. Global breaks (`Day:HH:MM-HH:MM`) block all arena runs and interviews during that window. Division-specific breaks (`Day:Division:HH:MM-HH:MM`) block only that division's arena runs.
8. After each complete round on an arena (all teams have had one run), the arena is blocked for `arena_reset=R` minutes (configured per division in the `--division` spec) before the next round begins.

Teams within a division are grouped for interviews by `--interview-group-size`. If a division's team count is not a multiple of that size, the last group is smaller.

If no valid slot can be found for a team, the tool exits with a clear error describing which team/resource is affected. Adjust the day length, buffer, or slot durations and retry.

## Schedule Viewer

Open `ui/schedule_viewer.html` in a browser and load a `schedule.json` file to view the schedule interactively.

## Development

```bash
pip install pytest
python -m pytest tests/
```

---

