#!/usr/bin/env python
"""
Test con autenticación usando Canvas API token
"""

import os
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import CanvasToken
from django.contrib.auth.models import User

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

print("=" * 80)
print("[TEST] Descarga PDF con autenticación Canvas")
print("=" * 80)

# Obtener token del usuario
try:
    user = User.objects.first()
    if user:
        canvas_token = CanvasToken.objects.filter(user=user).first()
        if canvas_token:
            access_token = canvas_token.access_token
            print(f"\nToken obtenido: {access_token[:20]}...")
            
            local_url = "http://127.0.0.1:3000/courses/1/files/2/download?download_frd=1"
            
            print(f"\nIntentando descargar con autenticación...")
            print(f"URL: {local_url}")
            print("-" * 80)
            
            # Intento 1: Authorization header
            print("\n[Intento 1] Authorization: Bearer {token}")
            response = requests.get(
                local_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Authorization": f"Bearer {access_token}"
                },
                verify=False,
                allow_redirects=True,
                timeout=10
            )
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type')}")
            print(f"  Content-Length: {len(response.content)} bytes")
            print(f"  URL Final: {response.url}")
            
            if response.content.startswith(b'%PDF'):
                print(f"  ✓ ¡ES UN PDF!")
            elif response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                print(f"  ✗ Recibimos HTML (probablemente sigue siendo login page)")
            
            # Intento 2: Token en query parameter
            print("\n[Intento 2] ?access_token={token}")
            url_with_token = f"{local_url}&access_token={access_token}" if "?" in local_url else f"{local_url}?access_token={access_token}"
            response = requests.get(
                url_with_token,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                allow_redirects=True,
                timeout=10
            )
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type')}")
            print(f"  Content-Length: {len(response.content)} bytes")
            print(f"  URL Final: {response.url}")
            
            if response.content.startswith(b'%PDF'):
                print(f"  ✓ ¡ES UN PDF!")
            elif response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                print(f"  ✗ Recibimos HTML")
            
            # Intento 3: Como parámetro Authorization (caso especial de algunos servers)
            print("\n[Intento 3] Authorization: token {token}")
            response = requests.get(
                local_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Authorization": f"token {access_token}"
                },
                verify=False,
                allow_redirects=True,
                timeout=10
            )
            print(f"  Status: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type')}")
            print(f"  Content-Length: {len(response.content)} bytes")
            
            if response.content.startswith(b'%PDF'):
                print(f"  ✓ ¡ES UN PDF!")
            elif response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                print(f"  ✗ Recibimos HTML")
        else:
            print("✗ No canvas token found for user")
    else:
        print("✗ No user found")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "-" * 80)
