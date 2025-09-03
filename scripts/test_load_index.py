import os
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDX_DIR = ROOT / 'data' / 'faiss' / 'products_index'
print('Workspace root:', ROOT)
print('Index dir:', IDX_DIR)
print('Files:')
for p in sorted(IDX_DIR.glob('*')):
    print(' -', p.name, p.stat().st_size, 'bytes')

try:
    import llm_agent
    print('Imported llm_agent:', llm_agent)
    print('Calling load_user_index("products_index")...')
    idx = llm_agent.load_user_index('products_index')
    print('Result:', type(idx), repr(idx))
    # if langchain FAISS object, try to run similarity search
    try:
        res = idx.similarity_search('test', k=2)
        print('similarity_search returned', len(res))
    except Exception as e:
        print('similarity_search raised:')
        traceback.print_exc()
except Exception as e:
    print('Exception while loading index:')
    traceback.print_exc()

print('\nEnvironment variables relevant:')
for k in ['OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_MODEL']:
    print(k, os.environ.get(k))
