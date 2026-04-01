"""
Download and decode audio from Telegram messages.

Telegram sends voice as OGG/Opus. Audio files can be MP3, WAV, FLAC, M4A, AAC,
or OGG. We keep the original file for use as the video's audio track, and
convert a copy to WAV so librosa can read it for spectrogram computation.
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


async def download_audio(bot: Bot, file_id: str, dest_dir: str, ext: str = ".ogg") -> tuple[str, np.ndarray, int]:
    """
    Download any Telegram audio file and decode it for analysis.

    Args:
        bot:      Telegram Bot instance
        file_id:  Telegram file_id to download
        dest_dir: directory to write files into
        ext:      file extension for the downloaded file (e.g. ".mp3", ".wav")
                  — used so ffmpeg detects the container format correctly

    Returns:
        audio_path: path to the original downloaded file (used as video audio track)
        samples:    mono float32 numpy array of audio samples
        sr:         sample rate of the returned samples
    """
    audio_path = os.path.join(dest_dir, f"audio{ext}")
    wav_path = os.path.join(dest_dir, "audio.wav")

    log.info("Downloading file %s (ext=%s)", file_id, ext)
    tg_file = await bot.get_file(file_id)
    await tg_file.download_to_drive(audio_path)

    # Decode to WAV via ffmpeg for librosa — handles OGG/Opus, MP3, FLAC,
    # WAV, M4A/AAC, and any other ffmpeg-supported container.
    log.info("Decoding %s to WAV", ext)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ar", str(ANALYSIS_SR),
            "-ac", "1",  # mono
            wav_path,
        ],
        check=True,
        capture_output=True,
    )

    samples, sr = librosa.load(wav_path, sr=None, mono=True)
    log.info("Loaded audio: %.2f s at %d Hz", len(samples) / sr, sr)
    return audio_path, samples, sr
