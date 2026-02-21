#!/usr/bin/env python
"""
Diagnóstico: Ver estado de módulos, items, y análisis
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
django.setup()

from tu_app.models import Module, ModuleItem, ModuleAnalysis
from django.contrib.auth.models import User
from pathlib import Path

print("=" * 80)
print("[DIAGNÓSTICO] Estado de módulos y PDFs en la base de datos")
print("=" * 80)

# Obtener usuario
user = User.objects.first()
if not user:
    print("✗ No user found")
    exit(1)

print(f"\n[USUARIO] {user.username}")

# Mostrar módulos
modules = Module.objects.filter(course__user=user)
print(f"\n[MÓDULOS] Total: {modules.count()}")
print("-" * 80)

for module in modules:
    items_count = module.items.count()
    analysis = ModuleAnalysis.objects.filter(module=module).first()
    
    print(f"\n📚 {module.name} (ID: {module.id})")
    print(f"   Items: {items_count}")
    print(f"   Análisis: {analysis.status if analysis else '❌ No análisis'}")
    
    # Ver items con archivos
    files = module.items.filter(item_type='file')
    if files.count() > 0:
        print(f"   Archivos en módulo: {files.count()}")
        for file_item in files[:5]:
            print(f"     - {file_item.title}")
            print(f"       URL: {file_item.url[:70]}...")
    
    # Ver estado de embeddings
    embeddings_dir = Path(".embeddings")
    collection_file = embeddings_dir / f"module_{module.id}_course_{module.course.id}.json"
    if collection_file.exists():
        import json
        try:
            with open(collection_file) as f:
                data = json.load(f)
                count = len(data.get('documents', []))
                print(f"   Embeddings JSON: ✅ {count} documentos")
        except:
            print(f"   Embeddings JSON: ❌ Error leyendo archivo")
    else:
        print(f"   Embeddings JSON: ❌ No existe")

print("\n" + "=" * 80)
print("\n[PASOS SIGUIENTES]")
print("1. Si hay items sin análisis, ejecutaremos el análisis")
print("2. Luego verificaremos que DeepSeek pueda acceder a los embeddings")
print("\n" + "=" * 80)
