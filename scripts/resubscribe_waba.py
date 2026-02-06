#!/usr/bin/env python3
"""Re-subscribes WABA to the app and notifies on failure."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


async def resubscribe() -> tuple[bool, str]:
    """Attempt WABA resubscription. Returns (success, message)."""
    waba_id = os.environ.get("WHATSAPP_WABA_ID")
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN")

    if not waba_id or not token:
        return False, "WHATSAPP_WABA_ID and WHATSAPP_ACCESS_TOKEN must be set"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://graph.facebook.com/v21.0/{waba_id}/subscribed_apps",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()

        if data.get("success"):
            return True, "WABA resubscribed successfully"
        else:
            error = data.get("error", {}).get("message", str(data))
            return False, f"WABA resubscription failed: {error}"


async def notify_failure(message: str):
    """Send WhatsApp notification about the failure."""
    user_phone = os.environ.get("USER_PHONE_NUMBER")
    if not user_phone:
        return

    try:
        from jarvis.whatsapp import WhatsAppClient
        client = WhatsAppClient()
        await client.send_text(user_phone, f"hey, heads up - {message}")
        await client.close()
    except Exception as e:
        print(f"Failed to send notification: {e}", file=sys.stderr)


async def main():
    success, message = await resubscribe()
    print(message)

    if not success:
        await notify_failure(message)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
