# ----------------------------------------
# 𝐌𝐀𝐃𝐄 𝐁𝐘 𝐀𝐁𝐇𝐈
# 𝐓𝐆 𝐈𝐃 : @𝐂𝐋𝐔𝐓𝐂𝐇𝟎𝟎𝟖
# ----------------------------------------

import os
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

from start import register_start_handlers
from status import register_status_handlers
from us import register_us_handlers
from video import register_video_handlers
from cancel import register_cancel_handlers
from getid import register_getid_handlers

# ----------------------------------------
# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------
# HEALTH CHECK SERVER (REQUIRED FOR KOYEB)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server():
    HTTPServer(("0.0.0.0", 8080), HealthHandler).serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()

# ----------------------------------------
# Pyrogram Client (BOT MODE ONLY)

app = Client(
    "audio_selector_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True  # VERY IMPORTANT
)

# ----------------------------------------
def main():
    register_start_handlers(app)
    register_status_handlers(app)
    register_us_handlers(app)
    register_video_handlers(app)
    register_cancel_handlers(app)
    register_getid_handlers(app)

    logger.info("Starting bot...")
    app.run()

# ----------------------------------------
if __name__ == "__main__":
    main()
# ----------------------------------------
