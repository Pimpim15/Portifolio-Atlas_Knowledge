environment                = "prod"
aws_region                 = "us-east-1"
alb_certificate_arn        = "arn:aws:acm:us-east-1:123456789012:certificate/example-prod"
vpc_az_count               = 3
vpc_nat_gateway_per_az     = true
enable_rds_secret_rotation = true
rds_secret_rotation_days   = 30
