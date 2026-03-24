#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch detailed certification status for one Credly user."""

import argparse
import json

import requests

from credly_badges_common import (
    fetch_github_external_badges,
    fetch_github_org_badges,
    is_allowed_cert_name,
    is_allowed_external_issuer,
    is_allowed_profile_issuer,
    is_badge_expired,
)

GITHUB_ORG_ID = '63074953-290b-4dce-86ce-ea04b4187219'


def _is_github_org_badge(issuer):
    """Return True when a badge issuer includes the GitHub org entity id."""
    entities = issuer.get('entities', []) if issuer else []
    for entity in entities:
        org_data = entity.get('entity', {})
        if org_data.get('id') == GITHUB_ORG_ID:
            return True
    return False


def _profile_issuer_display_name(issuer, is_github_org):
    """Resolve a readable issuer display name from profile badge issuer metadata."""
    issuer_name = ((issuer or {}).get('name') or '').strip()
    if issuer_name:
        return issuer_name

    for entity in (issuer or {}).get('entities', []):
        entity_name = ((entity.get('entity', {}) or {}).get('name') or '').strip()
        if entity_name:
            return entity_name

    if is_github_org:
        return 'GitHub'

    return ''


def fetch_profile_badge_details(user_id):
    """Fetch all regular profile badges and annotate whether each one counts."""
    page = 1
    results = []

    while True:
        url = f"https://www.credly.com/users/{user_id}/badges.json?page={page}&per_page=100"
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()

        badges = data.get('data', [])
        if not badges:
            break

        for badge in badges:
            badge_template = badge.get('badge_template', {})
            badge_name = (badge_template.get('name') or '').strip()
            expires_at_date = badge.get('expires_at_date')
            expired = is_badge_expired(expires_at_date)

            issuer = badge.get('issuer', {})
            is_github_org = _is_github_org_badge(issuer)
            issuer_name = _profile_issuer_display_name(issuer, is_github_org)
            is_allowed_microsoft = (
                is_allowed_profile_issuer(issuer)
                and is_allowed_cert_name(badge_name)
            )

            counts = (not expired) and (is_github_org or is_allowed_microsoft)

            results.append(
                {
                    'source': 'profile',
                    'name': badge_name,
                    'issuer': issuer_name,
                    'expires_at_date': expires_at_date,
                    'expired': expired,
                    'counts': counts,
                    'count_reason': (
                        'github_org'
                        if counts and is_github_org
                        else 'tracked_microsoft_profile'
                        if counts and is_allowed_microsoft
                        else 'not_counted'
                    ),
                }
            )

        page += 1
        if page > 10:
            break

    return results


def fetch_external_badge_details(user_id):
    """Fetch external badges and annotate whether each one counts."""
    url = f"https://www.credly.com/api/v1/users/{user_id}/external_badges/open_badges/public?page=1&page_size=48"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()

    results = []
    for badge in data.get('data', []):
        external_badge = badge.get('external_badge', {})
        badge_name = (external_badge.get('badge_name') or '').strip()
        issuer_name = (external_badge.get('issuer_name') or '').strip()
        expires_at_date = badge.get('expires_at_date')
        expired = is_badge_expired(expires_at_date)

        is_allowed_microsoft = (
            is_allowed_external_issuer(issuer_name)
            and is_allowed_cert_name(badge_name)
        )
        counts = (not expired) and is_allowed_microsoft

        results.append(
            {
                'source': 'external',
                'name': badge_name,
                'issuer': issuer_name,
                'expires_at_date': expires_at_date,
                'expired': expired,
                'counts': counts,
                'count_reason': 'tracked_microsoft_external' if counts else 'not_counted',
            }
        )

    return results


def build_user_report(user_id):
    """Build a JSON report with per-cert details and total counts."""
    profile_badges = fetch_profile_badge_details(user_id)
    external_badges = fetch_external_badge_details(user_id)

    org_count = fetch_github_org_badges(user_id)
    external_count = fetch_github_external_badges(user_id)

    return {
        'user_id': user_id,
        'total_count_current_logic': org_count + external_count,
        'org_profile_count_current_logic': org_count,
        'external_count_current_logic': external_count,
        'notes': {
            'counts_field_meaning': 'True means this cert instance qualifies under current ranking rules.',
            'total_logic': 'Total equals fetch_github_org_badges(user_id) + fetch_github_external_badges(user_id).',
        },
        'certifications': profile_badges + external_badges,
    }


def dedupe_counted_certifications(certifications):
    """Deduplicate counted certs by (source, name) to mirror count logic totals."""
    deduped = []
    seen = set()

    for cert in certifications:
        key = (cert.get('source'), cert.get('name'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cert)

    return deduped


def main():
    parser = argparse.ArgumentParser(description='Show cert details for a Credly user.')
    parser.add_argument('user_id', help='Credly user id/slug, for example: sujith')
    parser.add_argument('--only-counted', action='store_true', help='Show only certifications where counts=true')
    parser.add_argument(
        '--only-allowed',
        action='store_true',
        help='Show only certifications allowed by current ranking logic (equivalent to counts=true).',
    )
    parser.add_argument(
        '--only-allowlist',
        action='store_true',
        help='Show only allowlist cert names (ALLOWED_CERTIFICATION_NAMES).',
    )
    args = parser.parse_args()

    report = build_user_report(args.user_id)

    if args.only_allowlist:
        report['certifications'] = [
            c for c in report['certifications'] if is_allowed_cert_name(c.get('name'))
        ]

    if args.only_allowed or args.only_counted:
        report['certifications'] = [c for c in report['certifications'] if c.get('counts')]
        report['certifications'] = dedupe_counted_certifications(report['certifications'])

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
