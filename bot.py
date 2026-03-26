import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ENVIRONMENT VARIABLES ---
# Render will inject these from your dashboard
API_ID = os.environ.get("API_ID", "YOUR_API_ID") 
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
PORT = os.environ.get("PORT", "10000") # Render assigns a port dynamically

# Initialize Pyrogram
app = Client("universal_sniper", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- GLOBAL LOCK FOR RAM SAFETY ---
# This prevents 2 people from downloading a 2GB file at the same time and crashing Render
is_downloading = False

# --- DUMMY WEB SERVER ---
# Render requires a web server binding to $PORT to keep the Web Service alive
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly on Render!")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(PORT))
    await site.start()
    logger.info(f"Dummy Web Server running on port {PORT}")

# --- BOT LOGIC ---
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text("Universal Stream Sniper is online. Send me a video or m3u8 link.")

@app.on_message(filters.text & ~filters.command("start"))
async def download_handler(client: Client, message: Message):
    global is_downloading
    
    url = message.text.strip()
    if not url.startswith("http"):
        return

    if is_downloading:
        await message.reply_text("⚠️ **Queue Full:** I am currently processing a heavy file. Please wait a moment and try again.")
        return

    is_downloading = True
    status_msg = await message.reply_text("🔍 Analyzing link and starting secure download...")

    # We use a static filename to keep things simple and easy to clean up
    file_name = f"download_{message.from_user.id}.mp4"

    # Strict RAM-bypassing yt-dlp config
    ydl_opts = {
        'format': 'best', 
        'outtmpl': file_name,
        'quiet': True,
        'no_warnings': True,
        'external_downloader': 'aria2c',
        'external_downloader_args': [
            '-x', '4',                # Max 4 connections
            '-s', '4',                # Max 4 splits
            '--disk-cache=16M',       # Hard RAM cap
            '--file-allocation=none', # Stop RAM spikes
            '--summary-interval=0'
        ]
        # 'cookiefile': 'cookies.txt' # Uncomment this if you upload your cookies.txt
    }

    try:
        # Run yt-dlp in a separate thread so it doesn't freeze the bot's async loop
        await status_msg.edit_text("⬇️ **Downloading...** Bypassing RAM limits to disk.")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        # Check if the file actually downloaded
        if os.path.exists(file_name):
            await status_msg.edit_text("⬆️ **Uploading to Telegram...** Streaming from disk.")
            
            # The magic upload: Passing the string filepath, NOT the file bytes
            await client.send_video(
                chat_id=message.chat.id,
                video=file_name,
                caption="Here is your video!",
                supports_streaming=True
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Download failed. The file could not be extracted.")

    except Exception as e:
        logger.error(f"Download Error: {e}")
        await status_msg.edit_text(f"❌ **An error occurred:** `{str(e)[:100]}`")
        
    finally:
        # RUTHLESS CLEANUP: Delete the file instantly to free up the 50GB disk space
        if os.path.exists(file_name):
            os.remove(file_name)
            logger.info(f"Cleaned up {file_name}")
        
        # Release the lock for the next person
        is_downloading = False


# --- MAIN RUNNER ---
async def main():
    # Start the keep-alive server first
    await start_web_server()
    # Then start the bot
    logger.info("Starting Pyrogram bot...")
    await app.start()
    # Keep the script running forever
    await pyrogram.idle()

if __name__ == "__main__":
    import pyrogram
    asyncio.run(main())
