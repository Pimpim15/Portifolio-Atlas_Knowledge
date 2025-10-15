variable "aws_region" {
  description = "Região AWS"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Ambiente (dev/stage/prod)"
  type        = string
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
