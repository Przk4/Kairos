#!/usr/bin/env python
"""
Test PDF download directly from Canvas local instance (127.0.0.1:3000)
instead of through ngrok tunnel
"""

import requests
import sys

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

print("=" * 80)
print("[TEST] Descarga directa desde 127.0.0.1:3000 (sin ngrok)")
print("=" * 80)

# Intentar con la URL local directa que el usuario menciona
local_url = "http://127.0.0.1:3000/courses/1/files/2/download?download_frd=1"
ngrok_url = "https://malena-staphyloplastic-ecstatically.ngrok-free.dev/courses/1/files/2/download?download_frd=1"

for test_name, test_url in [("LOCAL (127.0.0.1)", local_url), ("NGROK (remoto)", ngrok_url)]:
    print(f"\n[TEST] {test_name}")
    print(f"URL: {test_url}")
    print("-" * 80)
    
    try:
        # Intenta con diferentes headers
        headers_variations = [
            {
                "name": "Solo User-Agent",
                "headers": {"User-Agent": "Mozilla/5.0"}
            },
            {
                "name": "Con Accept: application/pdf",
                "headers": {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"}
            },
            {
                "name": "Con Accept: */*",
                "headers": {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
            },
            {
                "name": "Más headers de navegador",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "*/*",
                    "Accept-Language": "es-ES,es;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                }
            }
        ]
        
        for variation in headers_variations:
            print(f"\n  [{variation['name']}]")
            
            response = requests.get(
                test_url,
                headers=variation['headers'],
                verify=False,
                allow_redirects=True,
                timeout=10
            )
            
            print(f"    Status: {response.status_code}")
            print(f"    Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            print(f"    Content-Length: {len(response.content)} bytes")
            
            # Mostrar primeros bytes
            if len(response.content) > 0:
                first_bytes = response.content[:10]
                is_pdf = first_bytes.startswith(b'%PDF')
                is_html = response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html')
                
                if is_pdf:
                    print(f"    ✓ ¡ES UN PDF! (starts with %PDF)")
                elif is_html:
                    print(f"    ✗ Recibimos HTML")
                    if len(response.text) < 500:
                        print(f"    Contenido:\n{response.text[:500]}")
                else:
                    print(f"    ? Contenido desconocido")
                    print(f"    Primeros bytes: {first_bytes}")
    
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ Error de conexión: {e}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

print("\n" + "=" * 80)
