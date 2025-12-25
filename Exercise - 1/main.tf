# Main Terraform configuration for load-balanced web servers
# This creates a secure, highly available web application infrastructure on AWS

# Terraform block defines version constraints and required providers
terraform {
  # Minimum Terraform version required to run this configuration
  required_version = ">= 1.0"
  
  # Define required providers and their version constraints
  required_providers {
    aws = {
      source  = "hashicorp/aws"  # Official HashiCorp AWS provider
      version = "~> 5.0"          # Allow 5.x versions (5.0, 5.1, etc.)
    }
  }
}

# Configure the AWS Provider with the target region
provider "aws" {
  region = var.aws_region  # Region is configurable via variables.tf
}

# Data source to dynamically fetch available Availability Zones in the region
# This ensures we use valid AZs regardless of which region is selected
data "aws_availability_zones" "available" {
  state = "available"  # Only return AZs that are currently available for use
}

# Data source to fetch the latest Amazon Linux 2 AMI
# This ensures we always use the most recent, patched version
data "aws_ami" "amazon_linux_2" {
  most_recent = true        # Get the newest AMI matching our criteria
  owners      = ["amazon"]  # Only AMIs owned by Amazon (official)

  # Filter for Amazon Linux 2 AMIs with specific naming pattern
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]  # Amazon Linux 2, HVM virtualization, x86_64 architecture, GP2 storage
  }

  # Ensure we get HVM (Hardware Virtual Machine) type for better performance
  filter {
    name   = "virtualization-type"
    values = ["hvm"]  # HVM provides better performance than PV (paravirtual)
  }
}

# Create Virtual Private Cloud (VPC) - the main network container for all resources
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr         # IP address range for the VPC (e.g., 10.0.0.0/16)
  enable_dns_hostnames = true                 # Allow DNS hostnames for EC2 instances
  enable_dns_support   = true                 # Enable DNS resolution within VPC

  tags = {
    Name        = "${var.project_name}-vpc"  # Concatenate project name with resource type
    Environment = var.environment             # Tag for environment identification (dev/staging/prod)
  }
}

# Create Internet Gateway - provides internet connectivity for public subnets
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id  # Attach IGW to our VPC

  tags = {
    Name        = "${var.project_name}-igw"  # Naming convention for easy identification
    Environment = var.environment              # Environment tag for resource management
  }
}

# Create public subnets for the Application Load Balancer
resource "aws_subnet" "public" {
  count                   = 2                    # Create 2 public subnets for high availability
  vpc_id                  = aws_vpc.main.id      # Associate subnet with our VPC
  
  # Calculate subnet CIDR dynamically (e.g., 10.0.0.0/24, 10.0.1.0/24)
  # cidrsubnet function: (prefix, newbits, netnum)
  # - prefix: base CIDR (var.vpc_cidr)
  # - newbits: 8 means add 8 bits to subnet mask (16 -> 24)
  # - netnum: count.index (0, 1) determines which subnet
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  
  # Place each subnet in a different AZ for high availability
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  
  # Auto-assign public IPs to resources launched in these subnets
  map_public_ip_on_launch = true

  # Explicit dependency to ensure VPC is created first
  depends_on = [
    aws_vpc.main
  ]

  tags = {
    Name        = "${var.project_name}-public-subnet-${count.index + 1}"  # Human-readable name
    Environment = var.environment                                           # Environment identifier
  }
}

# Create route table for public subnets - defines how traffic is directed
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id  # Associate route table with our VPC

  # Define route for internet-bound traffic
  route {
    cidr_block = "0.0.0.0/0"                   # All traffic not destined for local VPC
    gateway_id = aws_internet_gateway.main.id  # Route through Internet Gateway
  }

  # Ensure IGW exists before creating route table
  depends_on = [
    aws_internet_gateway.main
  ]

  tags = {
    Name        = "${var.project_name}-public-rt"  # Descriptive name for the route table
    Environment = var.environment                    # Environment tag
  }
}

# Associate route table with public subnets - links subnets to routing rules
resource "aws_route_table_association" "public" {
  count          = 2                                    # One association per public subnet
  subnet_id      = aws_subnet.public[count.index].id   # Reference each subnet by index
  route_table_id = aws_route_table.public.id           # Link to public route table

  # Ensure both resources exist before creating association
  depends_on = [
    aws_subnet.public,        # Public subnets must exist
    aws_route_table.public    # Route table must exist
  ]
}

# Create private subnets for EC2 instances - isolated from direct internet access
resource "aws_subnet" "private" {
  count                   = 2                      # Create 2 private subnets for HA
  vpc_id                  = aws_vpc.main.id        # Associate with our VPC
  
  # Calculate private subnet CIDRs (e.g., 10.0.10.0/24, 10.0.11.0/24)
  # Adding 10 to count.index ensures private subnets don't overlap with public
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  
  # Distribute across AZs for high availability
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  
  # Don't auto-assign public IPs - these are private subnets
  map_public_ip_on_launch = false

  # Ensure VPC exists first
  depends_on = [
    aws_vpc.main
  ]

  tags = {
    Name        = "${var.project_name}-private-subnet-${count.index + 1}"  # Clear naming
    Environment = var.environment                                            # Environment tag
  }
}

# Allocate Elastic IPs for NAT Gateways - static public IPs for outbound traffic
resource "aws_eip" "nat" {
  # Conditional count based on NAT Gateway configuration:
  # - If NAT disabled: 0 EIPs
  # - If single NAT: 1 EIP
  # - If multi-AZ NAT: 2 EIPs
  count  = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : 2) : 0
  
  domain = "vpc"  # Allocate EIP for use in VPC (not EC2-Classic)

  # EIP requires IGW to exist first
  depends_on = [
    aws_internet_gateway.main
  ]

  tags = {
    Name        = "${var.project_name}-eip-${count.index + 1}"  # Identify which EIP
    Environment = var.environment                                 # Environment tag
  }
}

# Create NAT Gateway(s) - enables outbound internet access for private subnets
resource "aws_nat_gateway" "main" {
  # Conditional creation based on configuration
  count         = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : 2) : 0
  
  # Assign the Elastic IP to this NAT Gateway
  allocation_id = aws_eip.nat[count.index].id
  
  # NAT Gateway must be in a public subnet (needs internet access)
  subnet_id     = aws_subnet.public[count.index].id

  # NAT Gateway needs both IGW and public subnets to function
  depends_on = [
    aws_internet_gateway.main,  # For internet connectivity
    aws_subnet.public           # Must be placed in public subnet
  ]

  tags = {
    Name        = "${var.project_name}-nat-${count.index + 1}"  # Identify NAT Gateway
    Environment = var.environment                                 # Environment tag
  }
}

# Create route table for private subnets - routes outbound traffic through NAT
resource "aws_route_table" "private" {
  # Create 1 or 2 route tables based on NAT configuration
  count  = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : 2) : 0
  vpc_id = aws_vpc.main.id  # Associate with VPC

  # Route for internet-bound traffic from private subnets
  route {
    cidr_block     = "0.0.0.0/0"  # All non-local traffic
    
    # Route through NAT Gateway:
    # - If single NAT: all use NAT Gateway 0
    # - If multi-AZ: each uses its own NAT Gateway
    nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.main[0].id : aws_nat_gateway.main[count.index].id
  }

  # Ensure NAT Gateway exists before creating route
  depends_on = [
    aws_nat_gateway.main
  ]

  tags = {
    Name        = "${var.project_name}-private-rt-${count.index + 1}"  # Identify route table
    Environment = var.environment                                        # Environment tag
  }
}

# Associate private route tables with private subnets - links routing rules
resource "aws_route_table_association" "private" {
  count          = 2  # One association per private subnet
  subnet_id      = aws_subnet.private[count.index].id  # Each private subnet
  
  # Complex routing logic:
  # - If NAT enabled + single NAT: both subnets use route table 0
  # - If NAT enabled + multi-AZ: each subnet uses its own route table
  # - If NAT disabled: use public route table (for testing only)
  route_table_id = var.enable_nat_gateway ? (var.single_nat_gateway ? aws_route_table.private[0].id : aws_route_table.private[count.index].id) : aws_route_table.public.id

  # Ensure resources exist before association
  depends_on = [
    aws_subnet.private,         # Private subnets must exist
    aws_route_table.private    # Private route tables must exist
  ]
}

# Create VPC Endpoint for S3 - allows private access to S3 for package downloads
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  
  # Associate with all route tables (both public and private)
  route_table_ids = concat(
    [aws_route_table.public.id],
    var.enable_nat_gateway ? aws_route_table.private[*].id : []
  )

  tags = {
    Name        = "${var.project_name}-s3-endpoint"
    Environment = var.environment
  }
}

# Security group for ALB - firewall rules for the load balancer
resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-sg"              # Auto-generate unique name with prefix
  description = "Security group for Application Load Balancer"  # Description for clarity
  vpc_id      = aws_vpc.main.id                            # Attach to our VPC

  # Inbound rule: Allow HTTP traffic from the internet
  ingress {
    description = "HTTP from anywhere"     # Rule description
    from_port   = 80                       # Starting port
    to_port     = 80                       # Ending port (same for single port)
    protocol    = "tcp"                    # TCP protocol for HTTP
    cidr_blocks = ["0.0.0.0/0"]           # Allow from any IP (public facing)
  }

  # Outbound rule: Allow all traffic (needed to reach EC2 instances)
  egress {
    description = "Allow all outbound traffic"  # Rule description
    from_port   = 0                             # All ports
    to_port     = 0                             # All ports
    protocol    = "-1"                          # All protocols (-1 means all)
    cidr_blocks = ["0.0.0.0/0"]                # To any destination
  }

  tags = {
    Name        = "${var.project_name}-alb-sg"  # Identifiable name
    Environment = var.environment                 # Environment tag
  }
}

# Security group for web servers - firewall rules for EC2 instances
resource "aws_security_group" "web" {
  name_prefix = "${var.project_name}-web-sg"                   # Auto-generate unique name
  description = "Security group for web servers in private subnets"  # Clear description
  vpc_id      = aws_vpc.main.id                                # Attach to VPC

  # ALB security group must exist first (referenced in ingress rule)
  depends_on = [
    aws_security_group.alb
  ]

  # Inbound rule 1: Allow HTTP only from ALB (not directly from internet)
  ingress {
    description     = "HTTP from ALB"                      # Rule purpose
    from_port       = 80                                   # HTTP port
    to_port         = 80                                   # HTTP port
    protocol        = "tcp"                                # TCP for HTTP
    security_groups = [aws_security_group.alb.id]         # Only from ALB security group
  }

  # Inbound rule 2: Allow SSH from within VPC (for management)
  ingress {
    description = "SSH from VPC (for management via bastion or SSM)"  # Rule purpose
    from_port   = 22                                                   # SSH port
    to_port     = 22                                                   # SSH port
    protocol    = "tcp"                                                # TCP for SSH
    cidr_blocks = [var.vpc_cidr]                                      # Only from VPC IPs
  }

  # Outbound rule: Allow all (needed for updates, package downloads via NAT)
  egress {
    description = "Allow all outbound traffic"  # For internet access via NAT
    from_port   = 0                             # All ports
    to_port     = 0                             # All ports
    protocol    = "-1"                          # All protocols
    cidr_blocks = ["0.0.0.0/0"]                # To anywhere
  }

  tags = {
    Name        = "${var.project_name}-web-sg"  # Identifiable name
    Environment = var.environment                 # Environment tag
  }
}

# Create EC2 instances in private subnets - the web servers running nginx
resource "aws_instance" "web" {
  count                  = var.instance_count               # Number of instances (default: 2)
  ami                    = data.aws_ami.amazon_linux_2.id   # Use latest Amazon Linux 2 AMI
  instance_type          = var.instance_type                # Instance size (default: t2.micro)
  
  # Distribute instances across private subnets using modulo operator
  # Instance 0 -> private subnet 0, Instance 1 -> private subnet 1
  subnet_id              = aws_subnet.private[count.index % 2].id
  
  vpc_security_group_ids = [aws_security_group.web.id]     # Apply web server security group
  key_name              = var.key_name                     # SSH key pair (optional)

  # User data script runs on first boot to install/configure nginx
  # templatefile() allows passing variables to the script
  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    server_id = count.index + 1  # Pass server number to script (1, 2, etc.)
  }))

  # Configure root EBS volume
  root_block_device {
    volume_type = "gp3"     # Latest generation SSD
    volume_size = 8         # Size in GB
    encrypted   = true      # Enable encryption at rest
  }

  # Ensure network infrastructure is ready before launching instances
  depends_on = [
    aws_route_table_association.private,  # Private subnet routing must be configured
    aws_security_group.web,               # Security group must exist
    aws_nat_gateway.main                  # NAT Gateway needed for internet access during setup
  ]

  tags = {
    Name        = "${var.project_name}-web-${count.index + 1}"  # e.g., superops-web-1, superops-web-2
    Environment = var.environment                                 # Environment tag
  }
}

# Create Application Load Balancer - distributes traffic to web servers
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"      # ALB name (must be unique in region)
  internal           = false                          # Internet-facing (not internal)
  load_balancer_type = "application"                  # ALB (Layer 7) vs NLB (Layer 4)
  security_groups    = [aws_security_group.alb.id]    # Apply ALB security group
  
  # Deploy ALB across all public subnets for high availability
  # The [*] syntax gets all elements from the list
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false  # Allow Terraform to delete (disable in production)
  enable_http2              = true    # Enable HTTP/2 for better performance

  # Ensure networking is ready before creating ALB
  depends_on = [
    aws_internet_gateway.main,  # Need internet connectivity
    aws_subnet.public           # Need public subnets
  ]

  tags = {
    Name        = "${var.project_name}-alb"  # Identifiable name
    Environment = var.environment              # Environment tag
  }
}

# Create target group - defines how ALB routes traffic to instances
resource "aws_lb_target_group" "web" {
  name     = "${var.project_name}-tg"  # Target group name
  port     = 80                         # Port where targets receive traffic
  protocol = "HTTP"                     # Protocol for traffic
  vpc_id   = aws_vpc.main.id           # VPC where targets are located

  # Health check configuration - determines if instances are healthy
  health_check {
    enabled             = true     # Enable health checks
    healthy_threshold   = 2        # Number of consecutive successful checks to mark healthy
    unhealthy_threshold = 2        # Number of consecutive failed checks to mark unhealthy
    timeout             = 5        # Seconds to wait for response
    interval            = 30       # Seconds between health checks
    path                = "/"      # URL path to check
    matcher             = "200"    # Expected HTTP status code for healthy response
  }

  tags = {
    Name        = "${var.project_name}-tg"  # Identifiable name
    Environment = var.environment             # Environment tag
  }
}

# Attach EC2 instances to target group - registers instances with load balancer
resource "aws_lb_target_group_attachment" "web" {
  count            = var.instance_count                 # One attachment per instance
  target_group_arn = aws_lb_target_group.web.arn       # ARN of the target group
  target_id        = aws_instance.web[count.index].id  # ID of each EC2 instance
  port             = 80                                # Port where instance receives traffic

  # Ensure both resources exist before creating attachment
  depends_on = [
    aws_instance.web,          # EC2 instances must exist
    aws_lb_target_group.web   # Target group must exist
  ]
}

# Create ALB listener - defines how ALB handles incoming requests
resource "aws_lb_listener" "web" {
  load_balancer_arn = aws_lb.main.arn  # Attach listener to our ALB
  port              = "80"              # Listen on port 80 (HTTP)
  protocol          = "HTTP"            # Protocol to listen for

  # Default action when request is received
  default_action {
    type             = "forward"                      # Action type (forward traffic)
    target_group_arn = aws_lb_target_group.web.arn   # Forward to this target group
  }

  # Ensure ALB and target group exist before creating listener
  depends_on = [
    aws_lb.main,              # ALB must exist
    aws_lb_target_group.web   # Target group must exist
  ]
}
