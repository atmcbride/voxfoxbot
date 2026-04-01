"""
Download and decode Telegram voice messages.

Telegram sends voice as OGG/Opus. We keep the original OGG for use as the
video's audio track (avoids re-encoding), and convert a copy to WAV so
librosa can read it for spectrogram computation.
"""

import logging
import os
import subprocess

import librosa
import numpy as np
from telegram import Bot

log = logging.getLogger(__name__)

# Sample rate to resample audio to for STFT analysis.
# 22050 Hz is librosa's default and captures frequencies up to ~11 kHz,
# which covers the full useful voice range.
ANALYSIS_SR = 22050


async def download_voice(bot: Bot, file_id: str, dest_dir: str) -> tuple[str, np.ndarray, int]:
    """
    Download a voice message and decode it for analysis.

    Returns:
        ogg_path: path to the original OGG file (used as video audio track)
        samples:  mono float32 numpy array of audio samples
        sr:       sample rate of the returned samples
    """
    ogg_path = os.path.join(dest_dir, "voice.ogg")
    wav_path = os.path.join(dest_dir, "voice.wav")

    log.info("Downloading voice file %s", file_id)
    tg_file = await bot.get_file(file_id)
    await tg_file.download_to_drive(ogg_path)

    # OGG Opus is not supported by soundfile/libsndfile, so we decode via
    # ffmpeg (which we require for video assembly anyway).
    log.info("Decoding OGG to WAV")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", ogg_path,
            "-ar", str(ANALYSIS_SR),
            "-ac", "1",  # mono
            wav_path,
        ],
        check=True,
        capture_output=True,
    )

    samples, sr = librosa.load(wav_path, sr=None, mono=True)
    log.info("Loaded audio: %.2f s at %d Hz", len(samples) / sr, sr)
    return ogg_path, samples, sr
