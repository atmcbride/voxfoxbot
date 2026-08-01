#!/usr/bin/env bash
# Point Telegram at the deployed Lambda Function URL.
# CI does this automatically after every deploy; this is the manual fallback.
#
# Usage: TG_BOT_TOKEN=<token> ./scripts/set-webhook.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${TG_BOT_TOKEN:?set TG_BOT_TOKEN}"

URL=$(tofu output -raw webhook_url)
SECRET=$(tofu output -raw webhook_secret)

curl -fsS "https://api.telegram.org/bot${TG_BOT_TOKEN}/setWebhook" \
  -d "url=${URL}" \
  -d "secret_token=${SECRET}" \
  -d 'allowed_updates=["message","channel_post"]'
echo
