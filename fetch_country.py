#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch GitHub Certifications for a single country
"""

import csv
import json
import os
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

GITHUB_ORG_ID = '63074953-290b-4dce-86ce-ea04b4187219'

ALLOWED_GITHUB_CERTIFICATION_TITLES = {
    'GitHub Copilot',
    'GitHub Actions',
    'GitHub Advanced Security',
    'GitHub Foundations',
    'GitHub Administration',
    'Microsoft Certified: DevOps Engineer Expert',
    'Microsoft Applied Skills: Accelerate AI-assisted development by using GitHub Copilot',
    'Microsoft Applied Skills: Accelerate app development by using GitHub Copilot',
    'Microsoft Applied Skills: Automate Azure Load Testing by using GitHub Actions',
    'GitHub Partner Pulse - Skilled',
}

def is_badge_expired(expires_at_date):
    """Check if a badge is expired based on expires_at_date"""
    if not expires_at_date:  # null = never expires
        return False
    
    try:
        expiration_date = datetime.strptime(expires_at_date, "%Y-%m-%d").date()
        return expiration_date < datetime.now().date()
    except Exception:
        # If we can't parse the date, assume not expired to avoid false positives
        return False

def count_user_github_certifications(user_id):
    """Count GitHub certifications for a user.

    Rules (non-expired only):
    - If it comes from GitHub (GitHub org issuer) → add to counter
    - If the title matches an allowed certification → add to counter
    """
    unique_certs = set()

    # Org badges: count if from GitHub OR title matches
    page = 1
    try:
        while True:
            url = f"https://www.credly.com/users/{user_id}/badges.json?page={page}&per_page=100"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            badges = data.get('data', [])
            if not badges:
                break

            for badge in badges:
                if is_badge_expired(badge.get('expires_at_date')):
                    continue

                badge_name = badge.get('badge_template', {}).get('name', '').strip()
                if not badge_name:
                    continue

                from_github = any(
                    e.get('entity', {}).get('id') == GITHUB_ORG_ID
                    for e in badge.get('issuer', {}).get('entities', [])
                )
                title_matches = badge_name in ALLOWED_GITHUB_CERTIFICATION_TITLES

                if from_github or title_matches:
                    unique_certs.add(badge_name)

            page += 1
            if page > 10:
                break
    except Exception as e:
        print(f"    ⚠️  Warning: Failed to fetch org badges for user {user_id}: {str(e)}")

    # External badges: count if title matches
    try:
        url = f"https://www.credly.com/api/v1/users/{user_id}/external_badges/open_badges/public?page=1&page_size=48"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        for badge in data.get('data', []):
            if is_badge_expired(badge.get('expires_at_date')):
                continue

            badge_name = badge.get('external_badge', {}).get('badge_name', '').strip()
            if badge_name in ALLOWED_GITHUB_CERTIFICATION_TITLES:
                unique_certs.add(badge_name)
    except Exception as e:
        print(f"    ⚠️  Warning: Failed to fetch external badges for user {user_id}: {str(e)}")

    return len(unique_certs)

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
            return count_user_github_certifications(user_id)
        
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
