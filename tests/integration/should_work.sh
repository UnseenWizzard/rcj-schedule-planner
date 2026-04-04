#!/bin/sh

TMPFILE=$(mktemp /tmp/Online_Simulation_XXXXXX.csv)
cat > "$TMPFILE" << 'EOF'
team_name
Metal Minds
MS LaHö
O-Dorf
MS HöWe
EOF

rcj-planner generate \
    --division "Online_Simulation:$TMPFILE:arenas=1:runs=4:arena_reset=60" \
    --run-time 10 --interview-time 15 --interview-group-size 2 \
    --day "Day1:10:30-18:00" \
    --day "Day2:09:00-13:00" \
    --break "Day1:12:30-13:30" \
    --buffer 10

rm -f "$TMPFILE"
