import re
import streamlit as st
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from datetime import datetime, timezone, time, timedelta
from scraper_api import NordotApiClient

st.set_page_config(page_title="Ekkow Content Quality Score", layout="wide")
api_key = st.secrets.get("OPENAI_API_KEY")

if "audit_results" not in st.session_state:
    st.session_state.audit_results = []

def sync_select_all():
    """Callback to update all individual checkboxes when 'Select All' is toggled."""
    new_state = st.session_state.master_selector
    for story in st.session_state.audit_results:
        st.session_state[f"cb_{story['title']}"] = new_state

def check_url(url):
    """Returns True if link is broken, False if OK."""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code >= 400
    except:
        return True

def find_broken_links(text):
    """Extracts links from text and checks them concurrently."""
    urls = re.findall(r'(https?://[^\s<>"]+|www\.[^\s<>"]+)', text)
    if not urls:
        return []
    
    broken_links = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(check_url, urls))
        for url, is_broken in zip(urls, results):
            if is_broken:
                broken_links.append(url)
    return broken_links

def get_ai_evaluation(client, title, body):
    prompt = f"""You are an expert journalism fact-checker. 
Your task is to score how accurately and objectively the Title represents the Article Body.

Scoring criteria (from 0.0 to 1.0):
- 0.0 to 0.3: Factually FALSE (e.g., wrong killer/victim), or highly manipulative (e.g., claiming deliberate murder when the text explicitly states accidental discharge or lack of indictment).
- 0.4 to 0.6: Partially true but sensationalized, omits crucial context, or uses emotionally manipulative framing (e.g., clickbait).
- 0.7 to 1.0: Factually accurate, non-manipulative, objective, and aligns perfectly with the text's nuance.

Article Body:
{body}

Title to Evaluate:
{title}

You MUST respond in this exact format:
Reasoning: [1-2 sentences explaining the logical check]
Score: [a single float between 0.0 and 1.0]"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a precise, unbiased fact-checking AI."},
                  {"role": "user", "content": prompt}],
        temperature=0.1
    )
    content = response.choices[0].message.content.strip()
    score_match = re.search(r"Score:\s*([0-9.]+)", content)
    score = float(score_match.group(1)) if score_match else 0.0
    reasoning_match = re.search(r"Reasoning:\s*(.*?)(?=\nScore:|$)", content, re.DOTALL | re.IGNORECASE)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else content
    return score, reasoning

st.title("Ekkow Content Quality Score")
st.markdown("Analyze headlines from Nordot units for accuracy, images, and broken links.")

with st.sidebar:
    st.header("Control Panel")
    unit_id = st.text_input("Nordot Unit ID:", placeholder="1305879384872009777")
    st.divider()
    audit_mode = st.radio("Audit Mode:", ["Latest Articles", "Date Range"], index=0)
    
    start_dt, end_dt, limit_count = None, None, None
    if audit_mode == "Latest Articles":
        limit_count = st.number_input("Number of articles:", min_value=1, max_value=100, value=20)
    else:
        today = datetime.now().date()
        date_range = st.date_input("Select Range:", value=(today - timedelta(days=7), today))
        if len(date_range) == 2:
            start_dt = datetime.combine(date_range[0], time.min).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(date_range[1], time.max).replace(tzinfo=timezone.utc)

    st.divider()
    run_audit = st.button("Start Audit", type="primary", use_container_width=True)
    
    if st.session_state.audit_results:
        st.divider()
        st.header("Export Data")
        
        selected_data = [
            s for s in st.session_state.audit_results 
            if st.session_state.get(f"cb_{s['title']}", False)
        ]
        
        if selected_data:
            df = pd.DataFrame(selected_data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"Download {len(selected_data)} Selected (CSV)",
                data=csv,
                file_name=f"nordot_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime='text/csv',
                use_container_width=True
            )
        else:
            st.info("Select articles using the checkboxes to export.")

if run_audit:
    if not unit_id:
        st.warning("Please provide a Unit ID.")
    elif not api_key:
        st.error("OpenAI API key missing.")
    else:
        client = OpenAI(api_key=api_key)
        scraper = NordotApiClient(unit_id)

        with st.status("Performing Multi-Point Audit...", expanded=True) as status:
            if audit_mode == "Date Range":
                stories = scraper.run(start_date=start_dt, end_date=end_dt)
            else:
                stories = scraper.run(limit=limit_count)

            if stories:
                temp_results = []
                for story in stories:
                    score, reasoning = get_ai_evaluation(client, story['title'], story['body_text'])

                    status.write(f"Checking links for: {story['title'][:30]}...")
                    broken_links = find_broken_links(story['body_text'])
                    
                    temp_results.append({
                        "title": story['title'],
                        "score": score,
                        "reasoning": reasoning,
                        "published_at": story['published_at'],
                        "has_images": story.get('has_images'),
                        "broken_links": ", ".join(broken_links) if broken_links else "",
                        "body_text": story['body_text']
                    })
                    st.session_state[f"cb_{story['title']}"] = False
                
                st.session_state.audit_results = temp_results
                status.update(label="Audit Complete!", state="complete", expanded=False)
            else:
                st.error("No articles found.")

if st.session_state.audit_results:
    st.divider()

    search_query = st.text_input("Search results by title:", key="main_search")
    results = st.session_state.audit_results
    if search_query:
        results = [s for s in results if search_query.lower() in s['title'].lower()]

    tab1, tab2, tab3 = st.tabs(["Quality Audit", "Missing Images", "Broken Links"])
    manipulative_count = 0

    with tab1:
        accurate_count, sens_count, manip_count = 0, 0, 0
        st.checkbox("Select All Visible", key="master_selector", on_change=sync_select_all)
        for story in results:
            if story['score'] >= 0.7:
                label, accurate_count = "✅ Accurate", accurate_count + 1
            elif story['score'] >= 0.4:
                label, sens_count = "⚠️ Sensationalized", sens_count + 1
            else:
                label, manipulative_count = "🚨 Manipulative", manip_count + 1

            col_sel, col_content = st.columns([0.1, 3.9])
            with col_sel:
                st.checkbox("", key=f"cb_{story['title']}")

            with col_content:
                with st.expander(f"[{story['score']}] {story['title']}"):
                    c1, c2 = st.columns([1, 4])
                    c1.metric("Score", story['score'], label)
                    c2.markdown(f"**Reasoning:** {story['reasoning']}")

        total = len(results)
        if total > 0:
            st.divider()
            st.subheader("Audit Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Accurate", accurate_count, f"{(accurate_count/total)*100:.1f}%")
            c2.metric("Sensationalized", sens_count, f"{(sens_count/total)*100:.1f}%")
            c3.metric("Manipulative", manipulative_count, f"{(manipulative_count/total)*100:.1f}%")

    with tab2:
        no_image_stories = [s for s in results if not s['has_images']]
        st.subheader(f"Articles without Images ({len(no_image_stories)})")
        if not no_image_stories:
            st.success("All articles have images!")
        for s in no_image_stories:
            st.warning(f"**Missing Image:** {s['title']}")
            st.caption(f"Published: {s['published_at']}")

    with tab3:
        broken_link_stories = [s for s in results if s['broken_links']]
        st.subheader(f"Articles with Broken Hyperlinks ({len(broken_link_stories)})")
        if not broken_link_stories:
            st.success("No broken links found!")
        for s in broken_link_stories:
            with st.expander(f"Broken Link(s) in: {s['title']}"):
                st.error(f"Links: {s['broken_links']}")
