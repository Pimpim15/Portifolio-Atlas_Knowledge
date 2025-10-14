variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "cluster_name" { type = string }
variable "rds_secret_arn" { type = string }
variable "opensearch_endpoint" { type = string }
variable "sqs_queue_arn" { type = string }

resource "aws_ecs_cluster" "this" {
  name = "${var.cluster_name}-${var.environment}"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/ecs/atlas-api-${var.environment}"
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

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/atlas-api:latest"
      essential = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = "us-east-1"
          awslogs-stream-prefix = "ecs"
        }
      }
      environment = [
        { name = "DATABASE_SECRET_ARN", value = var.rds_secret_arn },
        { name = "OPENSEARCH_ENDPOINT", value = var.opensearch_endpoint },
        { name = "SQS_QUEUE_ARN", value = var.sqs_queue_arn }
      ]
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "atlas-api-${var.environment}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    assign_public_ip = false
    security_groups = [aws_security_group.ecs.id]
  }
}

resource "aws_security_group" "ecs" {
  name        = "atlas-ecs-${var.environment}"
  description = "Acesso interno ECS"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
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
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role" "execution" {
  name = "atlas-execution-${var.environment}"
  assume_role_policy = aws_iam_role.task.assume_role_policy
}

output "api_target_group" {
  value = "atlas-api-tg-placeholder"
}

output "frontend_target_group" {
  value = "atlas-frontend-tg-placeholder"
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}
