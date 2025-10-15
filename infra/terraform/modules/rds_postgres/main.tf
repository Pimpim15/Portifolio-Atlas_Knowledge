terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "vpc_cidr_block" { type = string }
variable "db_name" {
  type        = string
  default     = "atlas"
  description = "Nome do banco principal"
}
variable "db_username" {
  type        = string
  default     = "atlas"
  description = "Usuário administrador do banco"
}
variable "multi_az" {
  type        = bool
  default     = false
  description = "Ativa instância Multi-AZ"
}

variable "enable_secret_rotation" {
  type        = bool
  default     = false
  description = "Habilita rotação automática do segredo no Secrets Manager"
}

variable "secret_rotation_lambda_arn" {
  type        = string
  default     = null
  description = "ARN da função Lambda responsável pela rotação do segredo"
}

variable "secret_rotation_days" {
  type        = number
  default     = 30
  description = "Intervalo (dias) para rotacionar automaticamente o segredo"
}

locals {
  base_tags = {
    Environment = var.environment
    Service     = "atlas-knowledge"
    ManagedBy   = "terraform"
  }
}

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*-=+"
}

resource "aws_db_subnet_group" "this" {
  name       = "atlas-${var.environment}-db-subnet"
  subnet_ids = var.private_subnet_ids
  tags       = merge(local.base_tags, { Name = "atlas-${var.environment}-db-subnet" })
}

resource "aws_security_group" "db" {
  name        = "atlas-${var.environment}-db-sg"
  description = "Acesso ao banco Postgres do Atlas"
  vpc_id      = var.vpc_id

  ingress {
    description = "Acesso interno na VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-db-sg" })
}

resource "aws_db_instance" "this" {
  identifier                 = "atlas-${var.environment}-pg"
  engine                     = "postgres"
  engine_version             = "15.5"
  instance_class             = "db.t4g.micro"
  allocated_storage          = 20
  username                   = var.db_username
  password                   = random_password.db.result
  db_name                    = var.db_name
  db_subnet_group_name       = aws_db_subnet_group.this.name
  skip_final_snapshot        = true
  publicly_accessible        = false
  multi_az                   = var.multi_az
  storage_encrypted          = true
  backup_retention_period    = 7
  auto_minor_version_upgrade = true
  deletion_protection        = false
  vpc_security_group_ids     = [aws_security_group.db.id]

  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-pg" })
}

resource "aws_secretsmanager_secret" "db" {
  name = "atlas/${var.environment}/database"
  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-db-secret" })
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    engine   = aws_db_instance.this.engine
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = var.db_name
  })
  depends_on = [aws_db_instance.this]
}

resource "aws_secretsmanager_secret_rotation" "db" {
  count               = var.enable_secret_rotation ? 1 : 0
  secret_id           = aws_secretsmanager_secret.db.id
  rotation_lambda_arn = var.secret_rotation_lambda_arn

  rotation_rules {
    automatically_after_days = var.secret_rotation_days
  }

  lifecycle {
    precondition {
      condition     = var.secret_rotation_lambda_arn != null && var.secret_rotation_lambda_arn != ""
      error_message = "secret_rotation_lambda_arn deve ser informado quando enable_secret_rotation estiver habilitado."
    }
  }
}

output "secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "endpoint" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "security_group_id" {
  value = aws_security_group.db.id
}

output "instance_identifier" {
  value = aws_db_instance.this.id
}
