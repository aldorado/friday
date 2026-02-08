"""Platform factory — picks WhatsApp or Telegram client based on PLATFORM env var."""

import os


def get_platform() -> str:
    return os.environ.get("PLATFORM", "whatsapp").lower()


def get_client():
    if get_platform() == "telegram":
        from .telegram import TelegramClient
        return TelegramClient()
    from .whatsapp import WhatsAppClient
    return WhatsAppClient()
