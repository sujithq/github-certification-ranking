#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch detailed GitHub certification data for a single Credly user.

Accepts one of:
- Credly user UUID
- Credly username
- Credly profile URL/path (for example: /users/jane-doe/badges)
"""

import json
import sys
from datetime import datetime

from credly_badges import (
    extract_username_from_profile_url,
    fetch_profile_by_username,
    fetch_user_github_badge_details,
    resolve_user_id,
)


def _resolve_profile(identifier, user_id):
    """Best-effort profile enrichment for output readability."""
    try:
        username = extract_username_from_profile_url(identifier) or identifier
        profile = fetch_profile_by_username(username)
        if profile:
            return profile
    except Exception:
        pass

    # Fallback: for raw UUID input we still provide a stable id field.
    return {"id": user_id}


def main():
    if len(sys.argv) < 2:
        print("Usage: ./fetch_user.py <user_uuid|username|profile_url>")
        print("Example: ./fetch_user.py 123e4567-e89b-12d3-a456-426614174000")
        print("         ./fetch_user.py john-doe")
        print("         ./fetch_user.py https://www.credly.com/users/john-doe/badges")
        sys.exit(1)

    identifier = sys.argv[1]

    print("=" * 80)
    print(f"Fetching user details for: {identifier}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    try:
        user_id = resolve_user_id(identifier)
        details = fetch_user_github_badge_details(identifier)
        profile = _resolve_profile(identifier, user_id)

        output = {
            "user": {
                "id": user_id,
                "username": profile.get("vanity_slug") or extract_username_from_profile_url(identifier) or "",
                "name": profile.get("display_name", ""),
                "profile_url": profile.get("url", ""),
                "country": profile.get("location", {}).get("country_name", ""),
                "current_organization": profile.get("current_organization_name", ""),
            },
            "counts": {
                "active_total": details["active_total"],
                "expired_total": details["expired_total"],
                "org_active": len(details["org"]["active"]),
                "org_expired": len(details["org"]["expired"]),
                "external_active": len(details["external"]["active"]),
                "external_expired": len(details["external"]["expired"]),
            },
            "badges": {
                "org_active": details["org"]["active"],
                "org_expired": details["org"]["expired"],
                "external_active": details["external"]["active"],
                "external_expired": details["external"]["expired"],
            },
            "generated_at": datetime.now().isoformat(),
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))
        print("=" * 80)
        print("Success")
        print("=" * 80)
        sys.exit(0)

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
