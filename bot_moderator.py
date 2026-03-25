"""
Telegram Bot — Message Moderator
Deploy on Render as a Background Worker.

Build command : pip install "python-telegram-bot[job-queue]==21.9"
Start command : python bot_moderator.py

Set TELEGRAM_BOT_TOKEN as an environment variable in Render dashboard.
"""

import os
import re
import asyncio
import logging
from telegram import Update, Message
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]   # set in Render dashboard

# Notify the group when a message is removed (notice auto-deletes after 10s)
NOTIFY_ON_DELETE: bool = True

# ─────────────────────────────────────────────
# HARDCODED BLACKLIST
# ─────────────────────────────────────────────
BLACKLIST: list[str] = [
    "spam",
    "scam",
    "casino",
    "betting",
    "forex signal",
    "crypto pump",
    "join now",
    "guaranteed profit",
    "investment opportunity",
    "click the link",
    "follow me",
    "check my channel",
    "send me a dm",
    "18+",
    "onlyfans",
]

# ─────────────────────────────────────────────
# PROMOTION PATTERNS  (regex)
# ─────────────────────────────────────────────
PROMO_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(buy now|limited offer|discount|promo code|use code|click here|subscribe now)\b", re.IGNORECASE),
    re.compile(r"\b(free gift|earn money|make money|passive income|work from home)\b", re.IGNORECASE),
    re.compile(r"\b(DM me|message me|check (my )?bio|link in bio)\b", re.IGNORECASE),
    re.compile(r"(https?://|t\.me/|bit\.ly/|tinyurl\.com/)", re.IGNORECASE),
    re.compile(r"(\d+%\s*off|\$\d+\s*off|₹\d+\s*off)", re.IGNORECASE),
]

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DETECTION HELPERS
# ─────────────────────────────────────────────
def contains_blacklisted_word(text: str) -> str | None:
    for word in BLACKLIST:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            return word
    return None


def contains_promotion(text: str) -> str | None:
    for pattern in PROMO_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


# ─────────────────────────────────────────────
# MESSAGE HANDLER
# ─────────────────────────────────────────────
async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message: Message = update.effective_message
    if not message or not message.text:
        return

    text  = message.text
    chat  = message.chat
    user  = message.from_user

    matched_word  = contains_blacklisted_word(text)
    matched_promo = None if matched_word else contains_promotion(text)

    reason = None
    if matched_word:
        reason = f"blacklisted word: «{matched_word}»"
    elif matched_promo:
        reason = f"promotional content: «{matched_promo}»"

    username = f"@{user.username}" if user.username else user.full_name

    if reason:
        logger.info(
            f"DELETED | chat={chat.title or chat.id} | "
            f"user={username} (id={user.id}) | reason={reason} | msg={text!r}"
        )
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Could not delete message: {e}")
            return

        if NOTIFY_ON_DELETE:
            notice = (
                f"⚠️ A message from {username} was removed.\n"
                f"Reason: {reason.capitalize()}."
            )
            try:
                sent = await context.bot.send_message(chat_id=chat.id, text=notice)
                context.job_queue.run_once(
                    lambda ctx: ctx.bot.delete_message(chat.id, sent.message_id),
                    when=10,
                )
            except Exception as e:
                logger.error(f"Could not send notice: {e}")
    else:
        logger.info(f"OK | chat={chat.title or chat.id} | user={username} | msg={text[:60]!r}")


# ─────────────────────────────────────────────
# MAIN  — uses asyncio.run() for Python 3.14 compatibility
# ─────────────────────────────────────────────
async def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(
        MessageHandler(
            filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            moderate_message,
        )
    )
    logger.info("🤖 Moderator bot running...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()   # block forever until Render stops the process


if __name__ == "__main__":
    asyncio.run(main())
