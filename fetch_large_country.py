#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Specialized script for fetching large countries with parallel page requests
"""

import csv
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from credly_badges import fetch_all_github_badges_count

def fetch_page(country, page):
    """Fetch a single page for a country (without detailed badge fetching)"""
    url = f"https://www.credly.com/api/v1/directory?organization_id=63074953-290b-4dce-86ce-ea04b4187219&sort=alphabetical&filter%5Blocation_name%5D={country.replace(' ', '%20')}&page={page}&format=json"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Get total_pages from metadata
        metadata = data.get('metadata', {})
        total_pages = metadata.get('total_pages', 0)
        
        # Just return users with directory badge_count (may include expired)
        # We'll fetch detailed badges only for top candidates later
        users = data.get('data', [])
        
        return (page, users, total_pages)
    except Exception as e:
        print(f"  Error on page {page}: {e}")
        return (page, [], 0)

def fetch_country_parallel(country, max_workers=20):
    """Fetch all pages for a country in parallel"""
    print(f"Fetching {country} with parallel requests...")
    
    # First, get the total number of pages
    _, _, total_pages = fetch_page(country, 1)
    
    if total_pages == 0:
        print(f"No data found for {country}")
        return []
    
    print(f"Total pages: {total_pages}")
    
    all_users = []
    
    # Fetch all pages in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_page, country, page): page 
                   for page in range(1, total_pages + 1)}
        
        completed = 0
        for future in as_completed(futures):
            page, users, _ = future.result()
            all_users.extend(users)
            completed += 1
            
            if completed % 100 == 0:
                print(f"  Progress: {completed}/{total_pages} pages ({len(all_users)} users)")
    
    print(f"✓ Completed: {len(all_users)} users from {total_pages} pages")
    
    # Optimization: Only fetch detailed badges for top candidates
    # This reduces requests from thousands to ~50-100
    if all_users:
        # Sort by directory badge_count (includes expired) to get top candidates
        all_users_sorted = sorted(all_users, key=lambda x: x.get('badge_count', 0), reverse=True)
        
        # Take top 30 candidates (with safety margin for ties and expired badges)
        # If fewer users, take all
        top_candidates = all_users_sorted[:min(30, len(all_users_sorted))]
        
        print(f"  Fetching detailed badges for top {len(top_candidates)} candidates (to check expiration)...")
        user_badge_counts = {}
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_user = {
                executor.submit(fetch_all_github_badges_count, user.get('id')): user.get('id')
                for user in top_candidates if user.get('id')
            }
            
            completed = 0
            for future in as_completed(future_to_user):
                user_id = future_to_user[future]
                try:
                    badge_count = future.result()
                    user_badge_counts[user_id] = badge_count
                    completed += 1
                except Exception as e:
                    print(f"    ⚠️  Error fetching badges for user {user_id}: {str(e)}")
                    user_badge_counts[user_id] = 0
        
        print(f"  Processed {len(user_badge_counts)} top candidates")
        
        # Update badge counts with valid (non-expired) badges only for top candidates
        # Keep original badge_count for others (they won't be in rankings anyway)
        for user in all_users:
            user_id = user.get('id')
            if user_id and user_id in user_badge_counts:
                user['badge_count'] = user_badge_counts[user_id]
    
    return all_users

def save_to_csv(country, users, output_dir='datasource'):
    """Save users to CSV file"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    file_suffix = country.lower().replace(' ', '-')
    output_file = f"{output_dir}/github-certs-{file_suffix}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['first_name', 'middle_name', 'last_name', 'badge_count', 'profile_url'])
        
        for user in users:
            writer.writerow([
                user.get('first_name', ''),
                user.get('middle_name', ''),
                user.get('last_name', ''),
                user.get('badge_count', 0),
                user.get('url', '')
            ])
    
    print(f"Saved to {output_file}")
    return output_file

def main():
    """Main execution"""
    if len(sys.argv) < 2:
        print("Usage: ./fetch_large_country.py <country_name>")
        print("Example: ./fetch_large_country.py India")
        sys.exit(1)
    
    country = sys.argv[1]
    
    print("=" * 80)
    print(f"Fetching large country: {country}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # Fetch with parallel requests (20 concurrent pages)
    users = fetch_country_parallel(country, max_workers=20)
    
    if users:
        save_to_csv(country, users)
        print()
        print("=" * 80)
        print(f"✅ Success! Downloaded {len(users)} users")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        sys.exit(0)
    else:
        print("❌ No users found")
        sys.exit(1)

if __name__ == "__main__":
    main()
