#!/usr/bin/env python3
"""Register webhook URL with Telegram Bot API."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import httpx


def main():
    parser = argparse.ArgumentParser(description="Set up Telegram webhook")
    parser.add_argument("url", help="Webhook URL (e.g. https://your-domain.com/webhook)")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

    payload = {"url": args.url}
    if secret:
        payload["secret_token"] = secret

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json=payload,
    )

    data = response.json()
    if data.get("ok"):
        print(f"Webhook set to {args.url}")
        if secret:
            print("(with secret token verification)")
    else:
        print(f"Failed: {data.get('description', data)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
