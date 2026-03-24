#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared Credly badge helpers used by country fetch scripts."""

from datetime import datetime

import requests


ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS = {
    'GitHub Copilot',
    'GitHub Actions',
    'GitHub Advanced Security',
    'GitHub Foundations',
    'GitHub Administration',
    'Microsoft Certified: DevOps Engineer Expert',
    'Microsoft Applied Skills: Accelerate AI-assisted development by using GitHub Copilot',
    'Microsoft Applied Skills: Accelerate app development by using GitHub Copilot',
    'Microsoft Applied Skills: Automate Azure Load Testing by using GitHub Actions',
}


def is_badge_expired(expires_at_date):
    """Check if a badge is expired based on expires_at_date."""
    if not expires_at_date:  # null = never expires
        return False

    try:
        expiration_date = datetime.strptime(expires_at_date, "%Y-%m-%d").date()
        current_date = datetime.now().date()
        return expiration_date < current_date
    except Exception:
        # If we can't parse the date, assume not expired to avoid false positives
        return False


def fetch_github_external_badges(user_id):
    """Fetch GitHub external badges (Microsoft-issued), excluding expired and duplicate badge names."""
    url = f"https://www.credly.com/api/v1/users/{user_id}/external_badges/open_badges/public?page=1&page_size=48"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        unique_badge_names = set()
        for badge in data.get('data', []):
            external_badge = badge.get('external_badge', {})
            badge_name = external_badge.get('badge_name', '')
            issuer_name = external_badge.get('issuer_name', '')
            expires_at_date = badge.get('expires_at_date')

            if issuer_name == 'Microsoft' and badge_name.strip() in ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS:
                if not is_badge_expired(expires_at_date):
                    unique_badge_names.add(badge_name)

        return len(unique_badge_names)
    except Exception as e:
        # If external badges endpoint fails, return 0 (user may have no external badges)
        print(f"    ⚠️  Warning: Failed to fetch external badges for user {user_id}: {str(e)}")
        return 0


def fetch_github_org_badges(user_id):
    """Fetch qualifying non-expired badges from regular profile badges.

    Note: function name is kept for compatibility with existing callers.
    """
    unique_badge_names = set()
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
                badge_template = badge.get('badge_template', {})
                badge_name = badge_template.get('name', '').strip()
                expires_at_date = badge.get('expires_at_date')

                issuer = badge.get('issuer', {})
                issuer_name = (issuer.get('name') or '').strip()
                if (
                    issuer_name == 'Microsoft'
                    and badge_name in ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS
                    and not is_badge_expired(expires_at_date)
                ):
                    unique_badge_names.add(badge_name)

                entities = issuer.get('entities', [])
                is_github_org_badge = False

                for entity in entities:
                    org_data = entity.get('entity', {})
                    if org_data.get('id') == '63074953-290b-4dce-86ce-ea04b4187219':  # GitHub org ID
                        is_github_org_badge = True
                        break

                if is_github_org_badge:
                    if not is_badge_expired(expires_at_date):
                        if badge_name:
                            unique_badge_names.add(badge_name)

            page += 1

            # Safety limit to avoid infinite loops
            if page > 10:
                break

        return len(unique_badge_names)
    except Exception as e:
        # If badges endpoint fails, return 0
        print(f"    ⚠️  Warning: Failed to fetch org badges for user {user_id}: {str(e)}")
        return 0
