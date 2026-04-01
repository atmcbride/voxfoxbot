# Infrastructure

OpenTofu config for deploying VoxFox Bot to a t3a.medium EC2 instance on AWS.

## Prerequisites

- [OpenTofu](https://opentofu.org/) installed
- AWS credentials configured (`aws configure` or environment variables)
- An EC2 key pair created in your target region

## Bootstrap (one-time, run with your privileged IAM role)

Creates the S3 state bucket, GitHub OIDC provider, and a tightly-scoped CI role (`voxfoxbot-ci`) that can only manage voxfoxbot's EC2 + security groups in us-east-1 and read/write the state bucket.

```bash
cd bootstrap
tofu init
tofu apply
cd ..
```

Note the `ci_role_arn` output — you'll need it for GitHub secrets.

## GitHub Secrets

After bootstrap, add these repo secrets (Settings > Secrets):

| Secret | Value |
|---|---|
| `AWS_ROLE_ARN` | `ci_role_arn` output from bootstrap |
| `KEY_NAME` | EC2 key pair name |
| `TG_BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) |

## Deploy

All deploys happen via CI. Push to `main` and GitHub Actions will `tofu apply` automatically using OIDC (no long-lived keys).

The CI role (`voxfoxbot-ci`) is scoped to:
- S3: read/write on `voxfoxbot-tfstate` only
- EC2: mutate only resources tagged `Project=voxfoxbot` (cannot touch other instances/SGs in the account)
- EC2: launch new instances only if tagged `Project=voxfoxbot`
- Read-only: AMIs, VPCs, subnets, instance types (required by tofu plan)

## Connect

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<instance-public-ip>
```

Public IP is available in the GitHub Actions run output.

## Tear down

Remove the EC2 resources by deleting them from `main.tf` and pushing. To also remove the bootstrap infrastructure (state bucket, CI role, OIDC provider):

```bash
cd bootstrap
tofu destroy
```
