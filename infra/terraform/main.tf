terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source      = "./modules/vpc"
  environment = var.environment
}

module "rds" {
  source             = "./modules/rds_postgres"
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  vpc_cidr_block     = module.vpc.cidr_block
}

module "opensearch" {
  source             = "./modules/opensearch"
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  vpc_cidr_block     = module.vpc.cidr_block
}

module "sqs" {
  source      = "./modules/sqs"
  environment = var.environment
}

module "alb" {
  source                 = "./modules/alb"
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  public_subnet_ids      = module.vpc.public_subnet_ids
  certificate_arn        = var.alb_certificate_arn
  allowed_cidrs          = var.alb_allowed_cidrs
  frontend_path_patterns = var.alb_frontend_path_patterns
}

module "ecs" {
  source                    = "./modules/ecs_service"
  environment               = var.environment
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  cluster_name              = "atlas-knowledge"
  rds_secret_arn            = module.rds.secret_arn
  opensearch_endpoint       = module.opensearch.endpoint
  sqs_queue_arn             = module.sqs.queue_arn
  sqs_queue_url             = module.sqs.queue_url
  alb_security_group_id     = module.alb.security_group_id
  api_target_group_arn      = module.alb.api_target_group_arn
  frontend_target_group_arn = module.alb.frontend_target_group_arn
  enable_frontend           = true
}

module "oidc" {
  source      = "./modules/iam_github_oidc"
  environment = var.environment
}
