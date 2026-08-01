# Infrastructure

OpenTofu config for running VoxFox Bot on AWS Lambda: one container-image
function behind a Lambda Function URL that Telegram calls as a webhook, plus a
DynamoDB table for per-chat settings and user stats. There is no server — the
function only runs (and only bills) while processing an update.

## How it works

- Telegram POSTs each update to the Function URL. The handler checks the
  webhook secret header, asynchronously re-invokes itself with the update,
  and acks immediately (Telegram retries slow webhooks; renders are slow).
- The async invocation runs the update through the same python-telegram-bot
  handlers as the old polling bot and replies with the rendered MP4.
- Per-chat settings live in DynamoDB (`chat#<id>`), unique users are counted
  with a conditional put + atomic counter (`user#<id>`, `stat#users`).

## Bootstrap (one-time, run with your privileged IAM role)

Creates the S3 state bucket, GitHub OIDC provider, and a tightly-scoped CI
role (`voxfoxbot-ci`) that can manage voxfoxbot's Lambda/ECR/DynamoDB stack
(and, until teardown is complete, its legacy EC2 resources) in us-east-1.

```bash
cd bootstrap
tofu init
tofu apply
cd ..
```

Note the `ci_role_arn` output — you'll need it for GitHub secrets.

## GitHub Secrets

| Secret | Value |
|---|---|
| `AWS_ROLE_ARN` | `ci_role_arn` output from bootstrap |
| `TG_BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |

(`KEY_NAME` and `SSH_PRIVATE_KEY` were for the EC2 era and can be deleted.)

## Deploy

All deploys happen via CI. Push to `main` and GitHub Actions will build the
container image, push it to ECR tagged with the git SHA, `tofu apply`, and
re-point the Telegram webhook — using OIDC, no long-lived keys.

Manual deploy, if ever needed (privileged credentials + Docker):

```bash
tofu init
tofu apply -target=aws_ecr_repository.voxfoxbot -var image_tag=manual -var tg_bot_token=$TG_BOT_TOKEN
aws ecr get-login-password | docker login --username AWS --password-stdin $(tofu output -raw ecr_repository_url | cut -d/ -f1)
docker build --platform linux/amd64 -t $(tofu output -raw ecr_repository_url):manual .
docker push $(tofu output -raw ecr_repository_url):manual
tofu apply -var image_tag=manual -var tg_bot_token=$TG_BOT_TOKEN
TG_BOT_TOKEN=... ./scripts/set-webhook.sh
```

## Monitoring

```bash
aws logs tail /aws/lambda/voxfoxbot --follow
```

Webhook delivery status (pending updates, last error):

```bash
curl -s "https://api.telegram.org/bot${TG_BOT_TOKEN}/getWebhookInfo"
```

## Local development

`python bot.py` still runs the bot in long-polling mode with local JSON
storage — no AWS involved. Delete the webhook first if the bot is deployed
(`curl .../deleteWebhook`), since polling and webhooks are mutually exclusive.

## Tear down

```bash
tofu destroy -var image_tag=unused -var tg_bot_token=unused
```

To also remove the bootstrap infrastructure (state bucket, CI role, OIDC
provider): `cd bootstrap && tofu destroy`.
