"""
VoxFox Bot — entry point.

Set TELEGRAM_BOT_TOKEN in your environment before running.

The bot must be added as an administrator of the target channel with
"Post Messages" permission. It listens for voice messages in both channels
and direct messages.

Configuration is global (single settings.json) — use commands in DM to
configure; settings apply to all chats including the channel.

Usage:
    TELEGRAM_BOT_TOKEN=<token> python bot.py
"""

import logging
import os
import tempfile
import time

from telegram import Update
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
# Voice message handler
# ---------------------------------------------------------------------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.voice:
        return

    cfg = config.get()
    log.info("Voice message received (%.1fs)", message.voice.duration)

    status = await message.reply_text("Processing spectrogram...")
    t_start = time.monotonic()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ogg_path, samples, sr = await audio.download_voice(
                context.bot, message.voice.file_id, tmpdir
            )

            mag_db, freqs, times = spectrogram.compute_stft(samples, sr, cfg)
            base_image, plot_bounds = spectrogram.render_base_image(mag_db, freqs, times, cfg)

            frames = spectrogram.frame_generator(base_image, plot_bounds, cfg["fps"])
            output_path = os.path.join(tmpdir, "spectrogram.mp4")
            video.assemble(
                frames,
                base_image.width,
                base_image.height,
                ogg_path,
                output_path,
                cfg["fps"],
            )

            elapsed = time.monotonic() - t_start
            with open(output_path, "rb") as f:
                await message.reply_video(
                    video=f,
                    caption=f"Spectrogram · {cfg['fmin']}–{cfg['fmax']} Hz · processed in {elapsed:.1f}s",
                )

        await status.delete()

    except Exception as e:
        log.exception("Failed to process voice message")
        await status.edit_text(f"Error: {e}")


# ---------------------------------------------------------------------------
# Command handlers
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


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = config.get()
    marker_lines = "\n".join(
        f"  • {m['freq']} Hz — {m['label']}" for m in cfg["markers"]
    ) or "  (none)"
    text = (
        f"Current settings:\n"
        f"  Freq range: {cfg['fmin']}–{cfg['fmax']} Hz\n"
        f"  Colormap:   {cfg['colormap']}\n"
        f"  FPS:        {cfg['fps']}\n"
        f"  Markers:\n{marker_lines}"
    )
    await update.effective_message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "VoxFox — voice message spectrograph bot\n\n"
        "Send or forward a voice message and I'll reply with an animated spectrogram video.\n\n"
        "Commands (use in DM — settings apply globally):\n"
        "  /config               — show current settings\n"
        "  /setrange <min> <max> — set frequency range in Hz\n"
        "  /addmarker <hz> [lbl] — add a horizontal reference line\n"
        "  /clearmarkers         — remove all reference lines\n"
        "  /setcolormap <name>   — change colour palette\n"
        "  /help                 — this message"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable is not set.")

    app = Application.builder().token(token).build()

    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

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
