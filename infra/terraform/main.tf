terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source = "./modules/vpc"
  environment = var.environment
}

module "rds" {
  source      = "./modules/rds_postgres"
  environment = var.environment
  vpc_id      = module.vpc.vpc_id
}

module "opensearch" {
  source      = "./modules/opensearch"
  environment = var.environment
  vpc_id      = module.vpc.vpc_id
}

module "sqs" {
  source      = "./modules/sqs"
  environment = var.environment
}

module "ecs" {
  source              = "./modules/ecs_service"
  environment         = var.environment
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  cluster_name        = "atlas-knowledge"
  rds_secret_arn      = module.rds.secret_arn
  opensearch_endpoint = module.opensearch.endpoint
  sqs_queue_arn       = module.sqs.queue_arn
}

module "alb" {
  source             = "./modules/alb"
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  api_target_group   = module.ecs.api_target_group
  fe_target_group    = module.ecs.frontend_target_group
}

module "oidc" {
  source      = "./modules/iam_github_oidc"
  environment = var.environment
}
