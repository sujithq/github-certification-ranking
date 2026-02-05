#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add mslearn_url column to all existing CSV files
Run this script once to migrate existing CSV files to the new format
"""

import csv
import glob
import os

DATASOURCE_DIR = 'datasource'

def add_mslearn_url_column():
    """Add mslearn_url column to all CSV files in datasource directory."""
    csv_files = glob.glob(os.path.join(DATASOURCE_DIR, 'github-certs-*.csv'))
    
    print(f"Found {len(csv_files)} CSV files to update...")
    
    updated_count = 0
    for csv_file in csv_files:
        try:
            # Read existing data
            rows = []
            with open(csv_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                # Check if mslearn_url column already exists
                if 'mslearn_url' in fieldnames:
                    print(f"  Skipping {os.path.basename(csv_file)} - mslearn_url column already exists")
                    continue
                
                for row in reader:
                    rows.append(row)
            
            # Add mslearn_url to fieldnames
            new_fieldnames = list(fieldnames) + ['mslearn_url']
            
            # Write updated data with new column
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=new_fieldnames)
                writer.writeheader()
                for row in rows:
                    row['mslearn_url'] = ''  # Empty by default
                    writer.writerow(row)
            
            print(f"  Updated {os.path.basename(csv_file)}")
            updated_count += 1
            
        except Exception as e:
            print(f"  Error processing {csv_file}: {e}")
    
    print(f"\nCompleted! Updated {updated_count} files.")

if __name__ == "__main__":
    add_mslearn_url_column()
