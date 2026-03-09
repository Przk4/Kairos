import chromadb
client = chromadb.PersistentClient(path='/opt/kairos/.chroma_db')
cols = client.list_collections()
print('Collections:', [c.name for c in cols])
col = client.get_collection('module_1_course_1')
print('Count:', col.count())
sample = col.get(limit=5, include=['metadatas'])
for m in sample['metadatas']:
    print('importance_score:', m.get('importance_score'), '| item_title:', m.get('item_title','?')[:50])
