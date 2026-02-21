#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to trigger analyze_module endpoint and verify multiple embeddings
"""

import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000"

# First, need to login to get csrf token
session = requests.Session()

print("\n" + "="*80)
print("TEST: Analyzing module with multiple embeddings")
print("="*80)

# Get CSRF token
print("\n[1] Getting CSRF token...")
resp = session.get(f"{BASE_URL}/admin/login/")
csrf_token = None
for cookie in session.cookies:
    if cookie.name == 'csrftoken':
        csrf_token = cookie.value

if csrf_token:
    print(f"  CSRF Token: {csrf_token[:20]}...")
else:
    print("  [WARN] No CSRF token - trying without")

# Try to call analyze_module endpoint directly
# Looking at the code, it seems like it might be accessible via POST to /api/analyze/module/{module_id}/
print("\n[2] Attempting to find modules...")

# Let's try to get module list from Django API
try:
    resp = session.get(f"{BASE_URL}/api/modules/")
    if resp.status_code == 200:
        modules = resp.json()
        print(f"  Found {len(modules)} modules")
        for m in modules[:2]:
            print(f"    - {m.get('name', 'Unknown')} (ID: {m.get('id', '?')})")
    else:
        print(f"  API endpoint not found or error: {resp.status_code}")
except Exception as e:
    print(f"  Error getting modules: {e}")

# Try calling the analyze endpoint
print("\n[3] Calling analyze_module endpoint...")
module_id = 1  # Based on the database, this is the first module

try:
    # POST to analyze module
    resp = session.post(
        f"{BASE_URL}/tu_app/analyze_module/{module_id}/",
        headers={'X-CSRFToken': csrf_token} if csrf_token else {},
        timeout=60
    )
    
    print(f"  Status: {resp.status_code}")
    
    if resp.status_code == 200:
        try:
            data = resp.json()
            print(f"  Response: {json.dumps(data, indent=2)[:500]}...")
        except:
            print(f"  Response: {resp.text[:500]}...")
    else:
        print(f"  Response: {resp.text[:1000]}...")
        
except requests.exceptions.Timeout:
    print(f"  Timeout (expected, analysis takes time)")
except Exception as e:
    print(f"  Error: {e}")

# Check if embeddings were created
print("\n[4] Checking embeddings created...")
embeddings_dir = ".embeddings"
if os.path.exists(embeddings_dir):
    files = os.listdir(embeddings_dir)
    print(f"  Found {len(files)} embedding files")
    
    for f in files[:3]:
        filepath = os.path.join(embeddings_dir, f)
        with open(filepath, 'r') as fp:
            data = json.load(fp)
            num_chunks = len(data.get('documents', []))
            total_chars = sum(len(d) for d in data.get('documents', []))
            print(f"    - {f}: {num_chunks} chunks, {total_chars} chars total")
            
            if num_chunks > 1:
                print(f"      SUCCESS! Multiple embeddings created")
                for i, doc in enumerate(data.get('documents', [])[:3]):
                    print(f"        Chunk {i+1}: {len(doc)} chars")
else:
    print(f"  No embeddings directory found")

print("\n" + "="*80)
