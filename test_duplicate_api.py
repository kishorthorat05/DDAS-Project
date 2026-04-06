#!/usr/bin/env python3
"""
Test duplicate detector API endpoints with the fixed database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
import json

app = create_app()
client = app.test_client()

print("=" * 70)
print("TESTING DUPLICATE DETECTOR API ENDPOINTS (with fixed database)")
print("=" * 70)

# Test 1: Statistics endpoint
print("\n[TEST 1] GET /api/duplicates/statistics")
try:
    res = client.get('/api/duplicates/statistics')
    data = res.get_json()
    print(f"  Status: {res.status_code}")
    print(f"  Response:")
    stats = data.get('data', {})
    for key, value in stats.items():
        print(f"    • {key}: {value}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: All duplicates endpoint
print("\n[TEST 2] GET /api/duplicates/all?limit=1000")
try:
    res = client.get('/api/duplicates/all?limit=1000')
    data = res.get_json()
    print(f"  Status: {res.status_code}")
    print(f"  Response:")
    print(f"    • success: {data.get('success')}")
    print(f"    • message: {data.get('message')}")
    
    duplicates = data.get('data', {})
    if isinstance(duplicates, dict):
        dup_list = duplicates.get('duplicates', [])
        print(f"    • total_groups: {duplicates.get('total_groups')}")
        
        if dup_list:
            print(f"\n  Duplicate Groups ({len(dup_list)} found):")
            for i, group in enumerate(dup_list, 1):
                files = group.get('all_files', [])  # Changed from 'files' to 'all_files'
                print(f"    Group {i} - {len(files)} files:")
                for file in files:
                    print(f"      • {file.get('file_name')} ({file.get('file_size')} bytes)")
                    print(f"        └─ {file.get('file_path')}")
        else:
            print("    No duplicates found")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
