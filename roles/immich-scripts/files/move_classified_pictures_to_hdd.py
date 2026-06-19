import sys
from pathlib import Path
import time
from datetime import datetime
import requests

IMMICH_URL = "http://100.100.50.50:2283/api"
API_KEY_FILE = "/opt/immich-scripts/immich-scripts.env"

DOCKER_INTERNAL_ROOT = "/data"
HOST_INTERNAL_ROOT = "/srv/immich/internal_library"

DOCKER_EXTERNAL_ROOT = "/external"
HOST_EXTERNAL_ROOT = "/srv/immich/external_library"

DRY_RUN = False

SKIP_ALBUMS = ["WhatsApp Video", "WhatsApp Images", "Camera", "BeReal"]

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


def translate_docker_path(docker_path: str) -> Path:
    """Translates docker path into a host machine path."""
    docker_root = Path(DOCKER_INTERNAL_ROOT)
    host_root = Path(HOST_INTERNAL_ROOT)

    path = Path(docker_path)
    relative = path.relative_to(docker_root)

    return host_root / relative


def get_albums() -> list[dict[str, str]]:
    assets = requests.get(f"{IMMICH_URL}/albums", headers=HEADERS).json()
    return assets


def get_album_assets(album_id: str) -> list[dict[str, str]]:
    """Returns the assets inside the given album."""
    return requests.get(f"{IMMICH_URL}/albums/{album_id}", headers=HEADERS).json()[
        "assets"
    ]


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


def move_internal_assert_to_external_album(asset_path: Path, album_name: str) -> str:
    """Moves asset from the internal library to the external one."""
    if not asset_path.exists():
        return f"File not found: {asset_path}"

    target_dir = Path(HOST_EXTERNAL_ROOT) / album_name
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / asset_path.name

    if target_path.exists():
        return f"Target path exists: {target_path}"

    # move file
    _ = asset_path.rename(target_path)
    return ""


def delete_asset(asset_id: str):
    payload = {"ids": [asset_id]}
    r = requests.delete(f"{IMMICH_URL}/assets", json=payload, headers=HEADERS)
    r.raise_for_status()
    return


def immich_external_library_rescan():
    library_id = get_external_library_id()
    r = requests.post(f"{IMMICH_URL}/libraries/{library_id}/scan", headers=HEADERS)
    r.raise_for_status()
    return


def get_external_library_id() -> str:
    r = requests.get(f"{IMMICH_URL}/libraries", headers=HEADERS)
    r.raise_for_status()

    id = None
    for library in r.json():
        paths = library["importPaths"]
        if paths == [DOCKER_EXTERNAL_ROOT]:
            id = library["id"]
    if id is None:
        raise ValueError("External library not found.")

    return id


def check_root_paths():
    if not Path(HOST_INTERNAL_ROOT).exists():
        raise ValueError(f"Host internal root not found: '{HOST_INTERNAL_ROOT}'.")
    if not Path(HOST_EXTERNAL_ROOT).exists():
        raise ValueError(f"Host external root not found: '{HOST_EXTERNAL_ROOT}'.")
    return


def check_immich_is_reachable():
    try:
        _ = requests.get(IMMICH_URL, timeout=3)
    except:
        raise ValueError(f"Immich not reachable: '{IMMICH_URL}'.")
    return


def print_v(string: str):
    string = f"{datetime.now()} {string}"
    print(string, file=sys.stderr)
    return


def wait_until_rescan_complete():
    while True:
        r = requests.get(f"{IMMICH_URL}/jobs", headers=HEADERS)
        r.raise_for_status()

        jobs = r.json()
        library: dict[str, int] = jobs.get("library", {}).get("jobCounts", {})

        active = library.get("active", 0)
        waiting = library.get("waiting", 0)

        if active == 0 and waiting == 0:
            return

        time.sleep(5)


if __name__ == "__main__":
    print_v("Checking root paths...")
    check_root_paths()
    print_v("Done")
    print_v("Checking if Immich is reachable...")
    check_immich_is_reachable()
    print_v("Done")

    print_v("Getting albums...")
    albums = get_albums()
    print_v("Done")

    print_v("Getting assets from albums...")
    asset_path_to_album: dict[Path, tuple[str, str | None]] = {}
    for album in albums:
        album_name = album["albumName"]
        if album_name in SKIP_ALBUMS:
            continue
        if (not is_valid_album_name(album_name)) and (album_name not in CUSTOM_ALBUMS):
            continue

        album_id = album["id"]
        assets = get_album_assets(album_id)

        for asset in assets:
            asset_path = translate_docker_path(asset["originalPath"])
            asset_id = asset["id"]
            if not str(asset_path).startswith(HOST_INTERNAL_ROOT):
                continue
            if asset_path in asset_path_to_album:
                print(f"Asset '{asset_path}' appears in multiple albums.")
                asset_path_to_album[asset_path] = (asset_id, None)
                continue

            if album_name in CUSTOM_ALBUMS:
                album_name = CUSTOM_ALBUMS[album_name]
            asset_path_to_album[asset_path] = (asset_id, album_name)
    print_v("Done")

    print_v("Moving assets to external library...")
    for asset_path, (asset_id, album_name) in asset_path_to_album.items():
        if album_name is None:
            continue

        print_v(f"ALBUM={album_name} INT_PATH={asset_path} ID={asset_id}")
        if not DRY_RUN:
            error = move_internal_assert_to_external_album(asset_path, album_name)
            if not error:
                delete_asset(asset_id)
            else:
                print_v(error)
    print_v("Done")

    if not DRY_RUN:
        print_v("Scanning Immich libraries...")
        immich_external_library_rescan()
        wait_until_rescan_complete()
        print_v("Done")

