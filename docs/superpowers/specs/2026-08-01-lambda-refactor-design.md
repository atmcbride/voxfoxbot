# VoxFox Lambda Refactor — Design

Date: 2026-08-01. Approved in conversation (option "straight to Lambda") after the
EC2 deployment was found dead since 2026-05-14 (instance replaced by AMI drift;
venv/.env never provisioned — see git history of `main.tf` user_data vs
`voxfoxbot.service` paths).

## Goals

- Replace the always-on t3a.small (~$19/mo incl. IPv4 + EBS) with on-demand
  compute (~$0/mo at current usage: July CPU averaged 0.28%).
- Remove all mutable instance state so a redeploy can never silently kill the bot.
- Keep bot behavior identical: same handlers, commands, per-chat settings.

## Architecture

One Lambda function (`voxfoxbot`, container image, python3.13, x86_64,
3008 MB / 600 s / 1 GB ephemeral), invoked in two modes:

1. **Webhook** — Telegram POSTs updates to a Lambda Function URL (auth NONE,
   verified via `X-Telegram-Bot-Api-Secret-Token` header against a
   terraform-generated secret). The handler triages the update (only
   `message`/`channel_post` have handlers), asynchronously re-invokes the same
   function with `{"voxfox_update": ...}`, and returns 200 immediately.
   Rationale: Telegram retries slow webhooks; renders take tens of seconds.
2. **Worker** — the async self-invocation runs the update through the
   unchanged python-telegram-bot Application (`process_update`). Async retry
   count is 0 for parity with the old bot (one attempt per update).

The PTB Application and event loop are module-global — built once per warm
container. Heavy imports (librosa/matplotlib via bot.py) are deferred out of
the webhook ack path.

## State

DynamoDB table `voxfoxbot` (on-demand, single table, hash key `pk`):

- `chat#<chat_id>` — per-chat setting overrides as a JSON string (JSON text
  avoids float/Decimal friction; blobs are tiny).
- `user#<user_id>` — first_seen epoch; conditional put keeps writes idempotent.
- `stat#users` — atomic counter incremented only when the conditional put
  succeeds, so `/stats` is a single read, no scans.

`config.py`/`stats.py` keep their public APIs; they fall back to local JSON
files when `VOXFOX_DDB_TABLE` is unset so `python bot.py` still runs locally
(polling mode, kept for development).

## Image

`public.ecr.aws/lambda/python:3.13` + static ffmpeg (BtbN GPL build, has
libx264) copied from an amazonlinux build stage. `HOME`/`MPLCONFIGDIR`/
`NUMBA_CACHE_DIR` point at /tmp (read-only filesystem). The DSP pipeline
(audio.py, spectrogram.py, video.py) is unchanged.

## Deploy

CI (GitHub OIDC, existing `voxfoxbot-ci` role with added ECR/Lambda/IAM/
DynamoDB/logs permissions — bootstrap/main.tf): tofu target-apply the ECR
repo, docker build/push tagged with the git SHA, full tofu apply
(`TF_VAR_image_tag=SHA`), then `setWebhook` with the Function URL + secret,
`allowed_updates=["message","channel_post"]`. The full apply also destroys
the EC2 instance/SG on first run. Old `voxfoxbot.service`/`deploy.sh` deleted;
`KEY_NAME`/`SSH_PRIVATE_KEY` secrets become unused.

## Trade-offs accepted

- Cold starts ~2–5 s (numba/matplotlib imports) — invisible next to render time.
- librosa kept (rather than a scipy rewrite) to avoid touching DSP code; the
  image is fat but Lambda allows 10 GB.
- Two invocations per handled update (ack + worker) — free-tier noise.
