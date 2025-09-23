import streamlit as st
import pandas as pd
import io
import logging
import streamlit as st
import pandas as pd
import logging
from pathlib import Path
from typing import List

from recommender import client, MODEL, load_profile, load_all_profiles, index_products_to_faiss, recommend

try:
    import llm_agent
except Exception:
    llm_agent = None

# Single-mode app: no external agents

# --- logging setup ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "zibochat.log"
logger = logging.getLogger("zibochat.streamlit")
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)

st.set_page_config(page_title='ZiboChat — چت و توصیه محصول', layout='wide')
st.title('زیبوچت — چت و توصیه محصول')

# --- Sidebar settings ---
st.sidebar.header('تنظیمات')
user_id = st.sidebar.text_input('User ID برای حافظه', value='testuser')
use_faiss = st.sidebar.checkbox('استفاده از حافظه (FAISS)', value=True)
st.sidebar.markdown('---')

if st.sidebar.button('ایندکس محصولات به FAISS'):
    try:
        n = index_products_to_faiss('products_index')
        st.sidebar.success(f'شامل {n} محصول در ایندکس ساخته شد.')
        logger.info('Indexed products to products_index')
    except Exception as e:
        logger.exception('Index products failed')
        st.sidebar.error(f'ایندکس محصولات شکست خورد: {e}')

if st.sidebar.button('لیست پروفایل‌ها (نمونه)'):
    try:
        rows = load_all_profiles(limit=5)
        st.sidebar.write(rows)
    except Exception as e:
        st.sidebar.error(f'بارگذاری پروفایل‌ها شکست خورد: {e}')

if st.sidebar.button('نمایش لاگ (آخرین 200 خط)'):
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-200:]
        st.sidebar.text(''.join(lines))
    except Exception as e:
        st.sidebar.error(f'خواندن لاگ شکست خورد: {e}')

st.sidebar.markdown('---')
st.sidebar.write('llm_agent در دسترس است' if llm_agent else 'llm_agent در دسترس نیست')

# --- session messages ---
if 'messages' not in st.session_state:
    st.session_state['messages'] = []  # list of dict {role, content}
if 'profile' not in st.session_state:
    # try to auto-load first profile from Excel (if present)
    try:
        p = load_profile(0)
        st.session_state['profile'] = p
    except Exception:
        st.session_state['profile'] = {}

def append_message(role: str, content: str):
    st.session_state['messages'].append({'role': role, 'content': content})

# Local greeting stripper to avoid repeated greetings in UI regardless of memory state
import re as _re

def _strip_greeting_ui(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.lstrip()
    patterns = [
        r'^(سلام( و وقت بخیر)?)\b[\s\W_]*',
        r'^(درود)\b[\s\W_]*',
        r'^(hi|hello|hey)\b[\s\W_]*',
    ]
    for pat in patterns:
        new_t = _re.sub(pat, '', t, flags=_re.IGNORECASE)
        if new_t != t:
            t = new_t
            break
    return t

def clear_history():
    st.session_state['messages'] = []

col1, col2 = st.columns([3,1])

with col1:
    st.header('چت و توصیه')
    chat_container = st.container()

    user_input = st.text_area('پیام خود را وارد کنید ', height=120)
    btn_send = st.button('ارسال')
    btn_clear = st.button('پاک کردن تاریخچه')

with col2:
    st.header('وضعیت')
    st.write(f'User ID: `{user_id}`')
    st.write(f'حافظه فعال: {"✅" if use_faiss else "❌"}')
    st.write('llm_agent: ' + ('✅' if llm_agent else '❌'))
    st.markdown('**پروفایل جاری:**')
    st.write(st.session_state.get('profile', {}))

    st.markdown('---')
    st.write('ابزارها:')
    
    # بخش حافظه مکالمه
    st.markdown('**حافظه مکالمه:**')
    if st.button('نمایش حافظه مکالمه'):
        try:
            if llm_agent is not None:
                # fallback به llm_agent قدیمی
                user_memory = llm_agent.get_user_memory(user_id)
                recent_context = user_memory.get_recent_context(num_messages=5)
                if recent_context:
                    st.text_area('مکالمات اخیر:', recent_context, height=200)
                else:
                    st.info('هیچ مکالمه‌ای در حافظه موجود نیست.')
            else:
                st.warning('هیچ سیستم حافظه‌ای در دسترس نیست.')
        except Exception as e:
            st.error(f'خطا در نمایش حافظه: {e}')
    
    if st.button('پاک کردن حافظه مکالمه'):
        try:
            if llm_agent is not None:
                # پاک کردن حافظه llm_agent قدیمی
                if 'conversation_memory' in st.session_state:
                    del st.session_state['conversation_memory']
                st.success('حافظه مکالمه پاک شد.')
            else:
                st.warning('هیچ سیستم حافظه‌ای در دسترس نیست.')
        except Exception as e:
            st.error(f'خطا در پاک کردن حافظه: {e}')
    
    st.markdown('---')
    if st.button('بارگزاری یک پروفایل نمونه'):
        try:
            p = load_profile(0)
            st.session_state['profile'] = p
            st.write(p)
        except Exception as e:
            st.error(f'خطا در بارگذاری پروفایل: {e}')

    st.markdown('**آپلود فایل پروفایل (Excel/CSV)**')
    uploaded_profile = st.file_uploader('فایل پروفایل را آپلود کنید (.xlsx یا .csv)', type=['xlsx', 'csv'])
    if uploaded_profile is not None:
        try:
            if str(uploaded_profile.name).lower().endswith('.csv'):
                df_up = pd.read_csv(uploaded_profile)
            else:
                df_up = pd.read_excel(uploaded_profile)
            st.sidebar.write('پیش‌نمایش فایل:')
            st.sidebar.write(df_up.head())
            max_idx = max(0, len(df_up) - 1)
            row_idx = st.sidebar.number_input('ردیف برای استفاده به‌عنوان پروفایل', min_value=0, max_value=max_idx, value=0)
            if st.sidebar.button('استفاده از ردیف انتخاب‌شده'):
                row = df_up.iloc[int(row_idx)].to_dict()
                # try to map common skin-type column names
                def _detect_skin_type(d):
                    keys = {k.lower(): k for k in d.keys()}
                    candidates = ['skin_type', 'skin', 'نوع پوست', 'پوست', 'skin_type_english', 'type']
                    for cand in candidates:
                        for k in keys:
                            if cand in k:
                                return d[keys[k]]
                    # try Persian variations
                    for k in keys:
                        if 'پوست' in k or 'نوع' in k:
                            return d[keys[k]]
                    return None

                st.session_state['profile'] = row
                skin = _detect_skin_type(row)
                if skin:
                    st.sidebar.success(f'پروفایل بارگذاری شد — نوع پوست تشخیص داده شد: {skin}')
                else:
                    st.sidebar.warning('پروفایل بارگذاری شد اما نوع پوست در ستون‌های متداول یافت نشد. می‌توانید دستی در پروفایل ویرایش کنید.')
        except Exception as e:
            st.sidebar.error(f'خواندن فایل شکست خورد: {e}')

    st.markdown('---')

if btn_clear:
    clear_history()

if btn_send and user_input.strip():
    append_message('user', user_input)

    # ایندکس پروفایل به حافظه برای RAG
    try:
        profile = st.session_state.get('profile') or {}
        if use_faiss and llm_agent is not None and profile:
            indexed_map = st.session_state.setdefault('profile_indexed_users', {})
            if not indexed_map.get(user_id):
                prof_text = '\n'.join([f"{k}: {v}" for k, v in profile.items()])
                doc = {'id': f'profile_{user_id}', 'text': prof_text, 'meta': {'type': 'profile'}}
                llm_agent.upsert_user_docs(user_id, [doc])
                indexed_map[user_id] = True
                logger.info(f'Profile for user {user_id} indexed into FAISS')
    except Exception:
        logger.exception('Profile indexing pre-step failed')

    # حالت واحد: پاسخ مدل + توصیه محصولات
    try:
        profile = st.session_state.get('profile', {})
        logger.info("ui:input user_id=%s msg='%s'", user_id, user_input)
        answer, log = recommend(profile, user_input, max_count=5, user_id=user_id)
        logger.info("ui:output user_id=%s ans='%s' log=%s", user_id, answer[:200], {k:log.get(k) for k in ['intent','priority_used','llm_unavailable','recommended_product_ids']})
        # Apply UI greeting stripper to avoid redundant greetings
        answer = _strip_greeting_ui(answer)
        append_message('assistant', answer)
        # Save interaction to memory (for next turns), if llm_agent is available
        try:
            if llm_agent is not None:
                llm_agent.save_conversation_interaction(user_id, user_input, answer)
                print(f"Saved conversation for user_id={user_id}: user='{user_input[:50]}', bot='{answer[:50]}'")
        except Exception as e:
            print(f"Failed to save conversation in Streamlit: {e}")

        # فقط وقتی توصیه واقعی وجود دارد، بخش محصولات را نشان بده
        if not log.get('llm_unavailable') and log.get('recommended_products'):
            st.subheader('نتیجه توصیه')
            priority_map = {1: 'اولویت ۱: محصولات دارای کامنت', 2: 'اولویت ۲: محصولات بدون کامنت', 3: 'اولویت ۳: دانش عمومی مدل'}
            st.write(f"اولویت استفاده‌شده: {priority_map.get(log.get('priority_used'), 'نامشخص')}")
            if log.get('recommended_products'):
                st.markdown('**محصولات پیشنهاد شده:**')
                for p in log['recommended_products']:
                    st.write(f"• {p.get('full_name', p.get('name',''))} (ID: {p.get('id')})")
        elif log.get('llm_unavailable'):
            st.warning('سرویس تولید پاسخ موقتاً در دسترس نیست. لطفاً بعداً مجدداً تلاش کنید.')
    except Exception as e:
        logger.exception('Unified recommend+chat failed')
        append_message('assistant', f'خطا در تولید پاسخ: {e}')

# پس از پردازش پیام‌ها، تاریخچه چت را در placeholder رندر کنیم تا پاسخ مدل بلافاصله دیده شود
def _render_messages(container):
    with container:
        for m in st.session_state['messages']:
            if m['role'] == 'user':
                st.markdown(f"**شما:** {m['content']}")
            else:
                st.markdown(f"**دستیار:** {m['content']}")

_render_messages(chat_container)

st.caption('این رابط برای تست و دیباگ است. برای تولید آماده‌سازی نشده است.')
