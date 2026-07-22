#!/bin/bash
LOGFILE_I="/opt/monitoring/data/cpu_temp.csv"
LOGFILE_H="/opt/monitoring/data/cpu_temp_last-hour.csv"
LOGFILE_D="/opt/monitoring/data/cpu_temp_last-day.csv"
MAX_LINES_H=800
MAX_LINES_D=3000

# add header if file doesn't exist
if [ ! -f "$LOGFILE_H" ]; then
  echo "timestamp,temperature_zone0,temperature_zone1,temperature_zone2" > "$LOGFILE_H"
fi
if [ ! -f "$LOGFILE_D" ]; then
  echo "timestamp,temperature_zone0,temperature_zone1,temperature_zone2" > "$LOGFILE_D"
fi

# prepare variables for running average for "last 24h"
INDEX=0
AVE_TEMP_Z0="0"
AVE_TEMP_Z1="0"
AVE_TEMP_Z2="0"

while true; do
  DATE=$(date -u '+%Y-%m-%d %H:%M:%S') # UTC format for Grafana
  TEMP_Z0=$(cat /sys/class/thermal/thermal_zone0/temp)
  TEMP_Z0=$(awk "BEGIN {printf \"%.1f\", $TEMP_Z0/1000}")
  TEMP_Z1=$(cat /sys/class/thermal/thermal_zone1/temp)
  TEMP_Z1=$(awk "BEGIN {printf \"%.1f\", $TEMP_Z1/1000}")
  TEMP_Z2=$(cat /sys/class/thermal/thermal_zone2/temp)
  TEMP_Z2=$(awk "BEGIN {printf \"%.1f\", $TEMP_Z2/1000}")
  INDEX=$((INDEX + 1))
  
  # instantaneous
  printf "timestamp,temperature_zone0,temperature_zone1,temperature_zone2\n$DATE,$TEMP_Z0,$TEMP_Z1,$TEMP_Z2" > "$LOGFILE_I"

  # last 1h
  echo "$DATE,$TEMP_Z0,$TEMP_Z1,$TEMP_Z2" >> "$LOGFILE_H"
  # store only the last lines
  LINE_COUNT=$(wc -l < "$LOGFILE_H")
  if (( LINE_COUNT > MAX_LINES_H + 1 )); then
    DATA=$(tail -n "$MAX_LINES_H" "$LOGFILE_H")
    printf "timestamp,temperature_zone0,temperature_zone1,temperature_zone2\n${DATA}\n" > "${LOGFILE_H}"
  fi

  # last 24h
  AVE_TEMP_Z0=$(awk "BEGIN {printf $TEMP_Z0/6 + $AVE_TEMP_Z0}")
  AVE_TEMP_Z1=$(awk "BEGIN {printf $TEMP_Z1/6 + $AVE_TEMP_Z1}")
  AVE_TEMP_Z2=$(awk "BEGIN {printf $TEMP_Z2/6 + $AVE_TEMP_Z2}")
  if (( INDEX == 6)); then
    AVE_TEMP_Z0=$(awk "BEGIN {printf \"%.1f\", $AVE_TEMP_Z0}")
    AVE_TEMP_Z1=$(awk "BEGIN {printf \"%.1f\", $AVE_TEMP_Z1}")
    AVE_TEMP_Z2=$(awk "BEGIN {printf \"%.1f\", $AVE_TEMP_Z2}")
    echo "$DATE,$AVE_TEMP_Z0,$AVE_TEMP_Z1,$AVE_TEMP_Z2" >> "$LOGFILE_D"
    # store only the last lines
    LINE_COUNT=$(wc -l < "$LOGFILE_D")
    if (( LINE_COUNT > MAX_LINES_D + 1 )); then
      DATA=$(tail -n "$MAX_LINES_D" "$LOGFILE_D")
      printf "timestamp,temperature_zone0,temperature_zone1,temperature_zone2\n${DATA}\n" > "${LOGFILE_D}"
    fi

    INDEX=0
    AVE_TEMP_Z0="0"
    AVE_TEMP_Z1="0"
    AVE_TEMP_Z2="0"
  fi

  sleep 5
done
