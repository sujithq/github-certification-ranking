#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep analysis of user certifications - matches fetch_country.py logic exactly
Shows where the count comes from and which ones are missing
"""

import requests
from datetime import datetime
from typing import Dict, List, Set, Tuple

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
    'GitHub Partner Pulse -​ Skilled',
}

def is_badge_expired(expires_at_date: str) -> bool:
    """Check if a badge is expired"""
    if not expires_at_date:
        return False
    try:
        expiration_date = datetime.strptime(expires_at_date, "%Y-%m-%d").date()
        return expiration_date < datetime.now().date()
    except Exception:
        return False

def is_from_github(badge: Dict) -> bool:
    """Check if badge is from GitHub organization"""
    issuer = badge.get('issuer', {})
    entities = issuer.get('entities', [])
    return any(e.get('entity', {}).get('id') == GITHUB_ORG_ID for e in entities)

def analyze_user_certifications(user_id: str):
    """
    Analyze user certifications using EXACT same logic as fetch_country.py
    Returns unique_certs set matching count_user_github_certifications
    """
    unique_certs = set()
    all_badges_detail = []
    
    print(f"\n{'='*90}")
    print(f"🔍 DETAILED CERTIFICATION ANALYSIS FOR: {user_id}")
    print(f"{'='*90}\n")
    
    # ===== ORG BADGES =====
    print(f"📥 FETCHING ORGANIZATION BADGES (Credly: /users/{user_id}/badges.json)")
    print(f"{'─'*90}\n")
    
    page = 1
    org_badges_all = []
    try:
        while True:
            url = f"https://www.credly.com/users/{user_id}/badges.json?page={page}&per_page=100"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            badges = data.get('data', [])
            if not badges:
                break

            org_badges_all.extend(badges)
            print(f"  ✓ Page {page}: fetched {len(badges)} badges")
            page += 1
            if page > 10:
                print(f"  ⚠️  Stopping at page 10 (fetch_country.py limit)")
                break
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print(f"\n📊 Total org badges fetched: {len(org_badges_all)}\n")
    
    # Process org badges
    print(f"{'─'*90}")
    print("PROCESSING ORG BADGES (counting non-expired, from GitHub OR title matches):")
    print(f"{'─'*90}\n")
    
    org_badges_counted = 0
    for i, badge in enumerate(org_badges_all, 1):
        badge_name = badge.get('badge_template', {}).get('name', '').strip()
        if not badge_name:
            continue
        
        expires_at = badge.get('expires_at_date')
        is_expired = is_badge_expired(expires_at)
        
        from_github = is_from_github(badge)
        title_matches = badge_name in ALLOWED_GITHUB_CERTIFICATION_TITLES
        
        # This is the exact logic from fetch_country.py
        should_count = (from_github or title_matches) and not is_expired
        
        if should_count:
            org_badges_counted += 1
            unique_certs.add(badge_name)
            status = "✅ COUNTED"
        elif is_expired:
            status = "⏰ EXPIRED"
        elif from_github or title_matches:
            status = "⏰ EXPIRED (would count if valid)"
        else:
            status = "ℹ️  OTHER BADGE"
        
        print(f"{i:2d}. [{status}]")
        print(f"    Name: {badge_name}")
        print(f"    From GitHub: {from_github} | Title Matches: {title_matches} | Expired: {is_expired}")
        print(f"    Expires: {expires_at or 'Never'}\n")
    
    # ===== EXTERNAL BADGES =====
    print(f"\n{'─'*90}")
    print(f"📥 FETCHING EXTERNAL BADGES (Credly: /api/v1/users/{user_id}/external_badges)")
    print(f"{'─'*90}\n")
    
    external_badges_all = []
    try:
        url = f"https://www.credly.com/api/v1/users/{user_id}/external_badges/open_badges/public?page=1&page_size=48"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        external_badges_all = data.get('data', [])
        print(f"  ✓ Fetched {len(external_badges_all)} external badges\n")
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
    
    print(f"{'─'*90}")
    print("PROCESSING EXTERNAL BADGES (counting non-expired, title must match):")
    print(f"{'─'*90}\n")
    
    external_badges_counted = 0
    for i, badge in enumerate(external_badges_all, 1):
        badge_name = badge.get('external_badge', {}).get('badge_name', '').strip()
        if not badge_name:
            continue
        
        expires_at = badge.get('expires_at_date')
        is_expired = is_badge_expired(expires_at)
        title_matches = badge_name in ALLOWED_GITHUB_CERTIFICATION_TITLES
        
        # For external: only count if title matches AND not expired
        should_count = title_matches and not is_expired
        
        if should_count:
            external_badges_counted += 1
            unique_certs.add(badge_name)
            status = "✅ COUNTED"
        elif is_expired:
            status = "⏰ EXPIRED"
        elif title_matches:
            status = "⏰ EXPIRED (would count if valid)"
        else:
            status = "ℹ️  OTHER BADGE"
        
        print(f"{i:2d}. [{status}]")
        print(f"    Name: {badge_name}")
        print(f"    Title Matches: {title_matches} | Expired: {is_expired}")
        print(f"    Expires: {expires_at or 'Never'}\n")
    
    # ===== SUMMARY =====
    print(f"\n{'='*90}")
    print(f"📊 FINAL COUNT (UNIQUE CERTIFICATION NAMES - matches fetch_country.py)")
    print(f"{'='*90}\n")
    
    print(f"✅ Org badges counted: {org_badges_counted}")
    print(f"✅ External badges counted: {external_badges_counted}")
    print(f"📈 TOTAL UNIQUE CERTIFICATIONS: {len(unique_certs)}")
    
    print(f"\n{'─'*90}")
    print("CERTIFICATIONS HELD:")
    print(f"{'─'*90}\n")
    
    for cert in sorted(unique_certs):
        print(f"  ✅ {cert}")
    
    print(f"\n{'─'*90}")
    print("MISSING CERTIFICATIONS:")
    print(f"{'─'*90}\n")
    
    missing = ALLOWED_GITHUB_CERTIFICATION_TITLES - unique_certs
    for cert in sorted(missing):
        print(f"  ❌ {cert}")
    
    print(f"\n{'='*90}\n")
    
    return len(unique_certs), unique_certs, missing

def main():
    """Main entry point"""
    import sys
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = input("Enter Credly user ID: ").strip()
    
    if not user_id:
        print("❌ User ID cannot be empty")
        sys.exit(1)
    
    count, held, missing = analyze_user_certifications(user_id)

if __name__ == '__main__':
    main()
