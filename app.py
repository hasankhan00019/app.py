

import streamlit as st
import pandas as pd
import utils
import os
from datetime import datetime
from streamlit_lottie import st_lottie
import requests
import altair as alt
from concurrent.futures import ThreadPoolExecutor, as_completed

# Helper to load Lottie animation from URL
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# Fetch Lottie animation
lottie_logo = load_lottieurl(
    "https://assets10.lottiefiles.com/packages/lf20_0yfsb3a1.json"
)

# Cache author fetches to speed repeated calls
@st.cache_data
def cached_fetch(name: str, affiliation: str):
    return utils.fetch_author_data(name, affiliation)

# Page config
st.set_page_config(
    page_title="University Ranking", layout="wide", page_icon="🎓"
)

# Custom CSS
st.markdown("""
    <style>
        body { background-color: #f0f2f6; }
        section[data-testid='stSidebar'] { background-color: #001f3f; color: white; }
        h1, h2, h3 { color: #001f3f; }
        .dataframe th { background-color: #0074D9; color: white; }
    </style>
""", unsafe_allow_html=True)

# Top animation
if lottie_logo:
    st_lottie(lottie_logo, height=150, key="logo")

# Sidebar settings & concurrency
st.sidebar.title("📂 Settings & Projects")
workers = st.sidebar.slider("Concurrent Workers", 1, 10, 5)
project = st.sidebar.text_input("Project Name", value="MyRankingProject")

if 'projects' not in st.session_state:
    st.session_state['projects'] = {}

if st.sidebar.button("💾 Save Project"):
    st.session_state['projects'][project] = {
        'domain': st.session_state.get('domain'),
        'names_list': st.session_state.get('names_list', [])
    }
    st.sidebar.success("Project saved!")

sel = st.sidebar.selectbox("Load Project", list(st.session_state['projects'].keys()))
if sel:
    proj = st.session_state['projects'][sel]
    st.session_state['domain'] = proj['domain']
    st.session_state['names_list'] = proj['names_list']

# Main UI
st.title("🎓 University Ranking Analytics")

# Domain input & verification
domain = st.text_input("Official Domain (e.g. university.edu)", key='domain')
if domain:
    valid, title = utils.verify_domain(domain)
    if valid:
        st.success(f"✔️ Verified Domain: {title}")
    else:
        st.error("❌ Invalid Domain")

# Professor names via text area
st.subheader("📝 Professor Names Input")
default_names = "\n".join(st.session_state.get('names_list', []))
names_text = st.text_area("Enter each professor name on its own line:", default_names, height=150)
names_list = [n.strip() for n in names_text.splitlines() if n.strip()]
st.session_state['names_list'] = names_list

# Summary metrics (before fetch)
st.subheader("📊 Summary Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Professors", len(names_list))
col2.metric("Avg. h-index", "—")
col3.metric("Avg. Citations", "—")
col4.metric("Publications Range", "—")

# Show previous fetched data if exists
if 'fetched_df' in st.session_state:
    st.subheader("📑 Previously Fetched Data")
    st.dataframe(st.session_state['fetched_df'], use_container_width=True)

# Fetch & Analyze button
status_text = st.empty()
if st.button("🚀 Fetch & Analyze"):
    results = []
    progress = st.progress(0)
    total = len(names_list)

    with st.spinner("Fetching data..."):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(cached_fetch, name, domain): name for name in names_list}
            for i, future in enumerate(as_completed(futures), start=1):
                prof = futures[future]
                status_text.info(f"Fetching data for: {prof}")
                try:
                    data = future.result()
                except Exception as e:
                    st.error(f"Error fetching {prof}: {e}")
                    data = {'name': prof, 'affiliation': None,
                            'total_citations': 0, 'h_index': 0,
                            'i10_index': 0, 'publications': 0}
                results.append(data)
                progress.progress(i/total)

    df = pd.DataFrame(results)
    st.session_state['fetched_df'] = df

    # Display fetched data immediately
    st.subheader("📑 Fetched Data")
    st.dataframe(df, use_container_width=True)

    # Compute safe metrics
    df_clean = df.dropna(subset=['h_index','total_citations','publications'])
    avg_h = round(df_clean['h_index'].mean(),1) if not df_clean.empty else 0
    avg_cit = int(df_clean['total_citations'].mean()) if not df_clean.empty else 0
    pub_min = int(df_clean['publications'].min()) if not df_clean.empty else 0
    pub_max = int(df_clean['publications'].max()) if not df_clean.empty else 0
    col2.metric("Avg. h-index", avg_h)
    col3.metric("Avg. Citations", avg_cit)
    col4.metric("Publications Range", f"{pub_min}–{pub_max}")

    # Visualizations
    st.subheader("📈 Citations Distribution")
    st.bar_chart(df[['name','total_citations']].set_index('name'))

    st.subheader("🔬 h-index vs Publications")
    scatter = alt.Chart(df).mark_circle(size=100).encode(
        x='h_index', y='publications', color='name',
        tooltip=['name','h_index','publications']
    ).interactive()
    st.altair_chart(scatter, use_container_width=True)

    # Download results
    st.download_button(
        "💾 Download Results as CSV",
        data=df.to_csv(index=False),
        file_name=f"ranking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime='text/csv'
    )

    # Final celebration
    st.snow()
    status_text.success("All data fetched successfully!")