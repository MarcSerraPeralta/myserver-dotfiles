import requests

IMMICH_URL = "http://100.100.50.50:2283/api"
API_KEY_FILE = "/opt/immich-scripts/immich-scripts.env"

SKIP_ALBUMS = ["WhatsApp Video", "WhatsApp Images", "Camera", "BeReal"]


# load API key
with open(API_KEY_FILE, "r") as file:
    API_KEY = file.read()[:-1]
HEADERS = {"x-api-key": API_KEY}


def get_album_ids() -> list[str]:
    r = requests.get(f"{IMMICH_URL}/albums", headers=HEADERS)
    r.raise_for_status()
    albums = r.json()
    album_ids = [a["id"] for a in albums if a["albumName"] not in SKIP_ALBUMS]
    return album_ids


def delete_album(album_id: str):
    r = requests.delete(f"{IMMICH_URL}/albums/{album_id}", headers=HEADERS)
    r.raise_for_status()
    return


def delete_albums(album_ids: list[str]):
    for album_id in album_ids:
        delete_album(album_id)
    return


if __name__ == "__main__":
    album_ids = get_album_ids()
    if album_ids:
        delete_albums(album_ids)

