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

variable "enable_rds_secret_rotation" {
  description = "Ativa a rotação automática do segredo RDS via Lambda gerenciada"
  type        = bool
  default     = false
}

variable "rds_secret_rotation_days" {
  description = "Intervalo (dias) entre rotações automáticas do segredo"
  type        = number
  default     = 30
}

variable "rds_secret_rotation_password_length" {
  description = "Comprimento das senhas geradas pelo processo de rotação"
  type        = number
  default     = 30
}

variable "rds_allocated_storage" {
  description = "Armazenamento inicial (GB) da instância RDS"
  type        = number
  default     = 20
}

variable "rds_max_allocated_storage" {
  description = "Limite máximo (GB) para autoscaling de armazenamento do RDS"
  type        = number
  default     = 100
}

variable "rds_performance_insights_enabled" {
  description = "Habilita Performance Insights na instância RDS"
  type        = bool
  default     = false
}

variable "enable_cost_budget" {
  description = "Cria um orçamento mensal no AWS Budgets para o ambiente"
  type        = bool
  default     = false
}

variable "cost_budget_amount" {
  description = "Valor mensal (USD) do orçamento"
  type        = number
  default     = 300
}

variable "cost_budget_threshold_percent" {
  description = "Percentual do orçamento que aciona notificação"
  type        = number
  default     = 80
}

variable "cost_budget_emails" {
  description = "Lista de e-mails que receberão alertas do orçamento"
  type        = list(string)
  default     = []
}
