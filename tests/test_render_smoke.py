"""End-to-end render smoke test: sine wave in, playable MP4 out.

Exercises the untouched DSP pipeline (spectrogram.py, video.py) against the
currently-installed library versions — the same requirements.txt the Lambda
image installs. Needs ffmpeg on PATH.
"""

import os
import subprocess

import librosa

import config
import spectrogram
import video


def test_sine_sweep_renders_mp4(tmp_path):
    wav = str(tmp_path / "tone.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "22050", "-ac", "1", wav],
        check=True,
        capture_output=True,
    )

    samples, sr = librosa.load(wav, sr=None, mono=True)
    cfg = dict(config.DEFAULTS)

    mag_db, freqs, times = spectrogram.compute_stft(samples, sr, cfg)
    assert mag_db.shape[0] == len(freqs)
    assert mag_db.shape[1] == len(times)

    base_image, plot_bounds = spectrogram.render_base_image(mag_db, freqs, times, cfg)
    assert (base_image.width, base_image.height) == (1280, 720)

    frames = spectrogram.frame_generator(base_image, plot_bounds, cfg["fps"])
    out = str(tmp_path / "spectrogram.mp4")
    video.assemble(frames, base_image.width, base_image.height, wav, out, cfg["fps"])

    assert os.path.getsize(out) > 10_000
    # container sanity: ffmpeg can read back both streams
    probe = subprocess.run(
        ["ffmpeg", "-i", out, "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
