#!/bin/bash
LOGFILE_I="/opt/monitoring/data/cpu_use.csv"
LOGFILE_H="/opt/monitoring/data/cpu_use_last-hour.csv"
LOGFILE_D="/opt/monitoring/data/cpu_use_last-day.csv"
MAX_LINES_H=800
MAX_LINES_D=3000

# add header if file doesn't exist
if [ ! -f "$LOGFILE_H" ]; then
  echo "timestamp,used" > "$LOGFILE_H"
fi
if [ ! -f "$LOGFILE_D" ]; then
  echo "timestamp,used" > "$LOGFILE_D"
fi

# prepare variables for running average for "last 24h"
INDEX=0
AVE_CPU_USE="0"

while true; do
  DATE=$(date -u '+%Y-%m-%d %H:%M:%S') # UTC format for Grafana

  # mpstat <interval> <count>, so no need for the 'sleep X' instruction
  CPU_USE=$(mpstat 5 1 | awk '/Average/ {print (100-$NF)/100}')
  INDEX=$((INDEX+1))

  # instantaneous
  printf "timestamp,used\n${DATE},${CPU_USE}" > "${LOGFILE_I}"

  # last 1h
  echo "$DATE,$CPU_USE" >> "$LOGFILE_H"
  # store only the last lines
  LINE_COUNT=$(wc -l < "$LOGFILE_H")
  if (( LINE_COUNT > MAX_LINES_H + 1 )); then
    DATA=$(tail -n "$MAX_LINES_H" "$LOGFILE_H")
    printf "timestamp,used\n${DATA}\n" > "${LOGFILE_H}"
  fi

  # last 24h
  AVE_CPU_USE=$(awk "BEGIN {printf $CPU_USE/6 + $AVE_CPU_USE}")
  if (( INDEX == 6 )); then
    AVE_CPU_USE=$(awk "BEGIN {printf \"%.3f\", $AVE_CPU_USE}")
    echo "$DATE,$AVE_CPU_USE" >> "$LOGFILE_D"
    # store only the last lines
    LINE_COUNT=$(wc -l < "$LOGFILE_D")
    if (( LINE_COUNT > MAX_LINES_D + 1 )); then
      DATA=$(tail -n "$MAX_LINES_D" "$LOGFILE_D")
      printf "timestamp,used\n${DATA}\n" > "${LOGFILE_D}"
    fi

    INDEX=0
    AVE_CPU_USE="0"
  fi

done
