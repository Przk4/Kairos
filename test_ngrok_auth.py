#!/usr/bin/env python
"""
Test descargar con Authorization header usando URL de ngrok
"""

import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.views import get_valid_canvas_token
from django.contrib.auth.models import User

requests.packages.urllib3.disable_warnings()

print("=" * 80)
print("[TEST] Descarga con Bearer token - URL de ngrok")
print("=" * 80)

user = User.objects.first()
access_token = get_valid_canvas_token(user)

if not access_token:
    print("✗ No Canvas token")
    exit(1)

print(f"\nToken: {access_token[:20]}...")

# URL de ngrok (como se usa en el análisis)
ngrok_url = "https://malena-staphyloplastic-ecstatically.ngrok-free.dev/courses/1/files/2/download?download_frd=1"

print(f"\nURL: {ngrok_url}")
print("-" * 80)

headers = {
    'User-Agent': 'Mozilla/5.0',
    'Authorization': f'Bearer {access_token}'
}

print(f"\nHeaders: {list(headers.keys())}")
print(f"Authorization: {headers['Authorization'][:40]}...")

response = requests.get(
    ngrok_url,
    headers=headers,
    verify=False,
    allow_redirects=True,
    timeout=10
)

print(f"\nRespuesta:")
print(f"  Status: {response.status_code}")
print(f"  Content-Type: {response.headers.get('Content-Type')}")
print(f"  Content-Length: {len(response.content)} bytes")

if response.content.startswith(b'%PDF'):
    print(f"  ✓ ¡ES UN PDF!")
elif response.content.startswith(b'<!DOCTYPE'):
    print(f"  ✗ HTML response - ngrok error page?")
    print(f"     {response.content[:200].decode('utf-8', errors='ignore')}")
else:
    print(f"  ? Contenido desconocido: {response.content[:50]}")

print("\n" + "=" * 80)
