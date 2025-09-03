from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

import llm_agent

user_index = 'products_index'
query = 'خط چشم'
print('Loading index:', user_index)
store = llm_agent.load_user_index(user_index)
if store is None:
    print('Index load returned None')
    raise SystemExit(1)

print('Index loaded:', type(store))
try:
    results = store.similarity_search_with_score(query, k=3)
    print(f'Found {len(results)} results for query="{query}"\n')
    for i, (doc, score) in enumerate(results, 1):
        meta = getattr(doc, 'metadata', {})
        snippet = doc.page_content.replace('\n', ' ')[:400]
        print(f'[{i}] id/meta: {meta} score={score:.4f}\n{snippet}\n')
except Exception as e:
    print('similarity_search_with_score failed:', e)
    raise

# Also test llm_agent.retrieve_user_memory convenience wrapper
print('\nUsing retrieve_user_memory wrapper:')
mems = llm_agent.retrieve_user_memory(user_index, query, k=3)
print(json.dumps(mems, ensure_ascii=False, indent=2))
