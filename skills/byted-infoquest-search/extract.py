#!/usr/bin/env python3
"""
InfoQuest Extract CLI (Python Version)
Extract webpage content using BytePlus InfoQuest API
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, Any, Optional

def usage():
    print("""Usage: extract.py "url"
    
Examples:
  python3 extract.py "https://github.com/openclaw/openclaw"
""")
    sys.exit(2)

def check_api_key():
    """Check if API key is set in environment"""
    api_key = os.environ.get("INFOQUEST_API_KEY", "").strip()
    if not api_key:
        print("Error: INFOQUEST_API_KEY environment variable is not set")
        print("Set it using: export INFOQUEST_API_KEY='your-api-key-here'")
        print("Get your API key from: https://docs.byteplus.com/en/docs/InfoQuest/What_is_Info_Quest")
        sys.exit(1)
    return api_key

def prepare_headers(api_key: str) -> Dict[str, str]:
    """Prepare request headers"""
    headers = {
        'Content-Type': 'application/json',
    }
    
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    
    return headers

def prepare_crawl_request_data(url: str) -> Dict[str, str]:
    """Prepare crawl request data"""
    return {
        'url': url,
        'format': 'HTML'
    }

def format_content(content: str, url: str) -> str:
    """Format extracted content"""
    if not content or content.startswith('Error:'):
        return f"# Failed to extract content from: {url}\nError: {content}\n"
    
    return f"# Content from: {url}\n\n{content}\n"

def fetch_content(url: str, api_key: str, return_format: str = 'html') -> str:
    """Fetch webpage content using InfoQuest API"""
    headers = prepare_headers(api_key)
    data = prepare_crawl_request_data(url)
    
    try:
        response = requests.post(
            'https://reader.infoquest.bytepluses.com',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if not response.ok:
            return f"Error: fetch API returned status {response.status}: {response.text}"
        
        text = response.text
        
        if not text or not text.strip():
            return 'Error: no result found'
        
        # Try to parse as JSON and extract reader_result
        try:
            json_data = json.loads(text)
            if 'reader_result' in json_data:
                return json_data['reader_result']
            elif 'content' in json_data:
                return 'Error: fetch API returned wrong format'
        except json.JSONDecodeError:
            # Not JSON, return as-is
            pass
        
        return text
        
    except requests.exceptions.RequestException as e:
        return f"Error: fetch API failed: {str(e)}"

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Extract webpage content using BytePlus InfoQuest API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s "https://github.com/openclaw/openclaw"
"""
    )
    
    parser.add_argument('url', help='URL to extract content from')
    
    args = parser.parse_args()
    
    # Check API key
    api_key = check_api_key()
    
    try:
        # Fetch content
        content = fetch_content(args.url, api_key)
        
        if content.startswith('Error:'):
            print(f"Error: {content}", file=sys.stderr)
            sys.exit(1)
        
        # Format and output content
        print(format_content(content, args.url))
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()