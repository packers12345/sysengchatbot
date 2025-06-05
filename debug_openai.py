#!/usr/bin/env python3
"""
Debug script to check OpenAI API key configuration
Run this script to diagnose API key issues
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def debug_api_key():
    print("=== OpenAI API Key Debug Script ===\n")
    
    # 1. Check current working directory
    print(f"Current working directory: {os.getcwd()}")
    
    # 2. Check if .env file exists
    env_path = Path(".env")
    env_path_full = Path(os.path.join(os.path.dirname(__file__), ".env"))
    
    print(f"Looking for .env at: {env_path.absolute()}")
    print(f"Alternative path: {env_path_full.absolute()}")
    
    if env_path.exists():
        print("✓ .env file found in current directory")
        env_file = env_path
    elif env_path_full.exists():
        print("✓ .env file found in script directory")
        env_file = env_path_full
    else:
        print("✗ .env file NOT found!")
        print("Please create a .env file in your project root directory")
        return False
    
    # 3. Load environment variables
    print(f"\nLoading environment variables from: {env_file}")
    load_dotenv(dotenv_path=env_file)
    
    # 4. Check .env file contents (without revealing the key)
    print("\n=== .env File Contents Check ===")
    try:
        with open(env_file, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line.startswith('OPENAI_API_KEY'):
                    if '=' in line:
                        key_part = line.split('=', 1)[1].strip()
                        # Remove quotes if present
                        key_part = key_part.strip('"\'')
                        if key_part:
                            print(f"Line {i}: OPENAI_API_KEY found (length: {len(key_part)} chars)")
                            print(f"  Key starts with: {key_part[:10]}...")
                            print(f"  Key ends with: ...{key_part[-4:]}")
                        else:
                            print(f"Line {i}: OPENAI_API_KEY found but empty!")
                    else:
                        print(f"Line {i}: OPENAI_API_KEY found but no '=' sign")
                elif line.startswith('API_KEY'):
                    if '=' in line:
                        key_part = line.split('=', 1)[1].strip()
                        key_part = key_part.strip('"\'')
                        if key_part:
                            print(f"Line {i}: API_KEY found (length: {len(key_part)} chars)")
                            print(f"  Key starts with: {key_part[:10]}...")
                            print(f"  Key ends with: ...{key_part[-4:]}")
                        else:
                            print(f"Line {i}: API_KEY found but empty!")
    except Exception as e:
        print(f"Error reading .env file: {e}")
        return False
    
    # 5. Check environment variables
    print("\n=== Environment Variables Check ===")
    openai_key = os.environ.get("OPENAI_API_KEY")
    api_key = os.environ.get("API_KEY")
    
    if openai_key:
        print(f"✓ OPENAI_API_KEY found in environment (length: {len(openai_key)} chars)")
        print(f"  Starts with: {openai_key[:10]}...")
        print(f"  Ends with: ...{openai_key[-4:]}")
    else:
        print("✗ OPENAI_API_KEY not found in environment")
    
    if api_key:
        print(f"✓ API_KEY found in environment (length: {len(api_key)} chars)")
        print(f"  Starts with: {api_key[:10]}...")
        print(f"  Ends with: ...{api_key[-4:]}")
    else:
        print("✗ API_KEY not found in environment")
    
    # 6. Validate API key format
    print("\n=== API Key Format Validation ===")
    key_to_check = openai_key or api_key
    
    if key_to_check:
        # OpenAI API keys typically start with "sk-" and are 51 characters long
        if key_to_check.startswith("sk-"):
            print("✓ API key starts with 'sk-' (correct format)")
        else:
            print("✗ API key does not start with 'sk-' (incorrect format)")
        
        if len(key_to_check) >= 40:  # Modern OpenAI keys are longer
            print(f"✓ API key length ({len(key_to_check)}) seems reasonable")
        else:
            print(f"✗ API key length ({len(key_to_check)}) seems too short")
        
        # Check for common issues
        if key_to_check.strip() != key_to_check:
            print("✗ API key has leading/trailing whitespace")
        else:
            print("✓ API key has no leading/trailing whitespace")
    else:
        print("✗ No API key found to validate")
        return False
    
    # 7. Test API key with OpenAI
    print("\n=== OpenAI API Test ===")
    try:
        import openai
        client = openai.OpenAI(api_key=key_to_check)
        
        # Test with a simple API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        print("✓ API key is valid and working!")
        return True
        
    except ImportError:
        print("✗ OpenAI package not installed. Run: pip install openai")
        return False
    except Exception as e:
        print(f"✗ API key test failed: {e}")
        if "Incorrect API key" in str(e):
            print("  The API key appears to be invalid")
        elif "quota" in str(e).lower():
            print("  API key is valid but you may have exceeded your quota")
        elif "rate limit" in str(e).lower():
            print("  API key is valid but you hit a rate limit")
        return False

def main():
    success = debug_api_key()
    
    print("\n=== Summary ===")
    if success:
        print("✓ Your OpenAI API key is properly configured and working!")
    else:
        print("✗ There are issues with your OpenAI API key configuration.")
        print("\nCommon solutions:")
        print("1. Ensure your .env file is in the correct location")
        print("2. Check that OPENAI_API_KEY=your_key_here (no spaces around =)")
        print("3. Remove any quotes around the key unless necessary")
        print("4. Ensure the key starts with 'sk-'")
        print("5. Verify the key is correct from OpenAI dashboard")
        print("6. Check your OpenAI account has credits")

if __name__ == "__main__":
    main()