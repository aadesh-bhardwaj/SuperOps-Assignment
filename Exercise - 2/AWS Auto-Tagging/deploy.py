#!/usr/bin/env python3
"""
AWS Auto-Tagger Deployment Script

This script deploys the auto-tagging solution to your AWS account.
It creates the Lambda function, IAM roles, CloudWatch Events rule,
and CloudTrail if needed.

Author: Aadesh
Date: December 2024
"""

import boto3
import json
import sys
import os
import time
import zipfile
import tempfile
from pathlib import Path
from botocore.exceptions import ClientError

# Configuration
CONFIG = {
    'function_name': 'auto-tagger',
    'role_name': 'auto-tagger-lambda-role',
    'policy_name': 'auto-tagger-policy',
    'rule_name': 'auto-tagger-rule',
    'trail_name': 'auto-tagger-trail',
    'runtime': 'python3.9',
    'timeout': 60,
    'memory_size': 256
}


class AutoTaggerDeployer:
    """Deploy the Auto-Tagger solution to AWS."""
    
    def __init__(self, region='us-east-1'):
        """
        Initialize the deployer with boto3 clients.
        
        Args:
            region: AWS region for deployment
        """
        self.region = region
        self.account_id = None
        
        # Initialize boto3 clients
        self.iam = boto3.client('iam', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.events = boto3.client('events', region_name=region)
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.sts = boto3.client('sts', region_name=region)
        
        # Get account ID
        try:
            self.account_id = self.sts.get_caller_identity()['Account']
            print(f"✅ Deploying to account: {self.account_id} in region: {region}")
        except Exception as e:
            print(f"❌ Failed to get account ID: {e}")
            sys.exit(1)
    
    def create_iam_role(self):
        """Create the IAM role for Lambda execution."""
        print("📦 Creating IAM role...")
        
        # Read trust policy
        with open('iam_policies/lambda_execution_role.json', 'r') as f:
            trust_policy = f.read()
        
        try:
            # Create role
            response = self.iam.create_role(
                RoleName=CONFIG['role_name'],
                AssumeRolePolicyDocument=trust_policy,
                Description='Execution role for Auto-Tagger Lambda function',
                MaxSessionDuration=3600
            )
            role_arn = response['Role']['Arn']
            print(f"  ✓ Created IAM role: {role_arn}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"  ℹ Role already exists, getting ARN...")
                response = self.iam.get_role(RoleName=CONFIG['role_name'])
                role_arn = response['Role']['Arn']
                print(f"  ✓ Using existing role: {role_arn}")
            else:
                print(f"  ❌ Failed to create role: {e}")
                raise
        
        # Attach policy
        print("  📎 Attaching policies...")
        
        # Read tagging policy
        with open('iam_policies/auto_tagging_policy.json', 'r') as f:
            tagging_policy = f.read()
        
        try:
            # Create and attach custom policy
            self.iam.put_role_policy(
                RoleName=CONFIG['role_name'],
                PolicyName=CONFIG['policy_name'],
                PolicyDocument=tagging_policy
            )
            print(f"  ✓ Attached tagging policy")
        except Exception as e:
            print(f"  ❌ Failed to attach policy: {e}")
            raise
        
        # Wait for role to be available (AWS IAM eventual consistency requires ~30 seconds)
        print("  ⏳ Waiting for role to propagate...")
        time.sleep(30)
        
        return role_arn
    
    def create_lambda_function(self, role_arn):
        """
        Create the Lambda function.
        
        Args:
            role_arn: ARN of the IAM role for Lambda
        
        Returns:
            Function ARN
        """
        print("🔧 Creating Lambda function...")
        
        # Create deployment package
        print("  📦 Creating deployment package...")
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            zip_file = tmp_file.name
            
            with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add lambda function
                zf.write('lambda_function.py', 'lambda_function.py')
        
        # Read zip file
        with open(zip_file, 'rb') as f:
            zip_content = f.read()
        
        try:
            # Create function
            response = self.lambda_client.create_function(
                FunctionName=CONFIG['function_name'],
                Runtime=CONFIG['runtime'],
                Role=role_arn,
                Handler='lambda_function.lambda_handler',
                Code={'ZipFile': zip_content},
                Description='Auto-tags AWS resources with creator information',
                Timeout=CONFIG['timeout'],
                MemorySize=CONFIG['memory_size'],
                Environment={
                    'Variables': {
                        'LOG_LEVEL': 'INFO',
                        'EXCLUDED_SERVICES': 'cloudtrail,logs'
                    }
                }
            )
            function_arn = response['FunctionArn']
            print(f"  ✓ Created Lambda function: {function_arn}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceConflictException':
                print(f"  ℹ Function already exists, updating...")
                # Update function code
                self.lambda_client.update_function_code(
                    FunctionName=CONFIG['function_name'],
                    ZipFile=zip_content
                )
                # Get function ARN
                response = self.lambda_client.get_function(FunctionName=CONFIG['function_name'])
                function_arn = response['Configuration']['FunctionArn']
                print(f"  ✓ Updated existing function: {function_arn}")
            else:
                print(f"  ❌ Failed to create function: {e}")
                raise
        finally:
            # Clean up temp file
            os.remove(zip_file)
        
        return function_arn
    
    def create_cloudwatch_rule(self, function_arn):
        """
        Create CloudWatch Events rule.
        
        Args:
            function_arn: ARN of the Lambda function
        """
        print("📊 Creating CloudWatch Events rule...")
        
        # Read event pattern
        with open('cloudwatch_rule.json', 'r') as f:
            rule_config = json.load(f)
        
        # Update with actual values
        rule_config['Targets'][0]['Arn'] = function_arn
        
        try:
            # Create rule
            response = self.events.put_rule(
                Name=CONFIG['rule_name'],
                EventPattern=json.dumps(rule_config['EventPattern']),
                State=rule_config['State'],
                Description=rule_config['Description']
            )
            rule_arn = response['RuleArn']
            print(f"  ✓ Created CloudWatch rule: {rule_arn}")
        except Exception as e:
            print(f"  ❌ Failed to create rule: {e}")
            raise
        
        # Add Lambda permission for CloudWatch Events
        print("  🔐 Adding Lambda permission...")
        try:
            self.lambda_client.add_permission(
                FunctionName=CONFIG['function_name'],
                StatementId='CloudWatchEventsInvokePermission',
                Action='lambda:InvokeFunction',
                Principal='events.amazonaws.com',
                SourceArn=rule_arn
            )
            print(f"  ✓ Added Lambda invoke permission")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceConflictException':
                print(f"  ℹ Permission already exists")
            else:
                print(f"  ❌ Failed to add permission: {e}")
                raise
        
        # Add target
        print("  🎯 Adding Lambda target to rule...")
        try:
            self.events.put_targets(
                Rule=CONFIG['rule_name'],
                Targets=[
                    {
                        'Id': '1',
                        'Arn': function_arn
                    }
                ]
            )
            print(f"  ✓ Added Lambda as target")
        except Exception as e:
            print(f"  ❌ Failed to add target: {e}")
            raise
    
    def enable_cloudtrail(self):
        """Enable CloudTrail if not already enabled."""
        print("🔍 Checking CloudTrail...")
        
        try:
            # Check if trail exists
            trails = self.cloudtrail.list_trails()['Trails']
            
            if trails:
                print(f"  ✓ CloudTrail already configured: {trails[0]['Name']}")
                return trails[0]['Name']
            
            print("  ⚠️ No CloudTrail found. Creating one...")
            
            # Create S3 bucket for CloudTrail
            bucket_name = f"cloudtrail-{self.account_id}-{self.region}"
            
            try:
                if self.region == 'us-east-1':
                    self.s3.create_bucket(Bucket=bucket_name)
                else:
                    self.s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
                print(f"  ✓ Created S3 bucket: {bucket_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                    print(f"  ℹ Bucket already exists: {bucket_name}")
                else:
                    raise
            
            # Set bucket policy for CloudTrail
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AWSCloudTrailAclCheck",
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudtrail.amazonaws.com"},
                        "Action": "s3:GetBucketAcl",
                        "Resource": f"arn:aws:s3:::{bucket_name}"
                    },
                    {
                        "Sid": "AWSCloudTrailWrite",
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudtrail.amazonaws.com"},
                        "Action": "s3:PutObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/AWSLogs/{self.account_id}/*",
                        "Condition": {
                            "StringEquals": {
                                "s3:x-amz-server-side-encryption": "AES256"
                            }
                        }
                    }
                ]
            }
            
            self.s3.put_bucket_policy(
                Bucket=bucket_name,
                Policy=json.dumps(bucket_policy)
            )
            
            # Create trail
            response = self.cloudtrail.create_trail(
                Name=CONFIG['trail_name'],
                S3BucketName=bucket_name,
                IsMultiRegionTrail=True,
                EnableLogFileValidation=True,
                EventSelectors=[
                    {
                        'ReadWriteType': 'WriteOnly',
                        'IncludeManagementEvents': True,
                        'DataResources': []
                    }
                ]
            )
            
            # Start logging
            self.cloudtrail.start_logging(Name=CONFIG['trail_name'])
            
            print(f"  ✓ Created and started CloudTrail: {CONFIG['trail_name']}")
            return CONFIG['trail_name']
            
        except Exception as e:
            print(f"  ⚠️ CloudTrail setup failed: {e}")
            print(f"  ℹ CloudTrail might already be configured in another region or account level")
            return None
    
    def deploy(self):
        """Deploy the complete solution."""
        print("\n🚀 Starting Auto-Tagger Deployment")
        print("=" * 50)
        
        try:
            # Create IAM role
            role_arn = self.create_iam_role()
            
            # Create Lambda function
            function_arn = self.create_lambda_function(role_arn)
            
            # Create CloudWatch Events rule
            self.create_cloudwatch_rule(function_arn)
            
            # Enable CloudTrail
            self.enable_cloudtrail()
            
            print("\n" + "=" * 50)
            print("✅ Deployment Complete!")
            print(f"   Lambda Function: {CONFIG['function_name']}")
            print(f"   CloudWatch Rule: {CONFIG['rule_name']}")
            print(f"   Region: {self.region}")
            print(f"   Account: {self.account_id}")
            print("\n📝 Next Steps:")
            print("   1. Create a new EC2 instance or other resource")
            print("   2. Check the tags after a few seconds")
            print("   3. Monitor CloudWatch Logs for any issues")
            print(f"   4. View logs at: /aws/lambda/{CONFIG['function_name']}")
            
        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    # Parse arguments
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    print("Arguments passed to the script: ", sys.argv) # printing the arguments passed to the script e.g. python deploy.py(arg-1) ap-south-1(arg-2)
    if len(sys.argv) > 1:
        region = sys.argv[1]
    
    # Deploy
    deployer = AutoTaggerDeployer(region)
    deployer.deploy()


if __name__ == '__main__':
    main()
