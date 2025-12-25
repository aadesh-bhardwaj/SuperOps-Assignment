#!/bin/bash

# Test script for load balancer functionality
# This script helps demonstrate load balancing and failover

set -e

echo "================================================"
echo "Load Balancer Testing Script"
echo "================================================"

# Get the load balancer DNS from Terraform output
LB_DNS=$(terraform output -raw load_balancer_dns 2>/dev/null || echo "")

if [ -z "$LB_DNS" ]; then
    echo "Error: Could not get load balancer DNS. Please run 'terraform apply' first."
    exit 1
fi

echo "Load Balancer URL: http://$LB_DNS"
echo ""

# Function to test load balancing
test_load_balancing() {
    echo "Testing Load Balancing (10 requests):"
    echo "--------------------------------------"
    
    for i in {1..10}; do
        echo -n "Request $i: "
        curl -s http://$LB_DNS | grep -o "Server [0-9]" || echo "Failed"
        sleep 0.5
    done
    echo ""
}

# Function to test health check
test_health() {
    echo "Testing Health Check:"
    echo "--------------------"
    response=$(curl -s -o /dev/null -w "%{http_code}" http://$LB_DNS)
    if [ "$response" = "200" ]; then
        echo "✅ Health check passed (HTTP $response)"
    else
        echo "❌ Health check failed (HTTP $response)"
    fi
    echo ""
}

# Function to show instance status
show_instances() {
    echo "Web Server Instances:"
    echo "--------------------"
    
    # Get instance IDs
    instance_ids=$(terraform output -json web_server_ids 2>/dev/null | jq -r '.[]' || echo "")
    
    if [ -z "$instance_ids" ]; then
        echo "Could not retrieve instance IDs"
        return
    fi
    
    # Get AWS region
    region=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")
    
    for id in $instance_ids; do
        status=$(aws ec2 describe-instances \
            --instance-ids $id \
            --region $region \
            --query 'Reservations[0].Instances[0].State.Name' \
            --output text 2>/dev/null || echo "unknown")
        echo "Instance $id: $status"
    done
    echo ""
}

# Function to simulate failover
simulate_failover() {
    echo "Simulating Failover Test:"
    echo "------------------------"
    echo "To test failover manually:"
    echo "1. Stop one instance using AWS Console or CLI"
    echo "2. Wait 30-60 seconds for health check to detect failure"
    echo "3. Run this script again to verify traffic goes to healthy instance"
    echo "4. Start the stopped instance to restore full capacity"
    echo ""
    
    # Get first instance ID for example command
    first_instance=$(terraform output -json web_server_ids 2>/dev/null | jq -r '.[0]' || echo "<instance-id>")
    region=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")
    
    echo "Example AWS CLI commands:"
    echo "  Stop:  aws ec2 stop-instances --instance-ids $first_instance --region $region"
    echo "  Start: aws ec2 start-instances --instance-ids $first_instance --region $region"
    echo ""
}

# Main menu
while true; do
    echo "Choose an option:"
    echo "1. Test Load Balancing"
    echo "2. Test Health Check"
    echo "3. Show Instance Status"
    echo "4. Simulate Failover (instructions)"
    echo "5. Run All Tests"
    echo "6. Exit"
    echo ""
    
    read -p "Enter choice (1-6): " choice
    echo ""
    
    case $choice in
        1)
            test_load_balancing
            ;;
        2)
            test_health
            ;;
        3)
            show_instances
            ;;
        4)
            simulate_failover
            ;;
        5)
            test_health
            show_instances
            test_load_balancing
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid choice. Please try again."
            echo ""
            ;;
    esac
done
