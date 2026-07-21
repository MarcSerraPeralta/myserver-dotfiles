#!/bin/bash
LOGFILE_I="/home/marc/monitoring/data/ram_use.csv"
LOGFILE_H="/home/marc/monitoring/data/ram_use_last-hour.csv"
LOGFILE_D="/home/marc/monitoring/data/ram_use_last-day.csv"
MAX_LINES_H=800
MAX_LINES_D=3000

# add header if file doesn't exist
if [ ! -f "$LOGFILE_H" ]; then
  echo "timestamp,total,used,available" > "$LOGFILE_H"
fi
if [ ! -f "$LOGFILE_D" ]; then
  echo "timestamp,total,used,available" > "$LOGFILE_D"
fi

# prepare variable for running average for "last 24h"
declare -a sums=( )
INDEX=0

while true; do
  DATE=$(date -u '+%Y-%m-%d %H:%M:%S') # UTC format for Grafana

  RAM_USAGE=$(free -k | awk 'NR==2 {print $2 "," $3 "," $7}')
  INDEX=$((INDEX+1))

  # instantaneous data
  printf "timestamp,total,used,available\n${DATE},${RAM_USAGE}" > "${LOGFILE_I}"

  # "last 1h" data
  echo "$DATE,$RAM_USAGE" >> "$LOGFILE_H"
  # store only the last lines
  LINE_COUNT=$(wc -l < "$LOGFILE_H")
  if (( LINE_COUNT > MAX_LINES_H + 1 )); then
    DATA=$(tail -n "$MAX_LINES_H" "$LOGFILE_H")
    printf "timestamp,total,used,available\n${DATA}\n" > "${LOGFILE_H}"
  fi

  
  # "last 24h" data
  # 1. convert CSV into array
  IFS=',' read -r -a values <<< "$RAM_USAGE"

  # 2. initialize sums array on first iteration
    if (( INDEX == 1 )); then
        for ((j=0; j<${#values[@]}; j++)); do
            sums[j]=0
        done
    fi

  # 3. accumulate sums
  for ((j=0; j<${#values[@]}; j++)); do
    sums[j]=$(awk "BEGIN {print ${sums[j]} + ${values[j]}}")
  done

  # 4. compute average very 30 seconds (6 iterations)
  if (( INDEX == 6 )); then
    RAM_USAGE=""

    for ((j=0; j<${#sums[@]}; j++)); do
      avg=$(awk "BEGIN {print int(${sums[j]} / 6)}")
      RAM_USAGE+="${avg},"
      sums[j]=0
    done
    RAM_USAGE="${RAM_USAGE%,}" # remove trailing comma

    echo "$DATE,$RAM_USAGE" >> "$LOGFILE_D"
    # store only the last lines
    LINE_COUNT=$(wc -l < "$LOGFILE_D")
    if (( LINE_COUNT > MAX_LINES_D + 1 )); then
      DATA=$(tail -n "$MAX_LINES_D" "$LOGFILE_D")
      printf "timestamp,total,used,available\n${DATA}\n" > "${LOGFILE_D}"
    fi

    INDEX=0
  fi

  sleep 5

done
