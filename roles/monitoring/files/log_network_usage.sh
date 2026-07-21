#!/bin/bash
LOGFILE_I="/home/marc/monitoring/data/net_use.csv"
LOGFILE_H="/home/marc/monitoring/data/net_use_last-hour.csv"
LOGFILE_D="/home/marc/monitoring/data/net_use_last-day.csv"
MAX_LINES_H=800
MAX_LINES_D=3000

# add header if file doesn't exist
if [ ! -f "$LOGFILE_H" ]; then
  echo "timestamp,eno1_in,eno1_out,tailscale0_in,tailscale0_out" > "$LOGFILE_H"
fi
if [ ! -f "$LOGFILE_D" ]; then
  echo "timestamp,eno1_in,eno1_out,tailscale0_in,tailscale0_out" > "$LOGFILE_D"
fi

# prepare variable for running average for "last 24h"
declare -a sums=( )
INDEX=0

while true; do
  DATE=$(date -u '+%Y-%m-%d %H:%M:%S') # UTC format for Grafana

  # running the ifstat command takes 5 second, so no need for the 'sleep 5' instruction
  NET_USAGE=$(ifstat -i eno1 -i tailscale0 5 1 | tail -1 | awk '{print $1 ",-" $2 "," $3 ",-" $4}')
  INDEX=$((INDEX+1))

  # instantaneous
  printf "timestamp,eno1_in,eno1_out,tailscale0_in,tailscale0_out\n$DATE,$NET_USAGE" > "$LOGFILE_I"

  # last 1h
  echo "$DATE,$NET_USAGE" >> "$LOGFILE_H"
  # store only the last lines
  LINE_COUNT=$(wc -l < "$LOGFILE_H")
  if (( LINE_COUNT > MAX_LINES_H + 1 )); then
    DATA=$(tail -n "$MAX_LINES_H" "$LOGFILE_H")
    printf "timestamp,eno1_in,eno1_out,tailscale0_in,tailscale0_out\n${DATA}\n" > "${LOGFILE_H}"
  fi

  # last 24h
  # 1. convert CSV into array
  IFS=',' read -r -a values <<< "$NET_USAGE"

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
    NET_USAGE=""

    for ((j=0; j<${#sums[@]}; j++)); do
      avg=$(awk "BEGIN {printf \"%.1f\", ${sums[j]} / 6}")
      NET_USAGE+="${avg},"
      sums[j]=0
    done
    NET_USAGE="${NET_USAGE%,}" # remove trailing comma

    echo "$DATE,$NET_USAGE" >> "$LOGFILE_D"
    # store only the last lines
    LINE_COUNT=$(wc -l < "$LOGFILE_D")
    if (( LINE_COUNT > MAX_LINES_D + 1 )); then
      DATA=$(tail -n "$MAX_LINES_D" "$LOGFILE_D")
      printf "timestamp,eno1_in,eno1_out,tailscale0_in,tailscale0_out\n${DATA}\n" > "${LOGFILE_D}"
    fi

    INDEX=0
  fi

done
