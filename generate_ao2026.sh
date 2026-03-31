#!/bin/sh

rcj-planner generate \
    --division "Line:input/Line.csv:arenas=3:runs=1" \
    --division "Line Entry:input/Line_Entry.csv:arenas=3:runs=1" \
    --division "Maze:input/Maze.csv:arenas=1:runs=3" \
    --run-time 10 --interview-time 15 --interview-group-size 2 \
    --day "Day1:11:00-18:00" \
    --day "Day2:09:00-14:00" \
    --break "Day1:12:30-13:30" \
    --break "Day1:Maze:14:00-14:40" \
    --break "Day1:Maze:11:00-11:40" \