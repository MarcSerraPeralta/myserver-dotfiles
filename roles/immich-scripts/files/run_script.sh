#!/bin/bash

python3 /opt/immich-scripts/move_classified_pictures_to_hdd.py
python3 /opt/immich-scripts/delete_all_albums.py
python3 /opt/immich-scripts/create_album_for_each_external_folder.py
python3 /opt/immich-scripts/clean_database.py

