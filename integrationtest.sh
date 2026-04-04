#!/bin/bash
source .venv/bin/activate
python -c "
from rcj_planner.loader import load_teams
from rcj_planner.scheduler import build_schedule, validate_schedule
from collections import defaultdict

teams = load_teams('input/Line_Entry.csv', division='Line Entry')
print(f'Teams: {len(teams)}')
divisions = [('Line Entry', teams, 3, 1)]

s = build_schedule(
    divisions=divisions,
    day_specs=['Day1:11:00-17:00', 'Day2:09:00-14:00'],
    run_time=10,
    interview_time=15,
    interview_group_size=2,
    buffer_minutes=10,
)
violations = validate_schedule(s)
print(f'Violations: {violations}')

team_day_runs = defaultdict(lambda: defaultdict(int))
for a in s.assignments:
    if a.resource.kind == 'arena':
        for t in a.teams:
            team_day_runs[t.name][a.slot.day] += 1

days = sorted(set(d for td in team_day_runs.values() for d in td))
print(f'{\"Team\":<25}' + ''.join(f'{d:>8}' for d in days) + f'{\"Total\":>8}')
for team in sorted(team_day_runs):
    d = team_day_runs[team]
    row = f'{team:<25}' + ''.join(f'{d.get(day,0):>8}' for day in days) + f'{sum(d.values()):>8}'
    print(row)

d1_total = sum(v.get('Day1', 0) for v in team_day_runs.values())
d2_total = sum(v.get('Day2', 0) for v in team_day_runs.values())
print(f'Totals: Day1={d1_total}, Day2={d2_total}')
teams_2plus_day1 = sum(1 for v in team_day_runs.values() if v.get('Day1',0) >= 2)
print(f'Teams with 2+ runs on Day1: {teams_2plus_day1}/{len(team_day_runs)}')
"
