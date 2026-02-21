#!/usr/bin/env python
"""
Test de descarga de PDF con URL correcta desde Django
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

import requests
import pdfplumber
import io
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 80)
print("[TEST] Descarga de PDF desde Canvas")
print("=" * 80)

from django.conf import settings

# URL correcta (como dijiste que funciona)
url = f"{settings.CANVAS_BASE_URL}/courses/1/files/2/download?download_frd=1"

print(f"\nURL: {url}")
print("\n[PASO 1] Descargando PDF...")
print("-" * 80)

try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    response = requests.get(url, headers=headers, timeout=30, verify=False)
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type', '?')}")
    print(f"Tamanio: {len(response.content)} bytes")
    
    if response.status_code != 200:
        print(f"[ERR OR] HTTP {response.status_code}")
        print(response.text[:500] if hasattr(response, 'text') else 'No text')
        sys.exit(1)
    
    content = response.content
    
    # Verificar si es HTML
    if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html'):
        print("[ERROR] RECIBIMOS HTML EN LUGAR DEL PDF")
        print(content[:500].decode('utf-8', errors='ignore'))
        sys.exit(1)
    
    print("[OK] Descarga exitosa - contenido es binario")
    
except Exception as e:
    print(f"[ERROR] Descargando: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[PASO 2] Extrayendo texto con pdfplumber...")
print("-" * 80)

try:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        print(f"PDF abierto, paginas: {len(pdf.pages)}")
        
        total_text = ""
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                print(f"  Pagina {page_num}: {len(page_text)} caracteres")
                total_text += page_text
            else:
                print(f"  Pagina {page_num}: SIN TEXTO")
        
        print(f"\n[OK] Extraccion exitosa!")
        print(f"Total: {len(total_text)} caracteres extraidos")
        
        if total_text:
            print(f"\nPrimeros 500 caracteres:")
            print("-" * 80)
            print(total_text[:500])
            print("-" * 80)
        
except Exception as e:
    print(f"[ERROR] Extrayendo PDF: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("[OK] PRUEBA COMPLETADA EXITOSAMENTE")
print("=" * 80)
