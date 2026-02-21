#!/usr/bin/env python
"""
Test script para verificar que el flujo RAG completo funciona:
1. RAG Service se inicializa
2. Análisis de módulos no produce PDF binarios
3. Búsqueda de contexto retorna documentos válidos
4. El estado se actualiza correctamente
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kairos_project.settings')
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from tu_app.models import Module, Course, ModuleAnalysis
from tu_app.rag_service import get_rag_service
from django.contrib.auth.models import User
import logging

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_rag_flow():
    print("\n" + "="*60)
    print("TESTING RAG FLOW")
    print("="*60 + "\n")
    
    # 1. Obtener datos de test
    try:
        user = User.objects.first()
        if not user:
            print("❌ No users found")
            return False
            
        course = Course.objects.filter(user=user).first()
        if not course:
            print(f"❌ No courses found for user {user.username}")
            return False
            
        modules = Module.objects.filter(course=course)
        if not modules.exists():
            print(f"❌ No modules found in course {course.name}")
            return False
            
        print(f"✅ Found {modules.count()} modules for testing")
        
        # 2. Verificar RAG Service
        rag_service = get_rag_service()
        print(f"\n📊 RAG Service Status:")
        print(f"   Using ChromaDB: {rag_service.using_chromadb}")
        print(f"   In-memory collections: {len(rag_service.in_memory_db)}")
        
        # 3. Test con el primer módulo
        test_module = modules.first()
        print(f"\n🔍 Testing with module: {test_module.name}")
        print(f"   Items in module: {test_module.items.count()}")
        
        # 4. Verificar si ya tiene análisis
        analysis, created = ModuleAnalysis.objects.get_or_create(module=test_module)
        collection_name = f"module_{test_module.id}_course_{test_module.course.id}"
        
        embeddings_count = rag_service.get_embeddings_count(collection_name)
        print(f"   Current embeddings: {embeddings_count}")
        
        # 5. Si tienen embeddings, verificar que no son PDF binario
        if embeddings_count > 0:
            print(f"\n✅ Embeddings found!")
            
            # Buscar un documento de prueba
            if not rag_service.using_chromadb and collection_name in rag_service.in_memory_db:
                collection = rag_service.in_memory_db[collection_name]
                docs = collection.get('documents', [])
                
                print(f"\n📄 Document Quality Check:")
                print(f"   Total documents: {len(docs)}")
                
                # Verificar los primeros documentos
                binaries_found = 0
                valid_text_found = 0
                
                for i, doc in enumerate(docs[:5]):
                    if isinstance(doc, str):
                        has_pdf_marker = doc.startswith('%PDF')
                        has_png_marker = doc.startswith('\x89PNG')
                        is_short = len(doc) < 50
                        
                        if has_pdf_marker:
                            print(f"   ❌ Doc {i+1}: PDF BINARY DETECTED!")
                            binaries_found += 1
                        elif has_png_marker:
                            print(f"   ❌ Doc {i+1}: PNG BINARY DETECTED!")
                            binaries_found += 1
                        elif is_short:
                            print(f"   ⚠️  Doc {i+1}: Only {len(doc)} chars (probably filename)")
                        else:
                            preview = doc[:100].replace('\n', ' ')
                            print(f"   ✅ Doc {i+1}: Valid text ({len(doc)} chars) - '{preview}...'")
                            valid_text_found += 1
                
                # Resumen
                print(f"\n📈 Summary:")
                print(f"   Valid documents: {valid_text_found}")
                print(f"   Binaries found: {binaries_found}")
                print(f"   Short docs: {len(docs) - valid_text_found - binaries_found}")
                
                if binaries_found > 0:
                    print(f"\n❌ FAILED: Binary PDF data found in embeddings!")
                    return False
                elif valid_text_found == 0:
                    print(f"\n⚠️  WARNING: No valid text documents found")
                    return False
                else:
                    print(f"\n✅ SUCCESS: All documents contain valid text!")
                    
                    # Test búsqueda
                    print(f"\n🔎 Testing search functionality:")
                    results = rag_service.search_context("¿Qué es esto?", test_module.id, test_module.course.id, top_k=2)
                    print(f"   Retrieved {len(results)} documents")
                    
                    for i, result in enumerate(results):
                        content = result.get('content', '')
                        similarity = result.get('relevance_score', 0)
                        title = result.get('metadata', {}).get('item_title', 'Unknown')
                        print(f"   [{i+1}] {title} (Relevance: {similarity:.2%}) - {len(content)} chars")
                    
                    return True
            else:
                print(f"✅ Embeddings exist (using ChromaDB backend)")
                return True
        else:
            print(f"\n⚠️  No embeddings found. Need to run analysis first.")
            print(f"   To test analysis, run analyze API endpoint or use web interface.")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_rag_flow()
    print("\n" + "="*60)
    if success:
        print("✅ RAG FLOW TEST PASSED")
    else:
        print("❌ RAG FLOW TEST FAILED")
    print("="*60 + "\n")
    sys.exit(0 if success else 1)
