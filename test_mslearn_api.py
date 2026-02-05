#!/usr/bin/env python3
"""Test script for MS Learn transcript API and integration."""

import requests
import json
import os

# Test with Jesse Houwing's share ID (from PR #661)
TEST_URL = "https://learn.microsoft.com/en-us/users/jessehouwing-1848/transcript/share/d5gza1z690gp607"
SHARE_ID = 'd5gza1z690gp607'

def test_extract_share_id():
    """Test share ID extraction from different URL formats."""
    from fetch_mslearn_badges import extract_share_id
    
    test_cases = [
        ("https://learn.microsoft.com/en-us/users/jessehouwing-1848/transcript/share/d5gza1z690gp607", "d5gza1z690gp607"),
        ("https://learn.microsoft.com/api/profiles/transcript/share/d5gza1z690gp607?locale=en-us", "d5gza1z690gp607"),
        ("https://learn.microsoft.com/api/profiles/transcript/share/d5gza1z690gp607?WT.mc_id=DOP-MVP-5001511", "d5gza1z690gp607"),
        ("d5gza1z690gp607", "d5gza1z690gp607"),
        ("", None),
        (None, None),
    ]
    
    print("Testing share ID extraction:")
    all_passed = True
    for url, expected in test_cases:
        result = extract_share_id(url)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] {url[:50] if url else 'None'}... -> {result} (expected: {expected})")
    
    return all_passed

def test_mslearn_api():
    """Test the MS Learn API with Jesse Houwing's share ID."""
    url = f"https://learn.microsoft.com/api/profiles/transcript/share/{SHARE_ID}?locale=en-us"
    
    print(f"\nTesting MS Learn API:")
    print(f"  URL: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Total modules completed: {data.get('totalModulesCompleted', 0)}")
            print(f"  UserName: {data.get('userName', 'N/A')}")
            
            cert_data = data.get('certificationData', {})
            print(f"  Active Certifications: {len(cert_data.get('activeCertifications', []))}")
            print(f"  Passed Exams: {len(cert_data.get('passedExams', []))}")
            print(f"  Applied Skills: {len(cert_data.get('appliedSkills', []))}")
            
            # Print details
            for cert in cert_data.get('activeCertifications', []):
                print(f"    - Cert: {cert.get('name')}")
            for exam in cert_data.get('passedExams', []):
                print(f"    - Exam: {exam.get('examNumber')}: {exam.get('examTitle')}")
            for skill in cert_data.get('appliedSkills', []):
                if isinstance(skill, dict):
                    print(f"    - Skill: {skill.get('name')}")
                else:
                    print(f"    - Skill: {skill}")
            
            return True
        else:
            print(f"  Error: API returned {response.status_code}")
            print(f"  Response: {response.text[:200] if response.text else 'empty'}")
            return False
            
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_mslearn_integration():
    """Test the full MS Learn integration with generate_rankings."""
    print("\nTesting MS Learn integration with generate_rankings:")
    
    try:
        from generate_rankings import read_all_csv_files, MSLEARN_AVAILABLE
        print(f"  MSLEARN_AVAILABLE: {MSLEARN_AVAILABLE}")
        
        users = read_all_csv_files('.')
        
        # Find users with mslearn_url
        users_with_mslearn = [u for u in users if u.get('mslearn_url')]
        print(f"  Users with mslearn_url: {len(users_with_mslearn)}")
        
        for u in users_with_mslearn[:5]:
            url = u.get('mslearn_url', '')
            print(f"    - {u['name']}: {url[:60]}..." if len(url) > 60 else f"    - {u['name']}: {url}")
        
        return len(users_with_mslearn) > 0
        
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_fetch_mslearn_badges():
    """Test the fetch_mslearn_github_badges function."""
    print("\nTesting fetch_mslearn_github_badges:")
    
    from fetch_mslearn_badges import fetch_mslearn_github_badges
    
    result = fetch_mslearn_github_badges(TEST_URL, verbose=True)
    
    print(f"  Badge count: {result['badge_count']}")
    print(f"  Certifications: {result['certifications']}")
    print(f"  Applied Skills: {result['applied_skills']}")
    print(f"  Is MVP: {result['is_mvp']}")
    if result['error']:
        print(f"  Error: {result['error']}")
    
    return result['error'] is None

if __name__ == "__main__":
    print("=" * 60)
    print("MS Learn Integration Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("Share ID Extraction", test_extract_share_id()))
    results.append(("MS Learn API", test_mslearn_api()))
    results.append(("Fetch MS Learn Badges", test_fetch_mslearn_badges()))
    results.append(("Integration with Rankings", test_mslearn_integration()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    all_passed = all(r[1] for r in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

