#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch GitHub Certifications data for all countries
Runs cert-github.sh in parallel for all countries in CONTINENT_MAP
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Import CONTINENT_MAP from generate_rankings
from generate_rankings import CONTINENT_MAP

METADATA_FILE = 'csv_metadata.json'
DATASOURCE_DIR = 'datasource'

def get_ignored_countries():
    """Get list of countries to ignore based on date"""
    # India only runs on the 1st of each month (too large for daily runs)
    current_day = datetime.now().day
    if current_day != 1:
        return ['India']
    return []

def get_all_countries():
    """Extract unique countries from CONTINENT_MAP"""
    ignored_countries = get_ignored_countries()
    countries = set()
    for country in CONTINENT_MAP.keys():
        # Convert to title case for proper country names
        country_name = country.title()
        if country_name not in ignored_countries:
            countries.add(country_name)
    return sorted(countries)

def load_metadata():
    """Load CSV metadata from file"""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    """Save CSV metadata to file"""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def get_csv_filename(country):
    """Get CSV filename for a country"""
    file_suffix = country.lower().replace(' ', '-')
    return f'{DATASOURCE_DIR}/github-certs-{file_suffix}.csv'

def fetch_country_data(country, metadata):
    """Fetch data for a single country using cert-github.sh"""
    # Very large countries need much more time (India can have 20k+ users = 2500+ pages)
    if country == 'India':
        timeout = 36000  # 10 hours for India
    elif country in ['Brazil', 'United States', 'China', 'Germany', 'United Kingdom', 'France', 'Canada', 'Japan']:
        timeout = 900  # 15 minutes for other large countries
    else:
        timeout = 300  # 5 minutes for regular countries
    
    csv_file = get_csv_filename(country)
    
    try:
        result = subprocess.run(
            ['./cert-github.sh', country],
            timeout=timeout,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Update metadata with successful download
            metadata[country] = {
                'csv_file': csv_file,
                'last_updated': datetime.now().isoformat(),
                'status': 'success'
            }
            return (country, 'success', None)
        else:
            return (country, 'failed', f"Exit code: {result.returncode}")
    except subprocess.TimeoutExpired:
        return (country, 'failed', f'Timeout ({timeout}s)')
    except Exception as e:
        return (country, 'failed', str(e))

def main():
    """Main execution"""
    print("=" * 80)
    print("GitHub Certifications Data Fetcher")
    print("=" * 80)
    print()
    
    # Create datasource directory if it doesn't exist
    os.makedirs(DATASOURCE_DIR, exist_ok=True)
    
    # Load existing metadata
    metadata = load_metadata()
    
    # Get all countries
    countries = get_all_countries()
    ignored = get_ignored_countries()
    total_countries = len(countries)
    
    print(f"📋 Found {total_countries} countries to process")
    if ignored:
        print(f"⏭️  Skipping (monthly only): {', '.join(ignored)}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Process countries in parallel
    max_workers = 10  # Maximum concurrent downloads
    success_count = 0
    failed_countries = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_country = {
            executor.submit(fetch_country_data, country, metadata): country 
            for country in countries
        }
        
        # Process results as they complete
        for i, future in enumerate(as_completed(future_to_country), 1):
            country, status, error = future.result()
            
            if status == 'success':
                print(f"✓ [{i}/{total_countries}] Success: {country}")
                success_count += 1
            else:
                print(f"✗ [{i}/{total_countries}] Failed: {country} ({error}) - using previous CSV if available")
                failed_countries.append(country)
    
    # Save updated metadata
    save_metadata(metadata)
    
    print()
    print("=" * 80)
    print(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"✅ Success: {success_count}/{total_countries}")
    print(f"❌ Failed: {len(failed_countries)}/{total_countries}")
    
    if failed_countries:
        print()
        print("⚠️  Failed countries (will use previous CSV if available):")
        for country in failed_countries:
            csv_file = get_csv_filename(country)
            if os.path.exists(csv_file):
                print(f"  - {country} (using previous CSV)")
            else:
                print(f"  - {country} (NO CSV AVAILABLE)")
    
    print("=" * 80)
    print("✅ Proceeding with ranking generation...")
    
    # Always exit with 0 to continue with ranking generation
    sys.exit(0)

if __name__ == "__main__":
    main()
