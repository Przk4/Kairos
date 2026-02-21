#!/usr/bin/env python
"""
MIGRACION DE EMBEDDINGS: De archivos .embeddings/ a BD (ModuleEmbedding)
Ejecutar ANTES de migrar a DigitalOcean
"""
import sys, os, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
sys.path.insert(0, os.path.dirname(__file__))
import django
django.setup()

from tu_app.models import ModuleEmbedding, Module

print("\n" + "="*80)
print("MIGRANDO EMBEDDINGS A BASE DE DATOS")
print("="*80)

# Buscar todos los archivos .embeddings/
embeddings_dir = ".embeddings"
migrated = 0
failed = 0

if not os.path.exists(embeddings_dir):
    print("No embedding directory found. Nothing to migrate.")
else:
    for filename in os.listdir(embeddings_dir):
        if not filename.endswith('.json'):
            continue
        
        filepath = os.path.join(embeddings_dir, filename)
        
        # Parse: module_X_course_Y.json
        try:
            parts = filename.replace('.json', '').split('_')
            module_id = int(parts[1])
            course_id = int(parts[3])
            
            # Cargar datos del archivo
            with open(filepath, 'r', encoding='utf-8') as f:
                embedding_data = json.load(f)
            
            # Obtener módulo
            module = Module.objects.get(id=module_id)
            
            # Crear o actualizar ModuleEmbedding
            embedding_obj, created = ModuleEmbedding.objects.get_or_create(module=module)
            embedding_obj.embedding_data = embedding_data
            embedding_obj.save()
            
            doc_count = len(embedding_data.get('documents', []))
            status = "CREATED" if created else "UPDATED"
            
            print(f"[OK] Module {module_id}: {status} ({doc_count} docs)")
            migrated += 1
            
        except Exception as e:
            print(f"[ERROR] {filename}: {e}")
            failed += 1

print("\n" + "="*80)
print(f"RESUMEN: {migrated} migrados, {failed} errores")
print("="*80)
print("\nProximos pasos:")
print("1. Verificar que todo se vea bien en la UI")
print("2. Hacer backup de .embeddings/ (opcional, ahora está en BD)")
print("3. Listo para DigitalOcean!")
print("\n")
