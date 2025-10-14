variable "environment" { type = string }
variable "vpc_id" { type = string }

resource "aws_db_subnet_group" "this" {
  name       = "atlas-${var.environment}-db-subnet"
  subnet_ids = []
}

resource "aws_db_instance" "this" {
  identifier              = "atlas-${var.environment}-pg"
  engine                  = "postgres"
  engine_version          = "15.5"
  instance_class          = "db.t4g.micro"
  allocated_storage       = 20
  username                = "atlas"
  password                = "temporary-password"
  db_subnet_group_name    = aws_db_subnet_group.this.name
  skip_final_snapshot     = true
  publicly_accessible     = false
  multi_az                = false
  storage_encrypted       = true
}

output "secret_arn" {
  value = "arn:aws:secretsmanager:us-east-1:123456789012:secret:atlas/${var.environment}/db"
}
