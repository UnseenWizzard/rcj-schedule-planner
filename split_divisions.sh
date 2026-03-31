#!/bin/bash
# Split a CSV file by division into separate per-division files
# Usage: ./split_divisions.sh rcj_ao_2026_rescue_teams.csv

INPUT_FILE="${1:-.}"
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: File '$INPUT_FILE' not found"
    exit 1
fi

# Use awk to process the CSV and create per-division files
awk -F',' 'NR==1 {next}
{
    division = $NF
    gsub(/^[ \t]+|[ \t]+$/, "", division)  # trim whitespace
    filename = division
    gsub(/ /, "_", filename)
    gsub(/\//, "-", filename)
    filename = filename ".csv"

    if (!(division in divisions)) {
        divisions[division] = filename
        print "team_name" > filename
    }

    print $1 >> filename
}
END {
    for (div in divisions) {
        filename = divisions[div]
        cmd = "wc -l < " filename
        cmd | getline count
        close(cmd)
        count--  # subtract header
        printf "  → %s (%d teams)\n", filename, count
    }
}' "$INPUT_FILE"

echo ""
echo "Done. Division files created."
