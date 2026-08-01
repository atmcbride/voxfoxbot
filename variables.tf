variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "tg_bot_token" {
  description = "Telegram bot token"
  type        = string
  sensitive   = true
}

variable "image_tag" {
  description = "Tag of the container image in ECR to deploy (CI passes the git SHA)"
  type        = string
}
