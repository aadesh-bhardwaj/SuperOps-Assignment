#!/usr/bin/env python3
"""
Integration Test for Auto-Tagger

This script tests the auto-tagging functionality by creating a test resource
and verifying that it gets tagged correctly.

Author: Aadesh
Date: December 2024
"""

import boto3
import time
import sys
import json
from datetime import datetime

def test_auto_tagging():
    """Test the auto-tagging functionality."""
    
    print("🧪 Auto-Tagger Integration Test")
    print("=" * 50)
    
    # Initialize clients
    ec2 = boto3.client('ec2')
    sts = boto3.client('sts')
    
    # Get current user info
    identity = sts.get_caller_identity()
    account_id = identity['Account']
    user_arn = identity['Arn']
    
    print(f"Testing as: {user_arn}")
    
    # Create a test security group
    test_name = f"auto-tagger-test-{int(time.time())}"
    print(f"\n📦 Creating test security group: {test_name}")
    
    try:
        # Get default VPC
        vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
        if not vpcs['Vpcs']:
            print("❌ No default VPC found. Please create one or specify a VPC ID.")
            return False
        
        vpc_id = vpcs['Vpcs'][0]['VpcId']
        
        # Create security group
        response = ec2.create_security_group(
            GroupName=test_name,
            Description='Test security group for auto-tagger verification',
            VpcId=vpc_id
        )
        
        sg_id = response['GroupId']
        print(f"✓ Created security group: {sg_id}")
        
        # Wait for tags to be applied
        print("\n⏳ Waiting 10 seconds for auto-tagging...")
        time.sleep(10)
        
        # Check tags
        print("\n🔍 Checking tags...")
        tags_response = ec2.describe_tags(
            Filters=[
                {'Name': 'resource-id', 'Values': [sg_id]}
            ]
        )
        
        tags = {tag['Key']: tag['Value'] for tag in tags_response['Tags']}
        
        # Verify expected tags
        expected_tags = ['CreatedBy', 'CreatedByUser', 'CreatedAt', 'AutoTagged']
        missing_tags = []
        
        print("\n📋 Tag Report:")
        print("-" * 40)
        for tag_key in expected_tags:
            if tag_key in tags:
                print(f"✅ {tag_key}: {tags[tag_key]}")
            else:
                print(f"❌ {tag_key}: MISSING")
                missing_tags.append(tag_key)
        
        # Show all tags
        if len(tags) > len(expected_tags):
            print("\n📎 Additional tags found:")
            for key, value in tags.items():
                if key not in expected_tags:
                    print(f"   {key}: {value}")
        
        # Clean up
        print("\n🧹 Cleaning up...")
        ec2.delete_security_group(GroupId=sg_id)
        print(f"✓ Deleted test security group: {sg_id}")
        
        # Result
        print("\n" + "=" * 50)
        if not missing_tags:
            print("✅ TEST PASSED: All expected tags were applied!")
            return True
        else:
            print(f"❌ TEST FAILED: Missing tags: {', '.join(missing_tags)}")
            print("\nPossible issues:")
            print("1. Lambda function might not be deployed")
            print("2. CloudWatch Events rule might not be active")
            print("3. CloudTrail might not be enabled")
            print("4. IAM permissions might be insufficient")
            print("\nCheck CloudWatch Logs for details:")
            print(f"   /aws/lambda/auto-tagger")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False


def check_deployment_status():
    """Check if all components are deployed."""
    
    print("\n🔍 Checking Deployment Status")
    print("-" * 40)
    
    lambda_client = boto3.client('lambda')
    events = boto3.client('events')
    cloudtrail = boto3.client('cloudtrail')
    
    status = {}
    
    # Check Lambda function
    try:
        lambda_client.get_function(FunctionName='auto-tagger')
        print("✅ Lambda function: Deployed")
        status['lambda'] = True
    except:
        print("❌ Lambda function: Not found")
        status['lambda'] = False
    
    # Check CloudWatch rule
    try:
        rule = events.describe_rule(Name='auto-tagger-rule')
        if rule['State'] == 'ENABLED':
            print("✅ CloudWatch rule: Enabled")
            status['rule'] = True
        else:
            print("⚠️  CloudWatch rule: Disabled")
            status['rule'] = False
    except:
        print("❌ CloudWatch rule: Not found")
        status['rule'] = False
    
    # Check CloudTrail
    try:
        trails = cloudtrail.describe_trails()
        if trails['trailList']:
            # Check if any trail is logging
            for trail in trails['trailList']:
                trail_status = cloudtrail.get_trail_status(Name=trail['Name'])
                if trail_status['IsLogging']:
                    print(f"✅ CloudTrail: Active ({trail['Name']})")
                    status['cloudtrail'] = True
                    break
            else:
                print("⚠️  CloudTrail: Found but not logging")
                status['cloudtrail'] = False
        else:
            print("❌ CloudTrail: Not configured")
            status['cloudtrail'] = False
    except:
        print("⚠️  CloudTrail: Unable to check status")
        status['cloudtrail'] = None
    
    return all(v for v in status.values() if v is not None)


def main():
    """Main entry point."""
    
    # Check deployment first
    if not check_deployment_status():
        print("\n⚠️  Not all components are deployed.")
        print("Run 'python deploy.py' first to deploy the solution.")
        sys.exit(1)
    
    # Run test
    print()
    if test_auto_tagging():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
