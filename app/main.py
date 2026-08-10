import os
import json
import time
import requests
import yt_dlp

from dotenv import load_dotenv
from logger import get_logger

load_dotenv()
logger = get_logger(__name__)
logger.debug("Logger initialized.")

class Orchestrator:
    def __init__(self):
        self.youtube_channel_url = os.getenv("YOUTUBE_CHANNEL_URL")
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    def load_state_json(self):
        default_state = {
            "last_shorts": []
        }

        try:
            with open("data/state.json", "r", encoding="utf-8") as file:
                state = json.load(file)

        except FileNotFoundError:
            logger.warning("State file not found. Creating a new state.")
            return default_state

        except json.JSONDecodeError:
            logger.warning("State file is invalid or empty. Creating a new state.")
            return default_state

        if not isinstance(state, dict):
            logger.warning("Invalid state structure. Creating a new state.")
            return default_state

        if not isinstance(state.get("last_shorts"), list):
            logger.warning("Missing or invalid 'last_shorts'. Resetting state.")
            return default_state

        return state

    def save_state_json(self, state):
        with open("data/state.json", "w", encoding="utf-8") as file:
            json.dump(
                state,
                file,
                indent=4,
                ensure_ascii=False,
            )
        logger.debug("State saved to state.json.")

    def get_shorts(self):
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "playlistend": 10,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            channel_info = ydl.extract_info(
                self.youtube_channel_url,
                download=False,
            )

        logger.info(f"{len(channel_info.get('entries'))} shorts retrieved.")
        return channel_info.get("entries", [])

    def compare_shorts(self, state, shorts):
        state_ids = set(state["last_shorts"])

        return [
            short
            for short in shorts
            if short["id"] not in state_ids
        ]

    def send_discord_notification(self, short):
        message = {"content": f"{short['url']}"}

        try:
            response = requests.post(
                self.discord_webhook_url,
                json=message,
                timeout=10,
            )

            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as error:
            logger.error(f"Failed to send notification for short {short['id']}: {error}")
            return False

    def run(self):
        logger.info("Starting application.")
        state = self.load_state_json()
        shorts = self.get_shorts()

        current_ids = [
            short["id"]
            for short in shorts
        ]

        if not state["last_shorts"]:
            state["last_shorts"] = current_ids
            self.save_state_json(state)

            logger.info("Initial state created.")
            return

        new_shorts = self.compare_shorts(
            state,
            shorts,
        )

        if not new_shorts:
            logger.info("No new shorts.")
            return

        state_ids = set(state["last_shorts"])

        for short in reversed(new_shorts):
            if self.send_discord_notification(short):
                state_ids.add(short["id"])
                logger.debug(f"Notification sent for short: {short['id']}")

        state["last_shorts"] = [
            short["id"]
            for short in shorts
            if short["id"] in state_ids
        ]

        self.save_state_json(state)


if __name__ == "__main__":
    orchestrator = Orchestrator()
    check_interval = int(os.getenv("CHECK_INTERVAL", 1800))

    while True:
        try:
            orchestrator.run()

        except Exception:
            logger.exception("Unexpected error during excution.")

        time.sleep(check_interval)