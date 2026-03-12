#!/usr/bin/env python3
"""
InfoQuest Search CLI (Python Version)
AI-optimized web search using BytePlus InfoQuest API
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, List, Any, Optional

def usage():
    print("""Usage: search.py "query" [options]
    
Options:
  -s, --site <domain>     Search within specific site (e.g., github.com)
  -d, --days <number>     Search within last N days
  -h, --help              Show this help message

Examples:
  python3 search.py "OpenClaw AI framework"
  python3 search.py "machine learning" -d 7
  python3 search.py "Python tutorials" -s github.com
  python3 search.py "latest news" -d 1
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

def clean_results(raw_results: List[Dict]) -> List[Dict]:
    """Clean and deduplicate search results"""
    seen_urls = set()
    clean_results = []
    
    for content_list in raw_results:
        content = content_list.get('content', {})
        results = content.get('results', {})
        
        # Process organic results
        if 'organic' in results:
            for result in results['organic']:
                clean_result = {'type': 'page'}
                if 'title' in result:
                    clean_result['title'] = result['title']
                if 'desc' in result:
                    clean_result['desc'] = result['desc']
                if 'url' in result:
                    clean_result['url'] = result['url']
                
                url = clean_result.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    clean_results.append(clean_result)
        
        # Process news results
        if 'top_stories' in results:
            news = results['top_stories']
            if 'items' in news:
                for item in news['items']:
                    clean_result = {'type': 'news'}
                    if 'time_frame' in item:
                        clean_result['time_frame'] = item['time_frame']
                    if 'source' in item:
                        clean_result['source'] = item['source']
                    if 'url' in item:
                        clean_result['url'] = item['url']
                    if 'title' in item:
                        clean_result['title'] = item['title']
                    
                    url = clean_result.get('url')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        clean_results.append(clean_result)
    
    return clean_results

def perform_search(query: str, api_key: str, site: str = '', days: int = -1) -> List[Dict]:
    """Perform web search using InfoQuest API"""
    headers = prepare_headers(api_key)
    params = {
        'format': 'JSON',
        'query': query
    }
    
    if days > 0:
        params['time_range'] = days
    
    if site:
        params['site'] = site
    
    try:
        response = requests.post(
            'https://search.infoquest.bytepluses.com',
            headers=headers,
            json=params,
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        if 'search_result' in data:
            results = data['search_result'].get('results', [])
            return clean_results(results)
        elif 'content' in data:
            raise ValueError('web search API returned wrong format')
        else:
            return data
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Search failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='AI-optimized web search using BytePlus InfoQuest API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s "AI framework"
  %(prog)s "machine learning" -d 7
  %(prog)s "Python tutorials" -s github.com
  %(prog)s "latest news" -d 1
"""
    )
    
    parser.add_argument('query', help='Search query')
    parser.add_argument('-s', '--site', help='Search within specific site (e.g., github.com)', default='')
    parser.add_argument('-d', '--days', type=int, help='Search within last N days', default=-1)
    
    args = parser.parse_args()
    
    # Check API key
    api_key = check_api_key()
    
    try:
        # Perform search
        results = perform_search(args.query, api_key, args.site, args.days)
        
        # Output results
        output = {
            'query': args.query,
            'count': len(results),
            'results': results
        }
        
        print(json.dumps(output, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()