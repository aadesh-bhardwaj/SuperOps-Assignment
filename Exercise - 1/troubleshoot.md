# Troubleshooting Guide for Unhealthy Targets

## Common Issues and Solutions

### 1. NAT Gateway Issues
**Problem**: EC2 instances in private subnets can't reach the internet to download packages.

**Solution Applied**: 
- NAT Gateway is enabled in your configuration
- Added VPC Endpoint for S3 to improve package downloads

### 2. User Data Script Issues
**Problem**: Nginx might not be installing correctly on Amazon Linux 2.

**Solutions Applied**:
- Added logging to `/var/log/user-data.log`
- Added alternative nginx installation method
- Added verification steps

### 3. To Apply the Fixes:

```bash
# Destroy and recreate the instances with updated user data
terraform destroy -target=aws_instance.web -auto-approve
terraform apply -auto-approve
```

### 4. Manual Verification Steps:

If you have SSH access, connect to an instance and check:

```bash
# Check user data log
sudo tail -f /var/log/user-data.log

# Check nginx status
sudo systemctl status nginx

# Check if nginx is listening
sudo netstat -tlnp | grep :80

# Test locally
curl http://localhost/

# Check cloud-init log
sudo cat /var/log/cloud-init-output.log
```

### 5. AWS Console Checks:

1. **VPC Flow Logs**: Check if traffic is reaching the instances
2. **Target Group Health Check Settings**: 
   - Path: `/`
   - Port: 80
   - Protocol: HTTP
   - Healthy threshold: 2
   - Unhealthy threshold: 2
   - Timeout: 5 seconds
   - Interval: 30 seconds

3. **Security Groups**:
   - ALB security group allows inbound HTTP (port 80) from 0.0.0.0/0
   - Web security group allows inbound HTTP (port 80) from ALB security group
   - Web security group allows all outbound traffic

### 6. Quick Test Without NAT Gateway:

If you want to test without NAT Gateway costs:

```bash
# Temporarily move instances to public subnets
terraform apply -var="enable_nat_gateway=false"
```

### 7. Alternative: Use Systems Manager to Check

If instances have SSM agent (they should on Amazon Linux 2):

1. Go to AWS Systems Manager > Session Manager
2. Start a session to connect to your instance
3. Check nginx status without needing SSH

### 8. Common Region-Specific Issues:

In `ap-south-1` (Mumbai), sometimes there are delays in:
- NAT Gateway provisioning
- Package repository access

**Solution**: Wait 5-10 minutes after deployment for everything to stabilize.

## Next Steps:

1. **Apply the updated configuration**:
   ```bash
   terraform apply -auto-approve
   ```

2. **Wait 3-5 minutes** for:
   - Instances to fully initialize
   - User data script to complete
   - Health checks to pass (requires 2 consecutive successful checks)

3. **Check the target group** health status again

4. **If still unhealthy**, check the CloudWatch logs or use Session Manager to investigate

## Emergency Workaround:

If you need to quickly test the load balancer:

```bash
# Create a simple test in public subnets
# Edit main.tf temporarily:
# Change: subnet_id = aws_subnet.private[count.index % 2].id
# To: subnet_id = aws_subnet.public[count.index % 2].id
# And disable NAT Gateway to save costs
```
