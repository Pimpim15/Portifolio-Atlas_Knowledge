variable "environment" { type = string }

resource "aws_sqs_queue" "docs" {
  name                       = "atlas-${var.environment}-docs-events"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 345600
}

resource "aws_sqs_queue" "docs_dlq" {
  name = "atlas-${var.environment}-docs-events-dlq"
}

output "queue_arn" {
  value = aws_sqs_queue.docs.arn
}

output "queue_url" {
  value = aws_sqs_queue.docs.id
}
