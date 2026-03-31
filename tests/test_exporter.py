import csv, os
from datetime import time
from rcj_planner.models import Team, TimeSlot, Resource, Assignment, Schedule
from rcj_planner.exporter import export_day_csvs


def make_schedule():
    t1, t2 = Team("Alpha"), Team("Beta")
    r1 = Resource("arena", "Arena 1")
    ri = Resource("interview", "Interview")
    s1 = TimeSlot("Day1", time(9, 0), time(9, 10))
    s2 = TimeSlot("Day1", time(9, 10), time(9, 20))
    s3 = TimeSlot("Day1", time(9, 0), time(9, 20))
    return Schedule(assignments=[
        Assignment(s1, r1, [t1]),
        Assignment(s2, r1, [t2]),
        Assignment(s3, ri, [t1, t2]),
    ])


def test_creates_day_csv(tmp_path):
    s = make_schedule()
    export_day_csvs(s, str(tmp_path))
    assert os.path.exists(tmp_path / "Day1.csv")


def test_csv_content(tmp_path):
    s = make_schedule()
    export_day_csvs(s, str(tmp_path))
    with open(tmp_path / "Day1.csv") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert rows[0]["time_slot"] == "09:00-09:10"
    assert rows[0]["resource"] == "Arena 1"
    assert rows[0]["teams"] == "Alpha"


def test_sorted_output(tmp_path):
    s = make_schedule()
    export_day_csvs(s, str(tmp_path))
    with open(tmp_path / "Day1.csv") as f:
        rows = list(csv.DictReader(f))
    times = [r["time_slot"] for r in rows]
    assert times == sorted(times)
