#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Display detailed certification information for a given user
Shows: cert name, issuer, external/internal, and missing GitHub certifications
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Set, Tuple

GITHUB_ORG_ID = '63074953-290b-4dce-86ce-ea04b4187219'

ISSUER_ID_MAP = {
    '63074953-290b-4dce-86ce-ea04b4187219': 'GitHub',
    '1392f199-abe0-4698-92b5-834610af6baf': 'Microsoft',
    '51b3fa6d-3818-4bb7-9de4-3e39cbde79bd': 'Microsoft Global Channel Partner Sales (GCPS)',
    '98835c80-ef29-4ca9-b9fb-eeaa3e25e48e': 'Microsoft MCAPS Academy',
}

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

def fetch_org_badges(user_id: str) -> List[Dict]:
    """Fetch organization/GitHub badges for a user"""
    badges = []
    page = 1
    try:
        while page <= 10:
            url = f"https://www.credly.com/users/{user_id}/badges.json?page={page}&per_page=100"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            page_badges = data.get('data', [])
            if not page_badges:
                break
            
            badges.extend(page_badges)
            page += 1
    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch org badges: {str(e)}")
    
    return badges

def fetch_external_badges(user_id: str) -> List[Dict]:
    """Fetch external badges for a user"""
    badges = []
    try:
        url = f"https://www.credly.com/api/v1/users/{user_id}/external_badges/open_badges/public?page=1&page_size=48"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        badges = data.get('data', [])
    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch external badges: {str(e)}")
    
    return badges

def is_from_github(badge: Dict) -> bool:
    """Check if badge is from GitHub organization"""
    issuer = badge.get('issuer', {})
    entities = issuer.get('entities', [])
    return any(e.get('entity', {}).get('id') == GITHUB_ORG_ID for e in entities)

def get_issuer_ids(badge: Dict) -> List[str]:
    """Extract all issuer entity IDs from an org badge"""
    entities = badge.get('issuer', {}).get('entities', [])
    return [e['entity']['id'] for e in entities if e.get('entity', {}).get('id')]

def resolve_issuer_name(badge: Dict) -> str:
    """Resolve issuer name using ISSUER_ID_MAP first, then payload fallbacks"""
    ids = get_issuer_ids(badge)
    # 1) ID map — deterministic, always wins
    for issuer_id in ids:
        if issuer_id in ISSUER_ID_MAP:
            return ISSUER_ID_MAP[issuer_id]
    # 2) payload name fallbacks
    issuer = badge.get('issuer', {})
    if isinstance(issuer, dict) and issuer.get('name'):
        return issuer['name']
    for e in badge.get('issuer', {}).get('entities', []):
        name = e.get('entity', {}).get('name', '')
        if name:
            return name
    # 3) traceable unknown
    if ids:
        return f'Unknown ({", ".join(ids)})'
    return 'Unknown (no-entity-id)'

def display_user_certificates(user_id: str):
    """Display detailed certificate information for a user"""
    print(f"\n{'='*80}")
    print(f"🔍 Certificate Details for User: {user_id}")
    print(f"{'='*80}\n")
    
    # Fetch org badges
    print("📥 Fetching organization badges...")
    org_badges = fetch_org_badges(user_id)
    
    # Fetch external badges
    print("📥 Fetching external badges...")
    external_badges = fetch_external_badges(user_id)
    
    # Process org badges
    print(f"\n{'─'*80}")
    print("🏢 ORGANIZATION BADGES (Internal)")
    print(f"{'─'*80}\n")
    
    # dict: badge_name -> issuer_name (deduped by name, first issuer wins)
    github_certs_held = {}
    
    if org_badges:
        for badge in org_badges:
            if is_badge_expired(badge.get('expires_at_date')):
                continue
            
            badge_name = badge.get('badge_template', {}).get('name', '').strip()
            if not badge_name:
                continue
            
            from_github = is_from_github(badge)
            issuer_name = resolve_issuer_name(badge)
            expires = badge.get('expires_at_date') or 'Never'
            is_official_cert = badge_name in ALLOWED_GITHUB_CERTIFICATION_TITLES
            
            # Count if from GitHub OR title matches (fetch_country.py logic)
            if from_github or is_official_cert:
                github_certs_held.setdefault(badge_name, issuer_name)
                status = "✅" if is_official_cert else "🔷"
                print(f"{status} {badge_name}")
                print(f"   Issuer: {issuer_name}")
                print(f"   From GitHub: {'Yes' if from_github else 'No'}")
                print(f"   Expires: {expires}\n")
    else:
        print("No organization badges found.\n")
    
    # Process external badges
    print(f"{'─'*80}")
    print("🌐 EXTERNAL BADGES (External)")
    print(f"{'─'*80}\n")
    
    if external_badges:
        for badge in external_badges:
            if is_badge_expired(badge.get('expires_at_date')):
                continue
            
            badge_name = badge.get('external_badge', {}).get('badge_name', '').strip()
            if not badge_name:
                continue
            
            issuer_name = (badge.get('external_badge', {}).get('issuer_name') or
                           resolve_issuer_name(badge) or
                           'Unknown (no-entity-id)')
            expires = badge.get('expires_at_date') or 'Never'
            is_official_cert = badge_name in ALLOWED_GITHUB_CERTIFICATION_TITLES
            
            if is_official_cert:
                github_certs_held.setdefault(badge_name, issuer_name)
            
            status = "✅" if is_official_cert else "ℹ️"
            print(f"{status} {badge_name}")
            print(f"   Issuer: {issuer_name}")
            print(f"   External: Yes")
            print(f"   Expires: {expires}\n")
    else:
        print("No external badges found.\n")
    
    # Display GitHub certifications held
    print(f"{'─'*80}")
    print(f"📊 GITHUB CERTIFICATIONS SUMMARY")
    print(f"{'─'*80}\n")
    print(f"🔷 ALL BADGES COUNTED IN RANKINGS: {len(github_certs_held)}")
    for cert in sorted(github_certs_held):
        is_official = cert in ALLOWED_GITHUB_CERTIFICATION_TITLES
        marker = "✅" if is_official else "🔷"
        issuer = github_certs_held[cert]
        print(f"   {marker} {cert}  [{issuer}]")
    
    # Show breakdown
    official_held = {c: v for c, v in github_certs_held.items() if c in ALLOWED_GITHUB_CERTIFICATION_TITLES}
    partner_held = {c: v for c, v in github_certs_held.items() if c not in ALLOWED_GITHUB_CERTIFICATION_TITLES}
    
    print(f"\n📈 Breakdown:")
    print(f"   ✅ Official GitHub Certifications: {len(official_held)}")
    print(f"   🔷 Partner/Other GitHub Badges: {len(partner_held)}")
    
    # Display missing OFFICIAL GitHub certifications
    missing_certs = ALLOWED_GITHUB_CERTIFICATION_TITLES - set(official_held)
    print(f"\n❌ Missing Official GitHub Certifications: {len(missing_certs)}")
    if missing_certs:
        for cert in sorted(missing_certs):
            print(f"   • {cert}")
    else:
        print("   🎉 All official GitHub certifications earned!")
    
    print(f"\n{'='*80}\n")

def main():
    """Main entry point"""
    print("\n🔐 GitHub Certification User Lookup\n")
    
    # Accept user ID from command line or prompt
    import sys
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = input("Enter Credly user ID (e.g., username or user-id): ").strip()
    
    if not user_id:
        print("❌ User ID cannot be empty")
        sys.exit(1)
    
    display_user_certificates(user_id)

if __name__ == '__main__':
    main()
