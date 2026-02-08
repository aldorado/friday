"""FastAPI webhook server for messaging platforms (WhatsApp / Telegram)."""

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, HTTPException

from .platform import get_platform, get_client
from .claude_runner import ClaudeRunner
from .voice import VoiceHandler
from .message_store import MessageStore

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("jarvis")

# Platform
platform = get_platform()

# Global instances
client = None
claude: ClaudeRunner
voice: VoiceHandler
message_store: MessageStore

# In-memory set for deduplication (prevents race conditions with parallel webhooks)
_processing_messages: set[str] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global client, claude, voice, message_store

    # Initialize clients
    project_dir = Path(__file__).parent.parent
    client = get_client()
    claude = ClaudeRunner(project_dir)
    voice = VoiceHandler()
    message_store = MessageStore(project_dir / "data")

    logger.info(f"Jarvis initialized on {platform} and ready")
    yield

    # Cleanup
    await client.close()
    logger.info("Jarvis shutdown complete")


app = FastAPI(title="Jarvis", lifespan=lifespan)


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handle webhook verification (WhatsApp challenge-response / Telegram simple OK)."""
    if platform == "telegram":
        return Response(content="OK", media_type="text/plain")

    # WhatsApp verification
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if not all([mode, token, challenge]):
        raise HTTPException(status_code=400, detail="Missing parameters")

    result = client.verify_webhook(mode, token, challenge)
    if result:
        logger.info("Webhook verified successfully")
        return Response(content=result, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming messages."""
    # Get signature based on platform
    if platform == "telegram":
        signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    else:
        signature = request.headers.get("X-Hub-Signature-256", "")

    body = await request.body()

    if not client.verify_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse the webhook payload
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Extract message info
    message_info = client.parse_webhook_message(data)
    if not message_info:
        # Not a message event (could be status update, etc.)
        return {"status": "ok"}

    # Telegram: only allow the configured user
    allowed_user = os.environ.get("USER_PHONE_NUMBER")
    if platform == "telegram" and allowed_user and message_info["from"] != allowed_user:
        logger.warning(f"Ignoring message from unauthorized user: {message_info['from']}")
        return {"status": "ok"}

    logger.info(f"Received message from {message_info['name']} ({message_info['from']})")
    logger.info(f"Message info: type={message_info['type']}, text={message_info.get('text')}, image_id={message_info.get('image_id')}, audio_id={message_info.get('audio_id')}, reply_to={message_info.get('reply_to_message_id')}, reaction={message_info.get('reaction_emoji')}")

    # Process in background to respond quickly to webhook
    import asyncio
    asyncio.create_task(process_message(message_info))

    return {"status": "ok"}


async def process_message(message_info: dict):
    """Process an incoming message and send response."""
    user_id = message_info["from"]
    user_name = message_info["name"]
    incoming_message_id = message_info.get("message_id")

    # Deduplicate: use in-memory set to prevent race conditions
    # The old check (message_store.is_processed) had a race condition:
    # two parallel requests could both pass the check before either stored
    if incoming_message_id:
        if incoming_message_id in _processing_messages:
            logger.info(f"Skipping duplicate message (in-flight): {incoming_message_id}")
            return
        # Also check persistent store for messages from previous server runs
        if message_store.is_processed(incoming_message_id):
            logger.info(f"Skipping duplicate message (already processed): {incoming_message_id}")
            return
        # Mark as processing IMMEDIATELY to prevent race conditions
        _processing_messages.add(incoming_message_id)

    # Check if this is a reply to another message
    quoted_message = None
    if reply_to_id := message_info.get("reply_to_message_id"):
        stored = message_store.get(reply_to_id)
        if stored:
            quoted_message = stored["content"]
            logger.info(f"Reply to message: {quoted_message[:50]}...")

    image_path = None
    try:
        # Handle different message types: reaction, voice, text, image
        if message_info["type"] == "reaction" and message_info.get("reaction_emoji"):
            logger.info("Processing reaction message")
            # Get the message that was reacted to
            reacted_to_id = message_info.get("reaction_message_id")
            reacted_to_content = None
            if reacted_to_id:
                stored = message_store.get(reacted_to_id)
                if stored:
                    reacted_to_content = stored["content"]
                    logger.info(f"Reaction to message: {reacted_to_content[:50]}...")

            emoji = message_info["reaction_emoji"]
            if reacted_to_content:
                user_message = f"[reacted with {emoji} to: \"{reacted_to_content}\"]"
            else:
                user_message = f"[reacted with {emoji}]"
            is_voice = False
        elif message_info["type"] == "audio" and message_info["audio_id"]:
            logger.info("Processing voice message")
            # Download and transcribe audio
            audio_data, content_type = await client.download_media(message_info["audio_id"])
            user_message = await voice.transcribe(audio_data, content_type)
            is_voice = True
            logger.info(f"Transcribed: {user_message[:100]}...")
        elif message_info["type"] == "image" and message_info["image_id"]:
            logger.info("Processing image message")
            # Download image and save to temp file
            image_data, content_type = await client.download_media(message_info["image_id"])
            # Determine extension from content type
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(image_data)
                image_path = f.name
            logger.info(f"Saved image to {image_path}")
            # Use caption as message, or generic prompt if no caption
            user_message = message_info.get("image_caption") or "what do you see in this image?"
            is_voice = False
        elif message_info["text"]:
            user_message = message_info["text"]
            is_voice = False
        else:
            logger.warning(f"Unsupported message type: {message_info['type']}")
            await client.send_text(user_id, "sorry, i can only handle text, voice and image messages right now")
            return

        # Store incoming message for future reply context lookups
        if incoming_message_id:
            message_store.store(incoming_message_id, user_message, user_name or user_id)

        # Log incoming message to session immediately (so it's visible even if Claude hangs)
        claude.session_logger.log_incoming(user_id, user_name or "user", user_message, is_voice)

        # Run Claude
        logger.info(f"Running Claude for: {user_message[:50]}...")
        response = await claude.run(
            message=user_message,
            user_id=user_id,
            user_name=user_name,
            is_voice=is_voice,
            image_path=image_path,
            quoted_message=quoted_message,
        )

        # Track if we need to restart after sending response
        needs_restart = response.code_changes

        # Send response
        if response.send_voice and response.voice_text:
            logger.info("Generating voice response")
            # Generate TTS
            _, audio_path = await voice.text_to_speech(response.voice_text)

            try:
                send_result = await client.send_audio_file(user_id, audio_path)
                # Store outgoing voice message for reply context
                if msg_id := send_result.get("messages", [{}])[0].get("id"):
                    message_store.store(msg_id, f"[voice] {response.voice_text}", "jarvis")
                logger.info("Voice response sent")
            finally:
                # Cleanup temp file
                Path(audio_path).unlink(missing_ok=True)

            # Also send text if it's different from voice text
            if response.response_text and response.response_text != response.voice_text:
                send_result = await client.send_text(user_id, response.response_text)
                if msg_id := send_result.get("messages", [{}])[0].get("id"):
                    message_store.store(msg_id, response.response_text, "jarvis")
        else:
            # Send text response
            if response.response_text:
                send_result = await client.send_text(user_id, response.response_text)
                # Store outgoing message for reply context
                if msg_id := send_result.get("messages", [{}])[0].get("id"):
                    message_store.store(msg_id, response.response_text, "jarvis")
                logger.info("Text response sent")
            else:
                logger.info("No response text to send (intentional silence)")

        # Restart if code changes were made (after response is sent)
        if needs_restart:
            logger.info("Code changes detected, exiting for systemd restart")
            os._exit(0)

    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        # Log error response to session (incoming message was already logged)
        error_msg = f"{type(e).__name__}: {str(e)}"
        claude.session_logger.log_response(user_id, f"[ERROR]: {error_msg}")
        try:
            await client.send_text(user_id, "oops, something went wrong on my end. give me a sec and try again?")
        except Exception:
            logger.exception("Failed to send error message")
    finally:
        # Clean up temp image file if created
        if image_path:
            Path(image_path).unlink(missing_ok=True)
        # Remove from in-flight set (keep in message_store for reply context)
        if incoming_message_id:
            _processing_messages.discard(incoming_message_id)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "jarvis"}


def main():
    """Run the server."""
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    uvicorn.run(
        "jarvis.main:app",
        host=host,
        port=port,
        reload=os.environ.get("DEBUG", "").lower() == "true",
    )


if __name__ == "__main__":
    main()
