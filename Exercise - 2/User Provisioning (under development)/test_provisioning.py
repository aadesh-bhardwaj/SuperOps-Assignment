#!/usr/bin/env python3
"""
Test script for AWS User Provisioning System

Author: Aadesh
Date: December 2024
"""

import json
import sys
import time
from user_provisioning import AWSUserProvisioner


def test_user_lifecycle():
    """Test complete user lifecycle."""
    print("🧪 Testing User Provisioning System")
    print("=" * 50)
    
    provisioner = AWSUserProvisioner()
    test_username = f"test-user-{int(time.time())}"
    
    try:
        # Test 1: Create user
        print(f"\n1️⃣ Creating test user: {test_username}")
        result = provisioner.create_user(
            username=test_username,
            email="test@example.com",
            department="Testing",
            groups=["ReadOnly"],
            console_access=True,
            programmatic_access=True
        )
        print(f"✅ User created: {result['user_arn']}")
        
        # Test 2: Rotate access keys
        print(f"\n2️⃣ Rotating access keys...")
        new_keys = provisioner.rotate_access_keys(test_username)
        print(f"✅ New access key: {new_keys['access_key_id']}")
        
        # Test 3: Enable MFA
        print(f"\n3️⃣ Enabling MFA...")
        mfa_result = provisioner.enable_mfa(test_username)
        print(f"✅ MFA device created: {mfa_result['serial_number']}")
        
        # Test 4: Generate report
        print(f"\n4️⃣ Generating access report...")
        report = provisioner.generate_report('access')
        print(f"✅ Report generated with {len(report.split('\\n'))} lines")
        
        # Test 5: Delete user
        print(f"\n5️⃣ Deleting test user...")
        provisioner.delete_user(test_username, force=True)
        print(f"✅ User deleted successfully")
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        # Cleanup
        try:
            provisioner.delete_user(test_username, force=True)
        except:
            pass
        return False


if __name__ == '__main__':
    success = test_user_lifecycle()
    sys.exit(0 if success else 1)
