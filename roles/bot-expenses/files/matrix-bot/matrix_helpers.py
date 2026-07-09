from datetime import datetime, timedelta
import os
from pathlib import Path
from dotenv import load_dotenv
import json
import aiofiles
import asyncio
from nio import (
    AsyncClient,
    AsyncClientConfig,
    RoomCreateResponse,
    RoomPreset,
    EnableEncryptionBuilder,
    UploadError,
    RoomPutStateError,
    RoomKickError,
    RoomLeaveError,
    RoomSendError,
    Event,
    MatrixRoom,
    DownloadError,
)
from nio.crypto.attachments import decrypt_attachment

_ = load_dotenv("/opt/bot-expenses/bot-expenses.env")

STORE_DIR: Path = Path(os.environ.get("STORE_DIR"))
CREDS_FILE: Path = STORE_DIR / os.environ.get("CREDENTIALS_NAME")
DATA_DIR: Path = Path(os.environ.get("DATA_DIR"))

HOMESERVER: str = os.environ.get("HOMESERVER")
BOT_USER_ID: str = os.environ.get("BOT_USER_ID")
MY_USER_ID: str = os.environ.get("MY_USER_ID")
ROOM_IMAGE_FILE: str = os.environ.get("ROOM_IMAGE_FILE")

DATE = datetime.now() - timedelta(days=5)
DATE_STR = DATE.strftime("%Y-%m")
DATA_DIR.mkdir(exist_ok=True, parents=True)


async def get_authenticated_client() -> AsyncClient:
    with open(CREDS_FILE, "r") as f:
        creds: dict[str, str] = json.load(f)

    config = AsyncClientConfig(encryption_enabled=True)
    client = AsyncClient(
        HOMESERVER,
        BOT_USER_ID,
        device_id=creds["device_id"],
        store_path=str(STORE_DIR),
        config=config,
    )
    client.restore_login(
        user_id=BOT_USER_ID,
        device_id=creds["device_id"],
        access_token=creds["access_token"],
    )

    # syncronize bot to server
    _ = await client.sync(timeout=3000, full_state=True)
    return client


async def create_encrypted_room(client: AsyncClient, room_name: str) -> str:
    # define room configuration:
    # - power level: bot and my user are admins, but bot can kick me out.
    # - encryption enabled.
    initial_state = [
        {
            "type": "m.room.power_levels",
            "content": {"users": {BOT_USER_ID: 100, MY_USER_ID: 99}},
        },
        {
            "type": "m.room.encryption",
            "content": EnableEncryptionBuilder().as_dict()["content"],
        },
    ]

    response = await client.room_create(
        name=room_name,
        invite=[MY_USER_ID],
        is_direct=True,
        preset=RoomPreset.private_chat,
        initial_state=initial_state,
    )

    if not isinstance(response, RoomCreateResponse):
        raise ValueError(f"Failed to create room: {response.message}")

    return response.room_id


async def set_room_avatar(client: AsyncClient, room_id: str) -> None:
    image_file = Path(ROOM_IMAGE_FILE)
    if not image_file.exists():
        raise ValueError(f"Image file not found: {image_file}.")

    # upload image to synapse
    async with aiofiles.open(image_file, "r+b") as file:
        upload_response, _ = await client.upload(
            file,
            content_type="image/jpeg",
            filename=image_file.name,
            filesize=image_file.stat().st_size,
        )

    if isinstance(upload_response, UploadError):
        raise ValueError("Upload failed with error: {upload_response.message}.")

    # assign uploaded image as room profile avatar
    mxc_uri = upload_response.content_uri
    avatar_content = {"url": mxc_uri, "info": {"mimetype": "image/jpeg"}}

    state_response = await client.room_put_state(
        room_id=room_id,
        event_type="m.room.avatar",
        content=avatar_content,
    )

    if isinstance(state_response, RoomPutStateError):
        raise ValueError(f"Failed to set room avatar: {state_response.message}")

    return


async def delete_room(client: AsyncClient, room_id: str) -> None:
    # kick myself from room
    kick_response = await client.room_kick(
        room_id=room_id,
        user_id=MY_USER_ID,
    )

    if isinstance(kick_response, RoomKickError):
        raise ValueError(f"Could not kick user: {kick_response.message}")

    # bot leaves room, dropping the room membership to 0
    leave_response = await client.room_leave(room_id=room_id)

    if isinstance(leave_response, RoomLeaveError):
        raise ValueError(f"Failed to leave room: {leave_response.message}")
    return


async def send_message(client: AsyncClient, message: str, room_id: str) -> None:
    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content={"msgtype": "m.text", "body": message},
        ignore_unverified_devices=True,  # bot is not a verified device
    )

    if isinstance(response, RoomSendError):
        raise ValueError(f"Failed to send message: {response.message}.")
    return


async def download_attachment_callback(
    client: AsyncClient,
    room: MatrixRoom,
    event: Event,
    room_id: str,
    bot_state: dict[str, int],
) -> None:
    # listen only to the specified room
    if room.room_id != room_id:
        return

    # extract file dictionary payload from the source JSON content block
    file_info = event.source.get("content", {}).get("file")
    if not file_info:
        raise ValueError("This event does not contain valid encrypted file metadata.")
    mxc_url: str = file_info.get("url")

    media_response = await client.download(mxc_url)
    if isinstance(media_response, DownloadError):
        raise ValueError(f"Failed to download file: {media_response.message}.")

    decrypted_bytes = decrypt_attachment(
        media_response.body,
        file_info["key"]["k"],
        file_info["hashes"]["sha256"],
        file_info["iv"],
    )

    output_path = DATA_DIR / f"{DATE_STR}-{bot_state['downloads']}.txt"
    with open(output_path, "wb") as f:
        _ = f.write(decrypted_bytes)
    bot_state["downloads"] += 1

    return


async def send_image(client: AsyncClient, image_path: str | Path, room_id: str) -> None:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Target image file not found at: {path}")
    file_size = path.stat().st_size

    # upload image to Synapse
    async with aiofiles.open(path, "r+b") as file:
        upload_response, decryption_info = await client.upload(
            data_provider=file,
            content_type="image/jpeg",
            filename=path.name,
            filesize=file_size,
            encrypt=True,
        )

    if isinstance(upload_response, UploadError):
        raise ValueError(
            f"Server rejected media payload upload: {upload_response.message}"
        )

    # send image
    image_content = {
        "msgtype": "m.image",
        "body": path.name,
        "info": {
            "mimetype": "image/jpeg",
            "size": file_size,
        },
        "file": {
            "url": upload_response.content_uri,
            "key": decryption_info["key"],
            "iv": decryption_info["iv"],
            "hashes": decryption_info["hashes"],
            "v": decryption_info["v"],
        },
    }
    response = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=image_content,
        ignore_unverified_devices=True,
    )

    if isinstance(response, RoomSendError):
        raise ValueError(
            f"Failed to post image metadata to the timeline: {response.message}"
        )
    return


async def send_poll(
    client: AsyncClient,
    room_id: str,
    question: str,
    options: list[str],
) -> str:
    poll_content = {
        "msgtype": "org.matrix.msc3381.poll.start",
        "body": question,
        "org.matrix.msc3381.poll.start": {
            "question": {
                "org.matrix.msc1767.text": question,
                "body": question,
            },
            "kind": "org.matrix.msc3381.poll.disclosed",
            "max_selections": 1,
            "answers": [
                {
                    "id": str(k),
                    "org.matrix.msc1767.text": option,
                    "body": option,
                }
                for k, option in enumerate(options)
            ],
        },
    }

    response = await client.room_send(
        room_id=room_id,
        message_type="org.matrix.msc3381.poll.start",
        content=poll_content,
        ignore_unverified_devices=True,
    )
    if isinstance(response, RoomSendError):
        raise ValueError(f"Failed to send poll: {response.message}.")
    return response.event_id


async def end_poll(client: AsyncClient, room_id: str, poll_event_id: str) -> None:
    end_content = {
        "m.relates_to": {"rel_type": "m.reference", "event_id": poll_event_id},
        "org.matrix.msc3381.poll.end": {},
        "body": "The poll is now closed.",
        "msgtype": "m.notice",
    }

    response = await client.room_send(
        room_id=room_id,
        message_type="org.matrix.msc3381.poll.end",
        content=end_content,
        ignore_unverified_devices=True,
    )
    if isinstance(response, RoomSendError):
        raise ValueError(f"Failed to end poll: {response.message}.")
    return


async def poll_event_callback(
    room: MatrixRoom,
    event: Event,
    bot_context: dict[str, str],
    poll_answered_signal: asyncio.Event,
    room_id: str,
    user_id: str,
) -> None:
    if room.room_id != room_id or event.sender != user_id:
        return

    # check if the incoming event is a response to currently active poll
    event_content = event.source.get("content", {})
    relation = event_content.get("m.relates_to", {})
    if relation.get("rel_type") != "m.reference":
        return
    if relation.get("event_id") != bot_context["active_poll_id"]:
        return
    poll_resp = event_content.get("org.matrix.msc3381.poll.response")
    if not poll_resp:
        return
    selections = poll_resp.get("answers", [])
    if not selections:
        return

    bot_context["user_selection"] = selections[0]
    poll_answered_signal.set()
    return


async def wait_for_message(client: AsyncClient, room_id: str) -> None:
    message_received_signal = asyncio.Event()

    def handle_incoming_message(room, event: Event) -> None:
        if room.room_id != room_id:
            return
        if event.sender == client.user_id:
            return
        # target cleartext room timeline messages specifically.
        if event.source.get("type") == "m.room.message":
            message_received_signal.set()

    # Register the cleartext Event listener
    client.add_event_callback(handle_incoming_message, Event)

    while not message_received_signal.is_set():
        _ = await client.sync(timeout=5000, full_state=False)
        await asyncio.sleep(0.5)

    return


async def wait_for_room_in_cache(
    client: AsyncClient, room_id: str, retries: int = 5
) -> None:
    for attempt in range(retries):
        if room_id in client.rooms:
            return
        _ = await client.sync(timeout=3000, full_state=True)
        await asyncio.sleep(1)
    raise TimeoutError(
        f"Room {room_id} failed to materialize in client after {retries} syncs."
    )
