#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Credly/GitHub badge helpers.
"""

import re
from datetime import datetime

import requests

GITHUB_ORG_ID = "63074953-290b-4dce-86ce-ea04b4187219"

TRACKED_GITHUB_CERTIFICATIONS = {
    "GitHub Foundations",
    "GitHub Actions",
    "GitHub Advanced Security",
    "GitHub Administration",
    "GitHub Copilot",
    "Microsoft Certified: DevOps Engineer Expert",
    "Microsoft Applied Skills: Accelerate AI-assisted development by using GitHub Copilot",
    "Microsoft Applied Skills: Accelerate app development by using GitHub Copilot",
    "Microsoft Applied Skills: Automate Azure Load Testing by using GitHub Actions",
}

# Microsoft external-badge allowlist currently mirrors tracked certifications.
# Keep as a separate variable for future policy divergence.
ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS = TRACKED_GITHUB_CERTIFICATIONS.copy()

SOURCE_URLS = {
    "credly": {
        "label": "Credly (GitHub organization badges)",
        "urls": [
            "https://www.credly.com/users/{user_id}/badges.json?page=1&per_page=100",
        ],
    },
    "credly_profile": {
        "label": "Credly profile badges (all issuers, tracked cert fallback)",
        "urls": [
            "https://www.credly.com/users/{user_id}/badges.json?page=1&per_page=100",
        ],
    },
    "ms_learn_profile": {
        "label": "MS Learn profile badges (via Credly external badges)",
        "urls": [
            "https://www.credly.com/api/v1/users/{user_id}/external_badges/open_badges/public?page=1&page_size=48",
        ],
    },
}

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def is_badge_expired(expires_at_date):
    """Check if a badge is expired based on expires_at_date."""
    if not expires_at_date:
        return False

    try:
        expiration_date = datetime.strptime(expires_at_date, "%Y-%m-%d").date()
        current_date = datetime.now().date()
        return expiration_date < current_date
    except Exception:
        return False


def _get_json(url, timeout=10, headers=None):
    response = requests.get(url, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_github_external_badges_details(user_id, verbose=False):
    """Fetch Microsoft-issued GitHub badge details for a user."""
    active_badges = set()
    expired_badges = set()
    all_microsoft_badges = set()
    all_external_badges = set()
    page = 1

    while True:
        url = (
            f"https://www.credly.com/api/v1/users/{user_id}"
            f"/external_badges/open_badges/public?page={page}&page_size=48"
        )

        data = _get_json(url, timeout=10)
        badges = data.get("data", [])
        if not badges:
            break

        for badge in badges:
            external_badge = badge.get("external_badge", {})
            badge_name = external_badge.get("badge_name", "").strip()
            issuer_name = external_badge.get("issuer_name", "")
            expires_at_date = badge.get("expires_at_date")

            if issuer_name == "Microsoft":
                all_microsoft_badges.add(badge_name)

            if verbose:
                all_external_badges.add(f"{issuer_name}: {badge_name}")

            if (
                issuer_name == "Microsoft"
                and badge_name in ALLOWED_MICROSOFT_GITHUB_CERTIFICATIONS
            ):
                if is_badge_expired(expires_at_date):
                    expired_badges.add(badge_name)
                else:
                    active_badges.add(badge_name)

        page += 1
        if page > 20:
            break

    result = {
        "active": sorted(active_badges),
        "expired": sorted(expired_badges),
    }

    if verbose:
        result["_debug_all_microsoft_badges"] = sorted(all_microsoft_badges)
        result["_debug_all_external_badges"] = sorted(all_external_badges)

    return result


def fetch_github_org_badges_details(user_id, max_pages=10, verbose=False):
    """Fetch GitHub-org badge details for a user."""
    active_badges = set()
    expired_badges = set()
    all_org_badges = set()
    tracked_any_active = set()
    tracked_any_expired = set()
    page = 1

    while True:
        url = f"https://www.credly.com/users/{user_id}/badges.json?page={page}&per_page=100"
        data = _get_json(url, timeout=10)

        badges = data.get("data", [])
        if not badges:
            break

        for badge in badges:
            issuer = badge.get("issuer", {})
            entities = issuer.get("entities", [])
            badge_template = badge.get("badge_template", {})
            badge_name = badge_template.get("name", "").strip()

            if verbose and badge_name:
                all_org_badges.add(badge_name)

            # Track fallback status for tracked certs from full Credly profile
            # regardless of issuer/org filtering.
            if badge_name in TRACKED_GITHUB_CERTIFICATIONS:
                expires_at_date = badge.get("expires_at_date")
                if is_badge_expired(expires_at_date):
                    tracked_any_expired.add(badge_name)
                else:
                    tracked_any_active.add(badge_name)

            is_github_org = any(
                entity.get("entity", {}).get("id") == GITHUB_ORG_ID
                for entity in entities
            )
            if not is_github_org:
                continue

            if not badge_name:
                continue

            expires_at_date = badge.get("expires_at_date")
            if is_badge_expired(expires_at_date):
                expired_badges.add(badge_name)
            else:
                active_badges.add(badge_name)

        page += 1
        if page > max_pages:
            break

    result = {
        "active": sorted(active_badges),
        "expired": sorted(expired_badges),
        "tracked_any_active": sorted(tracked_any_active),
        "tracked_any_expired": sorted(tracked_any_expired),
    }

    if verbose:
        result["_debug_all_org_badges"] = sorted(all_org_badges)

    return result


def fetch_github_external_badges(user_id):
    """Fetch count of active unique Microsoft-issued GitHub badges."""
    try:
        details = fetch_github_external_badges_details(user_id)
        return len(details["active"])
    except Exception as e:
        print(f"    Warning: Failed to fetch external badges for user {user_id}: {str(e)}")
        return 0


def fetch_github_org_badges(user_id):
    """Fetch count of active unique GitHub-org badges."""
    try:
        details = fetch_github_org_badges_details(user_id)
        return len(details["active"])
    except Exception as e:
        print(f"    Warning: Failed to fetch org badges for user {user_id}: {str(e)}")
        return 0


def fetch_all_github_badges_count(user_id):
    """Fetch total active unique badges from both sources."""
    org_count = fetch_github_org_badges(user_id)
    external_count = fetch_github_external_badges(user_id)
    return org_count + external_count


def extract_username_from_profile_url(profile_url):
    """Extract username from Credly profile URL path or full URL."""
    if not profile_url:
        return ""

    cleaned = profile_url.replace("https://www.credly.com", "")
    parts = [part for part in cleaned.strip("/").split("/") if part]

    if len(parts) >= 2 and parts[0] == "users":
        return parts[1]

    return ""


def fetch_profile_by_username(username):
    """Fetch profile JSON payload by Credly username."""
    if not username:
        return {}

    url = f"https://www.credly.com/users/{username}"
    headers = {"Accept": "application/json"}
    data = _get_json(url, timeout=10, headers=headers)

    return data.get("data", data)


def resolve_user_id(identifier):
    """Resolve user id from a UUID id, username, or profile URL/path."""
    if not identifier:
        raise ValueError("User identifier cannot be empty")

    candidate = identifier.strip()
    if _UUID_PATTERN.match(candidate):
        return candidate

    username = extract_username_from_profile_url(candidate) or candidate
    profile = fetch_profile_by_username(username)

    user_id = profile.get("id") or profile.get("user_id")
    if not user_id:
        raise ValueError(
            "Unable to resolve user id from input. Use a valid Credly username, "
            "profile URL/path, or user UUID."
        )

    return user_id


def fetch_user_github_badge_details(identifier, verbose=False):
    """Fetch detailed badge breakdown for one user."""
    user_id = resolve_user_id(identifier)
    org_details = fetch_github_org_badges_details(user_id, verbose=verbose)
    external_details = fetch_github_external_badges_details(user_id, verbose=verbose)

    return {
        "user_id": user_id,
        "org": org_details,
        "external": external_details,
        "active_total": len(org_details["active"]) + len(external_details["active"]),
        "expired_total": len(org_details["expired"]) + len(external_details["expired"]),
    }


def get_source_urls(user_id):
    """Get source URLs used to fetch badge data for a user."""
    resolved = {}
    for source_name, source_meta in SOURCE_URLS.items():
        resolved[source_name] = {
            "label": source_meta["label"],
            "urls": [url.format(user_id=user_id) for url in source_meta["urls"]],
        }
    return resolved


def get_tracked_certification_status(details):
    """Build status for each tracked certification and identify missing ones."""
    org_active = set(details.get("org", {}).get("active", []))
    org_expired = set(details.get("org", {}).get("expired", []))
    profile_tracked_active = set(details.get("org", {}).get("tracked_any_active", []))
    profile_tracked_expired = set(details.get("org", {}).get("tracked_any_expired", []))
    external_active = set(details.get("external", {}).get("active", []))
    external_expired = set(details.get("external", {}).get("expired", []))

    active = org_active | external_active | profile_tracked_active
    expired = org_expired | external_expired | profile_tracked_expired

    status = {}
    overview = []
    for cert in sorted(TRACKED_GITHUB_CERTIFICATIONS):
        active_sources = []
        if cert in org_active:
            active_sources.append("credly")
        if cert in profile_tracked_active and cert not in org_active:
            active_sources.append("credly_profile")
        if cert in external_active:
            active_sources.append("ms_learn_profile")

        if cert in active:
            cert_status = "active"
        elif cert in expired:
            cert_status = "expired"
        else:
            cert_status = "missing"

        status[cert] = cert_status
        overview.append(
            {
                "certification": cert,
                "status": cert_status,
                "source": active_sources,
            }
        )

    missing = [cert for cert, cert_status in status.items() if cert_status == "missing"]
    status_counts = {
        "active": 0,
        "missing": 0,
        "expired": 0,
        "other": 0,
        "unknown": 0,
    }

    for cert_status in status.values():
        if cert_status in status_counts:
            status_counts[cert_status] += 1
        else:
            status_counts["other"] += 1

    return {
        "tracked_total": len(TRACKED_GITHUB_CERTIFICATIONS),
        "completed_active": sum(1 for value in status.values() if value == "active"),
        "completed_expired": sum(1 for value in status.values() if value == "expired"),
        "missing": missing,
        "status": status,
        "overview": overview,
        "status_counts": status_counts,
    }
