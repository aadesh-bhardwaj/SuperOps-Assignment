# Load-Balanced Web Server Environment

## 📋 Overview

This project implements a highly available, load-balanced web server environment using Terraform on AWS. It creates two nginx web servers behind an Application Load Balancer (ALB) with automatic failover capabilities.

## 🏗️ Architecture

The infrastructure consists of:
- **1 VPC** with 2 public subnets and 2 private subnets across different availability zones
- **1 Application Load Balancer (ALB)** in public subnets for distributing traffic
- **2 EC2 instances** running nginx web servers in private subnets
- **NAT Gateway(s)** for outbound internet access from private subnets
- **Elastic IP(s)** for NAT Gateway(s)
- **Security Groups** for ALB and EC2 instances
- **Target Group** with health checks for automatic failover
- **Internet Gateway** for public subnet connectivity
- **Route tables** for public and private subnets

## 🚀 Prerequisites

1. **AWS Account**: You need an AWS account with appropriate permissions
2. **AWS CLI**: Install and configure AWS CLI
   ```bash
   aws configure
   ```
3. **Terraform**: Install Terraform (version >= 1.0)
   - [Download Terraform](https://www.terraform.io/downloads.html)
4. **Git**: For version control

## 📦 Installation & Deployment

### Step 1: Clone the Repository
```bash
git clone <your-repository-url>
cd superops-assignment
```

### Step 2: Initialize Terraform
```bash
terraform init
```

### Step 3: Review the Configuration
Review and modify `variables.tf` if needed:
- `aws_region`: AWS region (default: us-east-1)
- `instance_count`: Number of web servers (default: 2)
- `instance_type`: EC2 instance type (default: t2.micro)
- `key_name`: SSH key pair name (optional, for SSH access)
- `enable_nat_gateway`: Enable NAT Gateway for private subnets (default: true)
- `single_nat_gateway`: Use single NAT Gateway for cost optimization (default: false)

### Step 4: Plan the Deployment
```bash
terraform plan
```

### Step 5: Deploy the Infrastructure
```bash
terraform apply
```
Type `yes` when prompted to confirm the deployment.

### Step 6: Get the Load Balancer URL
After successful deployment, Terraform will output the Load Balancer DNS:
```bash
terraform output load_balancer_url
```

## 🧪 Testing

### Test Load Balancing
```bash
# Test the load balancer (run multiple times to see different servers)
curl http://<load-balancer-dns>

# Or use a loop to see load distribution
for i in {1..10}; do 
    echo "Request $i:"
    curl -s http://<load-balancer-dns> | grep "Server"
    echo ""
done
```

### Test Failover
1. **Get instance IDs**:
   ```bash
   terraform output web_server_ids
   ```

2. **Stop one instance** (via AWS Console or CLI):
   ```bash
   aws ec2 stop-instances --instance-ids <instance-id> --region <your-region>
   ```

3. **Test the load balancer** (should still work):
   ```bash
   curl http://<load-balancer-dns>
   ```

4. **Restart the instance**:
   ```bash
   aws ec2 start-instances --instance-ids <instance-id> --region <your-region>
   ```

## 🔧 Configuration Details

### File Structure
```
.
├── main.tf           # Main Terraform configuration
├── variables.tf      # Variable definitions
├── outputs.tf        # Output definitions
├── user_data.sh      # EC2 user data script for nginx setup
├── terraform.tfvars  # Variable values (optional, create if needed)
├── README.md         # This file
└── .gitignore        # Git ignore file
```

### Security Groups
- **ALB Security Group**: Allows HTTP (80) from anywhere (public-facing)
- **Web Server Security Group**: Allows HTTP from ALB only, SSH from within VPC

### Health Checks
- **Path**: `/`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Healthy Threshold**: 2 consecutive successful checks
- **Unhealthy Threshold**: 2 consecutive failed checks

## 🧹 Cleanup

To destroy all created resources:
```bash
terraform destroy
```
Type `yes` when prompted to confirm.

## 💰 Cost Considerations

This infrastructure uses:
- 2 x t2.micro EC2 instances (Free tier eligible)
- 1 x Application Load Balancer (charges apply)
- 1-2 x NAT Gateways (charges apply - ~$45/month each)
- 1-2 x Elastic IPs (free when attached)
- VPC and networking components (mostly free)

**Estimated monthly cost**: 
- With single NAT Gateway: ~$65-75
- With multi-AZ NAT Gateways: ~$110-120
(varies by region and data transfer)

## 🔐 Security Best Practices

1. **Network Isolation**: EC2 instances are in private subnets
   - No direct internet access (inbound)
   - Outbound access through NAT Gateway
   - Only accessible through Load Balancer

2. **SSH Access**: SSH is restricted to VPC CIDR. For access:
   - Use AWS Systems Manager Session Manager (recommended)
   - Or set up a bastion host in public subnet
   - Or use VPN/Direct Connect

2. **HTTPS**: For production, implement:
   - SSL/TLS certificates (AWS Certificate Manager)
   - HTTPS listeners on the ALB
   - Redirect HTTP to HTTPS

3. **Secrets Management**: 
   - Use AWS Secrets Manager for sensitive data
   - Implement IAM roles for EC2 instances

## 📝 Customization

### Change the "Hello World" Message
Edit the `user_data.sh` file and modify the HTML content, then:
```bash
terraform apply -auto-approve
```

### Add More Web Servers
Change `instance_count` in `variables.tf` or:
```bash
terraform apply -var="instance_count=3"
```

### Use Different Instance Types
```bash
terraform apply -var="instance_type=t3.small"
```

### Use Single NAT Gateway (Cost Optimization)
```bash
terraform apply -var="single_nat_gateway=true"
```

### Disable NAT Gateway (for testing)
```bash
terraform apply -var="enable_nat_gateway=false"
```

## 🐛 Troubleshooting

### Issue: Instances not healthy in target group
- Check security group rules
- Verify nginx is running: SSH to instance and run `sudo systemctl status nginx`
- Check instance logs: `/var/log/user-data.log`

### Issue: Cannot access Load Balancer
- Verify security group allows port 80
- Check if instances are healthy in target group
- Ensure Internet Gateway is attached to VPC

### Issue: Terraform state issues
- Run `terraform refresh` to sync state
- Check AWS Console for manual changes

## 📊 Monitoring (Optional Enhancements)

Consider adding:
- CloudWatch alarms for unhealthy targets
- CloudWatch dashboards for metrics
- AWS X-Ray for distributed tracing
- ELB access logs to S3

## 👍 What I Liked About This Solution

1. **Infrastructure as Code**: Fully automated deployment using Terraform
2. **High Availability**: Multi-AZ deployment with automatic failover
3. **Scalability**: Easy to add/remove web servers
4. **Visual Feedback**: Beautiful HTML page showing which server is serving the request
5. **Security**: EC2 instances in private subnets with no direct internet access
6. **Flexibility**: Option for single or multi-AZ NAT Gateway deployment
7. **Best Practices**: Follows AWS Well-Architected Framework principles

## 👎 What Could Be Improved

1. **HTTPS Support**: Currently only HTTP, should add SSL/TLS with ACM
2. **Monitoring**: No built-in monitoring or alerting (CloudWatch, X-Ray)
3. **Logging**: Could implement centralized logging (CloudWatch Logs, ELK)
4. **Auto-scaling**: Fixed number of instances, could add auto-scaling groups
5. **Configuration Management**: Could use Ansible/Chef for more complex configurations
6. **State Management**: Terraform state is local, should use remote backend (S3)
7. **Cost Optimization**: NAT Gateway is expensive, could use NAT instances or VPC endpoints
8. **Bastion Host**: No bastion host for secure SSH access (if needed)

## 📚 References

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)
- [Nginx Documentation](https://nginx.org/en/docs/)

## 📧 Support

For questions or issues, please create an issue in the repository.

---

**Author**: Aadesh  
**Date**: December 2024  
**License**: MIT
