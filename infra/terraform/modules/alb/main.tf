variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "api_target_group" { type = string }
variable "fe_target_group" { type = string }

resource "aws_lb" "this" {
  name               = "atlas-${var.environment}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.public_subnet_ids
}

output "dns_name" {
  value = aws_lb.this.dns_name
}
