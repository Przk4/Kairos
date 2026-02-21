#!/usr/bin/env python
"""
Test rápido: Verificar si existen embeddings y si tienen PDF binario
"""
import os
import sys
import json
from pathlib import Path

embeddings_dir = Path("c:/Users/Pruzhk4/Desktop/Kairos/.embeddings")

print("\n" + "="*60)
print("CHECKING EMBEDDINGS")
print("="*60 + "\n")

if not embeddings_dir.exists():
    print("❌ Embeddings directory doesn't exist yet")
    sys.exit(0)

json_files = list(embeddings_dir.glob("*.json"))
print(f"Found {len(json_files)} embeddings files\n")

for json_file in json_files:
    print(f"📄 {json_file.name}:")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        docs = data.get('documents', [])
        print(f"   Total documents: {len(docs)}")
        
        if len(docs) == 0:
            print(f"   ⚠️  No documents found")
            continue
        
        # Verificar primeros 3 documentos
        binaries = 0
        valid_text = 0
        
        for i, doc in enumerate(docs[:3]):
            if isinstance(doc, str):
                is_pdf_binary = doc.startswith('%PDF')
                is_png_binary = doc.startswith('\x89PNG')
                is_valid_text = not is_pdf_binary and not is_png_binary and len(doc) > 100
                
                if is_pdf_binary:
                    print(f"   ❌ Doc {i+1}: PDF BINARY <%PDF...>")
                    binaries += 1
                elif is_png_binary:
                    print(f"   ❌ Doc {i+1}: PNG BINARY <%89PNG...>")
                    binaries += 1
                elif is_valid_text:
                    preview = doc[:80].replace('\n', ' ')
                    print(f"   ✅ Doc {i+1}: Valid ({len(doc)} chars) - '{preview}...'")
                    valid_text += 1
                else:
                    print(f"   ⚠️  Doc {i+1}: Short ({len(doc)} chars) - '{doc[:50]}'")
        
        print(f"   → Valid text: {valid_text}, Binaries: {binaries}\n")
        
        if binaries > 0:
            print(f"   ❌ FAILED: PDF binaries detected in embeddings!\n")
        elif valid_text > 0:
            print(f"   ✅ SUCCESS: Valid text found in embeddings!\n")
        else:
            print(f"   ⚠️  No conclusion possible yet (need to analyze)\n")
            
    except Exception as e:
        print(f"   ❌ Error reading: {e}\n")

print("="*60 + "\n")
