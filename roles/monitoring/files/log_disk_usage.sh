#!/bin/bash
LOGFILE="/opt/monitoring/data/disk_use.csv"

while true; do
  DISK_USAGE=$(df -k / | awk 'NR==2 {print $3 "," $4 "," $3 / ($3 + $4)}')
  DISK_USAGE_SRV=$(df -k /srv/ | awk 'NR==2 {print $3 "," $4 "," $3 / ($3 + $4)}')
  DISK_USAGE_SRV_MSATA=$(df -k /srv_msata/ | awk 'NR==2 {print $3 "," $4 "," $3 / ($3 + $4)}')
  
  printf "used,available,used_fraction,used_srv,available_srv,used_fraction_srv,used_srv_msata,available_srv_msata,used_fraction_srv_msata\n$DISK_USAGE,$DISK_USAGE_SRV,$DISK_USAGE_SRV_MSATA" > "$LOGFILE"
  
  sleep 10
done
