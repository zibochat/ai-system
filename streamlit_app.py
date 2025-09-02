import streamlit as st
import pandas as pd
import io
import logging
import traceback
from pathlib import Path

from recommender import client, MODEL, load_profile, load_all_profiles
import llm_agent

# --- logging setup ---
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "zibochat.log"
logger = logging.getLogger("zibochat")
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)

st.set_page_config(page_title='ZiboChat Memory Test', layout='wide')

st.title('ZiboChat — FAISS Memory Tester')

user_id = st.text_input('User ID (for FAISS index)', value='testuser')

st.header('1) Upload profile Excel (optional)')
uploaded = st.file_uploader('Upload Excel (one or more rows)', type=['xlsx'])
if uploaded is not None:
    try:
        df = pd.read_excel(uploaded)
        st.write('Preview:', df.head())
        if st.button('Index uploaded profile'):
            # take first row as profile
            try:
                row = df.iloc[0].to_dict()
                text = '\n'.join([f"{k}: {v}" for k,v in row.items()])
                llm_agent.upsert_user_docs(user_id, [{'id': f'profile_row_0', 'text': text, 'meta': {'type':'profile'}}])
                st.success('Profile indexed into FAISS for user: %s' % user_id)
                logger.info(f'Indexed profile for user {user_id}')
            except Exception as e:
                logger.exception('Failed to index uploaded profile')
                st.error('Indexing failed: %s' % e)
    except Exception as e:
        logger.exception('Failed to read uploaded excel')
        st.error('Failed to read uploaded excel: %s' % e)

st.header('2) Retrieve existing profiles')
if st.button('List built-in profiles'):
    rows = load_all_profiles(limit=5)
    st.write(rows)

st.header('3) Chat (RAG + store facts)')
user_msg = st.text_area('User message', '')
if st.button('Send message'):
    if not user_msg.strip():
        st.warning('Write a message first')
    else:
        # retrieve user memory
        try:
            mem = llm_agent.retrieve_user_memory(user_id, user_msg, k=6)
            st.subheader('Retrieved memories')
            for m in mem:
                st.write(m)
        except Exception as e:
            logger.exception('Memory retrieval failed')
            st.error('Memory retrieval failed: %s' % e)

        # call chat_with_context
        try:
            resp = llm_agent.chat_with_context(messages=[{'role':'user','content':user_msg}], model=MODEL, user_id=user_id, client=client)
            st.subheader('Model response')
            st.write(resp)
            logger.info(f'Chat success for user {user_id}')
        except Exception as e:
            logger.exception('Chat failed')
            st.error('Chat failed: %s' % e)
            st.error('See logs for details')

        # extract facts and store
        try:
            facts = llm_agent.extract_and_store_chat_facts(user_id, user_msg, client=client)
            st.subheader('Extracted facts stored')
            st.write(facts)
        except Exception as e:
            logger.exception('Fact extraction failed')
            st.error('Fact extraction failed: %s' % e)

st.caption('This is a simple test UI — not for production.')

# --- log viewer ---
st.sidebar.header('Logs')
if st.sidebar.button('Show last 200 lines'):
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-200:]
        st.sidebar.text(''.join(lines))
    except Exception as e:
        st.sidebar.error('Failed to read log file: %s' % e)
