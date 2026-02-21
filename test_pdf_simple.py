#!/usr/bin/env python
"""
Test simple de descarga de PDF con la URL correcta
"""
import requests
import pdfplumber
import io

print("=" * 80)
print("[TEST] Descarga simple de PDF desde Canvas")
print("=" * 80)

# URL correcta (como dijiste que funciona)
url = "http://127.0.0.1:3000/courses/1/files/2/download?download_frd=1"

print(f"\nURL: {url}")
print("\n[PASO 1] Descargando PDF...")
print("-" * 80)

try:
    headers = {
        'User-Agent': 'Mozilla/5.0',
    }
    
    response = requests.get(url, headers=headers, timeout=30, verify=False)
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type', '?')}")
    print(f"Tamaño: {len(response.content)} bytes")
    
    if response.status_code != 200:
        print(f"[ERROR] HTTP {response.status_code}")
        print(response.text[:500])
        exit(1)
    
    content = response.content
    
    # Verificar si es HTML
    if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html'):
        print("[ERROR] RECIBIMOS HTML EN LUGAR DEL PDF")
        print(content[:500].decode('utf-8', errors='ignore'))
        exit(1)
    
    print("[OK] Descarga exitosa - contenido es binario")
    
except Exception as e:
    print(f"[ERROR] Descargando: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n[PASO 2] Extrayendo texto con pdfplumber...")
print("-" * 80)

try:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        print(f"PDF abierto, páginas: {len(pdf.pages)}")
        
        total_text = ""
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                print(f"  Página {page_num}: {len(page_text)} caracteres")
                total_text += page_text
            else:
                print(f"  Página {page_num}: SIN TEXTO")
        
        print(f"\n[OK] Extracción exitosa!")
        print(f"Total: {len(total_text)} caracteres extraídos")
        
        if total_text:
            print(f"\nPrimeros 500 caracteres:")
            print("-" * 80)
            print(total_text[:500])
            print("-" * 80)
        
except Exception as e:
    print(f"[ERROR] Extrayendo PDF: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 80)
print("[OK] PRUEBA COMPLETADA EXITOSAMENTE")
print("=" * 80)
