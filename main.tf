terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "voxfoxbot-tfstate"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "voxfoxbot" {
  name        = "voxfoxbot-sg"
  description = "Security group for voxfoxbot"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "voxfoxbot"
  }
}

resource "aws_instance" "voxfoxbot" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3a.medium"
  key_name      = var.key_name

  vpc_security_group_ids = [aws_security_group.voxfoxbot.id]

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e
    apt-get update
    apt-get install -y python3 python3-pip python3-venv ffmpeg
    mkdir -p /opt/voxfoxbot
    python3 -m venv /opt/voxfoxbot/venv
    /opt/voxfoxbot/venv/bin/pip install python-telegram-bot librosa matplotlib numpy pillow
    EOF

  tags = {
    Name    = "voxfoxbot"
    Project = "voxfoxbot"
  }
}

output "instance_id" {
  value = aws_instance.voxfoxbot.id
}

output "public_ip" {
  value = aws_instance.voxfoxbot.public_ip
}
