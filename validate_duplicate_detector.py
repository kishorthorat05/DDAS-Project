#!/usr/bin/env python3
"""
Final validation test - verify all duplicate detector features are working
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import create_app
import json

app = create_app()
client = app.test_client()

print("\n" + "="*80)
print("DUPLICATE DETECTOR - FINAL VALIDATION TEST")
print("="*80 + "\n")

tests_passed = 0
tests_failed = 0

def test(name, condition, details=""):
    global tests_passed, tests_failed
    status = "[PASS]" if condition else "[FAIL]"
    print(f"{status} {name}")
    if details and not condition:
        print(f"  Details: {details}")
    if condition:
        tests_passed += 1
    else:
        tests_failed += 1

# TEST 1: Basic API Endpoints
print("TEST GROUP 1: API ENDPOINTS\n")

res = client.get('/api/duplicates/statistics')
test("Statistics endpoint responds", res.status_code == 200)
test("Statistics returns success", res.get_json().get('success') == True)

res = client.get('/api/duplicates/all')
test("Get duplicates endpoint responds", res.status_code == 200)
test("Get duplicates returns success", res.get_json().get('success') == True)

# TEST 2: Statistics Data Fields
print("\nTEST GROUP 2: STATISTICS DATA FIELDS\n")

stats = client.get('/api/duplicates/statistics').get_json().get('data', {})
required_stats = [
    'duplicate_files',
    'duplicate_groups', 
    'total_files',
    'unique_files',
    'wasted_storage_bytes',
    'total_storage_bytes',
    'duplicate_percentage'
]

for field in required_stats:
    test(f"Statistics has '{field}'", field in stats, 
         f"Missing field: {field}")

test("Statistics shows duplicates found", stats.get('duplicate_groups', 0) > 0,
     f"Expected > 0, got {stats.get('duplicate_groups', 0)}")

test("Statistics shows wasted storage", stats.get('wasted_storage_bytes', 0) > 0,
     f"Expected > 0 bytes, got {stats.get('wasted_storage_bytes', 0)}")

# TEST 3: Duplicate Group Structure
print("\nTEST GROUP 3: DUPLICATE GROUP STRUCTURE\n")

dup_data = client.get('/api/duplicates/all').get_json().get('data', {})
dup_groups = dup_data.get('duplicates', [])

test("Duplicates API returns groups", len(dup_groups) > 0,
     f"Expected > 0 groups, got {len(dup_groups)}")

if dup_groups:
    group = dup_groups[0]
    required_group_fields = [
        'file_hash',
        'total_copies',
        'all_files'
    ]
    
    for field in required_group_fields:
        test(f"Group has '{field}'", field in group,
             f"Missing field: {field}")
    
    # TEST 4: File Details in Group
    print("\nTEST GROUP 4: FILE DETAILS IN GROUP\n")
    
    files = group.get('all_files', [])
    test("Group has files", len(files) > 0,
         f"Expected > 0 files, got {len(files)}")
    
    if files:
        file_obj = files[0]
        required_file_fields = [
            'file_name',
            'file_path',
            'file_size',
            'file_type',
            'created_at',
            'user_name'
        ]
        
        for field in required_file_fields:
            test(f"File has '{field}'", field in file_obj,
                 f"Missing field: {field}")
    
    # TEST 5: Data Validation
    print("\nTEST GROUP 5: DATA VALIDATION\n")
    
    test("File name is string", isinstance(file_obj.get('file_name'), str))
    test("File path is string", isinstance(file_obj.get('file_path'), str))
    test("File size is number", isinstance(file_obj.get('file_size'), (int, float)))
    test("File type is string", isinstance(file_obj.get('file_type'), str))
    test("File has path displayed", len(file_obj.get('file_path', '')) > 0)
    test("File size > 0", file_obj.get('file_size', 0) > 0)

# TEST 6: Frontend Compatibility
print("\nTEST GROUP 6: FRONTEND COMPATIBILITY\n")

test("API returns 'all_files' for duplicates", 
     'all_files' in dup_groups[0] if dup_groups else False,
     "Frontend expects 'all_files' key")

test("Files use 'file_path' field",
     'file_path' in (dup_groups[0].get('all_files', [{}])[0] if dup_groups else {}),
     "Frontend uses 'file_path' not 'file_location'")

# SUMMARY
print("\n" + "="*80)
print(f"TEST SUMMARY: {tests_passed} PASSED, {tests_failed} FAILED")
print("="*80 + "\n")

if tests_failed == 0:
    print("SUCCESS! All tests passed. Duplicate detector is ready for use.\n")
    sys.exit(0)
else:
    print(f"FAILURE! {tests_failed} test(s) failed.\n")
    sys.exit(1)
