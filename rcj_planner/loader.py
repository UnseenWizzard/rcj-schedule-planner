from __future__ import annotations
import csv
from datetime import time, datetime, timedelta
from rcj_planner.models import Team, TimeSlot, Break


def load_teams(path: str, division: str = "") -> list[Team]:
    teams = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            teams.append(Team(name=row["team_name"], division=division or row.get("division", "")))
    return teams


def parse_division_spec(spec: str) -> tuple[str, str, int, int]:
    """Parse 'Label:path/to/teams.csv:arenas=N[:runs=M]' into (label, path, num_arenas, runs_per_arena)."""
    parts = spec.split(":")
    if len(parts) not in (3, 4):
        raise ValueError(f"Invalid division spec {spec!r}. Expected 'Label:path:arenas=N' or 'Label:path:arenas=N:runs=M'")
    label, path, arenas_part = parts[0], parts[1], parts[2]
    if not arenas_part.startswith("arenas="):
        raise ValueError(f"Invalid arenas part {arenas_part!r}. Expected 'arenas=N'")
    num_arenas = int(arenas_part.split("=", 1)[1])
    runs_per_arena = 1
    if len(parts) == 4:
        runs_part = parts[3]
        if not runs_part.startswith("runs="):
            raise ValueError(f"Invalid runs part {runs_part!r}. Expected 'runs=N'")
        runs_per_arena = int(runs_part.split("=", 1)[1])
    return label.strip(), path.strip(), num_arenas, runs_per_arena


def parse_break_spec(spec: str) -> Break:
    """Parse a break spec into a Break.

    Formats:
      'Day1:12:00-13:00'              — global break on Day1 12:00–13:00
      'Day1:Line:12:00-13:00'         — division-specific break (Line only)
    """
    parts = spec.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"Invalid break spec {spec!r}")
    day = parts[0].strip()
    rest = parts[1] if len(parts) == 2 else parts[1] + ":" + parts[2]

    # Try to parse rest as 'HH:MM-HH:MM' (global) or 'Division:HH:MM-HH:MM'
    # A time range contains exactly one '-' between two HH:MM tokens.
    # If rest starts with digits it's a time range; otherwise it's 'Division:HH:MM-HH:MM'.
    if rest[0].isdigit():
        # global: rest = 'HH:MM-HH:MM'
        division = None
        timerange = rest
    else:
        # division-specific: rest = 'Division:HH:MM-HH:MM'
        div_sep = rest.index(":")
        division = rest[:div_sep].strip()
        timerange = rest[div_sep + 1:]

    if "-" not in timerange:
        raise ValueError(f"Invalid time range in break spec {spec!r}")
    start_str, end_str = timerange.split("-", 1)
    start = datetime.strptime(start_str.strip(), "%H:%M").time()
    end = datetime.strptime(end_str.strip(), "%H:%M").time()
    return Break(day=day, start=start, end=end, division=division)


def parse_day_spec(spec: str) -> tuple[str, time, time]:
    """Parse 'Label:HH:MM-HH:MM' into (label, start_time, end_time)."""
    label, timerange = spec.split(":", 1)
    start_str, end_str = timerange.split("-", 1)
    start = datetime.strptime(start_str.strip(), "%H:%M").time()
    end = datetime.strptime(end_str.strip(), "%H:%M").time()
    return label, start, end


def generate_slots(day_specs: list[str], slot_minutes: int) -> list[TimeSlot]:
    """Generate all fixed-width TimeSlots for each day spec."""
    slots = []
    delta = timedelta(minutes=slot_minutes)
    for spec in day_specs:
        label, start, end = parse_day_spec(spec)
        current = datetime(2000, 1, 1, start.hour, start.minute)
        day_end = datetime(2000, 1, 1, end.hour, end.minute)
        while current + delta <= day_end:
            slot_end = current + delta
            slots.append(TimeSlot(label, current.time(), slot_end.time()))
            current = slot_end
    return slots
