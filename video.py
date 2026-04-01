"""
Assemble spectrogram frames + original audio into an MP4.

Frames are piped to ffmpeg as raw RGB24 video to avoid writing thousands of
PNG files to disk. The original OGG is passed as the audio track directly;
ffmpeg re-encodes it to AAC for the MP4 container.
"""

import logging
import subprocess
from typing import Generator

from PIL import Image

log = logging.getLogger(__name__)


def assemble(
    frames: Generator[Image.Image, None, None],
    width: int,
    height: int,
    audio_path: str,
    output_path: str,
    fps: int,
) -> None:
    """
    Pipe PIL Image frames into ffmpeg alongside the audio file and write an MP4.

    Args:
        frames:      generator yielding PIL Images in RGB mode
        width:       frame width in pixels (must be even for h264)
        height:      frame height in pixels (must be even for h264)
        audio_path:  path to the original audio file (OGG/WAV/etc.)
        output_path: destination MP4 path
        fps:         frames per second, must match the frame generator's rate
    """
    # h264 requires even dimensions
    assert width % 2 == 0 and height % 2 == 0, "Frame dimensions must be even"

    cmd = [
        "ffmpeg", "-y",
        # Video input: raw RGB frames from stdin
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        # Audio input: original voice file
        "-i", audio_path,
        # Output encoding
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",  # required for broad player compatibility
        "-shortest",            # stop when the shorter stream ends
        output_path,
    ]

    log.info("Starting ffmpeg: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        _, stderr = proc.communicate()
        raise RuntimeError(f"ffmpeg pipe broke early:\n{stderr.decode()}") from None

    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read()
        raise RuntimeError(f"ffmpeg exited with code {proc.returncode}:\n{stderr.decode()}")

    log.info("Video written to %s", output_path)
