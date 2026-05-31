# create_super_teams

Pairs Maze and Line rescue teams into SuperTeams for the same competition level (Entry / Regular).

## Usage

```
python create_super_teams.py <teams.csv> [--points-range N] [--output-dir DIR]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--points-range` | `20` | Maximum allowed points difference between the two paired teams |
| `--output-dir` / `-o` | `.` | Directory where output files are written |

## Input

A semicolon-delimited CSV with a header row:

```
TeamName;Discipline;Level;City;Institution;Language;Points
```

- `Discipline` must be `Maze` or `Line`; all other disciplines are ignored.
- `Level` must be `Entry` or `Regular`; other levels are ignored.
- `Language` is optional — rows without it are treated as unknown language.
- `Points` must be an integer; rows with non-numeric values are skipped.

## Matching rules

For each Maze team the script finds the best available Line team of the **same level** such that:

1. Points difference ≤ `--points-range`
2. **Different language** (primary constraint)
3. **Different city** (always required)

If no different-language candidate exists within the points range, the city constraint alone is applied as a fallback, allowing a same-language pairing.

Each team is used at most once. Among valid candidates the one with the smallest points difference is chosen.

## Output

Two CSV files in the output directory:

- `superteams_entry.csv`
- `superteams_regular.csv`

Each file has the columns:

```
Level, MazeTeam, MazeCity, MazeLanguage, MazePoints,
LineTeam, LineCity, LineLanguage, LinePoints, PointsDiff
```

Teams that could not be matched are not included in any output file.
