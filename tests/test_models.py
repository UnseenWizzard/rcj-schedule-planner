from datetime import time
from rcj_planner.models import Team, TimeSlot, Resource, Assignment, Schedule


def make_slot(day, h1, m1, h2, m2):
    return TimeSlot(day, time(h1, m1), time(h2, m2))


def test_timeslot_overlaps():
    a = make_slot("Day1", 9, 0, 9, 10)
    b = make_slot("Day1", 9, 5, 9, 15)
    c = make_slot("Day1", 9, 10, 9, 20)
    assert a.overlaps(b)
    assert not a.overlaps(c)


def test_timeslot_different_days_no_overlap():
    a = make_slot("Day1", 9, 0, 9, 10)
    b = make_slot("Day2", 9, 0, 9, 10)
    assert not a.overlaps(b)


def test_buffer_conflict():
    a = make_slot("Day1", 9, 0, 9, 10)
    b = make_slot("Day1", 9, 15, 9, 25)
    assert a.buffer_conflict(b, 10)   # gap=5min < 10
    assert not a.buffer_conflict(b, 5)  # gap=5min >= 5


def test_schedule_assignments_for_team():
    t1 = Team("Alpha")
    t2 = Team("Beta")
    r = Resource("arena", "Arena 1")
    slot = make_slot("Day1", 9, 0, 9, 10)
    a = Assignment(slot, r, [t1])
    s = Schedule(assignments=[a])
    assert s.assignments_for_team(t1) == [a]
    assert s.assignments_for_team(t2) == []


def test_schedule_assignments_for_resource():
    r1 = Resource("arena", "Arena 1")
    r2 = Resource("arena", "Arena 2")
    slot = make_slot("Day1", 9, 0, 9, 10)
    a = Assignment(slot, r1, [Team("Alpha")])
    s = Schedule(assignments=[a])
    assert s.assignments_for_resource(r1) == [a]
    assert s.assignments_for_resource(r2) == []
