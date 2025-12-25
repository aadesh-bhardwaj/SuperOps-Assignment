#!/usr/bin/env python3
"""
Cleanup Script for Auto-Tagger

This script removes all resources created by the auto-tagger deployment.

Author: Aadesh
Date: December 2024
"""

import boto3
import sys
import os
from botocore.exceptions import ClientError

# Configuration (same as deploy.py)
CONFIG = {
    'function_name': 'auto-tagger',
    'role_name': 'auto-tagger-lambda-role',
    'policy_name': 'auto-tagger-policy',
    'rule_name': 'auto-tagger-rule',
    'trail_name': 'auto-tagger-trail'
}


def cleanup():
    """Remove all auto-tagger resources."""
    
    print("🧹 Auto-Tagger Cleanup")
    print("=" * 50)
    print("⚠️  This will remove all auto-tagger resources!")
    
    response = input("Are you sure? (yes/no): ")
    if response.lower() != 'yes':
        print("Cleanup cancelled.")
        return
    
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Initialize clients
    iam = boto3.client('iam', region_name=region)
    lambda_client = boto3.client('lambda', region_name=region)
    events = boto3.client('events', region_name=region)
    cloudtrail = boto3.client('cloudtrail', region_name=region)
    
    errors = []
    
    # Remove CloudWatch Events rule
    print("\n📊 Removing CloudWatch Events rule...")
    try:
        # Remove targets first
        events.remove_targets(Rule=CONFIG['rule_name'], Ids=['1'])
        print("  ✓ Removed rule targets")
        
        # Delete rule
        events.delete_rule(Name=CONFIG['rule_name'])
        print("  ✓ Deleted rule")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("  ℹ Rule not found")
        else:
            print(f"  ❌ Error: {e}")
            errors.append(f"CloudWatch rule: {e}")
    
    # Remove Lambda function
    print("\n🔧 Removing Lambda function...")
    try:
        lambda_client.delete_function(FunctionName=CONFIG['function_name'])
        print("  ✓ Deleted Lambda function")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("  ℹ Function not found")
        else:
            print(f"  ❌ Error: {e}")
            errors.append(f"Lambda function: {e}")
    
    # Remove IAM role and policy
    print("\n🔐 Removing IAM role and policy...")
    try:
        # Delete role policy first
        iam.delete_role_policy(
            RoleName=CONFIG['role_name'],
            PolicyName=CONFIG['policy_name']
        )
        print("  ✓ Deleted role policy")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print("  ℹ Policy not found")
        else:
            print(f"  ❌ Error: {e}")
            errors.append(f"IAM policy: {e}")
    
    try:
        # Delete role
        iam.delete_role(RoleName=CONFIG['role_name'])
        print("  ✓ Deleted IAM role")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print("  ℹ Role not found")
        else:
            print(f"  ❌ Error: {e}")
            errors.append(f"IAM role: {e}")
    
    # CloudTrail cleanup (optional)
    print("\n🔍 CloudTrail...")
    try:
        trails = cloudtrail.describe_trails(trailNameList=[CONFIG['trail_name']])
        if trails['trailList']:
            response = input("  Delete CloudTrail? This may affect other services (yes/no): ")
            if response.lower() == 'yes':
                # Stop logging first
                cloudtrail.stop_logging(Name=CONFIG['trail_name'])
                # Delete trail
                cloudtrail.delete_trail(Name=CONFIG['trail_name'])
                print("  ✓ Deleted CloudTrail")
            else:
                print("  ℹ CloudTrail preserved")
        else:
            print("  ℹ CloudTrail not found")
    except:
        print("  ℹ CloudTrail not managed by auto-tagger")
    
    # Summary
    print("\n" + "=" * 50)
    if errors:
        print("⚠️  Cleanup completed with errors:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("✅ Cleanup completed successfully!")
        print("   All auto-tagger resources have been removed.")


if __name__ == '__main__':
    cleanup()
