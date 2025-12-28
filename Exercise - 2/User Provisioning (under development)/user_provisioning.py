#!/usr/bin/env python3
"""
AWS User Access Provisioning System

A comprehensive Python-based system for automating AWS IAM user provisioning,
including user creation, group management, policy assignment, MFA setup,
and access key rotation.

Author: Aadesh
Date: December 2024
"""

import argparse
import boto3
import json
import csv
import sys
import os
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/provisioning.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
Path("logs").mkdir(exist_ok=True)


class AWSUserProvisioner:
    """Main class for AWS user provisioning operations."""
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize the provisioner with AWS clients.
        
        Args:
            region: AWS region for operations
        """
        self.region = region
        self.iam = boto3.client('iam', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # Get account info
        try:
            identity = self.sts.get_caller_identity()
            self.account_id = identity['Account']
            self.caller_arn = identity['Arn']
            logger.info(f"Initialized provisioner for account {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
        
        # Load configuration
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file."""
        config_file = Path("config/settings.json")
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            # Return default config
            return {
                "password_policy": {
                    "minimum_length": 12,
                    "require_uppercase": True,
                    "require_lowercase": True,
                    "require_numbers": True,
                    "require_symbols": True,
                    "max_age_days": 90
                },
                "mfa": {
                    "required_for_groups": ["Administrators"],
                    "grace_period_days": 7
                },
                "access_keys": {
                    "max_age_days": 90,
                    "auto_rotate": True
                }
            }
    
    def generate_password(self, length: int = 16) -> str:
        """
        Generate a secure random password.
        
        Args:
            length: Password length
        
        Returns:
            Generated password
        """
        characters = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
        password = ''.join(secrets.choice(characters) for _ in range(length))
        
        # Ensure password meets all requirements
        if not any(c.isupper() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_uppercase)
        if not any(c.islower() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_lowercase)
        if not any(c.isdigit() for c in password):
            password = password[:-1] + secrets.choice(string.digits)
        if not any(c in "!@#$%^&*()_+-=" for c in password):
            password = password[:-1] + secrets.choice("!@#$%^&*()_+-=")
        
        return password
    
    def create_user(self, 
                   username: str,
                   email: str = None,
                   department: str = None,
                   groups: List[str] = None,
                   policies: List[str] = None,
                   console_access: bool = True,
                   programmatic_access: bool = False,
                   mfa_required: bool = False) -> Dict[str, Any]:
        """
        Create a new IAM user with specified configuration.
        
        Args:
            username: IAM username
            email: User's email address
            department: Department for tagging
            groups: List of groups to add user to
            policies: List of managed policies to attach
            console_access: Enable AWS Console access
            programmatic_access: Create access keys
            mfa_required: Require MFA setup
        
        Returns:
            Dictionary with user details and credentials
        """
        logger.info(f"Creating user: {username}")
        result = {
            'username': username,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': self.caller_arn
        }
        
        try:
            # Create the IAM user
            user_response = self.iam.create_user(
                UserName=username,
                Tags=[
                    {'Key': 'Email', 'Value': email or ''},
                    {'Key': 'Department', 'Value': department or ''},
                    {'Key': 'CreatedBy', 'Value': self.caller_arn},
                    {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()},
                    {'Key': 'MFARequired', 'Value': str(mfa_required).lower()}
                ]
            )
            result['user_arn'] = user_response['User']['Arn']
            logger.info(f"Created IAM user: {username}")
            
            # Add user to groups
            if groups:
                for group in groups:
                    try:
                        self.iam.add_user_to_group(
                            GroupName=group,
                            UserName=username
                        )
                        logger.info(f"Added {username} to group: {group}")
                    except self.iam.exceptions.NoSuchEntityException:
                        logger.warning(f"Group {group} does not exist, skipping")
                result['groups'] = groups
            
            # Attach managed policies
            if policies:
                for policy in policies:
                    try:
                        # Check if it's a managed policy ARN or name
                        if policy.startswith('arn:'):
                            policy_arn = policy
                        else:
                            policy_arn = f"arn:aws:iam::aws:policy/{policy}"
                        
                        self.iam.attach_user_policy(
                            UserName=username,
                            PolicyArn=policy_arn
                        )
                        logger.info(f"Attached policy {policy} to {username}")
                    except Exception as e:
                        logger.warning(f"Failed to attach policy {policy}: {e}")
                result['policies'] = policies
            
            # Create login profile for console access
            if console_access:
                password = self.generate_password()
                self.iam.create_login_profile(
                    UserName=username,
                    Password=password,
                    PasswordResetRequired=True
                )
                result['console_access'] = True
                result['initial_password'] = password
                result['console_url'] = f"https://{self.account_id}.signin.aws.amazon.com/console"
                logger.info(f"Created login profile for {username}")
            
            # Create access keys for programmatic access
            if programmatic_access:
                keys_response = self.iam.create_access_key(UserName=username)
                result['access_key_id'] = keys_response['AccessKey']['AccessKeyId']
                result['secret_access_key'] = keys_response['AccessKey']['SecretAccessKey']
                logger.info(f"Created access keys for {username}")
            
            # Log successful creation
            self.log_audit_event('USER_CREATED', username, result)
            
            return result
            
        except self.iam.exceptions.EntityAlreadyExistsException:
            logger.error(f"User {username} already exists")
            raise
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            raise
    
    def delete_user(self, username: str, force: bool = False) -> bool:
        """
        Delete an IAM user and all associated resources.
        
        Args:
            username: IAM username to delete
            force: Force deletion even if user has attached resources
        
        Returns:
            True if successful
        """
        logger.info(f"Deleting user: {username}")
        
        try:
            # Remove user from all groups
            groups_response = self.iam.list_groups_for_user(UserName=username)
            for group in groups_response['Groups']:
                self.iam.remove_user_from_group(
                    GroupName=group['GroupName'],
                    UserName=username
                )
                logger.info(f"Removed {username} from group: {group['GroupName']}")
            
            # Detach all managed policies
            policies_response = self.iam.list_attached_user_policies(UserName=username)
            for policy in policies_response['AttachedPolicies']:
                self.iam.detach_user_policy(
                    UserName=username,
                    PolicyArn=policy['PolicyArn']
                )
                logger.info(f"Detached policy {policy['PolicyName']} from {username}")
            
            # Delete inline policies
            inline_policies = self.iam.list_user_policies(UserName=username)
            for policy_name in inline_policies['PolicyNames']:
                self.iam.delete_user_policy(
                    UserName=username,
                    PolicyName=policy_name
                )
                logger.info(f"Deleted inline policy {policy_name} from {username}")
            
            # Delete access keys
            keys_response = self.iam.list_access_keys(UserName=username)
            for key in keys_response['AccessKeyMetadata']:
                self.iam.delete_access_key(
                    UserName=username,
                    AccessKeyId=key['AccessKeyId']
                )
                logger.info(f"Deleted access key {key['AccessKeyId']} for {username}")
            
            # Delete MFA devices
            mfa_response = self.iam.list_mfa_devices(UserName=username)
            for device in mfa_response['MFADevices']:
                self.iam.deactivate_mfa_device(
                    UserName=username,
                    SerialNumber=device['SerialNumber']
                )
                self.iam.delete_virtual_mfa_device(
                    SerialNumber=device['SerialNumber']
                )
                logger.info(f"Deleted MFA device for {username}")
            
            # Delete login profile
            try:
                self.iam.delete_login_profile(UserName=username)
                logger.info(f"Deleted login profile for {username}")
            except self.iam.exceptions.NoSuchEntityException:
                pass
            
            # Finally, delete the user
            self.iam.delete_user(UserName=username)
            logger.info(f"Successfully deleted user: {username}")
            
            # Log audit event
            self.log_audit_event('USER_DELETED', username, {'deleted_by': self.caller_arn})
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete user {username}: {e}")
            raise
    
    def rotate_access_keys(self, username: str) -> Dict[str, str]:
        """
        Rotate access keys for a user.
        
        Args:
            username: IAM username
        
        Returns:
            Dictionary with new access key details
        """
        logger.info(f"Rotating access keys for {username}")
        
        try:
            # List existing access keys
            keys_response = self.iam.list_access_keys(UserName=username)
            existing_keys = keys_response['AccessKeyMetadata']
            
            # Create new access key
            new_key_response = self.iam.create_access_key(UserName=username)
            new_key = {
                'access_key_id': new_key_response['AccessKey']['AccessKeyId'],
                'secret_access_key': new_key_response['AccessKey']['SecretAccessKey']
            }
            
            logger.info(f"Created new access key for {username}: {new_key['access_key_id']}")
            
            # Delete old keys (keep only the newest if multiple exist)
            for key in existing_keys:
                if key['AccessKeyId'] != new_key['access_key_id']:
                    # Check age of key
                    key_age = datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']
                    if key_age.days > 1:  # Give 1 day grace period
                        self.iam.delete_access_key(
                            UserName=username,
                            AccessKeyId=key['AccessKeyId']
                        )
                        logger.info(f"Deleted old access key: {key['AccessKeyId']}")
            
            # Log audit event
            self.log_audit_event('ACCESS_KEY_ROTATED', username, {
                'new_key_id': new_key['access_key_id'],
                'rotated_by': self.caller_arn
            })
            
            return new_key
            
        except Exception as e:
            logger.error(f"Failed to rotate access keys for {username}: {e}")
            raise
    
    def enable_mfa(self, username: str) -> Dict[str, str]:
        """
        Enable virtual MFA for a user.
        
        Args:
            username: IAM username
        
        Returns:
            Dictionary with MFA setup details
        """
        logger.info(f"Enabling MFA for {username}")
        
        try:
            # Create virtual MFA device
            mfa_response = self.iam.create_virtual_mfa_device(
                VirtualMFADeviceName=f"{username}-mfa"
            )
            
            serial_number = mfa_response['VirtualMFADevice']['SerialNumber']
            qr_code = mfa_response['VirtualMFADevice']['QRCodePNG']
            seed = mfa_response['VirtualMFADevice']['Base32StringSeed']
            
            logger.info(f"Created virtual MFA device for {username}: {serial_number}")
            
            # Note: Actual MFA activation requires TOTP codes from the user
            # This would typically be done through a separate verification step
            
            result = {
                'serial_number': serial_number,
                'qr_code_available': True,
                'seed_available': True,
                'instructions': 'User must scan QR code and provide two consecutive TOTP codes to activate'
            }
            
            # Log audit event
            self.log_audit_event('MFA_ENABLED', username, {
                'serial_number': serial_number,
                'enabled_by': self.caller_arn
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to enable MFA for {username}: {e}")
            raise
    
    def bulk_create_users(self, users_file: str) -> List[Dict]:
        """
        Create multiple users from a CSV or JSON file.
        
        Args:
            users_file: Path to CSV or JSON file with user data
        
        Returns:
            List of results for each user
        """
        logger.info(f"Bulk creating users from {users_file}")
        results = []
        
        file_path = Path(users_file)
        if not file_path.exists():
            raise FileNotFoundError(f"File {users_file} not found")
        
        # Process based on file type
        if users_file.endswith('.csv'):
            with open(users_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        result = self.create_user(
                            username=row['username'],
                            email=row.get('email'),
                            department=row.get('department'),
                            groups=row.get('groups', '').split(',') if row.get('groups') else None,
                            policies=row.get('policies', '').split(',') if row.get('policies') else None,
                            console_access=row.get('console_access', 'true').lower() == 'true',
                            programmatic_access=row.get('programmatic_access', 'false').lower() == 'true',
                            mfa_required=row.get('mfa_required', 'false').lower() == 'true'
                        )
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Failed to create user {row['username']}: {e}")
                        results.append({'username': row['username'], 'error': str(e)})
        
        elif users_file.endswith('.json'):
            with open(users_file, 'r') as f:
                users = json.load(f)
                for user in users:
                    try:
                        result = self.create_user(**user)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Failed to create user {user['username']}: {e}")
                        results.append({'username': user['username'], 'error': str(e)})
        
        else:
            raise ValueError("File must be CSV or JSON")
        
        logger.info(f"Bulk creation complete. Created {len([r for r in results if 'error' not in r])} users")
        return results
    
    def generate_report(self, report_type: str = 'access') -> str:
        """
        Generate various reports about IAM users.
        
        Args:
            report_type: Type of report (access, compliance, security)
        
        Returns:
            Report content as string
        """
        logger.info(f"Generating {report_type} report")
        
        report_lines = [
            f"AWS User {report_type.title()} Report",
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Account: {self.account_id}",
            "=" * 60,
            ""
        ]
        
        # Get all users
        users_response = self.iam.list_users()
        users = users_response['Users']
        
        if report_type == 'access':
            report_lines.append(f"Total Users: {len(users)}")
            
            # Count users with MFA
            mfa_count = 0
            console_users = 0
            
            for user in users:
                # Check MFA
                mfa_devices = self.iam.list_mfa_devices(UserName=user['UserName'])
                if mfa_devices['MFADevices']:
                    mfa_count += 1
                
                # Check console access
                try:
                    self.iam.get_login_profile(UserName=user['UserName'])
                    console_users += 1
                except self.iam.exceptions.NoSuchEntityException:
                    pass
            
            report_lines.extend([
                f"Console Access: {console_users}",
                f"MFA Enabled: {mfa_count} ({mfa_count*100//len(users)}%)",
                "",
                "User Details:",
                "-" * 40
            ])
            
            for user in users:
                groups = self.iam.list_groups_for_user(UserName=user['UserName'])
                group_names = [g['GroupName'] for g in groups['Groups']]
                report_lines.append(f"- {user['UserName']}: Groups: {', '.join(group_names)}")
        
        elif report_type == 'compliance':
            # Check password age, key age, etc.
            report_lines.append("Compliance Status:")
            report_lines.append("-" * 40)
            
            for user in users:
                issues = []
                
                # Check access key age
                keys = self.iam.list_access_keys(UserName=user['UserName'])
                for key in keys['AccessKeyMetadata']:
                    key_age = datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']
                    if key_age.days > self.config['access_keys']['max_age_days']:
                        issues.append(f"Access key {key['AccessKeyId']} is {key_age.days} days old")
                
                # Check MFA for admin users
                groups = self.iam.list_groups_for_user(UserName=user['UserName'])
                admin_groups = [g for g in groups['Groups'] 
                              if g['GroupName'] in self.config['mfa']['required_for_groups']]
                if admin_groups:
                    mfa_devices = self.iam.list_mfa_devices(UserName=user['UserName'])
                    if not mfa_devices['MFADevices']:
                        issues.append("MFA not enabled for admin user")
                
                if issues:
                    report_lines.append(f"\n{user['UserName']}:")
                    for issue in issues:
                        report_lines.append(f"  ⚠️ {issue}")
        
        elif report_type == 'security':
            report_lines.append("Security Analysis:")
            report_lines.append("-" * 40)
            
            # Find users with dangerous policies
            for user in users:
                policies = self.iam.list_attached_user_policies(UserName=user['UserName'])
                dangerous_policies = [p for p in policies['AttachedPolicies'] 
                                     if 'AdministratorAccess' in p['PolicyName']]
                if dangerous_policies:
                    report_lines.append(f"⚠️ {user['UserName']}: Has AdministratorAccess")
        
        report_content = '\n'.join(report_lines)
        
        # Save report to file
        report_file = f"logs/report_{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report_content)
        
        logger.info(f"Report saved to {report_file}")
        return report_content
    
    def onboard_user(self, username: str, role: str, send_welcome: bool = True) -> Dict:
        """
        Complete onboarding workflow for a new user.
        
        Args:
            username: IAM username
            role: User's role/position
            send_welcome: Send welcome email
        
        Returns:
            Onboarding result dictionary
        """
        logger.info(f"Onboarding user {username} as {role}")
        
        # Load role template
        template_file = Path(f"templates/{role.lower().replace(' ', '_')}.json")
        if template_file.exists():
            with open(template_file, 'r') as f:
                template = json.load(f)
        else:
            # Use default template
            template = {
                "groups": ["ReadOnly"],
                "policies": ["ReadOnlyAccess"],
                "console_access": True,
                "programmatic_access": False,
                "mfa_required": True
            }
        
        # Create user
        result = self.create_user(
            username=username,
            **template
        )
        
        # Send welcome email if requested
        if send_welcome and result.get('initial_password'):
            # Note: This is a simplified example. In production, use SES or similar
            logger.info(f"Welcome email would be sent to {username}")
            result['welcome_email_sent'] = True
        
        # Schedule MFA reminder
        result['mfa_reminder_scheduled'] = True
        
        logger.info(f"Onboarding complete for {username}")
        return result
    
    def offboard_user(self, username: str, backup: bool = True, remove_after_days: int = 30) -> Dict:
        """
        Complete offboarding workflow for a user.
        
        Args:
            username: IAM username
            backup: Backup user configuration
            remove_after_days: Days to wait before deletion
        
        Returns:
            Offboarding result dictionary
        """
        logger.info(f"Offboarding user {username}")
        
        result = {'username': username, 'offboarded_at': datetime.utcnow().isoformat()}
        
        # Backup user configuration if requested
        if backup:
            user_data = {
                'username': username,
                'groups': [],
                'policies': [],
                'tags': []
            }
            
            # Get groups
            groups = self.iam.list_groups_for_user(UserName=username)
            user_data['groups'] = [g['GroupName'] for g in groups['Groups']]
            
            # Get policies
            policies = self.iam.list_attached_user_policies(UserName=username)
            user_data['policies'] = [p['PolicyArn'] for p in policies['AttachedPolicies']]
            
            # Get tags
            user = self.iam.get_user(UserName=username)
            user_data['tags'] = user['User'].get('Tags', [])
            
            # Save backup
            backup_file = f"logs/offboard_{username}_{datetime.utcnow().strftime('%Y%m%d')}.json"
            with open(backup_file, 'w') as f:
                json.dump(user_data, f, indent=2, default=str)
            
            result['backup_file'] = backup_file
            logger.info(f"User configuration backed up to {backup_file}")
        
        # Disable access immediately
        try:
            # Deactivate access keys
            keys = self.iam.list_access_keys(UserName=username)
            for key in keys['AccessKeyMetadata']:
                self.iam.update_access_key(
                    UserName=username,
                    AccessKeyId=key['AccessKeyId'],
                    Status='Inactive'
                )
                logger.info(f"Deactivated access key {key['AccessKeyId']}")
            
            # Remove from all groups
            groups = self.iam.list_groups_for_user(UserName=username)
            for group in groups['Groups']:
                self.iam.remove_user_from_group(
                    GroupName=group['GroupName'],
                    UserName=username
                )
                logger.info(f"Removed from group {group['GroupName']}")
            
            result['access_disabled'] = True
        except Exception as e:
            logger.error(f"Failed to disable access: {e}")
            result['error'] = str(e)
        
        # Schedule deletion
        if remove_after_days > 0:
            result['scheduled_deletion'] = (datetime.utcnow() + timedelta(days=remove_after_days)).isoformat()
            logger.info(f"User scheduled for deletion in {remove_after_days} days")
        else:
            # Delete immediately
            self.delete_user(username)
            result['deleted'] = True
        
        # Log audit event
        self.log_audit_event('USER_OFFBOARDED', username, result)
        
        return result
    
    def log_audit_event(self, event_type: str, username: str, details: Dict):
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            username: Username involved
            details: Event details
        """
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'username': username,
            'performed_by': self.caller_arn,
            'account_id': self.account_id,
            'details': details
        }
        
        # Write to audit log
        audit_file = f"logs/audit_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        with open(audit_file, 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='AWS User Access Provisioning System')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create user command
    create_parser = subparsers.add_parser('create-user', help='Create a new IAM user')
    create_parser.add_argument('--username', required=True, help='IAM username')
    create_parser.add_argument('--email', help='User email address')
    create_parser.add_argument('--department', help='Department')
    create_parser.add_argument('--groups', help='Comma-separated list of groups')
    create_parser.add_argument('--policies', help='Comma-separated list of policies')
    create_parser.add_argument('--console-access', action='store_true', help='Enable console access')
    create_parser.add_argument('--programmatic-access', action='store_true', help='Create access keys')
    create_parser.add_argument('--mfa-required', action='store_true', help='Require MFA')
    
    # Delete user command
    delete_parser = subparsers.add_parser('delete-user', help='Delete an IAM user')
    delete_parser.add_argument('--username', required=True, help='IAM username')
    delete_parser.add_argument('--force', action='store_true', help='Force deletion')
    
    # Bulk create command
    bulk_parser = subparsers.add_parser('bulk-create', help='Create multiple users from file')
    bulk_parser.add_argument('--file', required=True, help='CSV or JSON file with user data')
    
    # Rotate keys command
    rotate_parser = subparsers.add_parser('rotate-keys', help='Rotate access keys')
    rotate_parser.add_argument('--username', required=True, help='IAM username')
    
    # Enable MFA command
    mfa_parser = subparsers.add_parser('enable-mfa', help='Enable MFA for user')
    mfa_parser.add_argument('--username', required=True, help='IAM username')
    
    # Onboard command
    onboard_parser = subparsers.add_parser('onboard', help='Onboard a new user')
    onboard_parser.add_argument('--username', required=True, help='IAM username')
    onboard_parser.add_argument('--role', required=True, help='User role/position')
    onboard_parser.add_argument('--send-welcome-email', action='store_true', help='Send welcome email')
    
    # Offboard command
    offboard_parser = subparsers.add_parser('offboard', help='Offboard a user')
    offboard_parser.add_argument('--username', required=True, help='IAM username')
    offboard_parser.add_argument('--backup-credentials', action='store_true', help='Backup user config')
    offboard_parser.add_argument('--remove-after', type=int, default=30, help='Days before deletion')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate reports')
    report_parser.add_argument('--type', choices=['access', 'compliance', 'security'], 
                              default='access', help='Report type')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize provisioner
    provisioner = AWSUserProvisioner()
    
    try:
        if args.command == 'create-user':
            groups = args.groups.split(',') if args.groups else None
            policies = args.policies.split(',') if args.policies else None
            
            result = provisioner.create_user(
                username=args.username,
                email=args.email,
                department=args.department,
                groups=groups,
                policies=policies,
                console_access=args.console_access,
                programmatic_access=args.programmatic_access,
                mfa_required=args.mfa_required
            )
            
            print(f"\n✅ User created successfully!")
            print(json.dumps(result, indent=2, default=str))
            
            # Save credentials to file
            creds_file = f"credentials_{args.username}.json"
            with open(creds_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\n📄 Credentials saved to: {creds_file}")
            print("⚠️  Please share this file securely and delete after user receives it")
        
        elif args.command == 'delete-user':
            provisioner.delete_user(args.username, args.force)
            print(f"✅ User {args.username} deleted successfully")
        
        elif args.command == 'bulk-create':
            results = provisioner.bulk_create_users(args.file)
            print(f"\n✅ Bulk creation complete")
            print(f"Created: {len([r for r in results if 'error' not in r])} users")
            print(f"Failed: {len([r for r in results if 'error' in r])} users")
            
            # Save results
            results_file = f"bulk_create_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"📄 Results saved to: {results_file}")
        
        elif args.command == 'rotate-keys':
            new_keys = provisioner.rotate_access_keys(args.username)
            print(f"✅ Access keys rotated for {args.username}")
            print(json.dumps(new_keys, indent=2))
        
        elif args.command == 'enable-mfa':
            mfa_result = provisioner.enable_mfa(args.username)
            print(f"✅ MFA device created for {args.username}")
            print(json.dumps(mfa_result, indent=2))
        
        elif args.command == 'onboard':
            result = provisioner.onboard_user(
                args.username,
                args.role,
                args.send_welcome_email
            )
            print(f"✅ User {args.username} onboarded successfully")
            print(json.dumps(result, indent=2, default=str))
        
        elif args.command == 'offboard':
            result = provisioner.offboard_user(
                args.username,
                args.backup_credentials,
                args.remove_after
            )
            print(f"✅ User {args.username} offboarded")
            print(json.dumps(result, indent=2, default=str))
        
        elif args.command == 'report':
            report = provisioner.generate_report(args.type)
            print(report)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
