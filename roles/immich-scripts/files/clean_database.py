import sys
from pathlib import Path
from datetime import datetime
import requests

IMMICH_URL = "http://100.100.50.50:2283/api"
API_KEY_FILE = "/opt/immich-scripts/immich-scripts.env"

DOCKER_INTERNAL_ROOT = "/data"
HOST_INTERNAL_ROOT = "/srv/immich/internal_library"

DRY_RUN = False


# load API key
with open(API_KEY_FILE, "r") as file:
    API_KEY = file.read()[:-1]
HEADERS = {"x-api-key": API_KEY}


def translate_docker_path(docker_path: str) -> Path:
    """Translates docker path into a host machine path."""
    if docker_path.startswith(DOCKER_INTERNAL_ROOT):
        docker_root = Path(DOCKER_INTERNAL_ROOT)
        host_root = Path(HOST_INTERNAL_ROOT)

        path = Path(docker_path)
        relative = path.relative_to(docker_root)
    else:
        raise ValueError("File not in supported library.")

    return host_root / relative


def delete_asset(asset_id: str):
    payload = {"ids": [asset_id]}
    r = requests.delete(f"{IMMICH_URL}/assets", json=payload, headers=HEADERS)
    r.raise_for_status()
    return


def print_v(string: str):
    string = f"{datetime.now()} {string}"
    print(string, file=sys.stderr)
    return


if __name__ == "__main__":
    if not Path(HOST_INTERNAL_ROOT).exists():
        raise ValueError("Host internal root does not exist.")

    page_size = 1000
    page = 1
    while True:
        print_v(f"PAGE={page}")
        payload = {"page": page, "size": page_size}
        r = requests.post(
            f"{IMMICH_URL}/search/metadata", json=payload, headers=HEADERS
        )
        r.raise_for_status()

        data = r.json()["assets"]["items"]

        if not data:
            break

        for asset in data:
            docker_path: str = asset["originalPath"]
            if not str(docker_path).startswith(DOCKER_INTERNAL_ROOT):
                continue

            host_path = translate_docker_path(docker_path)
            if not host_path.exists():
                print_v(f"PATH={host_path}")
                if not DRY_RUN:
                    delete_asset(asset["id"])

        page += 1

