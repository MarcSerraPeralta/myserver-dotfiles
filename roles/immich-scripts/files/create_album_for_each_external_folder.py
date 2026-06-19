import sys
import os
from pathlib import Path
from datetime import datetime
import requests

IMMICH_URL = "http://100.100.50.50:2283/api"
API_KEY_FILE = "/opt/immich-scripts/immich-scripts.env"

DOCKER_EXTERNAL_ROOT = "/external"
HOST_EXTERNAL_ROOT = "/srv/immich/external_library"

DRY_RUN = False

CUSTOM_ALBUMS = {
    "nuria": "persones/nuria",
    "pau_martinez": "persones/pau_martinez",
    "phd": "phd",
    "family": "family",
    "bereal": "bereal",
}


# load API key
with open(API_KEY_FILE, "r") as file:
    API_KEY = file.read()[:-1]
HEADERS = {"x-api-key": API_KEY}


def get_immich_album_names() -> list[str]:
    assets = requests.get(f"{IMMICH_URL}/albums", headers=HEADERS).json()
    album_names = [asset["albumName"] for asset in assets]
    return album_names


def is_valid_album_name(album_name: str) -> bool:
    """Returns ``True`` only if the given album name has the following format:
    YYYY_MM_DD-{name} with name made of letters, numbers, "-", and/or "_".
    """
    if len(album_name) < 11:
        return False
    if any(album_name[i] != "_" for i in [4, 7]):
        return False
    if not album_name[:10].replace("_", "").isdigit():
        return False
    if album_name[10] != "-":
        return False
    filtered_name = album_name[10:]
    filtered_name = filtered_name.replace("-", "").replace("_", "")
    for n in range(10):
        filtered_name = filtered_name.replace(str(n), "")
    if not filtered_name.isalpha():
        return False
    return True


def get_external_album_names() -> list[str]:
    root = Path(HOST_EXTERNAL_ROOT)
    dirs = [d for d in os.listdir(root) if os.path.isdir(root / d)]
    dirs = [d for d in dirs if is_valid_album_name(d)]
    return dirs


def create_album(name: str) -> str:
    payload = {"albumName": name, "description": ""}
    r = requests.post(f"{IMMICH_URL}/albums", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()["id"]


def print_v(string: str):
    string = f"{datetime.now()} {string}"
    print(string, file=sys.stderr)
    return


if __name__ == "__main__":
    immich_albums = get_immich_album_names()
    external_albums = get_external_album_names() + list(CUSTOM_ALBUMS)
    missing_external_albums = set(external_albums).difference(immich_albums)

    for album in sorted(missing_external_albums):
        print_v(f"NEW ALBUM={album}")
        if not DRY_RUN:
            _ = create_album(album)

