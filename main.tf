terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
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

# --- Container registry ---

resource "aws_ecr_repository" "voxfoxbot" {
  name         = "voxfoxbot"
  force_delete = true

  tags = {
    Project = "voxfoxbot"
  }
}

# --- State: per-chat settings, unique-user stats ---

resource "aws_dynamodb_table" "voxfoxbot" {
  name         = "voxfoxbot"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  tags = {
    Project = "voxfoxbot"
  }
}

# --- Lambda ---

# Telegram echoes this back in the X-Telegram-Bot-Api-Secret-Token header so
# the public Function URL only accepts genuine webhook calls.
resource "random_password" "webhook_secret" {
  length  = 48
  special = false
}

resource "aws_iam_role" "lambda" {
  name = "voxfoxbot-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = "voxfoxbot"
  }
}

resource "aws_cloudwatch_log_group" "voxfoxbot" {
  name              = "/aws/lambda/voxfoxbot"
  retention_in_days = 30

  tags = {
    Project = "voxfoxbot"
  }
}

resource "aws_iam_role_policy" "lambda_base" {
  name = "voxfoxbot-lambda-base"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.voxfoxbot.arn}:*"
      },
      {
        Sid    = "Dynamo"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
        ]
        Resource = aws_dynamodb_table.voxfoxbot.arn
      },
    ]
  })
}

resource "aws_lambda_function" "voxfoxbot" {
  function_name = "voxfoxbot"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.voxfoxbot.repository_url}:${var.image_tag}"

  timeout     = 600
  memory_size = 3008

  ephemeral_storage {
    size = 1024
  }

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.tg_bot_token
      TG_WEBHOOK_SECRET  = random_password.webhook_secret.result
      VOXFOX_DDB_TABLE   = aws_dynamodb_table.voxfoxbot.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.voxfoxbot]

  tags = {
    Project = "voxfoxbot"
  }
}

# Defined after the function to avoid a role<->function reference cycle.
resource "aws_iam_role_policy" "lambda_self_invoke" {
  name = "voxfoxbot-lambda-self-invoke"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "SelfInvoke"
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.voxfoxbot.arn
    }]
  })
}

# One attempt per update, like the old polling bot — a failed render should
# not be retried minutes later with a duplicate video.
resource "aws_lambda_function_event_invoke_config" "voxfoxbot" {
  function_name          = aws_lambda_function.voxfoxbot.function_name
  maximum_retry_attempts = 0
}

resource "aws_lambda_function_url" "webhook" {
  function_name      = aws_lambda_function.voxfoxbot.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "webhook" {
  statement_id           = "AllowFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.voxfoxbot.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# --- Outputs ---

output "webhook_url" {
  value = aws_lambda_function_url.webhook.function_url
}

output "webhook_secret" {
  value     = random_password.webhook_secret.result
  sensitive = true
}

output "ecr_repository_url" {
  value = aws_ecr_repository.voxfoxbot.repository_url
}
