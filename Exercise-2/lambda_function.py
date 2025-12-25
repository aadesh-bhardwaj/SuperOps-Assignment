"""
AWS Auto-Tagger Lambda Function

This Lambda function automatically tags AWS resources when they are created.
It processes CloudWatch Events from CloudTrail and applies tags including
the creator's ARN, timestamp, and other metadata.

Author: Aadesh
Date: December 2024
"""

import json
import boto3
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize boto3 clients
# These will be initialized per service as needed to avoid unnecessary connections
CLIENTS = {}

# Configuration
CONFIG = {
    'excluded_services': os.environ.get('EXCLUDED_SERVICES', 'cloudtrail,logs').split(','),
    'max_retry_attempts': int(os.environ.get('MAX_RETRY_ATTEMPTS', '3')),
    'default_tags': {
        'AutoTagged': 'true',
        'ManagedBy': 'AutoTagger'
    }
}

# Service-specific tagging functions mapping
TAGGING_FUNCTIONS = {}


def get_client(service_name: str, region: str = None):
    """
    Get or create a boto3 client for the specified service.
    
    Args:
        service_name: AWS service name
        region: AWS region (optional)
    
    Returns:
        boto3 client instance
    """
    client_key = f"{service_name}_{region or 'default'}"
    if client_key not in CLIENTS:
        if region:
            CLIENTS[client_key] = boto3.client(service_name, region_name=region)
        else:
            CLIENTS[client_key] = boto3.client(service_name)
    return CLIENTS[client_key]


def parse_arn(arn: str) -> Dict[str, str]:
    """
    Parse an ARN into its components.
    
    Args:
        arn: AWS ARN string
    
    Returns:
        Dictionary with ARN components
    """
    # ARN format: arn:partition:service:region:account:resource
    parts = arn.split(':')
    return {
        'partition': parts[1] if len(parts) > 1 else '',
        'service': parts[2] if len(parts) > 2 else '',
        'region': parts[3] if len(parts) > 3 else '',
        'account': parts[4] if len(parts) > 4 else '',
        'resource': ':'.join(parts[5:]) if len(parts) > 5 else ''
    }


def get_user_identity(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract user identity information from CloudWatch Event.
    
    Args:
        event: CloudWatch Event dict
    
    Returns:
        Dictionary with user identity information
    """
    detail = event.get('detail', {})
    user_identity = detail.get('userIdentity', {})
    
    identity_info = {
        'CreatedBy': user_identity.get('arn', 'unknown'),
        'CreatedByUser': 'unknown',
        'CreatedByType': user_identity.get('type', 'unknown'),
        'CreatedByAccountId': user_identity.get('accountId', 'unknown'),
        'CreatedAt': detail.get('eventTime', datetime.utcnow().isoformat() + 'Z')
    }
    
    # Extract username based on identity type
    if user_identity.get('type') == 'IAMUser':
        identity_info['CreatedByUser'] = user_identity.get('userName', 'unknown')
    elif user_identity.get('type') == 'AssumedRole':
        session_name = user_identity.get('sessionContext', {}).get('sessionIssuer', {}).get('userName')
        if not session_name:
            # Try to extract from ARN
            arn_parts = identity_info['CreatedBy'].split('/')
            session_name = arn_parts[-1] if arn_parts else 'unknown'
        identity_info['CreatedByUser'] = session_name
    elif user_identity.get('type') == 'Root':
        identity_info['CreatedByUser'] = 'root'
    
    return identity_info


def tag_ec2_resource(resource_id: str, resource_type: str, tags: Dict[str, str], region: str):
    """
    Tag an EC2 resource.
    
    Args:
        resource_id: Resource ID
        resource_type: Type of EC2 resource
        tags: Dictionary of tags to apply
        region: AWS region
    """
    ec2 = get_client('ec2', region)
    
    tag_list = [{'Key': k, 'Value': v} for k, v in tags.items()]
    
    try:
        ec2.create_tags(Resources=[resource_id], Tags=tag_list)
        logger.info(f"Successfully tagged EC2 {resource_type}: {resource_id}")
    except ClientError as e:
        logger.error(f"Failed to tag EC2 {resource_type} {resource_id}: {e}")
        raise


def tag_s3_bucket(bucket_name: str, tags: Dict[str, str], region: str):
    """
    Tag an S3 bucket.
    
    Args:
        bucket_name: Name of the S3 bucket
        tags: Dictionary of tags to apply
        region: AWS region
    """
    s3 = get_client('s3', region)
    
    try:
        # Get existing tags
        try:
            response = s3.get_bucket_tagging(Bucket=bucket_name)
            existing_tags = {tag['Key']: tag['Value'] for tag in response.get('TagSet', [])}
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchTagSet':
                existing_tags = {}
            else:
                raise
        
        # Merge with new tags
        existing_tags.update(tags)
        
        # Apply tags
        tag_set = [{'Key': k, 'Value': v} for k, v in existing_tags.items()]
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': tag_set}
        )
        logger.info(f"Successfully tagged S3 bucket: {bucket_name}")
    except ClientError as e:
        logger.error(f"Failed to tag S3 bucket {bucket_name}: {e}")
        raise


def tag_rds_resource(resource_arn: str, tags: Dict[str, str], region: str):
    """
    Tag an RDS resource.
    
    Args:
        resource_arn: ARN of the RDS resource
        tags: Dictionary of tags to apply
        region: AWS region
    """
    rds = get_client('rds', region)
    
    tag_list = [{'Key': k, 'Value': v} for k, v in tags.items()]
    
    try:
        rds.add_tags_to_resource(ResourceName=resource_arn, Tags=tag_list)
        logger.info(f"Successfully tagged RDS resource: {resource_arn}")
    except ClientError as e:
        logger.error(f"Failed to tag RDS resource {resource_arn}: {e}")
        raise


def tag_lambda_function(function_name: str, tags: Dict[str, str], region: str):
    """
    Tag a Lambda function.
    
    Args:
        function_name: Name or ARN of the Lambda function
        tags: Dictionary of tags to apply
        region: AWS region
    """
    lambda_client = get_client('lambda', region)
    
    try:
        # Get the function ARN if only name is provided
        if not function_name.startswith('arn:'):
            response = lambda_client.get_function(FunctionName=function_name)
            function_arn = response['Configuration']['FunctionArn']
        else:
            function_arn = function_name
        
        lambda_client.tag_resource(Resource=function_arn, Tags=tags)
        logger.info(f"Successfully tagged Lambda function: {function_name}")
    except ClientError as e:
        logger.error(f"Failed to tag Lambda function {function_name}: {e}")
        raise


def tag_dynamodb_table(table_name: str, tags: Dict[str, str], region: str):
    """
    Tag a DynamoDB table.
    
    Args:
        table_name: Name of the DynamoDB table
        tags: Dictionary of tags to apply
        region: AWS region
    """
    dynamodb = get_client('dynamodb', region)
    
    try:
        # Get table ARN
        response = dynamodb.describe_table(TableName=table_name)
        table_arn = response['Table']['TableArn']
        
        # Apply tags
        tag_list = [{'Key': k, 'Value': v} for k, v in tags.items()]
        dynamodb.tag_resource(ResourceArn=table_arn, Tags=tag_list)
        logger.info(f"Successfully tagged DynamoDB table: {table_name}")
    except ClientError as e:
        logger.error(f"Failed to tag DynamoDB table {table_name}: {e}")
        raise


def process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a CloudWatch Event and tag the created resource.
    
    Args:
        event: CloudWatch Event from CloudTrail
    
    Returns:
        Result dictionary with status and details
    """
    detail = event.get('detail', {})
    event_name = detail.get('eventName', '')
    event_source = detail.get('eventSource', '')
    aws_region = detail.get('awsRegion', os.environ.get('AWS_REGION', 'us-east-1'))
    
    # Skip if service is excluded
    service = event_source.split('.')[0] if '.' in event_source else event_source
    if service in CONFIG['excluded_services']:
        logger.debug(f"Skipping excluded service: {service}")
        return {'status': 'skipped', 'reason': 'excluded_service'}
    
    # Get user identity tags
    user_tags = get_user_identity(event)
    
    # Add default tags
    all_tags = {**CONFIG['default_tags'], **user_tags}
    
    # Process based on event type
    tagged_resources = []
    
    try:
        # EC2 Instance
        if event_source == 'ec2.amazonaws.com' and event_name == 'RunInstances':
            response_elements = detail.get('responseElements', {})
            if response_elements:
                instances = response_elements.get('instancesSet', {}).get('items', [])
                for instance in instances:
                    instance_id = instance.get('instanceId')
                    if instance_id:
                        tag_ec2_resource(instance_id, 'instance', all_tags, aws_region)
                        tagged_resources.append(f"ec2:instance:{instance_id}")
        
        # EC2 Volume
        elif event_source == 'ec2.amazonaws.com' and event_name == 'CreateVolume':
            response_elements = detail.get('responseElements', {})
            volume_id = response_elements.get('volumeId')
            if volume_id:
                tag_ec2_resource(volume_id, 'volume', all_tags, aws_region)
                tagged_resources.append(f"ec2:volume:{volume_id}")
        
        # EC2 Security Group
        elif event_source == 'ec2.amazonaws.com' and event_name == 'CreateSecurityGroup':
            response_elements = detail.get('responseElements', {})
            group_id = response_elements.get('groupId')
            if group_id:
                tag_ec2_resource(group_id, 'security-group', all_tags, aws_region)
                tagged_resources.append(f"ec2:security-group:{group_id}")
        
        # S3 Bucket
        elif event_source == 's3.amazonaws.com' and event_name == 'CreateBucket':
            request_parameters = detail.get('requestParameters', {})
            bucket_name = request_parameters.get('bucketName')
            if bucket_name:
                tag_s3_bucket(bucket_name, all_tags, aws_region)
                tagged_resources.append(f"s3:bucket:{bucket_name}")
        
        # RDS Instance
        elif event_source == 'rds.amazonaws.com' and event_name in ['CreateDBInstance', 'CreateDBCluster']:
            response_elements = detail.get('responseElements', {})
            if event_name == 'CreateDBInstance':
                db_instance = response_elements.get('dBInstanceArn')
                if db_instance:
                    tag_rds_resource(db_instance, all_tags, aws_region)
                    tagged_resources.append(f"rds:instance:{db_instance}")
            else:
                db_cluster = response_elements.get('dBClusterArn')
                if db_cluster:
                    tag_rds_resource(db_cluster, all_tags, aws_region)
                    tagged_resources.append(f"rds:cluster:{db_cluster}")
        
        # Lambda Function
        elif event_source == 'lambda.amazonaws.com' and event_name == 'CreateFunction20150331':
            response_elements = detail.get('responseElements', {})
            function_name = response_elements.get('functionName')
            if function_name:
                tag_lambda_function(function_name, all_tags, aws_region)
                tagged_resources.append(f"lambda:function:{function_name}")
        
        # DynamoDB Table
        elif event_source == 'dynamodb.amazonaws.com' and event_name == 'CreateTable':
            response_elements = detail.get('responseElements', {})
            table_description = response_elements.get('tableDescription', {})
            table_name = table_description.get('tableName')
            if table_name:
                tag_dynamodb_table(table_name, all_tags, aws_region)
                tagged_resources.append(f"dynamodb:table:{table_name}")
        
        # VPC
        elif event_source == 'ec2.amazonaws.com' and event_name == 'CreateVpc':
            response_elements = detail.get('responseElements', {})
            vpc_id = response_elements.get('vpc', {}).get('vpcId')
            if vpc_id:
                tag_ec2_resource(vpc_id, 'vpc', all_tags, aws_region)
                tagged_resources.append(f"ec2:vpc:{vpc_id}")
        
        # Subnet
        elif event_source == 'ec2.amazonaws.com' and event_name == 'CreateSubnet':
            response_elements = detail.get('responseElements', {})
            subnet_id = response_elements.get('subnet', {}).get('subnetId')
            if subnet_id:
                tag_ec2_resource(subnet_id, 'subnet', all_tags, aws_region)
                tagged_resources.append(f"ec2:subnet:{subnet_id}")
        
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'event_name': event_name,
            'event_source': event_source
        }
    
    return {
        'status': 'success',
        'tagged_resources': tagged_resources,
        'tags_applied': all_tags,
        'event_name': event_name,
        'event_source': event_source
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function.
    
    Args:
        event: CloudWatch Event
        context: Lambda context object
    
    Returns:
        Response dictionary
    """
    logger.info(f"Processing event: {json.dumps(event)}")
    
    try:
        result = process_event(event)
        
        if result['status'] == 'success' and result.get('tagged_resources'):
            logger.info(f"Successfully tagged resources: {result['tagged_resources']}")
        elif result['status'] == 'skipped':
            logger.debug(f"Skipped event: {result.get('reason')}")
        else:
            logger.warning(f"No resources tagged for event: {event.get('detail', {}).get('eventName')}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e)
            })
        }


# For local testing
if __name__ == '__main__':
    # Example event for testing
    test_event = {
        'detail': {
            'eventName': 'RunInstances',
            'eventSource': 'ec2.amazonaws.com',
            'awsRegion': 'us-east-1',
            'userIdentity': {
                'type': 'IAMUser',
                'arn': 'arn:aws:iam::123456789012:user/test.user',
                'accountId': '123456789012',
                'userName': 'test.user'
            },
            'eventTime': '2024-12-25T10:30:00Z',
            'responseElements': {
                'instancesSet': {
                    'items': [
                        {'instanceId': 'i-1234567890abcdef0'}
                    ]
                }
            }
        }
    }
    
    print(json.dumps(lambda_handler(test_event, None), indent=2))
