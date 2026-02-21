#!/usr/bin/env python
import json

with open('.embeddings/module_2_course_1.json', encoding='utf-8') as f:
    data = json.load(f)

docs = data.get('documents', [])
print(f'Total documents: {len(docs)}\n')

for i, doc in enumerate(docs, 1):
    length = len(doc)
    preview = doc[:100].replace('\n', ' ')[:100]
    print(f'Doc {i}: {length} chars')
    print(f'  > {preview}...\n')
