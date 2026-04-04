from __future__ import annotations
import sys
import click
from rcj_planner.loader import load_teams, parse_division_spec, parse_break_spec
from rcj_planner.scheduler import build_schedule, validate_schedule, SchedulingError
from rcj_planner.persistence import save, load
from rcj_planner.exporter import export_day_csvs


@click.group()
def cli():
    """RCJ Schedule Planner"""


@cli.command()
@click.option("--division", "division_specs", required=True, multiple=True,
              help="Division spec: 'Label:path/to/teams.csv:arenas=N'")
@click.option("--run-time", required=True, type=int, help="Minutes per run slot")
@click.option("--interview-time", required=True, type=int, help="Minutes per interview slot")
@click.option("--interview-group-size", required=True, type=int, help="Teams per interview slot")
@click.option("--day", "days", required=True, multiple=True, help="Day spec: Label:HH:MM-HH:MM")
@click.option("--interview-day", "interview_days", multiple=True,
              help="Override interview time window for a day: Label:HH:MM-HH:MM")
@click.option("--interview-rooms", default=1, type=int, show_default=True,
              help="Number of parallel interview rooms")
@click.option("--output-dir", default="./output", show_default=True, help="Output directory for CSVs")
@click.option("--save", "save_path", default="schedule.json", show_default=True, help="Path to save schedule JSON")
@click.option("--buffer", default=None, type=int, help="Buffer gap in minutes (default: run-time)")
@click.option("--break", "break_specs", multiple=True,
              help="Break spec: 'Day:HH:MM-HH:MM' (global) or 'Day:Division:HH:MM-HH:MM' (division-specific)")
def generate(division_specs, run_time, interview_time, interview_group_size, days,
             interview_days, interview_rooms, output_dir, save_path, buffer, break_specs):
    """Generate a conflict-free schedule and export CSVs."""
    import os
    if save_path == "schedule.json":
        save_path = os.path.join(output_dir, "schedule.json")
    os.makedirs(output_dir, exist_ok=True)
    buffer_minutes = buffer if buffer is not None else run_time
    try:
        divisions = []
        for spec in division_specs:
            label, path, num_arenas, runs_per_arena, arena_reset = parse_division_spec(spec)
            teams = load_teams(path, division=label)
            divisions.append((label, teams, num_arenas, runs_per_arena, arena_reset))

        parsed_breaks = [parse_break_spec(s) for s in break_specs]

        day_labels = {d.split(":")[0] for d in days}
        for iday in interview_days:
            label = iday.split(":")[0]
            if label not in day_labels:
                raise click.BadParameter(
                    f"'{label}' does not match any --day label", param_hint="--interview-day"
                )
        interview_overrides = {iday.split(":")[0]: iday for iday in interview_days}
        resolved_interview_day_specs = [
            interview_overrides.get(d.split(":")[0], d) for d in days
        ]

        schedule = build_schedule(
            divisions=divisions,
            day_specs=list(days),
            run_time=run_time,
            interview_time=interview_time,
            interview_group_size=interview_group_size,
            buffer_minutes=buffer_minutes,
            breaks=parsed_breaks,
            interview_day_specs=resolved_interview_day_specs,
            num_interview_rooms=interview_rooms,
        )
    except (SchedulingError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    save(schedule, save_path)
    export_day_csvs(schedule, output_dir)
    click.echo(f"Schedule saved to {save_path}")
    click.echo(f"CSVs written to {output_dir}/")


@cli.command()
@click.argument("schedule_path")
@click.option("--day", "filter_day", default=None, help="Show only a specific day")
def show(schedule_path, filter_day):
    """Print a formatted schedule table."""
    schedule = load(schedule_path)
    from collections import defaultdict
    by_day = defaultdict(list)
    for a in schedule.assignments:
        by_day[a.slot.day].append(a)

    for day in sorted(by_day):
        if filter_day and day != filter_day:
            continue
        click.echo(f"\n=== {day} ===")
        click.echo(f"{'Time':<16} {'Resource':<16} {'Teams'}")
        click.echo("-" * 60)
        assignments = sorted(by_day[day], key=lambda a: (a.slot.start, a.resource.name))
        for a in assignments:
            time_str = f"{a.slot.start.strftime('%H:%M')}-{a.slot.end.strftime('%H:%M')}"
            teams_str = ", ".join(t.name for t in a.teams)
            click.echo(f"{time_str:<16} {a.resource.name:<16} {teams_str}")


@cli.command()
@click.argument("schedule_path")
def validate(schedule_path):
    """Validate a saved schedule for constraint violations."""
    schedule = load(schedule_path)
    violations = validate_schedule(schedule)
    if violations:
        for v in violations:
            click.echo(f"VIOLATION: {v}")
        sys.exit(1)
    else:
        click.echo("Schedule is valid. No violations found.")
