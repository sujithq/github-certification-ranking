#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch GitHub Certifications for a single country
Includes GitHub-org badges plus tracked Microsoft badges from both
external and regular Credly profile sources.
"""

import csv
import json
import os
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from credly_badges_common import fetch_github_external_badges, fetch_github_org_badges

def fetch_country_data(country):
    """Fetch all data for a country"""
    base_url = f"https://www.credly.com/api/v1/directory?organization_id=63074953-290b-4dce-86ce-ea04b4187219&sort=alphabetical&filter%5Blocation_name%5D={country.replace(' ', '%20')}&page="
    
    all_users = []
    page = 1
    
    print(f"Fetching data for {country}...")
    
    while True:
        url = f"{base_url}{page}&format=json"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            users = data.get('data', [])
            if not users:
                break
            
            all_users.extend(users)
            print(f"  Page {page}: {len(users)} users")
            page += 1
            
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break
    
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
        
        def fetch_all_badges(user_id):
            """Fetch both org badges and external badges"""
            org_count = fetch_github_org_badges(user_id)
            external_count = fetch_github_external_badges(user_id)
            return org_count + external_count
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_user = {
                executor.submit(fetch_all_badges, user.get('id')): user.get('id')
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
    
    print(f"\nSaved to {output_file}")
    return output_file

def main():
    """Main execution"""
    if len(sys.argv) < 2:
        print("Usage: ./fetch_country.py <country_name>")
        print("Example: ./fetch_country.py Brazil")
        print("         ./fetch_country.py \"United States\"")
        sys.exit(1)
    
    country = sys.argv[1]
    
    print("=" * 80)
    print(f"Fetching GitHub certifications for: {country}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    users = fetch_country_data(country)
    
    # Always save CSV, even if empty (to maintain consistency)
    save_to_csv(country, users)
    print()
    print("=" * 80)
    print(f"✅ Success! Downloaded {len(users)} users")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    main()
