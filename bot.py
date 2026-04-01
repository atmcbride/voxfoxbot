"""
VoxFox Bot — entry point.

Set TELEGRAM_BOT_TOKEN in your environment before running.

The bot must be added as an administrator of the target channel with
"Post Messages" permission. It listens for:
  - Voice messages (OGG/Opus) sent directly
  - Audio files (MP3, WAV, FLAC, M4A, AAC, OGG) sent directly or as documents
  - /vox replied to any of the above
  - @voxfoxbot mention in a reply to any of the above

Configuration is global (single settings.json) — use commands in DM to
configure; settings apply to all chats including the channel.

Usage:
    TELEGRAM_BOT_TOKEN=<token> python bot.py
"""

import logging
import os
import tempfile
import time

from telegram import Message, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import audio
import config
import spectrogram
import video

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MIME-type → file extension map for audio formats ffmpeg can handle
# ---------------------------------------------------------------------------

_MIME_TO_EXT: dict[str, str] = {
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "video/mp4": ".mp4",   # video_note container
    "video/webm": ".webm",
}

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".webm"}


def _audio_from_message(message: Message) -> tuple[str, str] | None:
    """
    Extract (file_id, ext) from a Telegram message, or return None.

    Checks, in order:
      - voice        (OGG/Opus — Telegram's native voice note format)
      - audio        (MP3, FLAC, M4A, AAC, OGG — Telegram audio messages)
      - video_note   (circular video messages with an audio track)
      - document     (raw file uploads with an audio MIME type or extension)
    """
    if message.voice:
        return message.voice.file_id, ".ogg"

    if message.audio:
        ext = _MIME_TO_EXT.get(message.audio.mime_type or "", ".mp3")
        return message.audio.file_id, ext

    if message.video_note:
        return message.video_note.file_id, ".mp4"

    if message.document:
        mime = message.document.mime_type or ""
        if mime.startswith("audio/") or mime.startswith("video/"):
            ext = _MIME_TO_EXT.get(mime, ".audio")
            return message.document.file_id, ext
        # Fall back to filename extension for files with missing/generic MIME types
        name = (message.document.file_name or "").lower()
        for suffix in _AUDIO_EXTENSIONS:
            if name.endswith(suffix):
                return message.document.file_id, suffix

    return None


# ---------------------------------------------------------------------------
# Core processing helpers
# ---------------------------------------------------------------------------

async def _run_spectrogram(
    bot,
    file_id: str,
    ext: str,
    cfg: dict,
    tmpdir: str,
) -> str:
    """Download audio, compute spectrogram, assemble MP4. Returns output path."""
    audio_path, samples, sr = await audio.download_audio(bot, file_id, tmpdir, ext)
    mag_db, freqs, times = spectrogram.compute_stft(samples, sr, cfg)
    base_image, plot_bounds = spectrogram.render_base_image(mag_db, freqs, times, cfg)
    frames = spectrogram.frame_generator(base_image, plot_bounds, cfg["fps"])
    output_path = os.path.join(tmpdir, "spectrogram.mp4")
    video.assemble(
        frames,
        base_image.width,
        base_image.height,
        audio_path,
        output_path,
        cfg["fps"],
    )
    return output_path


async def _process_message_audio(
    source: Message,
    reply_target: Message,
    cfg: dict,
    bot,
) -> None:
    """
    Process audio from `source` and send the spectrogram video as a reply to
    `reply_target`.

    When a user sends audio directly, source == reply_target.
    When a user uses /vox or @mention on a reply, source is the original
    message and reply_target is the command/mention message.
    """
    audio_info = _audio_from_message(source)
    if audio_info is None:
        await reply_target.reply_text(
            "No supported audio found. I can process voice messages, MP3, WAV, "
            "FLAC, M4A, AAC, and OGG files."
        )
        return

    file_id, ext = audio_info
    status = await reply_target.reply_text("Processing spectrogram...")
    t_start = time.monotonic()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = await _run_spectrogram(bot, file_id, ext, cfg, tmpdir)
            elapsed = time.monotonic() - t_start
            with open(output_path, "rb") as f:
                await reply_target.reply_video(
                    video=f,
                    caption=(
                        f"Spectrogram · {cfg['fmin']}–{cfg['fmax']} Hz "
                        f"· processed in {elapsed:.1f}s"
                    ),
                )
        await status.delete()

    except Exception as e:
        log.exception("Failed to process audio")
        await status.edit_text(f"Error: {e}")


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    cfg = config.get()
    if not cfg.get("auto_spectrogram", True):
        return
    log.info("Voice message received (%.1fs)", message.voice.duration)
    await _process_message_audio(message, message, cfg, context.bot)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    cfg = config.get()
    if not cfg.get("auto_spectrogram", True):
        return
    log.info("Audio file received")
    await _process_message_audio(message, message, cfg, context.bot)


async def handle_audio_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    cfg = config.get()
    if not cfg.get("auto_spectrogram", True):
        return
    log.info("Audio document received")
    await _process_message_audio(message, message, cfg, context.bot)


# ---------------------------------------------------------------------------
# /vox command — reply to any audio message to trigger the bot manually
# ---------------------------------------------------------------------------

async def cmd_vox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /vox (or @mention) — process the audio in the replied-to message.

    Usage: reply to a voice message or audio file with /vox (or mention the bot).
    """
    message = update.effective_message
    if not message:
        return

    target = message.reply_to_message
    if not target:
        await message.reply_text(
            "Reply to a voice message or audio file with /vox to run the spectrogram on it."
        )
        return

    log.info("/vox triggered on replied-to message")
    await _process_message_audio(target, message, config.get(), context.bot)


# ---------------------------------------------------------------------------
# Configuration commands
# ---------------------------------------------------------------------------

async def cmd_setrange(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    try:
        fmin = float(context.args[0])
        fmax = float(context.args[1])
        if fmin >= fmax:
            await message.reply_text("fmin must be less than fmax.")
            return
        config.update(fmin=fmin, fmax=fmax)
        await message.reply_text(f"Frequency range set to {fmin}–{fmax} Hz.")
    except (IndexError, ValueError):
        await message.reply_text("Usage: /setrange <fmin_hz> <fmax_hz>\nExample: /setrange 80 8000")


async def cmd_addmarker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    try:
        freq = float(context.args[0])
        label = " ".join(context.args[1:]) if len(context.args) > 1 else f"{freq:.0f} Hz"
        cfg = config.get()
        markers = cfg["markers"]
        markers.append({"freq": freq, "label": label})
        config.update(markers=markers)
        await message.reply_text(f"Marker added: '{label}' at {freq} Hz.")
    except (IndexError, ValueError):
        await message.reply_text("Usage: /addmarker <freq_hz> [label]\nExample: /addmarker 1000 1kHz")


async def cmd_clearmarkers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config.update(markers=[])
    await update.effective_message.reply_text("All markers cleared.")


async def cmd_setcolormap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    try:
        cmap = context.args[0]
        config.update(colormap=cmap)
        await message.reply_text(
            f"Colormap set to '{cmap}'.\n"
            "Common options: magma, inferno, viridis, plasma, cividis, turbo"
        )
    except IndexError:
        await message.reply_text(
            "Usage: /setcolormap <name>\nExample: /setcolormap magma"
        )


async def cmd_toggleauto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = config.get()
    new_value = not cfg.get("auto_spectrogram", True)
    config.update(auto_spectrogram=new_value)
    state = "ON" if new_value else "OFF"
    await update.effective_message.reply_text(
        f"Auto-spectrogram is now {state}.\n"
        + ("Audio messages will be processed automatically." if new_value
           else "Use /vox or @mention to trigger manually.")
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config.reset()
    await update.effective_message.reply_text(
        "Settings reset to defaults.\n"
        "  Freq range: 70–4000 Hz\n"
        "  Colormap:   magma\n"
        "  Auto-spectrogram: ON\n"
        "  Markers: D2, E3, D4"
    )


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = config.get()
    marker_lines = "\n".join(
        f"  • {m['freq']} Hz — {m['label']}" for m in cfg["markers"]
    ) or "  (none)"
    auto = "ON" if cfg.get("auto_spectrogram", True) else "OFF"
    text = (
        f"Current settings:\n"
        f"  Freq range:      {cfg['fmin']}–{cfg['fmax']} Hz\n"
        f"  Colormap:        {cfg['colormap']}\n"
        f"  FPS:             {cfg['fps']}\n"
        f"  Auto-spectrogram:{auto}\n"
        f"  Markers:\n{marker_lines}"
    )
    await update.effective_message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "VoxFox — voice message spectrograph bot\n\n"
        "Supported audio:\n"
        "  • Voice messages (OGG/Opus)\n"
        "  • Audio files: MP3, WAV, FLAC, M4A, AAC, OGG\n\n"
        "How to trigger:\n"
        "  • Send/forward any supported audio — bot replies automatically\n"
        "    (when auto-spectrogram is ON)\n"
        "  • Reply to any audio message with /vox\n"
        "  • Reply to any audio message and @mention the bot\n\n"
        "Commands (use in DM — settings apply globally):\n"
        "  /vox                  — run on a replied-to audio message\n"
        "  /toggleauto           — toggle automatic spectrogram on/off\n"
        "  /config               — show current settings\n"
        "  /reset                — reset all settings to defaults\n"
        "  /setrange <min> <max> — set frequency range in Hz\n"
        "  /addmarker <hz> [lbl] — add a horizontal reference line\n"
        "  /clearmarkers         — remove all reference lines\n"
        "  /setcolormap <name>   — change colour palette\n"
        "  /help                 — this message"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def post_init(app: Application) -> None:
    """Register the @mention-reply handler after we know the bot's username."""
    me = await app.bot.get_me()
    log.info("Bot username: @%s", me.username)
    app.add_handler(
        MessageHandler(
            filters.REPLY & filters.Mention(me.username),
            cmd_vox,
        )
    )


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is not set.")

    app = Application.builder().token(token).post_init(post_init).build()

    # Direct audio — fires when the message itself contains audio
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(
        MessageHandler(
            filters.Document.FileExtension("mp3")
            | filters.Document.FileExtension("wav")
            | filters.Document.FileExtension("flac")
            | filters.Document.FileExtension("m4a")
            | filters.Document.FileExtension("aac")
            | filters.Document.FileExtension("ogg"),
            handle_audio_document,
        )
    )

    # Manual trigger
    app.add_handler(CommandHandler("vox", cmd_vox))

    # Config commands
    app.add_handler(CommandHandler("toggleauto", cmd_toggleauto))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("setrange", cmd_setrange))
    app.add_handler(CommandHandler("addmarker", cmd_addmarker))
    app.add_handler(CommandHandler("clearmarkers", cmd_clearmarkers))
    app.add_handler(CommandHandler("setcolormap", cmd_setcolormap))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    log.info("Bot started. Polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
