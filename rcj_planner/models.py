from __future__ import annotations
from dataclasses import dataclass, field
from datetime import time
from typing import Literal, Optional


@dataclass
class Team:
    name: str
    division: str = ""

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, Team) and self.name == other.name


@dataclass
class Division:
    label: str
    teams: list  # list[Team], avoid forward-ref issues
    num_arenas: int
    runs_per_arena: int = 1
    arena_reset_minutes: int = 0
    no_interviews: bool = False
    day_specs: list | None = None  # None = use global day_specs
    day_run_limits: dict = field(default_factory=dict)  # {day_label: int} max runs per team per day


@dataclass(frozen=True)
class TimeSlot:
    day: str
    start: time
    end: time

    def overlaps(self, other: TimeSlot) -> bool:
        if self.day != other.day:
            return False
        return self.start < other.end and other.start < self.end

    def buffer_conflict(self, other: TimeSlot, gap_minutes: int) -> bool:
        if self.day != other.day:
            return False
        from datetime import datetime, date
        d = date.today()
        a_start = datetime.combine(d, self.start)
        a_end = datetime.combine(d, self.end)
        b_start = datetime.combine(d, other.start)
        b_end = datetime.combine(d, other.end)
        gap = gap_minutes * 60  # seconds
        # gap between the two slots (non-overlapping)
        if a_end <= b_start:
            return (b_start - a_end).seconds < gap
        if b_end <= a_start:
            return (a_start - b_end).seconds < gap
        return True  # overlapping counts as conflict


@dataclass(frozen=True)
class Resource:
    kind: Literal["arena", "interview"]
    name: str


@dataclass
class Assignment:
    slot: TimeSlot
    resource: Resource
    teams: list[Team]


@dataclass(frozen=True)
class Break:
    """A time window during which no assignments may be scheduled.

    If division is None, the break is global (applies to all divisions and interviews).
    If division is set, it only blocks arena runs for that division.
    """
    day: str
    start: time
    end: time
    division: Optional[str] = None

    def blocks_slot(self, slot: TimeSlot) -> bool:
        """Return True if this break window overlaps the given slot."""
        if self.day != slot.day:
            return False
        return self.start < slot.end and slot.start < self.end


@dataclass
class Schedule:
    assignments: list[Assignment] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def assignments_for_team(self, team: Team) -> list[Assignment]:
        return [a for a in self.assignments if team in a.teams]

    def assignments_for_resource(self, resource: Resource) -> list[Assignment]:
        return [a for a in self.assignments if a.resource == resource]
