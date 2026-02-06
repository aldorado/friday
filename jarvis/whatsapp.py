"""WhatsApp API client for sending and receiving messages."""

import hashlib
import hmac
import httpx
import os
from typing import Optional


class WhatsAppClient:
    """Client for WhatsApp Business API."""

    BASE_URL = "https://graph.facebook.com/v21.0"

    def __init__(self):
        self.access_token = os.environ["WHATSAPP_ACCESS_TOKEN"]
        self.phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        self.verify_token = os.environ["WHATSAPP_VERIFY_TOKEN"]
        self.app_secret = os.environ.get("WHATSAPP_APP_SECRET")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """Verify webhook subscription request from Meta."""
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return None

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify payload signature from Meta."""
        if not self.app_secret:
            return True  # Skip verification if secret not configured

        if not signature.startswith("sha256="):
            return False

        expected_sig = hmac.new(
            self.app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected_sig}", signature)

    async def send_text(self, to: str, text: str) -> dict:
        """Send a text message."""
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        response = await self._client.post(url, headers=headers, json=payload)
        if not response.is_success:
            print(f"WhatsApp send_text error: {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()

    async def send_audio(self, to: str, audio_url: str) -> dict:
        """Send an audio message via URL."""
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"link": audio_url},
        }

        response = await self._client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    async def upload_media(self, file_path: str, mime_type: str) -> str:
        """Upload media file and return media ID."""
        url = f"{self.BASE_URL}/{self.phone_number_id}/media"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, mime_type),
                "messaging_product": (None, "whatsapp"),
                "type": (None, mime_type),
            }
            response = await self._client.post(url, headers=headers, files=files)

        response.raise_for_status()
        return response.json()["id"]

    async def send_audio_by_id(self, to: str, media_id: str) -> dict:
        """Send an audio message using uploaded media ID."""
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"id": media_id},
        }

        response = await self._client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Download media file by ID. Returns (content, content_type)."""
        # First get the media URL
        url = f"{self.BASE_URL}/{media_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        media_url = response.json()["url"]

        # Then download the actual file
        response = await self._client.get(media_url, headers=headers)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "audio/ogg")
        return response.content, content_type

    @staticmethod
    def parse_webhook_message(data: dict) -> Optional[dict]:
        """Parse incoming webhook data and extract message info."""
        try:
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            message = messages[0]
            contact = value.get("contacts", [{}])[0]

            # Extract reply context if this is a reply to another message
            context = message.get("context", {})
            reply_to_message_id = context.get("id")  # ID of the message being replied to

            # Extract reaction info if this is a reaction
            reaction = message.get("reaction", {})
            reaction_emoji = reaction.get("emoji")
            reaction_message_id = reaction.get("message_id")  # ID of the message being reacted to

            return {
                "from": message.get("from"),
                "name": contact.get("profile", {}).get("name"),
                "message_id": message.get("id"),
                "timestamp": message.get("timestamp"),
                "type": message.get("type"),
                "text": message.get("text", {}).get("body"),
                "audio_id": message.get("audio", {}).get("id"),
                "image_id": message.get("image", {}).get("id"),
                "image_caption": message.get("image", {}).get("caption"),
                "reply_to_message_id": reply_to_message_id,
                "reaction_emoji": reaction_emoji,
                "reaction_message_id": reaction_message_id,
            }
        except (KeyError, IndexError):
            return None
