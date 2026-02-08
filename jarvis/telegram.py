"""Telegram Bot API client for sending and receiving messages."""

import hmac
import httpx
import os
from typing import Optional


class TelegramClient:
    """Client for Telegram Bot API."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self):
        self.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
        self.api_url = f"{self.BASE_URL}/bot{self.bot_token}"
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self._client.aclose()

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return True
        return hmac.compare_digest(signature, self.webhook_secret)

    @staticmethod
    def parse_webhook_message(data: dict) -> Optional[dict]:
        """Parse incoming Telegram Update into normalized message_info dict."""
        # Handle message or edited_message
        message = data.get("message") or data.get("edited_message")

        # Handle message reactions
        if reaction_update := data.get("message_reaction"):
            chat_id = str(reaction_update.get("chat", {}).get("id", ""))
            user = reaction_update.get("user", {})
            user_name = user.get("first_name", "")
            reacted_msg_id = str(reaction_update.get("message_id", ""))
            new_reaction = reaction_update.get("new_reaction", [])
            emoji = new_reaction[0].get("emoji", "") if new_reaction else ""

            return {
                "from": chat_id,
                "name": user_name,
                "message_id": f"reaction_{reacted_msg_id}",
                "timestamp": str(reaction_update.get("date", "")),
                "type": "reaction",
                "text": None,
                "audio_id": None,
                "image_id": None,
                "image_caption": None,
                "reply_to_message_id": None,
                "reaction_emoji": emoji,
                "reaction_message_id": reacted_msg_id,
            }

        if not message:
            return None

        chat_id = str(message.get("chat", {}).get("id", ""))
        user = message.get("from", {})
        user_name = user.get("first_name", "")
        message_id = str(message.get("message_id", ""))
        timestamp = str(message.get("date", ""))

        # Reply context
        reply_to_message_id = None
        if reply_to := message.get("reply_to_message"):
            reply_to_message_id = str(reply_to.get("message_id", ""))

        # Determine message type and extract content
        if voice := message.get("voice"):
            return {
                "from": chat_id,
                "name": user_name,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": "audio",
                "text": None,
                "audio_id": voice["file_id"],
                "image_id": None,
                "image_caption": None,
                "reply_to_message_id": reply_to_message_id,
                "reaction_emoji": None,
                "reaction_message_id": None,
            }

        if audio := message.get("audio"):
            return {
                "from": chat_id,
                "name": user_name,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": "audio",
                "text": None,
                "audio_id": audio["file_id"],
                "image_id": None,
                "image_caption": None,
                "reply_to_message_id": reply_to_message_id,
                "reaction_emoji": None,
                "reaction_message_id": None,
            }

        if photo_list := message.get("photo"):
            # Use largest photo (last in array)
            photo = photo_list[-1]
            return {
                "from": chat_id,
                "name": user_name,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": "image",
                "text": None,
                "audio_id": None,
                "image_id": photo["file_id"],
                "image_caption": message.get("caption"),
                "reply_to_message_id": reply_to_message_id,
                "reaction_emoji": None,
                "reaction_message_id": None,
            }

        # Text message
        text = message.get("text")
        if text is not None:
            return {
                "from": chat_id,
                "name": user_name,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": "text",
                "text": text,
                "audio_id": None,
                "image_id": None,
                "image_caption": None,
                "reply_to_message_id": reply_to_message_id,
                "reaction_emoji": None,
                "reaction_message_id": None,
            }

        return None

    async def send_text(self, to: str, text: str) -> dict:
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": to,
            "text": text,
            "parse_mode": "Markdown",
        }

        response = await self._client.post(url, json=payload)
        if not response.is_success:
            print(f"Telegram send_text error: {response.status_code} - {response.text}")
        response.raise_for_status()

        data = response.json()
        msg_id = str(data.get("result", {}).get("message_id", ""))
        return {"messages": [{"id": msg_id}]}

    async def send_audio_file(self, to: str, file_path: str) -> dict:
        url = f"{self.api_url}/sendVoice"

        with open(file_path, "rb") as f:
            files = {"voice": (os.path.basename(file_path), f, "audio/mpeg")}
            data = {"chat_id": to}
            response = await self._client.post(url, data=data, files=files)

        if not response.is_success:
            print(f"Telegram send_audio_file error: {response.status_code} - {response.text}")
        response.raise_for_status()

        result = response.json()
        msg_id = str(result.get("result", {}).get("message_id", ""))
        return {"messages": [{"id": msg_id}]}

    async def download_media(self, file_id: str) -> tuple[bytes, str]:
        # Get file path from Telegram
        url = f"{self.api_url}/getFile"
        response = await self._client.get(url, params={"file_id": file_id})
        response.raise_for_status()

        file_path = response.json()["result"]["file_path"]
        content_type = _guess_content_type(file_path)

        # Download the file
        download_url = f"{self.BASE_URL}/file/bot{self.bot_token}/{file_path}"
        response = await self._client.get(download_url)
        response.raise_for_status()

        return response.content, content_type


def _guess_content_type(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return {
        "ogg": "audio/ogg",
        "oga": "audio/ogg",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")
