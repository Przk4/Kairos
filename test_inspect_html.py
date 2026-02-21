#!/usr/bin/env python
"""
Inspecciona el contenido HTML que Canvas está devolviendo
para entender qué página está siendo mostrada
"""

import requests

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

local_url = "http://127.0.0.1:3000/courses/1/files/2/download?download_frd=1"

print("=" * 80)
print("[TEST] Inspeccionar HTML devuelto por Canvas")
print("=" * 80)
print(f"URL: {local_url}\n")

response = requests.get(
    local_url,
    headers={"User-Agent": "Mozilla/5.0"},
    verify=False,
    allow_redirects=True,
    timeout=10
)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"Content-Length: {len(response.content)}")
print(f"URL Final (después de redirecciones): {response.url}")
print("\n" + "-" * 80)
print("CONTENT HTML (primeros 2000 caracteres):")
print("-" * 80)
print(response.text[:2000])
print("\n" + "-" * 80)

# Ver si hay un enlace de descarga real en el HTML
if 'href' in response.text:
    print("\n[BUSCANDO ENLACES EN HTML]")
    import re
    enlaces = re.findall(r'href=["\']([^"\']+)["\']', response.text)
    for i, enlace in enumerate(enlaces[:10], 1):
        print(f"  {i}. {enlace}")

# Ver si hay algún formulario
if '<form' in response.text:
    print("\n[HAY FORMULARIOS EN HTML]")
    forms = re.findall(r'<form[^>]*>(.*?)</form>', response.text, re.DOTALL)
    for i, form in enumerate(forms[:3], 1):
        print(f"\n  Formulario {i}:")
        print(form[:500])

# Buscar palabras clave
keywords = ['download', 'file', 'pdf', 'attachment', 'unauthorized', 'login', 'authenticate', 'error', 'forbidden']
print(f"\n[PALABRAS CLAVE ENCONTRADAS]")
text_lower = response.text.lower()
for keyword in keywords:
    if keyword in text_lower:
        print(f"  ✓ '{keyword}' encontrada en HTML")
