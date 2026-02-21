import os
import sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kairos_project.settings")
import django
django.setup()

from tu_app.models import Module, ModuleEmbedding
import json

# Force UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("\n" + "=" * 80)
print("CONTENIDO DETALLADO DE ModuleEmbedding")
print("=" * 80)

for module in Module.objects.all():
    try:
        embedding = ModuleEmbedding.objects.get(module=module)
        data = embedding.embedding_data
        
        # Ver qué contiene
        if isinstance(data, dict):
            keys = list(data.keys())
            print(f"\n[MODULE {module.id}] {module.name}")
            print(f"    Keys: {keys}")
            print(f"    document_count en BD: {embedding.document_count}")
            
            # Ver si tiene 'documents'
            if 'documents' in data:
                docs = data.get('documents', [])
                print(f"    [HAS] documents count: {len(docs)}")
                if len(docs) > 0:
                    print(f"      Primer doc: {docs[0][:100] if isinstance(docs[0], str) else str(docs[0])[:100]}...")
            else:
                print(f"    [NO] 'documents' key")
                
            # Ver tamaño
            size = len(json.dumps(data))
            print(f"    Size: {size} bytes")
            
            if size > 100:
                print(f"    >> HAS CONTENT")
            else:
                print(f"    >> EMPTY/ALMOST EMPTY")
                print(f"    Content: {data}")
        else:
            print(f"\n[ERROR] Module {module.id}: data is {type(data)}, not dict")
            
    except ModuleEmbedding.DoesNotExist:
        print(f"\n[MISSING] Module {module.id}: NO ModuleEmbedding")

print("\n" + "=" * 80)
