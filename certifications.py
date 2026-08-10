#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared certification allowlists and resilient fetch helpers.
"""

import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

# HTTP status codes worth retrying (rate limiting + transient server errors).
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
GITHUB_ORG_ID = '63074953-290b-4dce-86ce-ea04b4187219'


def request_with_retries(url, timeout=30, max_retries=3, base_delay=3):
    """GET a URL with retries and exponential backoff on transient failures.

    Retries on connection/timeout/SSL errors and on retryable HTTP status codes
    (429, 500, 502, 503, 504). Non-retryable HTTP errors (e.g. 404) raise
    immediately. Raises the last exception if every attempt fails so callers can
    distinguish a genuine failure from an empty-but-successful response.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(
                    f"{response.status_code} Server Error", response=response
                )
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            last_exc = e
            if status in RETRYABLE_STATUS and attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise
        except (requests.ConnectionError, requests.Timeout) as e:
            # requests.exceptions.SSLError subclasses ConnectionError, so
            # transient TLS handshake failures are retried here too.
            last_exc = e
            if attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise
    raise last_exc


def count_existing_rows(csv_path):
    """Return the number of data rows (excluding header) in an existing CSV.

    Returns 0 when the file is missing or unreadable. Used to guard against
    overwriting good data with a smaller/degraded dataset from a failed run.
    """
    if not os.path.exists(csv_path):
        return 0
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0


# Badges issued by the GitHub org on Credly that are NOT certifications
# (community awards, recognition programs, sales-only badges). Excluded from all
# counts even though they come from the GitHub organization.
EXCLUDED_BADGES = {
    'GitHub Sales Professional',
    'GitHub Digital Public Goods Open Source Community Manager Program',
    'Hubber Champion',
}

# Whole families of non-certification award badges, matched by name prefix so new
# variants (e.g. "All In Africa <something> Award", "RKO'27 Outstanding Team
# Award - Support") are excluded automatically.
EXCLUDED_BADGE_PREFIXES = (
    'All In Africa',
    'RKO',
)


def is_excluded_badge(badge_name):
    """Return True if a badge is not a certification and must be excluded.

    Matches exact names in EXCLUDED_BADGES and any name starting with one of
    EXCLUDED_BADGE_PREFIXES (award families that keep gaining new variants).
    """
    if not badge_name:
        return False
    name = badge_name.strip()
    if name in EXCLUDED_BADGES:
        return True
    return any(name.startswith(p) for p in EXCLUDED_BADGE_PREFIXES)


ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS = {
    'GitHub Copilot',
    'GitHub Actions',
    'GitHub Advanced Security',
    'GitHub Foundations',
    'GitHub Administration',
    'GitHub Certified: Agentic AI Developer',
    'Microsoft Certified: DevOps Engineer Expert',
    'Microsoft Applied Skills: Accelerate AI-assisted development by using GitHub Copilot',
    'Microsoft Applied Skills: Accelerate app development by using GitHub Copilot',
    'Microsoft Applied Skills: Automate Azure Load Testing by using GitHub Actions',
    'Microsoft Applied Skills: Resolve GitHub issues by using GitHub Copilot',
    'Microsoft Applied Skills: Manage GitHub secret scanning by using GitHub Copilot',
}

# Map of renamed/duplicate badges to their canonical name.
# When Microsoft renames a badge, add the old name as key and the current name as value.
BADGE_NAME_ALIASES = {
    'Microsoft Applied Skills: Accelerate app development by using GitHub Copilot':
        'Microsoft Applied Skills: Accelerate AI-assisted development by using GitHub Copilot',
}


def normalize_badge_name(badge_name):
    """Normalize badge name to its canonical form to avoid counting renamed badges as duplicates."""
    return BADGE_NAME_ALIASES.get(badge_name, badge_name)


def parse_credly_username(person: str) -> str:
    """Return a Credly username from a username or public profile URL."""
    value = person.strip()
    path = urlparse(value).path if '://' in value else value
    parts = [part for part in path.split('/') if part]

    if len(parts) >= 2 and parts[0].lower() == 'users':
        username = parts[1]
    elif len(parts) == 1:
        username = parts[0]
    else:
        raise ValueError('Expected a Credly username or /users/<username> profile URL')

    if not re.fullmatch(r'[A-Za-z0-9._-]+', username):
        raise ValueError(f'Invalid Credly username: {username}')
    return username


def _is_badge_expired(expires_at_date: str | None) -> bool:
    """Return True when a YYYY-MM-DD expiration date is in the past."""
    if not expires_at_date:
        return False
    try:
        return datetime.strptime(expires_at_date, '%Y-%m-%d').date() < datetime.now().date()
    except (TypeError, ValueError):
        return False


def fetch_user_certifications(person: str) -> set[str] | None:
    """Fetch active, tracked certification names for one public Credly user.

    Returns None when either Credly endpoint fails so callers do not report a
    misleading set of missing certifications from partial data.
    """
    username = parse_credly_username(person)
    certification_names: set[str] = set()

    try:
        for page in range(1, 11):
            response = request_with_retries(
                f'https://www.credly.com/users/{username}/badges.json?page={page}&per_page=100',
                timeout=30,
            )
            badges = response.json().get('data', [])
            if not badges:
                break

            for badge in badges:
                entities = badge.get('issuer', {}).get('entities', [])
                is_github_badge = any(
                    item.get('entity', {}).get('id') == GITHUB_ORG_ID
                    for item in entities
                )
                badge_name = badge.get('badge_template', {}).get('name', '').strip()
                if (
                    is_github_badge
                    and badge_name
                    and not is_excluded_badge(badge_name)
                    and not _is_badge_expired(badge.get('expires_at_date'))
                ):
                    certification_names.add(normalize_badge_name(badge_name))

        for page in range(1, 11):
            response = request_with_retries(
                f'https://www.credly.com/api/v1/users/{username}/external_badges/open_badges/public?page={page}&page_size=48',
                timeout=30,
            )
            external_badges = response.json().get('data', [])
            for badge in external_badges:
                external_badge = badge.get('external_badge', {})
                badge_name = external_badge.get('badge_name', '').strip()
                if (
                    external_badge.get('issuer_name') == 'Microsoft'
                    and badge_name in ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS
                    and not _is_badge_expired(badge.get('expires_at_date'))
                ):
                    certification_names.add(normalize_badge_name(badge_name))
            if len(external_badges) < 48:
                break
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f'⚠️  Failed to fetch certifications for {username}: {error}')
        return None

    return certification_names
