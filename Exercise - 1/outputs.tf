# Output values for the infrastructure

output "load_balancer_dns" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_url" {
  description = "URL to access the load balancer"
  value       = "http://${aws_lb.main.dns_name}"
}

output "web_server_ips" {
  description = "Public IP addresses of web servers"
  value       = aws_instance.web[*].public_ip
}

output "web_server_ids" {
  description = "Instance IDs of web servers"
  value       = aws_instance.web[*].id
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "nat_gateway_ips" {
  description = "Elastic IP addresses of NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}

output "target_group_arn" {
  description = "ARN of the target group"
  value       = aws_lb_target_group.web.arn
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}
