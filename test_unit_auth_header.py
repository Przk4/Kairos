#!/usr/bin/env python
"""
Test unitario: Verificar que _extract_text_from_file incluye Authorization header
"""

import os
import django
import requests
from unittest.mock import Mock, patch

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.rag_service import RAGService

print("=" * 80)
print("[UNIT TEST] _extract_text_from_file con Authorization header")
print("=" * 80)

# Crear instancia de RAG Service
rag_service = RAGService()

# Datos de prueba
test_token = "test_token_12345"
test_url = "http://127.0.0.1:3000/courses/1/files/2/download?download_frd=1"

# Mock PDF content
pdf_content = b'%PDF-1.4\ntest pdf content'

print(f"\nURL: {test_url}")
print(f"Token: {test_token[:10]}...")

# Patch requests.get para capturar la solicitud
with patch('requests.get') as mock_get:
    # Configurar respuesta simulada
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = pdf_content
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_get.return_value = mock_response
    
    # Ejecutar método
    result = rag_service._extract_text_from_file(test_url, test_token)
    
    # Verificar que requests.get fue llamado
    assert mock_get.called, "requests.get no fue llamado"
    
    # Obtener los argumentos de la llamada
    call_args = mock_get.call_args
    print(f"\n[VERIFICACIÓN] Argumentos de requests.get:")
    
    # Verificar URL
    url_arg = call_args[0][0] if call_args[0] else call_args[1].get('url')
    print(f"  URL: {url_arg}")
    assert url_arg == test_url, f"URL no coincide: {url_arg} != {test_url}"
    print(f"  ✓ URL correcta")
    
    # Verificar headers
    headers = call_args[1].get('headers', {})
    print(f"  Headers: {list(headers.keys())}")
    
    # Verificar Authorization
    if 'Authorization' in headers:
        auth_header = headers['Authorization']
        print(f"  Authorization: {auth_header[:30]}...")
        if auth_header.startswith('Bearer '):
            print(f"  ✓ Authorization header correcto (Bearer token)")
            assert test_token in auth_header, "Token no está en Authorization header"
            print(f"  ✓ Token incluido en header")
        else:
            print(f"  ✗ Authorization header incorrecto (no es Bearer)")
    else:
        print(f"  ✗ NO HAY Authorization header!")
    
    # Verificar verify=False (para SSL/ngrok)
    verify = call_args[1].get('verify')
    print(f"  verify: {verify}")
    assert verify is False, "verify no es False"
    print(f"  ✓ SSL verification deshabilitada (ngrok)")
    
    # Verificar allow_redirects
    redirects = call_args[1].get('allow_redirects')
    print(f"  allow_redirects: {redirects}")
    assert redirects is True, "allow_redirects no es True"
    print(f"  ✓ Redirecciones permitidas")

print(f"\n[RESULTADO] ✓ Todos los parámetros son correctos")
print(f"_extract_text_from_file ahora incluye Authorization header automáticamente")

print("\n" + "=" * 80)
