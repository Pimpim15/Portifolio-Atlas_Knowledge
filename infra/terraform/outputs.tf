output "vpc_id" {
  value = module.vpc.vpc_id
}

output "alb_dns" {
  value = module.alb.dns_name
}

output "api_service_name" {
  value = module.ecs.api_service_name
}
