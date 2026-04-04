# How to work

- Make small changes and verify after each one.
- When significant code changes are done, make a git commit.

# Planning

- When asked to plan, write the plan to a file named `PLAN_<topic>.md` in the repo root, then stop — do not execute it.
- Plans must contain a checklist of tasks, each broken down into clear, numbered steps that a simpler agent can pick up independently.
- Each task that touches Python code must end with: run any existing or newly created tests and fix failures, then make a git commit. Tasks that only change non-Python files (e.g. HTML, shell scripts, markdown) do not need a test run — just commit.
- Use GitHub Flavored Markdown task list syntax (`- [ ] Task`) for each task so they can be ticked off.

## Implementing a plan

- When implementing a plan, tick off each task (`- [x]`) in the plan file as it is completed.
- Update the plan file after completing each task — do not batch updates.

# Project overview

A CLI tool (`rcj-planner`) that generates conflict-free schedules for RoboCupJunior events. It takes divisions (teams + arena count), time parameters, and day/timeframe specs, then outputs per-day CSVs and a `schedule.json`.

See README.md for full usage, input/output format, and scheduling rules.

# Project structure

```
rcj_planner/
  cli.py          # Entry point — Click CLI commands: generate, show, validate
  scheduler.py    # Core scheduling logic: build_schedule, validate_schedule
  models.py       # Data models: Division, Team, Slot, Assignment, Schedule
  loader.py       # CSV team file loading
  exporter.py     # CSV output generation
  persistence.py  # schedule.json save/load
tests/
  test_models.py
  test_exporter.py
ui/
  schedule_viewer.html  # Browser-based schedule viewer
```

# Development

Activate the venv before running anything:

```bash
source .venv/bin/activate
```

Run tests:

```bash
python -m pytest tests/
```

Quick integration smoke-test (uses `input/` files):

```bash
bash integrationtest.sh
```

Generate a schedule and inspect it:

```bash
rcj-planner generate --division "Maze:input/maze.csv:arenas=3" --run-time 10 --interview-time 20 --interview-group-size 3 --day "Day1:09:00-17:00" --output-dir ./output
rcj-planner show schedule.json
rcj-planner validate schedule.json
```
