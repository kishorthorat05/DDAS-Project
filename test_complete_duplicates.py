#!/usr/bin/env python3
"""
Comprehensive test of duplicate detector - verify all data is displayed correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
import json

app = create_app()
client = app.test_client()

print("=" * 80)
print("COMPREHENSIVE DUPLICATE DETECTOR TEST")
print("=" * 80)

# Test 1: Get Statistics
print("\n[1] TESTING STATISTICS ENDPOINT")
print("-" * 80)
res = client.get('/api/duplicates/statistics')
data = res.get_json()
print(f"Status: {res.status_code}")
print(f"Success: {data.get('success')}")
stats = data.get('data', {})
print(f"\nStatistics returned:")
for key, value in sorted(stats.items()):
    print(f"  • {key}: {value}")

# Test 2: Get Duplicates
print("\n\n[2] TESTING DUPLICATES ENDPOINT")
print("-" * 80)
res = client.get('/api/duplicates/all?limit=1000')
data = res.get_json()
print(f"Status: {res.status_code}")
print(f"Success: {data.get('success')}")

duplicates_data = data.get('data', {})
if duplicates_data:
    dup_list = duplicates_data.get('duplicates', [])
    print(f"\nDuplicate groups: {len(dup_list)}")
    
    for i, group in enumerate(dup_list, 1):
        print(f"\n--- Group {i} ---")
        print(f"  file_hash: {group.get('file_hash', 'N/A')[:20]}...")
        print(f"  total_copies: {group.get('total_copies', 'N/A')}")
        
        files = group.get('all_files', [])
        print(f"  Files in group: {len(files)}")
        
        for j, file in enumerate(files, 1):
            print(f"\n    File {j}:")
            print(f"      • Name: {file.get('file_name', 'N/A')}")
            print(f"      • Path: {file.get('file_path', 'N/A')}")
            print(f"      • Size: {file.get('file_size', 'N/A')} bytes")
            print(f"      • Type: {file.get('file_type', 'N/A')}")
            print(f"      • Created: {file.get('created_at', 'N/A')}")
            print(f"      • User: {file.get('user_name', 'N/A')}")

print("\n" + "=" * 80)
print("REQUIRED FIELDS CHECKLIST")
print("=" * 80)

# Verify all required fields are present
required_fields = {
    'Statistics': ['duplicate_files', 'duplicate_groups', 'total_files', 'wasted_storage_bytes', 'duplicate_percentage'],
    'Duplicate Group': ['file_hash', 'total_copies', 'all_files'],
    'File Details': ['file_name', 'file_path', 'file_size', 'file_type', 'created_at', 'user_name']
}

print("\n✓ Statistics fields:")
for field in required_fields['Statistics']:
    has_field = field in stats
    status = "✅" if has_field else "❌"
    print(f"  {status} {field}")

if dup_list:
    group = dup_list[0]
    print("\n✓ Duplicate Group fields:")
    for field in required_fields['Duplicate Group']:
        has_field = field in group
        status = "✅" if has_field else "❌"
        print(f"  {status} {field}")
    
    files = group.get('all_files', [])
    if files:
        file = files[0]
        print("\n✓ File Details fields:")
        for field in required_fields['File Details']:
            has_field = field in file
            status = "✅" if has_field else "❌"
            print(f"  {status} {field}")

print("\n" + "=" * 80)
