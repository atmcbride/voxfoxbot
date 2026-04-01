terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# --- State bucket ---

resource "aws_s3_bucket" "tfstate" {
  bucket = "voxfoxbot-tfstate"
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- GitHub OIDC provider ---

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

# --- CI role scoped to voxfoxbot ---

resource "aws_iam_role" "ci" {
  name = "voxfoxbot-ci"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:atmcbride/voxfoxbot:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "ci_tfstate" {
  name = "voxfoxbot-ci-tfstate"
  role = aws_iam_role.ci.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "StateBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.tfstate.arn,
          "${aws_s3_bucket.tfstate.arn}/*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "ci_ec2" {
  name = "voxfoxbot-ci-ec2"
  role = aws_iam_role.ci.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2MutateTagged"
        Effect = "Allow"
        Action = [
          "ec2:TerminateInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:ModifyInstanceAttribute",
          "ec2:DeleteTags",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Project" = "voxfoxbot"
          }
        }
      },
      {
        Sid    = "EC2RunInstances"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
        ]
        Resource = [
          "arn:aws:ec2:us-east-1::image/*",
          "arn:aws:ec2:us-east-1:*:subnet/*",
          "arn:aws:ec2:us-east-1:*:network-interface/*",
          "arn:aws:ec2:us-east-1:*:volume/*",
          "arn:aws:ec2:us-east-1:*:key-pair/*",
          "arn:aws:ec2:us-east-1:*:security-group/*",
        ]
      },
      {
        Sid    = "EC2RunInstancesTagged"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
        ]
        Resource = "arn:aws:ec2:us-east-1:*:instance/*"
        Condition = {
          StringEquals = {
            "aws:RequestTag/Project" = "voxfoxbot"
          }
        }
      },
      {
        Sid    = "EC2CreateTagsOnLaunch"
        Effect = "Allow"
        Action = "ec2:CreateTags"
        Resource = "*"
        Condition = {
          StringEquals = {
            "ec2:CreateAction" = "RunInstances"
          }
        }
      },
      {
        Sid    = "EC2CreateTagsOnTagged"
        Effect = "Allow"
        Action = "ec2:CreateTags"
        Resource = "*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Project" = "voxfoxbot"
          }
        }
      },
      {
        Sid    = "SecurityGroupMutateTagged"
        Effect = "Allow"
        Action = [
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/Project" = "voxfoxbot"
          }
        }
      },
      {
        Sid    = "SecurityGroupCreate"
        Effect = "Allow"
        Action = "ec2:CreateSecurityGroup"
        Resource = [
          "arn:aws:ec2:us-east-1:*:security-group/*",
          "arn:aws:ec2:us-east-1:*:vpc/*",
        ]
      },
      {
        Sid    = "SecurityGroupCreateTags"
        Effect = "Allow"
        Action = "ec2:CreateTags"
        Resource = "arn:aws:ec2:us-east-1:*:security-group/*"
        Condition = {
          StringEquals = {
            "ec2:CreateAction" = "CreateSecurityGroup"
          }
        }
      },
      {
        Sid    = "DescribeReadOnly"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeInstanceAttribute",
          "ec2:DescribeImages",
          "ec2:DescribeTags",
          "ec2:DescribeVolumes",
          "ec2:DescribeKeyPairs",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSecurityGroupRules",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeAccountAttributes",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeInstanceCreditSpecifications",
        ]
        Resource = "*"
      }
    ]
  })
}

# --- Outputs ---

output "ci_role_arn" {
  value = aws_iam_role.ci.arn
}

output "tfstate_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}
