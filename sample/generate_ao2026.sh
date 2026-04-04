#!/bin/sh

# --interview-day restricts interviews to the afternoon on Day1
# --interview-rooms 2 allows two groups to be interviewed simultaneously
rcj-planner generate \
    --division "Line:input/Line.csv:arenas=3:runs=2" \
    --division "Line Entry:input/Line_Entry.csv:arenas=3:runs=1" \
    --division "Maze:input/Maze.csv:arenas=1:runs=4:arena_reset=50" \
    --division "Online_Simulation:input/Online_Simulation.csv:arenas=1:runs=4:arena_reset=30" \
    --run-time 10 --interview-time 15 --interview-group-size 2 \
    --day "Day1:10:30-18:00" \
    --day "Day2:09:00-13:00" \
    --interview-day "Day1:13:30-18:00" \
    --interview-rooms 2 \
    --break "Day1:12:30-13:30" \
    --buffer 10