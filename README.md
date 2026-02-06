# jarvis

A WhatsApp AI agent powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Voice messages, persistent memory, self-scheduling via cronjobs, and extensible skills — all through WhatsApp.

## How it works

Jarvis is a FastAPI webhook server that receives WhatsApp messages and routes them to Claude Code in headless mode. Claude reads the project's `.claude/CLAUDE.md` for personality, skills, and instructions — then responds via WhatsApp. It can schedule itself for later, remember things across conversations, and send/receive voice messages.

The key idea: **run `claude` in this repo and it will help you set everything up.** The CLAUDE.md contains setup instructions that Claude follows to walk you through configuration.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- A WhatsApp Business API account ([Meta Business Dashboard](https://business.facebook.com/))
- A server with a public URL (for the webhook)

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/zahlmann/jarvis.git
   cd jarvis
   ```

2. Copy the env template and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

3. Run `claude` in the repo — it will guide you through the rest:
   ```bash
   claude
   ```

4. Start the server:
   ```bash
   uv run python -m jarvis.main
   ```

5. Set up your WhatsApp webhook in the Meta dashboard pointing to `https://your-domain.com/webhook`

> **Important: Subscribe your WABA to receive inbound messages**
>
> Even after adding your webhook URL in the dashboard, incoming messages won't arrive until you explicitly subscribe your WhatsApp Business Account (WABA) to your app. This step is often missed because it's not obvious in the UI.
>
> Without this, outbound messages work fine, but inbound webhooks (replies) will be silent.
>
> ```bash
> curl -X POST "https://graph.facebook.com/v21.0/{YOUR_WABA_ID}/subscribed_apps" \
>   -H "Authorization: Bearer {YOUR_SYSTEM_USER_ACCESS_TOKEN}"
> ```
>
> Use your WABA ID (Business Account ID), not the Phone Number ID. You should get `{"success": true}`.

> **Exposing your server publicly**
>
> The webhook needs a public HTTPS URL. If you're running jarvis on a home server or a machine without a domain, you can use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) to expose it — no port forwarding or static IP needed:
> ```bash
> cloudflared tunnel --url http://localhost:8000
> ```
> Then use the generated URL as your webhook in the Meta dashboard.

### Optional: run as a systemd service

```bash
cp jarvis.service.example jarvis.service
# Edit jarvis.service with your paths and username
sudo cp jarvis.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis
```

## Features

- **Voice**: transcription (OpenAI) and text-to-speech (ElevenLabs) with emotion tags
- **Memory**: persistent semantic memory with embeddings, automatic cleanup
- **Scheduling**: self-modifying cronjobs — set reminders, recurring tasks, proactive check-ins
- **Skills**: extensible skill system (chat history, memory lookup, scheduling, skill creator)
- **Session resume**: conversations carry context across messages

## Customization

The personality and behavior are defined in `.claude/CLAUDE.md`. Edit it to change how jarvis talks, what it prioritizes, and how it responds. You can also add new skills in `.claude/skills/`.
