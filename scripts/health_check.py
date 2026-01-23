#!/usr/bin/env python3
"""
Health check script for semantic AI system on Railway.
Validates that the API is running and semantic model is loaded.
"""

import requests
import sys
import argparse


def check_railway_health(base_url: str, verbose: bool = False) -> bool:
    """
    Check Railway deployment health.
    
    Args:
        base_url: Base URL of the Railway deployment
        verbose: Print detailed information
        
    Returns:
        True if healthy, False otherwise
    """
    try:
        # Check API health endpoint
        if verbose:
            print(f"🔍 Checking health endpoint: {base_url}/health")
        
        response = requests.get(f"{base_url}/health", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            if verbose:
                print(f"Response: {response.text}")
            return False
        
        health_data = response.json()
        print(f"✅ API Health: {health_data.get('status', 'unknown')}")
        
        if verbose:
            print(f"Full response: {health_data}")
        
        # Check if semantic model is loaded
        if 'semantic_model_loaded' in health_data:
            if health_data['semantic_model_loaded']:
                print("✅ Semantic model is loaded and ready")
                return True
            else:
                print("❌ Semantic model is NOT loaded")
                print("⚠️  System will use exact matching only")
                return False
        else:
            print("⚠️  Semantic model status not available in health response")
            print("   (This may be expected if health endpoint doesn't expose this info)")
            return True  # Don't fail if status not available
            
    except requests.exceptions.Timeout:
        print(f"❌ Request timeout: Could not reach {base_url}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error: Could not connect to {base_url}")
        print("   Make sure the Railway deployment is running")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Health check for Railway deployment'
    )
    parser.add_argument(
        'url',
        nargs='?',
        default='https://your-railway-url.railway.app',
        help='Railway deployment URL (default: https://your-railway-url.railway.app)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print detailed information'
    )
    
    args = parser.parse_args()
    
    # Remove trailing slash if present
    base_url = args.url.rstrip('/')
    
    print("=" * 60)
    print("Railway Deployment Health Check")
    print("=" * 60)
    print(f"Target: {base_url}")
    print()
    
    success = check_railway_health(base_url, args.verbose)
    
    print()
    print("=" * 60)
    if success:
        print("✅ Health check PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ Health check FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
