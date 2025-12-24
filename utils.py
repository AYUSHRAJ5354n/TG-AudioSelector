# ----------------------------------------
# 𝐌𝐀𝐃𝐄 𝐁𝐘 𝐀𝐁𝐇𝐈
# 𝐓𝐆 𝐈𝐃 : @𝐂𝐋𝐔𝐓𝐂𝐇𝟎𝟎𝟖
# ----------------------------------------

from collections import defaultdict
import os
import ffmpeg
import asyncio
import re
import logging
from datetime import datetime, timedelta

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from tqdm import tqdm

from config import (
    DOWNLOAD_DIR,
    MAX_FILE_SIZE,
    PREMIUM_USERS,
    DAILY_LIMIT_FREE,
    DAILY_LIMIT_PREMIUM
)

logger = logging.getLogger(__name__)

# ----------------------------------------
# Runtime Storage

user_selections = defaultdict(lambda: defaultdict(dict))
status_messages = {}
daily_limits = defaultdict(lambda: {"count": 0, "last_reset": datetime.now()})
last_update_time = defaultdict(lambda: 0)

# ----------------------------------------
# Helpers

def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)

def validate_video_file(path: str) -> bool:
    try:
        probe = ffmpeg.probe(path)
        return any(s["codec_type"] == "video" for s in probe["streams"])
    except Exception:
        return False

# ----------------------------------------
# Audio Track Info

def get_audio_tracks(input_file: str):
    probe = ffmpeg.probe(input_file)
    tracks = []
    audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]

    for idx, stream in enumerate(audio):
        name = stream.get("tags", {}).get("language", f"Track {idx}")
        title = stream.get("tags", {}).get("title")
        if title:
            name += f" ({title})"
        tracks.append((idx, name))

    return tracks

# ----------------------------------------
# NON-BLOCKING FFMPEG (CRITICAL FIX)

async def select_audio_tracks(
    input_file: str,
    output_file: str,
    selected_indices: list,
    output_format: str
):
    if not selected_indices:
        raise ValueError("No audio tracks selected")

    stream = ffmpeg.input(input_file)

    maps = ["0:v:0"]
    for idx in selected_indices:
        maps.append(f"0:a:{idx}")

    args = {
        "map": maps,
        "c:v": "copy",
        "c:a": "copy"
    }

    if output_format == "mkv":
        args["f"] = "matroska"

    stream = ffmpeg.output(stream, output_file, **args)

    await asyncio.to_thread(
        ffmpeg.run,
        stream,
        overwrite_output=True,
        quiet=True
    )

# ----------------------------------------
async def generate_thumbnail(input_file: str, output_path: str):
    stream = ffmpeg.input(input_file, ss="00:00:01")
    stream = ffmpeg.output(stream, output_path, vframes=1)

    await asyncio.to_thread(
        ffmpeg.run,
        stream,
        overwrite_output=True,
        quiet=True
    )

# ----------------------------------------
# Daily Limits

def check_daily_limit(user_id: int) -> bool:
    now = datetime.now()
    data = daily_limits[user_id]

    if now - data["last_reset"] > timedelta(days=1):
        data["count"] = 0
        data["last_reset"] = now

    limit = DAILY_LIMIT_PREMIUM if user_id in PREMIUM_USERS else DAILY_LIMIT_FREE

    if data["count"] >= limit:
        return False

    data["count"] += 1
    return True

# ----------------------------------------
# Telegram Safe Call

async def safe_telegram_call(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if "FLOOD_WAIT" in str(e):
            wait = int(str(e).split("wait of ")[1].split(" seconds")[0])
            await asyncio.sleep(wait)
            return await func(*args, **kwargs)
        raise

# ----------------------------------------
# Download with Progress

async def download_with_progress(
    client: Client,
    message: Message,
    file_path: str,
    chat_id: int,
    user_id: int
):
    size = message.video.file_size if message.video else message.document.file_size
    if size and size > MAX_FILE_SIZE:
        raise ValueError("File too large")

    bar = None

    async def progress(cur, total):
        nonlocal bar
        if not bar:
            bar = tqdm(total=total, unit="B", unit_scale=True)
        bar.n = cur
        bar.refresh()
        if cur == total:
            bar.close()

    await client.download_media(message, file_path, progress=progress)

# ----------------------------------------
# Upload with Progress

async def upload_with_progress(
    client: Client,
    chat_id: int,
    user_id: int,
    file_path: str,
    caption: str,
    output_format: str,
    thumb: str = None,
    reply_to_message_id: int = None
):
    bar = None

    async def progress(cur, total):
        nonlocal bar
        if not bar:
            bar = tqdm(total=total, unit="B", unit_scale=True)
        bar.n = cur
        bar.refresh()
        if cur == total:
            bar.close()

    if output_format == "video":
        await client.send_video(
            chat_id,
            file_path,
            caption=caption,
            progress=progress,
            thumb=thumb,
            reply_to_message_id=reply_to_message_id
        )
    else:
        await client.send_document(
            chat_id,
            file_path,
            caption=caption,
            progress=progress,
            reply_to_message_id=reply_to_message_id
        )

# ----------------------------------------
# Keyboards

async def create_track_selection_keyboard(chat_id, user_id, tracks):
    buttons = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if idx in user_selections[chat_id][user_id].get('selected_tracks', set()) else ''}{name}",
                callback_data=f"track_{idx}"
            )
        ]
        for idx, name in tracks
    ]
    buttons.append([InlineKeyboardButton("Done", callback_data="done_tracks")])
    return InlineKeyboardMarkup(buttons)

async def create_format_selection_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Video (MP4)", callback_data="format_video")],
        [InlineKeyboardButton("Document (MKV)", callback_data="format_mkv")]
    ])

# ----------------------------------------
