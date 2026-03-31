from __future__ import annotations
import csv
import os
from collections import defaultdict
from rcj_planner.models import Schedule


def export_day_csvs(schedule: Schedule, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    by_day: dict[str, list] = defaultdict(list)
    for a in schedule.assignments:
        by_day[a.slot.day].append(a)

    for day, assignments in by_day.items():
        assignments.sort(key=lambda a: (a.slot.start, a.resource.name))
        path = os.path.join(output_dir, f"{day}.csv")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_slot", "resource", "teams"])
            for a in assignments:
                time_slot = f"{a.slot.start.strftime('%H:%M')}-{a.slot.end.strftime('%H:%M')}"
                teams_str = ", ".join(t.name for t in a.teams)
                writer.writerow([time_slot, a.resource.name, teams_str])
