#!/bin/bash
LOGFILE="/opt/monitoring/data/srv_disk_use.csv"
BASE_DIR="/srv"

TMPFILE="$(mktemp)"

echo "used,available,path,depth" > "$LOGFILE"
  
# suppress permission errors, sort by size
du --max-depth=3 "$BASE_DIR" 2>/dev/null | sort -rn > "$TMPFILE"

AVAIL_SPACE=$(df -k /srv/ | awk 'NR==2 {print $4}')

while read -r size path; do
    # remove base directory from path for depth calculation
    relative_path="${path#$BASE_DIR}"

    if [[ -z "$relative_path" ]]; then
        depth=0
        full_path="$BASE_DIR"
    else
        # remove leading slash
        relative_path="${relative_path#/}"

        # count slashes to determine depth
        depth=$(( $(grep -o "/" <<< "$relative_path" | wc -l) + 1 ))
        full_path="$BASE_DIR/$relative_path"
    fi

    echo "$size,$AVAIL_SPACE,\"$full_path\",$depth" >> "$LOGFILE"

done < "$TMPFILE"

rm "$TMPFILE"
