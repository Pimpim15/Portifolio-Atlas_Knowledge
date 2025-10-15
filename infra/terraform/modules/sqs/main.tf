variable "environment" {
  type = string
}

variable "visibility_timeout_seconds" {
  type        = number
  description = "Tempo de invisibilidade ao consumir mensagens"
  default     = 60
}

variable "message_retention_seconds" {
  type        = number
  description = "Tempo de retenção das mensagens na fila principal"
  default     = 345600
}

variable "dead_letter_retention_seconds" {
  type        = number
  description = "Tempo de retenção das mensagens na DLQ"
  default     = 1209600
}

variable "max_receive_count" {
  type        = number
  description = "Número máximo de tentativas antes de enviar para DLQ"
  default     = 5
}

variable "alarm_actions" {
  type        = list(string)
  description = "ARNs para acionar quando alarmes disparam"
  default     = []
}

variable "ok_actions" {
  type        = list(string)
  description = "ARNs para acionar quando alarmes normalizam"
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags adicionais para os recursos"
  default     = {}
}

locals {
  base_tags = merge(
    {
      Environment = var.environment
      Service     = "atlas-knowledge"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

resource "aws_sqs_queue" "docs_dlq" {
  name                      = "atlas-${var.environment}-docs-events-dlq"
  message_retention_seconds = var.dead_letter_retention_seconds
  sqs_managed_sse_enabled   = true
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = ["*"]
  })
  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-docs-events-dlq" })
}

resource "aws_sqs_queue" "docs" {
  name                       = "atlas-${var.environment}-docs-events"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.docs_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-docs-events" })
}

resource "aws_sqs_queue_redrive_allow_policy" "dlq_allow" {
  queue_url = aws_sqs_queue.docs_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.docs.arn]
  })
}

resource "aws_cloudwatch_metric_alarm" "queue_age_high" {
  alarm_name          = "atlas-${var.environment}-docs-queue-age-high"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.docs.name }
  comparison_operator = "GreaterThanThreshold"
  threshold           = 300
  evaluation_periods  = 2
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  alarm_description   = "Mensagens aguardando processamento há mais de 5 minutos na fila principal"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
  tags                = local.base_tags
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "atlas-${var.environment}-docs-dlq-depth"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.docs_dlq.name }
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 1
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "notBreaching"
  alarm_description   = "Existem mensagens na DLQ do pipeline de documentos"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions
  tags                = local.base_tags
}

output "queue_arn" {
  value = aws_sqs_queue.docs.arn
}

output "queue_url" {
  value = aws_sqs_queue.docs.id
}

output "queue_name" {
  value = aws_sqs_queue.docs.name
}

output "dlq_arn" {
  value = aws_sqs_queue.docs_dlq.arn
}

output "dlq_url" {
  value = aws_sqs_queue.docs_dlq.id
}

output "dlq_name" {
  value = aws_sqs_queue.docs_dlq.name
}
