#!/bin/bash

ARCHIVE_DIR="/srv_msata/mail-archive/gmail"

echo "Starting mail archive cleanup: $(date)"

# Find files larger than 5MB (5120 KB) and delete them
# Target the 'cur' and 'new' directories inside Maildir
find "$ARCHIVE_DIR" -type f -size +5M -name "*" -exec echo "Deleting large email: {}" \; -exec rm {} \;

echo "Cleanup finished: $(date)"
