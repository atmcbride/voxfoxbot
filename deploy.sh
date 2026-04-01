#!/usr/bin/env bash
set -euo pipefail

HOST="${1:?Usage: ./deploy.sh <instance-ip>}"
KEY="${2:-~/.ssh/voxfoxbot.pem}"

rsync -avz --exclude '.git' --exclude 'venv' --exclude '__pycache__' --exclude '.terraform' --exclude '*.tfstate*' --exclude 'terraform.tfvars' --exclude 'bootstrap' \
  -e "ssh -i $KEY -o StrictHostKeyChecking=no" \
  ./ "ubuntu@${HOST}:~/voxfoxbot/"

ssh -i "$KEY" "ubuntu@${HOST}" 'cd ~/voxfoxbot && source venv/bin/activate && sudo systemctl restart voxfoxbot || echo "no systemd service yet — start manually"'
