import os
import subprocess
import threading
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8643276744:AAHPOFjTc9cKKMUWXZignM2LKEZryEJIRzU")
DOWNLOAD_DIR = "/tmp/videos"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED = ["youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.watch", "threads.net"]

def is_supported(url: str) -> bool:
    return any(s in url.lower() for s in SUPPORTED)

def download_video(url: str) -> tuple:
    cmd = [
        "yt-dlp",
        "--restrict-filenames",
        "-o", os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "--print", "after_move:filepath",
        url
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True,
            encoding="utf-8", errors="replace", timeout=300
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            filepath = lines[-1].strip() if lines else None
            if filepath and os.path.exists(filepath):
                return True, filepath
            files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)]
            if files:
                return True, max(files, key=os.path.getctime)
            return False, "File not found after download."
        else:
            return False, result.stderr or result.stdout or "Unknown error"
    except subprocess.TimeoutExpired:
        return False, "Download timed out (5 min limit)."
    except FileNotFoundError:
        return False, "yt-dlp not found."
    except Exception as e:
        return False, str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *DYFIVideoBot*!\n\n"
        "Send me a video link from:\n"
        "▶️ YouTube\n"
        "📸 Instagram\n"
        "📘 Facebook\n"
        "🧵 Threads\n\n"
        "I'll download and send it to you!",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*How to use:*\n"
        "1. Copy any video link\n"
        "2. Paste it here\n"
        "3. Wait for the video!\n\n"
        "*Supported:*\n"
        "• YouTube & Shorts\n"
        "• Instagram Reels & Posts\n"
        "• Facebook Videos\n"
        "• Threads Videos\n\n"
        "_Max size: 50MB (Telegram limit)_",
        parse_mode="Markdown"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not is_supported(url):
        await update.message.reply_text(
            "Unsupported link.\nSend a YouTube, Instagram, Facebook or Threads link."
        )
        return
    msg = await update.message.reply_text("Downloading your video, please wait...")
    def do_download():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_send_video(update, context, msg, url))
        loop.close()
    threading.Thread(target=do_download, daemon=True).start()

async def _send_video(update, context, msg, url):
    success, result = download_video(url)
    if not success:
        await msg.edit_text(f"Download failed:\n{result[:300]}")
        return
    filepath = result
    filesize = os.path.getsize(filepath)
    if filesize > 50 * 1024 * 1024:
        await msg.edit_text("Video too large for Telegram (max 50MB). Try a shorter video!")
        os.remove(filepath)
        return
    await msg.edit_text("Uploading to Telegram...")
    try:
        with open(filepath, "rb") as f:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=f,
                caption="Here's your video!",
                supports_streaming=True
            )
        await msg.delete()
        os.remove(filepath)
    except Exception as e:
        await msg.edit_text(f"Upload failed: {str(e)[:200]}")

async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a valid video URL. Type /help for instructions.")

def main():
    print("DYFIVideoBot starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://'), handle_url))
    app.add_handler(MessageHandler(filters.TEXT, handle_other))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
