"""
STFT computation and spectrogram frame rendering.

Pipeline:
  1. compute_stft()       — numpy arrays (mag_db, freqs, times)
  2. render_base_image()  — full spectrogram as a PIL Image + pixel bounds of
                            the plot area (needed to place the playhead line)
  3. frame_generator()    — yields one PIL Image per video frame, with a
                            vertical playhead line swept across the plot
"""

import io
import logging

import librosa
import matplotlib
import numpy as np
from PIL import Image, ImageDraw

matplotlib.use("Agg")  # non-interactive backend, must be set before pyplot import
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)

# Output video resolution
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# STFT parameters. hop_length controls time resolution of frames;
# n_fft controls frequency resolution.
N_FFT = 2048
HOP_LENGTH = 512


def compute_stft(
    samples: np.ndarray, sr: int, cfg: dict
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute a magnitude spectrogram in dB.

    Returns:
        mag_db: 2-D array (freq_bins, time_frames), values in dB
        freqs:  1-D array of frequency bin centres in Hz
        times:  1-D array of frame timestamps in seconds
    """
    log.info("Computing STFT (n_fft=%d, hop=%d)", N_FFT, HOP_LENGTH)
    D = librosa.stft(samples, n_fft=N_FFT, hop_length=HOP_LENGTH)
    mag_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    times = librosa.frames_to_time(np.arange(D.shape[1]), sr=sr, hop_length=HOP_LENGTH)
    return mag_db, freqs, times


def render_base_image(
    mag_db: np.ndarray,
    freqs: np.ndarray,
    times: np.ndarray,
    cfg: dict,
) -> tuple[Image.Image, dict]:
    """
    Render the full spectrogram as a static PIL Image.

    Returns:
        image:       PIL Image at FRAME_WIDTH x FRAME_HEIGHT
        plot_bounds: pixel x-coordinates of the plot area's left and right
                     edges, plus the time range — used to position the playhead
    """
    fmin = cfg["fmin"]
    fmax = cfg["fmax"]
    colormap = cfg["colormap"]

    # Clip to the requested frequency range
    freq_mask = (freqs >= fmin) & (freqs <= fmax)
    mag_clipped = mag_db[freq_mask]
    freqs_clipped = freqs[freq_mask]

    dpi = 100
    fig, ax = plt.subplots(
        figsize=(FRAME_WIDTH / dpi, FRAME_HEIGHT / dpi),
        dpi=dpi,
        constrained_layout=True,
    )
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    mesh = ax.pcolormesh(
        times,
        freqs_clipped,
        mag_clipped,
        cmap=colormap,
        shading="gouraud",
        rasterized=True,
    )

    if cfg.get("linear_scale", False):
        ax.set_yscale("linear")
    else:
        ax.set_yscale("log")
    ax.set_ylim(fmin, fmax)
    ax.set_xlim(times[0], times[-1])
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#444444")
    ax.set_xlabel("Time (s)", color="white")
    ax.set_ylabel("Frequency (Hz)", color="white")
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())

    cbar = fig.colorbar(mesh, ax=ax, pad=0.01)
    cbar.set_label("dB", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    for marker in cfg.get("markers", []):
        freq = marker["freq"]
        label = marker["label"]
        if fmin <= freq <= fmax:
            ax.axhline(y=freq, color="white", linestyle="--", linewidth=1.5, zorder=10)
            ax.text(
                times[0] + (times[-1] - times[0]) * 0.005,
                freq,
                label,
                color="white",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                zorder=11,
            )

    # Draw the canvas so matplotlib finalises layout before we read positions
    fig.canvas.draw()
    ax_pos = ax.get_position()  # normalised figure coordinates (0–1)
    plot_x0 = ax_pos.x0 * FRAME_WIDTH
    plot_x1 = ax_pos.x1 * FRAME_WIDTH

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="black", dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    image = Image.open(buf).convert("RGB")
    # Force size in case of rounding
    image = image.resize((FRAME_WIDTH, FRAME_HEIGHT), Image.LANCZOS)

    plot_bounds = {
        "x0": plot_x0,
        "x1": plot_x1,
        "t0": float(times[0]),
        "t1": float(times[-1]),
    }
    log.info("Base image rendered; plot x-range: %.0f–%.0f px", plot_x0, plot_x1)
    return image, plot_bounds


def frame_generator(base_image: Image.Image, plot_bounds: dict, fps: int):
    """
    Yield one PIL Image per video frame, with a playhead line drawn at the
    current time position.
    """
    t0 = plot_bounds["t0"]
    t1 = plot_bounds["t1"]
    x0 = plot_bounds["x0"]
    x1 = plot_bounds["x1"]
    duration = t1 - t0
    total_frames = int(duration * fps)

    log.info("Generating %d frames at %d fps", total_frames, fps)
    for i in range(total_frames):
        t = t0 + i / fps
        x = int(x0 + (t - t0) / duration * (x1 - x0))

        frame = base_image.copy()
        draw = ImageDraw.Draw(frame)
        # Bright white line with a subtle shadow for contrast on any colormap
        draw.line([(x - 1, 0), (x - 1, frame.height)], fill=(0, 0, 0, 128), width=1)
        draw.line([(x, 0), (x, frame.height)], fill=(255, 255, 255), width=2)
        yield frame
