from __future__ import annotations
import json
from datetime import time
from rcj_planner.models import Team, TimeSlot, Resource, Assignment, Schedule


def save(schedule: Schedule, path: str) -> None:
    data = {
        "meta": schedule.meta,
        "assignments": [
            {
                "day": a.slot.day,
                "start": a.slot.start.strftime("%H:%M"),
                "end": a.slot.end.strftime("%H:%M"),
                "resource_kind": a.resource.kind,
                "resource_name": a.resource.name,
                "teams": [t.name for t in a.teams],
                "divisions": [t.division for t in a.teams],
            }
            for a in schedule.assignments
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load(path: str) -> Schedule:
    with open(path) as f:
        data = json.load(f)

    assignments = []
    for item in data["assignments"]:
        slot = TimeSlot(
            day=item["day"],
            start=time.fromisoformat(item["start"]),
            end=time.fromisoformat(item["end"]),
        )
        resource = Resource(kind=item["resource_kind"], name=item["resource_name"])
        teams = [
            Team(name=name, division=div)
            for name, div in zip(item["teams"], item.get("divisions", [""] * len(item["teams"])))
        ]
        assignments.append(Assignment(slot=slot, resource=resource, teams=teams))

    return Schedule(assignments=assignments, meta=data.get("meta", {}))
