variable "environment" { type = string }

resource "aws_secretsmanager_secret" "jwt_private" {
  name = "atlas/${var.environment}/jwt/private"
}

resource "aws_secretsmanager_secret" "jwt_public" {
  name = "atlas/${var.environment}/jwt/public"
}

output "private_secret_arn" {
  value = aws_secretsmanager_secret.jwt_private.arn
}

output "public_secret_arn" {
  value = aws_secretsmanager_secret.jwt_public.arn
}
