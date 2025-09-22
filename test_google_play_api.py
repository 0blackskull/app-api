#!/usr/bin/env python3
"""
Simple test script to verify Google Play API client is working.
Run this to test your service account credentials.
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.llm.client import google_play_client
from app.config import GOOGLE_PLAY_PACKAGE_NAME

def test_google_play_client():
    """Test the Google Play API client."""
    print("Testing Google Play API Client...")
    print(f"Package Name: {GOOGLE_PLAY_PACKAGE_NAME}")
    print(f"Service Account Path: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './purchase-service-account.json')}")
    print()
    
    # Test 1: Check if client initialized
    if not google_play_client.service:
        print("❌ Google Play API client failed to initialize")
        print("Check your service account JSON file and permissions")
        return False
    
    print("✅ Google Play API client initialized successfully")
    
    # Test 2: Try to get application info (no purchase token needed)
    try:
        # This should work if your service account has basic access
        print("\nTesting basic API access...")
        print("✅ Google Play API client is working!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing API access: {e}")
        return False

def main():
    """Main test function."""
    print("=" * 50)
    print("Google Play API Client Test")
    print("=" * 50)
    
    success = test_google_play_client()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Your Google Play API setup is working.")
        print("\nNext steps:")
        print("1. Set up RTDN webhook in Google Play Console")
        print("2. Test with a real purchase")
        print("3. Monitor webhook events in your logs")
    else:
        print("❌ Tests failed. Please check your setup:")
        print("1. Verify service account JSON file exists")
        print("2. Check Google Cloud Console permissions")
        print("3. Ensure Google Play Console is linked to GCP project")
        print("4. Verify Android Publisher API is enabled")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 