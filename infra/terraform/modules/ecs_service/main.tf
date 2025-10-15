variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "cluster_name" { type = string }
variable "rds_secret_arn" { type = string }
variable "opensearch_endpoint" { type = string }
variable "sqs_queue_arn" { type = string }
variable "sqs_queue_url" { type = string }
variable "alb_security_group_id" { type = string }
variable "api_target_group_arn" { type = string }
variable "frontend_target_group_arn" {
  type        = string
  default     = ""
  description = "Target group ARN para o frontend"
}
variable "api_image" {
  type    = string
  default = "123456789012.dkr.ecr.us-east-1.amazonaws.com/atlas-api:latest"
}
variable "worker_image" {
  type    = string
  default = "123456789012.dkr.ecr.us-east-1.amazonaws.com/atlas-worker:latest"
}
variable "frontend_image" {
  type    = string
  default = "123456789012.dkr.ecr.us-east-1.amazonaws.com/atlas-frontend:latest"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "api_min_capacity" {
  type    = number
  default = 2
}

variable "api_max_capacity" {
  type    = number
  default = 4
}

variable "api_scale_cpu_threshold" {
  type    = number
  default = 60
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

variable "frontend_desired_count" {
  type    = number
  default = 2
}

variable "frontend_min_capacity" {
  type    = number
  default = 2
}

variable "frontend_max_capacity" {
  type    = number
  default = 4
}

variable "frontend_scale_cpu_threshold" {
  type    = number
  default = 55
}

variable "enable_frontend" {
  type        = bool
  default     = false
  description = "Cria service Fargate para o frontend"
}

variable "enable_otel_sidecar" {
  type        = bool
  default     = false
  description = "Adiciona sidecar do AWS Distro for OpenTelemetry nas tasks"
}

variable "otel_collector_image" {
  type        = string
  default     = "public.ecr.aws/aws-observability/aws-otel-collector:latest"
  description = "Imagem usada pelo sidecar do ADOT collector"
}

data "aws_region" "current" {}

locals {
  api_environment = concat(
    [
      { name = "DATABASE_SECRET_ARN", value = var.rds_secret_arn },
      { name = "OPENSEARCH_ENDPOINT", value = var.opensearch_endpoint },
      { name = "SQS_QUEUE_ARN", value = var.sqs_queue_arn },
      { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
      { name = "AWS_REGION", value = data.aws_region.current.name }
    ],
    var.enable_otel_sidecar ? [
      { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://127.0.0.1:4317" },
      { name = "OTEL_EXPORTER_OTLP_PROTOCOL", value = "grpc" },
      { name = "OTEL_RESOURCE_ATTRIBUTES", value = "service.name=atlas-api,service.namespace=atlas-knowledge,deployment.environment=${var.environment}" }
    ] : []
  )

  worker_environment = concat(
    [
      { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
      { name = "SQS_QUEUE_ARN", value = var.sqs_queue_arn },
      { name = "OPENSEARCH_ENDPOINT", value = var.opensearch_endpoint },
      { name = "AWS_REGION", value = data.aws_region.current.name }
    ],
    var.enable_otel_sidecar ? [
      { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://127.0.0.1:4317" },
      { name = "OTEL_EXPORTER_OTLP_PROTOCOL", value = "grpc" },
      { name = "OTEL_RESOURCE_ATTRIBUTES", value = "service.name=atlas-worker,service.namespace=atlas-knowledge,deployment.environment=${var.environment}" }
    ] : []
  )

  adot_environment = [
    { name = "AWS_REGION", value = data.aws_region.current.name }
  ]

  api_container = merge(
    {
      name         = "api"
      image        = var.api_image
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
      environment = local.api_environment
    },
    var.enable_otel_sidecar ? {
      dependsOn = [{
        containerName = "adot"
        condition     = "START"
      }]
    } : {}
  )

  worker_container = merge(
    {
      name      = "worker"
      image     = var.worker_image
      essential = true
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
      environment = local.worker_environment
    },
    var.enable_otel_sidecar ? {
      dependsOn = [{
        containerName = "adot"
        condition     = "START"
      }]
    } : {}
  )

  api_adot_container = {
    name      = "adot"
    image     = var.otel_collector_image
    essential = true
    command   = ["--config=/etc/ecs/ecs-default-config.yaml"]
    environment = concat(
      local.adot_environment,
      [
        { name = "OTEL_RESOURCE_ATTRIBUTES", value = "service.name=atlas-api,service.namespace=atlas-knowledge,deployment.environment=${var.environment}" }
      ]
    )
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = try(aws_cloudwatch_log_group.api_adot[0].name, "")
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "ecs"
      }
    }
  }

  worker_adot_container = {
    name      = "adot"
    image     = var.otel_collector_image
    essential = true
    command   = ["--config=/etc/ecs/ecs-default-config.yaml"]
    environment = concat(
      local.adot_environment,
      [
        { name = "OTEL_RESOURCE_ATTRIBUTES", value = "service.name=atlas-worker,service.namespace=atlas-knowledge,deployment.environment=${var.environment}" }
      ]
    )
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = try(aws_cloudwatch_log_group.worker_adot[0].name, "")
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = "ecs"
      }
    }
  }
}

resource "aws_ecs_cluster" "this" {
  name = "${var.cluster_name}-${var.environment}"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/ecs/atlas-api-${var.environment}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/ecs/atlas-worker-${var.environment}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "api_adot" {
  count             = var.enable_otel_sidecar ? 1 : 0
  name              = "/aws/ecs/atlas-api-adot-${var.environment}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker_adot" {
  count             = var.enable_otel_sidecar ? 1 : 0
  name              = "/aws/ecs/atlas-worker-adot-${var.environment}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "frontend" {
  count             = var.enable_frontend ? 1 : 0
  name              = "/aws/ecs/atlas-frontend-${var.environment}"
  retention_in_days = 14
}

resource "aws_ecs_task_definition" "api" {
  family                   = "atlas-api-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode(
    concat(
      [local.api_container],
      var.enable_otel_sidecar ? [local.api_adot_container] : []
    )
  )
}

resource "aws_ecs_service" "api" {
  name                               = "atlas-api-${var.environment}"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.api_desired_count
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = true

  network_configuration {
    subnets          = var.private_subnet_ids
    assign_public_ip = false
    security_groups  = [aws_security_group.ecs_tasks.id]
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "atlas-worker-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode(
    concat(
      [local.worker_container],
      var.enable_otel_sidecar ? [local.worker_adot_container] : []
    )
  )
}

resource "aws_ecs_service" "worker" {
  name                   = "atlas-worker-${var.environment}"
  cluster                = aws_ecs_cluster.this.id
  task_definition        = aws_ecs_task_definition.worker.arn
  desired_count          = var.worker_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = true

  network_configuration {
    subnets          = var.private_subnet_ids
    assign_public_ip = false
    security_groups  = [aws_security_group.worker.id]
  }
}

resource "aws_ecs_task_definition" "frontend" {
  count                    = var.enable_frontend ? 1 : 0
  family                   = "atlas-frontend-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name         = "frontend"
      image        = var.frontend_image
      essential    = true
      portMappings = [{ containerPort = 80, protocol = "tcp" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.frontend[0].name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }
      environment = []
    }
  ])
}

resource "aws_ecs_service" "frontend" {
  count                              = var.enable_frontend && length(var.frontend_target_group_arn) > 0 ? 1 : 0
  name                               = "atlas-frontend-${var.environment}"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.frontend[0].arn
  desired_count                      = var.frontend_desired_count
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_execute_command             = true

  network_configuration {
    subnets          = var.private_subnet_ids
    assign_public_ip = false
    security_groups  = [aws_security_group.frontend[0].id]
  }

  load_balancer {
    target_group_arn = var.frontend_target_group_arn
    container_name   = "frontend"
    container_port   = 80
  }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "atlas-ecs-api-${var.environment}"
  description = "Permite ALB acessar tasks da API"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "worker" {
  name        = "atlas-ecs-worker-${var.environment}"
  description = "Permite worker sair para serviços externos"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "frontend" {
  count       = var.enable_frontend ? 1 : 0
  name        = "atlas-ecs-frontend-${var.environment}"
  description = "Permite ALB acessar tasks do frontend"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "task" {
  name = "atlas-task-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role" "execution" {
  name               = "atlas-execution-${var.environment}"
  assume_role_policy = aws_iam_role.task.assume_role_policy
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task" {
  name = "atlas-task-policy-${var.environment}"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes", "sqs:SendMessage"]
        Resource = [var.sqs_queue_arn]
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = concat(
          ["${aws_cloudwatch_log_group.api.arn}:*", "${aws_cloudwatch_log_group.worker.arn}:*"],
          var.enable_frontend ? ["${aws_cloudwatch_log_group.frontend[0].arn}:*"] : [],
          var.enable_otel_sidecar ? [
            "${aws_cloudwatch_log_group.api_adot[0].arn}:*",
            "${aws_cloudwatch_log_group.worker_adot[0].arn}:*"
          ] : []
        )
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.rds_secret_arn]
      }
    ]
  })
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_capacity
  min_capacity       = var.api_min_capacity
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "atlas-api-cpu-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.api_scale_cpu_threshold
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_target" "frontend" {
  count              = var.enable_frontend && length(var.frontend_target_group_arn) > 0 ? 1 : 0
  max_capacity       = var.frontend_max_capacity
  min_capacity       = var.frontend_min_capacity
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.frontend[0].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "frontend_cpu" {
  count              = var.enable_frontend && length(var.frontend_target_group_arn) > 0 ? 1 : 0
  name               = "atlas-frontend-cpu-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.frontend[0].resource_id
  scalable_dimension = aws_appautoscaling_target.frontend[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.frontend[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.frontend_scale_cpu_threshold
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_security_group_id" {
  value = aws_security_group.ecs_tasks.id
}

output "frontend_service_name" {
  value = try(aws_ecs_service.frontend[0].name, null)
}

output "frontend_security_group_id" {
  value = try(aws_security_group.frontend[0].id, null)
}

output "api_log_group_name" {
  value = aws_cloudwatch_log_group.api.name
}

output "worker_log_group_name" {
  value = aws_cloudwatch_log_group.worker.name
}

output "frontend_log_group_name" {
  value = try(aws_cloudwatch_log_group.frontend[0].name, null)
}
