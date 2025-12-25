# AWS User Access Provisioning System

## 📋 Overview

This solution provides a comprehensive Python-based system for automating AWS IAM user provisioning, including user creation, group management, policy assignment, MFA setup, and access key rotation.

## 🎯 Problem Statement

**From Assignment**: AWS user access provision should be done via a programming language.

## 🏗️ Architecture

```
User Request → Python CLI → IAM API → AWS Account
     ↓            ↓           ↓
  Config     Validation    Logging
  Files      & Policies    & Audit
```

## ✨ Features

### Core Functionality
- **User Management**: Create, update, delete IAM users
- **Group Management**: Organize users into logical groups
- **Policy Management**: Attach managed and inline policies
- **Access Keys**: Generate, rotate, and manage access keys
- **MFA Setup**: Enable and configure MFA devices
- **Password Management**: Set initial passwords and enforce policies
- **Bulk Operations**: Process multiple users from CSV/JSON
- **Audit Trail**: Complete logging of all provisioning actions

### Advanced Features
- **Template-based Provisioning**: Pre-defined user profiles
- **Automated Onboarding**: Welcome emails with credentials
- **Scheduled Rotation**: Automatic access key rotation
- **Compliance Checks**: Verify users meet security requirements
- **Role-based Access**: Assign roles based on job function
- **Cost Tagging**: Tag users for cost allocation
- **Integration Ready**: REST API for external systems

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- AWS CLI configured with admin privileges
- boto3 library

### Installation

```bash
# Clone repository
git clone <your-repo>
cd Exercise-2-UserProvisioning

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials (if not done)
aws configure
```

### Basic Usage

#### 1. Create a Single User
```bash
python user_provisioning.py create-user \
    --username john.doe \
    --email john.doe@company.com \
    --department Engineering \
    --groups Developers,ReadOnly
```

#### 2. Bulk User Creation
```bash
# From CSV file
python user_provisioning.py bulk-create --file users.csv

# From JSON file
python user_provisioning.py bulk-create --file users.json
```

#### 3. User Onboarding Workflow
```bash
python user_provisioning.py onboard \
    --username jane.smith \
    --role "Senior Developer" \
    --send-welcome-email
```

#### 4. Offboarding User
```bash
python user_provisioning.py offboard \
    --username john.doe \
    --backup-credentials \
    --remove-after 30
```

#### 5. Rotate Access Keys
```bash
# Single user
python user_provisioning.py rotate-keys --username john.doe

# All users
python user_provisioning.py rotate-keys --all --older-than 90
```

#### 6. Enable MFA
```bash
python user_provisioning.py enable-mfa \
    --username john.doe \
    --device-type virtual
```

## 📁 File Structure

```
Exercise-2-UserProvisioning/
├── user_provisioning.py      # Main CLI application
├── iam_manager.py            # Core IAM management class
├── policy_manager.py         # Policy management utilities
├── group_manager.py          # Group management utilities
├── mfa_manager.py           # MFA configuration
├── templates/               # User profile templates
│   ├── developer.json
│   ├── admin.json
│   ├── readonly.json
│   └── finance.json
├── policies/               # Custom IAM policies
│   ├── developer_policy.json
│   ├── readonly_policy.json
│   └── admin_policy.json
├── config/                 # Configuration files
│   ├── settings.json
│   └── groups.json
├── tests/                  # Unit and integration tests
├── logs/                   # Audit logs
├── README.md              # This file
└── requirements.txt       # Python dependencies
```

## 🎭 User Profiles/Templates

### Developer Profile
```json
{
  "groups": ["Developers", "ReadOnly"],
  "policies": ["AmazonEC2FullAccess", "AmazonS3ReadOnlyAccess"],
  "tags": {
    "Department": "Engineering",
    "CostCenter": "CC-1001"
  },
  "mfa_required": true,
  "console_access": true
}
```

### Admin Profile
```json
{
  "groups": ["Administrators"],
  "policies": ["AdministratorAccess"],
  "tags": {
    "Department": "IT",
    "CostCenter": "CC-3001"
  },
  "mfa_required": true,
  "console_access": true
}
```

## 🔒 Security Features

1. **Password Policy Enforcement**
   - Minimum 12 characters
   - Require uppercase, lowercase, numbers, symbols
   - Password expiration after 90 days
   - Prevent password reuse

2. **MFA Enforcement**
   - Mandatory for admin users
   - Optional virtual or hardware MFA
   - QR code generation for easy setup

3. **Access Key Rotation**
   - Automatic rotation reminders
   - Dual-key rotation for zero downtime
   - Secure key delivery via encrypted email

4. **Least Privilege**
   - Start with minimal permissions
   - Permission boundary enforcement
   - Regular access reviews

## 📊 Reporting & Monitoring

### Available Reports
```bash
# User access report
python user_provisioning.py report --type access

# Compliance report
python user_provisioning.py report --type compliance

# Cost allocation report
python user_provisioning.py report --type cost

# Security audit report
python user_provisioning.py report --type security
```

### Sample Output
```
AWS User Access Report
Generated: 2024-12-25 10:30:00
=====================================================
Total Users: 45
Active Users: 42
MFA Enabled: 38 (84%)
Password Expired: 3
Access Keys > 90 days: 7

Top Groups:
- Developers: 20 users
- ReadOnly: 15 users
- Administrators: 5 users

Recent Activities:
- john.doe: Created (2024-12-20)
- jane.smith: MFA enabled (2024-12-22)
- bob.wilson: Access key rotated (2024-12-24)
```

## 🧪 Testing

### Unit Tests
```bash
python -m pytest tests/unit -v
```

### Integration Tests
```bash
python -m pytest tests/integration -v
```

### Test Coverage
```bash
python -m pytest --cov=. --cov-report=html
```

## 📈 Scalability

### Current Capabilities
- Handle 1000+ users efficiently
- Bulk operations with parallel processing
- Pagination for large user lists
- Caching for frequently accessed data

### Scaling Strategies

1. **Database Backend**
   - Store user metadata in DynamoDB
   - Track provisioning history
   - Enable complex queries

2. **Queue-based Processing**
   - SQS for asynchronous operations
   - Handle large bulk requests
   - Retry logic for failures

3. **API Gateway**
   - RESTful API for external integrations
   - Rate limiting and throttling
   - Authentication via API keys

4. **Lambda Functions**
   - Serverless execution for provisioning
   - Event-driven workflows
   - Auto-scaling capability

## 🔄 Integration Options

### Slack Integration
```python
# Notify Slack on user creation
notify_slack(
    channel="#aws-users",
    message=f"New user created: {username}"
)
```

### JIRA Integration
```python
# Create JIRA ticket for access request
ticket = create_jira_ticket(
    summary=f"AWS Access for {username}",
    assignee="security-team"
)
```

### Active Directory Sync
```python
# Sync users from AD
sync_from_ad(
    domain="company.local",
    ou="Engineering"
)
```

## 💰 Cost Optimization

- **Tag all users** for cost allocation
- **Regular cleanup** of unused accounts
- **Right-sizing** of permissions
- **Automated offboarding** to prevent lingering access

## 📝 Configuration

### config/settings.json
```json
{
  "password_policy": {
    "minimum_length": 12,
    "require_uppercase": true,
    "require_lowercase": true,
    "require_numbers": true,
    "require_symbols": true,
    "max_age_days": 90
  },
  "mfa": {
    "required_for_groups": ["Administrators"],
    "grace_period_days": 7
  },
  "access_keys": {
    "max_age_days": 90,
    "auto_rotate": true
  },
  "notifications": {
    "email_enabled": true,
    "slack_enabled": false
  }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **Permission Denied**
   - Ensure your AWS credentials have IAM admin permissions
   - Check if STS token has expired

2. **User Already Exists**
   - Use `--force` flag to update existing user
   - Or delete first with `delete-user` command

3. **MFA Device Error**
   - Ensure virtual MFA app is synced
   - Check time sync on server

## 👍 What I Liked About This Solution

1. **Comprehensive**: Covers entire user lifecycle
2. **Automated**: Reduces manual work and errors
3. **Scalable**: Handles growth from 10 to 10,000 users
4. **Secure**: Enforces best practices by default
5. **Auditable**: Complete logging and reporting
6. **Flexible**: Template-based for different roles
7. **Pythonic**: Clean, maintainable code

## 👎 What Could Be Improved

1. **UI/UX**: Currently CLI-only, could add web interface
2. **Approval Workflow**: Manual approval still needed for sensitive roles
3. **Cost**: No built-in cost estimation before provisioning
4. **Rollback**: Limited automatic rollback on failures
5. **Multi-Account**: Complex setup for AWS Organizations
6. **External IdP**: Better integration with Okta/Azure AD

## 🚀 Future Enhancements

- [ ] Web dashboard for self-service
- [ ] Mobile app for approvals
- [ ] AI-based permission recommendations
- [ ] Automated compliance reporting
- [ ] Integration with HR systems
- [ ] Temporary elevated access workflows
- [ ] Break-glass procedures

## 📞 Support

For issues or questions:
1. Check the troubleshooting guide
2. Review logs in `logs/` directory
3. Open an issue in the repository

---

**Author**: Aadesh  
**Date**: December 2024  
**Assignment**: DevOps Exercise-2 (Option 2)
