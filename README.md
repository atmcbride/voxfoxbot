# VoxFox Bot

A Telegram bot that listens for voice messages and replies with an animated spectrogram video. The spectrogram is computed via STFT (sliding FFT) and rendered as an MP4 with a playhead sweeping across in sync with the audio.

## Requirements

- Python 3.11+
- ffmpeg (`brew install ffmpeg`)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a bot via [@BotFather](https://t.me/BotFather) on Telegram and copy the token. Add the bot as an administrator of your channel with "Post Messages" permission.

## Running

```bash
TELEGRAM_BOT_TOKEN=<your_token> python bot.py
```

## Commands

Send these to the bot in DM — settings apply globally.

| Command | Description |
|---|---|
| `/config` | Show current settings |
| `/setrange <fmin> <fmax>` | Set frequency range in Hz |
| `/addmarker <hz> [label]` | Add a horizontal reference line at a frequency |
| `/clearmarkers` | Remove all reference lines |
| `/setcolormap <name>` | Change colour palette (magma, inferno, viridis, plasma, turbo) |
| `/help` | Show help message |

## Deploy to AWS

See [INFRA-README.md](INFRA-README.md) for full infrastructure setup, bootstrap, and CI details.

## Defaults

- Frequency range: 70–4000 Hz
- Colormap: magma
- FPS: 30
- Markers: D2 (74.42 Hz), E3 (164.81 Hz), D4 (293.66 Hz)
