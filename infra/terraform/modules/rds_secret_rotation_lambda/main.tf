terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

variable "environment" {
  description = "Ambiente (dev/stage/prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID da VPC onde a função Lambda será executada"
  type        = string
}

variable "subnet_ids" {
  description = "Subnets privadas usadas pela função de rotação"
  type        = list(string)
}

variable "secret_arn" {
  description = "ARN do segredo armazenando as credenciais do banco"
  type        = string
}

variable "db_instance_identifier" {
  description = "Identificador da instância RDS alvo da rotação"
  type        = string
}

variable "password_length" {
  description = "Comprimento das senhas geradas durante a rotação"
  type        = number
  default     = 30
}

variable "log_retention_in_days" {
  description = "Retenção (dias) dos logs da função Lambda"
  type        = number
  default     = 14
}

locals {
  name_prefix = "atlas-${var.environment}-rds-rotation"
  tags = {
    Environment = var.environment
    Service     = "atlas-knowledge"
    ManagedBy   = "terraform"
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../../functions/rds_secret_rotation"
  output_path = "${path.module}/build/rotation_lambda.zip"
}

resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-sg"
  description = "Permite a função de rotação acessar recursos internos"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-sg" })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}"
  retention_in_days = var.log_retention_in_days
  tags              = local.tags
}

resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.name_prefix}-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:UpdateSecretVersionStage",
          "secretsmanager:PutSecretValue",
          "secretsmanager:GetRandomPassword"
        ]
        Resource = var.secret_arn
      },
      {
        Effect = "Allow"
        Action = [
          "rds:ModifyDBInstance",
          "rds:DescribeDBInstances"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "this" {
  function_name    = local.name_prefix
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 900
  memory_size      = 256

  environment {
    variables = {
      DB_INSTANCE_IDENTIFIER = var.db_instance_identifier
      PASSWORD_LENGTH        = tostring(var.password_length)
      EXCLUDE_CHARACTERS     = "\"\\/@"
    }
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  depends_on = [aws_iam_role_policy.lambda]
  tags       = local.tags
}

resource "aws_lambda_permission" "allow_secrets_manager" {
  statement_id  = "AllowSecretsManagerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "secretsmanager.amazonaws.com"
}

output "lambda_arn" {
  value = aws_lambda_function.this.arn
}
