import os
from pathlib import Path
import json
import pathlib
import asyncio
from nio import AsyncClient, AsyncClientConfig
from dotenv import load_dotenv

_ = load_dotenv("/opt/bot-expenses/bot-expenses.env")

HOMESERVER: str = os.environ.get("HOMESERVER")
BOT_USER_ID: str = os.environ.get("BOT_USER_ID")
BOT_PASSWORD: str = os.environ.get("BOT_PASSWORD")
STORE_DIR = pathlib.Path(os.environ.get("STORE_DIR"))
CREDS_FILE: Path = STORE_DIR / os.environ.get("CREDENTIALS_NAME")

STORE_DIR.mkdir(exist_ok=True)


async def main():
    config = AsyncClientConfig(encryption_enabled=True)

    # handle first-time log in (no credentials stored)
    if not CREDS_FILE.exists():
        print("No saved credentials found. Logging in via password...")
        client = AsyncClient(HOMESERVER, BOT_USER_ID, config=config)
        response = await client.login(BOT_PASSWORD)

        creds = {"device_id": response.device_id, "access_token": response.access_token}
        with open(CREDS_FILE, "w") as f:
            json.dump(creds, f)

        print(f"Logged in successfully! Generated Device ID: {response.device_id}")
        print("Credentials saved. Please RERUN this script to initialize encryption.")
        await client.close()
        return

    # load the saved credentials
    with open(CREDS_FILE, "r") as f:
        creds: dict[str, str] = json.load(f)

    print(f"Initializing client with permanent Device ID: {creds['device_id']}")

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

    # explicitly push E2EE identity keys to Synapse
    if client.should_upload_keys:
        print("Detected unpushed local keys. Uploading identity keys to Synapse...")
        await client.keys_upload()
        print("Identity keys successfully published!")

    # downstream syncronization
    print("Performing downstream sync...")
    await client.sync(timeout=3000)
    print("Sync complete. Bot is fully alive and encrypted.")

    print("Keeping bot alive for 120 seconds. Check if it is online!")
    try:
        await asyncio.sleep(120)
    except asyncio.CancelledError:
        pass
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
