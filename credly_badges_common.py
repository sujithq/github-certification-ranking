#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared Credly badge helpers used by country fetch scripts."""

from datetime import datetime

import requests


ALLOWED_CERTIFICATION_NAMES = {
    'GitHub Copilot',
    'GitHub Actions',
    'GitHub Advanced Security',
    'GitHub Foundations',
    'GitHub Administration',
    'Microsoft Certified: DevOps Engineer Expert',
    'Microsoft Applied Skills: Accelerate AI-assisted development by using GitHub Copilot',
    'Microsoft Applied Skills: Accelerate app development by using GitHub Copilot',
    'Microsoft Applied Skills: Automate Azure Load Testing by using GitHub Actions',
    'GitHub Partner Pulse - Skilled'
}

ALLOWED_ISSUER_ENTITY_IDS = {
    # Microsoft Global Channel Partner Sales (GCPS)
    '51b3fa6d-3818-4bb7-9de4-3e39cbde79bd',
}

ALLOWED_ISSUER_NAME_PREFIXES = (
    'microsoft',
)


def normalize_cert_name(value):
    """Normalize cert names for robust allowlist matching."""
    text = (value or '').replace('\u200b', '').strip()
    return ' '.join(text.split())


NORMALIZED_ALLOWED_CERTIFICATION_NAMES = {
    normalize_cert_name(name) for name in ALLOWED_CERTIFICATION_NAMES
}


def is_allowed_cert_name(name):
    """Return True when cert name is in allowlist after normalization."""
    return normalize_cert_name(name) in NORMALIZED_ALLOWED_CERTIFICATION_NAMES


def _is_allowed_issuer_name(value):
    """Return True when issuer name matches configured issuer prefixes."""
    normalized = (value or '').strip().lower()
    return any(normalized.startswith(prefix) for prefix in ALLOWED_ISSUER_NAME_PREFIXES)


def _has_allowed_issuer_entity_id(issuer):
    """Return True when issuer has an allowlisted organization id."""
    for entity in (issuer or {}).get('entities', []):
        org_data = entity.get('entity', {})
        org_id = (org_data.get('id') or '').strip()
        if org_id in ALLOWED_ISSUER_ENTITY_IDS:
            return True
    return False


def is_allowed_profile_issuer(issuer):
    """Return True when profile issuer metadata matches issuer allowlist."""
    if _has_allowed_issuer_entity_id(issuer):
        return True

    issuer_name = (issuer or {}).get('name')
    if _is_allowed_issuer_name(issuer_name):
        return True

    summary = (issuer or {}).get('summary')
    if _is_allowed_issuer_name(summary):
        return True

    for entity in (issuer or {}).get('entities', []):
        entity_name = (entity.get('entity', {}) or {}).get('name')
        if _is_allowed_issuer_name(entity_name):
            return True

    return False


def is_allowed_external_issuer(issuer_name):
    """Return True when external issuer name matches issuer allowlist."""
    return _is_allowed_issuer_name(issuer_name)


def is_allowed_profile_microsoft_issuer(issuer):
    """Backward-compatible wrapper for previous function name."""
    return is_allowed_profile_issuer(issuer)


def is_allowed_external_microsoft_issuer(issuer_name):
    """Backward-compatible wrapper for previous function name."""
    return is_allowed_external_issuer(issuer_name)


def is_microsoft_profile_issuer(issuer):
    """Backward-compatible wrapper for profile issuer checks."""
    return is_allowed_profile_issuer(issuer)


def is_microsoft_external_issuer(issuer_name):
    """Backward-compatible wrapper for external issuer checks."""
    return is_allowed_external_issuer(issuer_name)


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

            if is_allowed_external_issuer(issuer_name) and is_allowed_cert_name(badge_name):
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
                if (
                    is_allowed_profile_issuer(issuer)
                    and is_allowed_cert_name(badge_name)
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
