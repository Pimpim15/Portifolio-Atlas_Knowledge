locals {
  ecs_cluster_name            = module.ecs.cluster_name
  ecs_api_service_name        = module.ecs.api_service_name
  ecs_worker_service_name     = module.ecs.worker_service_name
  ecs_frontend_service_name   = try(module.ecs.frontend_service_name, null)
  sqs_queue_name              = module.sqs.queue_name
  sqs_dlq_name                = module.sqs.dlq_name
  rds_instance_identifier     = module.rds.instance_identifier
  ecs_api_log_group_name      = module.ecs.api_log_group_name
  ecs_worker_log_group_name   = module.ecs.worker_log_group_name
  ecs_frontend_log_group_name = try(module.ecs.frontend_log_group_name, null)
}

resource "aws_cloudwatch_dashboard" "atlas_operations" {
  dashboard_name = "atlas-${var.environment}-operations"
  dashboard_body = jsonencode({
    start          = "-P1D"
    periodOverride = "inherit"
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "SQS - Mensagens Visíveis"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", local.sqs_queue_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "SQS DLQ - Mensagens Visíveis"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", local.sqs_dlq_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ECS API - CPU Utilization"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", local.ecs_cluster_name, "ServiceName", local.ecs_api_service_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ECS Worker - CPU Utilization"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", local.ecs_cluster_name, "ServiceName", local.ecs_worker_service_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "RDS - Conexões"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", local.rds_instance_identifier]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "OpenSearch - Free Storage"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/ES", "FreeStorageSpace", "DomainName", "atlas-${var.environment}-os", { "stat" = "Minimum" }]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "ecs_api_cpu_high" {
  alarm_name          = "atlas-${var.environment}-ecs-api-cpu-high"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  evaluation_periods  = 3
  period              = 60
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  alarm_description   = "CPU da API acima de 80% por 3 minutos"
  dimensions = {
    ClusterName = local.ecs_cluster_name
    ServiceName = local.ecs_api_service_name
  }
  alarm_actions = var.cloudwatch_alarm_actions
  ok_actions    = var.cloudwatch_ok_actions
}

resource "aws_cloudwatch_metric_alarm" "ecs_api_memory_high" {
  alarm_name          = "atlas-${var.environment}-ecs-api-memory-high"
  namespace           = "AWS/ECS"
  metric_name         = "MemoryUtilization"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  evaluation_periods  = 3
  period              = 60
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  alarm_description   = "Memória da API acima de 80% por 3 minutos"
  dimensions = {
    ClusterName = local.ecs_cluster_name
    ServiceName = local.ecs_api_service_name
  }
  alarm_actions = var.cloudwatch_alarm_actions
  ok_actions    = var.cloudwatch_ok_actions
}

resource "aws_cloudwatch_metric_alarm" "ecs_worker_cpu_high" {
  alarm_name          = "atlas-${var.environment}-ecs-worker-cpu-high"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 70
  evaluation_periods  = 3
  period              = 60
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  alarm_description   = "CPU do worker acima de 70% por 3 minutos"
  dimensions = {
    ClusterName = local.ecs_cluster_name
    ServiceName = local.ecs_worker_service_name
  }
  alarm_actions = var.cloudwatch_alarm_actions
  ok_actions    = var.cloudwatch_ok_actions
}

resource "aws_cloudwatch_metric_alarm" "ecs_frontend_cpu_high" {
  count               = local.ecs_frontend_service_name != null ? 1 : 0
  alarm_name          = "atlas-${var.environment}-ecs-frontend-cpu-high"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 75
  evaluation_periods  = 3
  period              = 60
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  alarm_description   = "CPU do frontend acima de 75% por 3 minutos"
  dimensions = {
    ClusterName = local.ecs_cluster_name
    ServiceName = local.ecs_frontend_service_name
  }
  alarm_actions = var.cloudwatch_alarm_actions
  ok_actions    = var.cloudwatch_ok_actions
}

resource "aws_cloudwatch_query_definition" "worker_failures" {
  name            = "atlas-${var.environment}-worker-failures"
  log_group_names = [local.ecs_worker_log_group_name]
  query_string    = <<-EOT
    fields @timestamp, event, trace_id, 'atlas.worker.job_id' as job_id, 'atlas.worker.document_id' as document_id
    | filter component = "worker" and (level = "error" or level = "exception")
    | sort @timestamp desc
    | limit 50
  EOT
}

resource "aws_cloudwatch_query_definition" "api_5xx" {
  name            = "atlas-${var.environment}-api-5xx"
  log_group_names = [local.ecs_api_log_group_name]
  query_string    = <<-EOT
    fields @timestamp, route, status, trace_id
    | filter component = "api" and status >= 500
    | sort @timestamp desc
    | limit 50
  EOT
}

resource "aws_cloudwatch_query_definition" "frontend_errors" {
  count           = local.ecs_frontend_log_group_name != null ? 1 : 0
  name            = "atlas-${var.environment}-frontend-errors"
  log_group_names = [local.ecs_frontend_log_group_name]
  query_string    = <<-EOT
    fields @timestamp, @message
    | filter @message like /error|exception|warn/i
    | sort @timestamp desc
    | limit 50
  EOT
}