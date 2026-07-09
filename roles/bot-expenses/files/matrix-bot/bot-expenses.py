import yaml
import os
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from nio import RoomEncryptedFile, AsyncClient, MegolmEvent, Event

from matrix_helpers import (
    get_authenticated_client,
    create_encrypted_room,
    set_room_avatar,
    send_message,
    download_attachment_callback,
    send_image,
    delete_room,
    poll_event_callback,
    send_poll,
    wait_for_room_in_cache,
    wait_for_message,
    MY_USER_ID,
    DATE_STR,
)
from expense_helpers import (
    process_expenses,
    add_missing_categories,
    plot_summary,
    relabel_bank_statement_files,
    LONG_ALPHABETIC,
)

_ = load_dotenv("/opt/bot-expenses/bot-expenses.env")

PLOTS_DIR: Path = Path(os.environ.get("PLOTS_DIR"))
SUMMARY_ROOM_ID: str = os.environ.get("SUMMARY_ROOM_ID")
CATEGORIES_FILE: str = os.environ.get("CATEGORIES_FILE")

with open(CATEGORIES_FILE, "r") as file:
    CATEGORIES: list[str] = list(yaml.safe_load(file))


async def get_bank_statements(client: AsyncClient) -> str:
    # get room name
    y, m = map(int, DATE_STR.split("-"))
    room_name = f"Expenses {LONG_ALPHABETIC[m]} {y}"

    room_id = await create_encrypted_room(client, room_name)
    await set_room_avatar(client, room_id)

    # sync local room cache with server
    await wait_for_room_in_cache(client, room_id, retries=10)
    await send_message(client, "Upload bank statements to continue", room_id)

    # set bot behaviour when it sees an attached file
    bot_state = {"downloads": 0}
    client.add_event_callback(
        lambda room, event: download_attachment_callback(
            client, room, event, room_id=room_id, bot_state=bot_state
        ),
        RoomEncryptedFile,
    )

    while bot_state["downloads"] < 2:
        _ = await client.sync(timeout=30_000, full_state=True)

    return room_id


async def request_missing_categories(
    client: AsyncClient, unclassified_elements: list[str], room_id: str
) -> list[str]:
    bot_context = {"active_poll_id": "", "user_selection": ""}
    poll_answered_signal = asyncio.Event()  # to track answers asyncronously

    # catch any Event (not just encrypted ones) because the poll response
    # may be a UnkownEvent which is not a MegolmEvent.
    client.add_event_callback(
        lambda room, event: poll_event_callback(
            room,
            event,
            bot_context,
            poll_answered_signal,
            room_id=room_id,
            user_id=MY_USER_ID,
        ),
        Event,
    )
    # enable decyption by setting a callback listening to MegolmEvent.
    client.add_event_callback(lambda r, e: None, MegolmEvent)

    answers: list[str] = []
    for element in unclassified_elements:
        poll_answered_signal.clear()

        poll_id = await send_poll(client, room_id, question=element, options=CATEGORIES)
        bot_context["active_poll_id"] = poll_id

        while not poll_answered_signal.is_set():
            _ = await client.sync(timeout=5000, full_state=False)
            await asyncio.sleep(0.5)

        selected_id = int(bot_context["user_selection"])
        answer = CATEGORIES[selected_id]
        answers.append(answer)

    return answers


async def send_summary(client: AsyncClient, date_str: str, room_id: str) -> None:
    await delete_room(client, room_id)

    image_path = PLOTS_DIR / f"{date_str}_summary.jpg"
    await send_image(client, image_path, SUMMARY_ROOM_ID)

    await client.close()
    return


async def acknowledge_warnings(
    client: AsyncClient, warnings: list[str], room_id: str
) -> None:
    for warning in warnings:
        await send_message(client, warning, room_id)
    await send_message(client, "Send any message to continue", room_id)

    await wait_for_message(client, room_id)

    return


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = loop.run_until_complete(get_authenticated_client())

    room_id = loop.run_until_complete(get_bank_statements(client))
    relabel_bank_statement_files(DATE_STR)

    unclassified_elements, warnings = process_expenses(DATE_STR)
    if warnings:
        loop.run_until_complete(acknowledge_warnings(client, warnings, room_id))

    answers = loop.run_until_complete(
        request_missing_categories(client, unclassified_elements, room_id)
    )
    add_missing_categories(DATE_STR, answers)

    plot_summary(DATE_STR)
    loop.run_until_complete(send_summary(client, DATE_STR, room_id))

    if DATE_STR.endswith("12"):
        YEAR_STR = DATE_STR.split("-")[0]
        plot_summary(YEAR_STR)
        loop.run_until_complete(send_summary(client, YEAR_STR, room_id))

    loop.run_until_complete(client.close())
