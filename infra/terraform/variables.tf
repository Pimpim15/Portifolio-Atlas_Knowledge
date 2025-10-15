variable "aws_region" {
  description = "Região AWS"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Ambiente (dev/stage/prod)"
  type        = string
}

variable "vpc_az_count" {
  description = "Quantidade de zonas de disponibilidade usadas pela VPC"
  type        = number
  default     = 2
}

variable "vpc_nat_gateway_per_az" {
  description = "Define se a VPC cria um NAT Gateway por AZ (true) ou apenas um compartilhado (false)"
  type        = bool
  default     = true
}

variable "alb_certificate_arn" {
  description = "ARN do certificado ACM utilizado pelo ALB"
  type        = string
}

variable "alb_allowed_cidrs" {
  description = "CIDRs autorizados a acessar o ALB"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "alb_frontend_path_patterns" {
  description = "Paths encaminhados para o target group do frontend"
  type        = list(string)
  default     = ["/app/*"]
}

variable "cloudwatch_alarm_actions" {
  description = "ARNs acionados quando alarmes CloudWatch disparam"
  type        = list(string)
  default     = []
}

variable "cloudwatch_ok_actions" {
  description = "ARNs acionados quando alarmes CloudWatch retornam ao estado OK"
  type        = list(string)
  default     = []
}
