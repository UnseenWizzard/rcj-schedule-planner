#!/bin/sh

rcj-planner generate \
    --division "Line:input/Line.csv:arenas=3:runs=2" \
    --division "Line Entry:input/Line_Entry.csv:arenas=3:runs=1" \
    --division "Maze:input/Maze.csv:arenas=1:runs=4:arena_reset=0" \
    --division "Online_Simulation:input/Online_Simulation.csv:arenas=1:runs=4:arena_reset=30" \
    --run-time 10 --interview-time 15 --interview-group-size 2 \
    --day "Day1:10:30-18:00" \
    --day "Day2:09:00-13:00" \
    --break "Day1:12:30-13:30" \
    --buffer 10