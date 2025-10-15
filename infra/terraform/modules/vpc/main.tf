variable "environment" {
  type = string
}

variable "cidr_block" {
  type        = string
  description = "CIDR principal da VPC"
  default     = "10.0.0.0/16"
}

variable "availability_zone_count" {
  type        = number
  description = "Quantidade de AZs a utilizar"
  default     = 2
}

variable "public_subnet_newbits" {
  type        = number
  description = "Quantidade de bits adicionados ao CIDR para subnets públicas"
  default     = 4
}

variable "private_subnet_newbits" {
  type        = number
  description = "Quantidade de bits adicionados ao CIDR para subnets privadas"
  default     = 4
}

variable "tags" {
  type        = map(string)
  description = "Tags adicionais para os recursos"
  default     = {}
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  requested_azs = max(1, min(var.availability_zone_count, length(data.aws_availability_zones.available.names)))
  azs           = slice(data.aws_availability_zones.available.names, 0, local.requested_azs)
  base_tags     = merge({ Environment = var.environment, Service = "atlas-knowledge", ManagedBy = "terraform" }, var.tags)
  public_map = {
    for idx, az in local.azs : tostring(idx) => {
      az     = az
      cidr   = cidrsubnet(var.cidr_block, var.public_subnet_newbits, idx)
      name   = "atlas-${var.environment}-public-${idx}"
      map_ip = true
    }
  }
  private_map = {
    for idx, az in local.azs : tostring(idx) => {
      az   = az
      cidr = cidrsubnet(var.cidr_block, var.private_subnet_newbits, idx + 8)
      name = "atlas-${var.environment}-private-${idx}"
    }
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.base_tags, { Name = "atlas-${var.environment}-vpc" })
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.base_tags, { Name = "atlas-${var.environment}-igw" })
}

resource "aws_subnet" "public" {
  for_each                = local.public_map
  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true
  tags = merge(
    local.base_tags,
    {
      Name        = each.value.name
      NetworkType = "public"
    }
  )
}

resource "aws_subnet" "private" {
  for_each          = local.private_map
  vpc_id            = aws_vpc.this.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az
  tags = merge(
    local.base_tags,
    {
      Name        = each.value.name
      NetworkType = "private"
    }
  )
}

resource "aws_eip" "nat" {
  for_each = local.public_map
  domain   = "vpc"
  tags     = merge(local.base_tags, { Name = "atlas-${var.environment}-nat-eip-${each.key}" })
}

resource "aws_nat_gateway" "nat" {
  for_each      = local.public_map
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  depends_on    = [aws_internet_gateway.igw]
  tags          = merge(local.base_tags, { Name = "atlas-${var.environment}-nat-${each.key}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.base_tags, { Name = "atlas-${var.environment}-public-rt" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  for_each = aws_subnet.private
  vpc_id   = aws_vpc.this.id
  tags = merge(
    local.base_tags,
    { Name = "atlas-${var.environment}-private-rt-${each.key}" }
  )
}

resource "aws_route" "private_nat" {
  for_each               = aws_subnet.private
  route_table_id         = aws_route_table.private[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat[each.key].id
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  value = [for subnet in aws_subnet.private : subnet.id]
}

output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "private_route_table_ids" {
  value = [for rt in aws_route_table.private : rt.id]
}

output "nat_gateway_ids" {
  value = [for nat in aws_nat_gateway.nat : nat.id]
}

output "nat_gateway_id" {
  value = try(aws_nat_gateway.nat["0"].id, null)
}

output "cidr_block" {
  value = var.cidr_block
}

output "availability_zones" {
  value = local.azs
}
