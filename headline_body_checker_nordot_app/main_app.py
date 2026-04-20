import re
import streamlit as st
from openai import OpenAI
from datetime import datetime, timezone, time, timedelta
from scraper_api import NordotApiClient

st.set_page_config(page_title="Ekkow Content Quality Score", layout="wide")
api_key = st.secrets.get("OPENAI_API_KEY")

def get_ai_evaluation(client, title, body):
    """Sends the title and body to OpenAI and parses the result."""
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
        messages=[
            {"role": "system", "content": "You are a precise, unbiased fact-checking AI."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

    content = response.choices[0].message.content.strip()
    score_match = re.search(r"Score:\s*([0-9.]+)", content)
    score = float(score_match.group(1)) if score_match else 0.0
    reasoning_match = re.search(r"Reasoning:\s*(.*?)(?=\nScore:|$)", content, re.DOTALL | re.IGNORECASE)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else content
    
    return score, reasoning

st.title("Ekkow Content Quality Score")
st.markdown("Analyze headlines from Nordot units for accuracy and manipulation.")

with st.sidebar:
    st.header("Control Panel")
    unit_id = st.text_input("Nordot Unit ID:", placeholder="1305879384872009777")

    st.divider()

    audit_mode = st.radio(
        "Audit Mode:",
        ["Latest Articles", "Date Range"],
        index=0,
        help="Choose whether to fetch the most recent N articles or articles from a specific time period."
    )
    
    start_dt = None
    end_dt = None
    limit_count = None

    if audit_mode == "Latest Articles":
        limit_count = st.number_input("Number of articles to fetch:", min_value=1, max_value=100, value=20)
    else:
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        date_range = st.date_input(
            "Select Range:",
            value=(week_ago, today),
            help="Articles outside this range will be ignored."
        )
        if len(date_range) == 2:
            start_dt = datetime.combine(date_range[0], time.min).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(date_range[1], time.max).replace(tzinfo=timezone.utc)

    st.divider()
    run_audit = st.button("Start Audit", type="primary", use_container_width=True)
    
    st.markdown("### Scoring Guide")
    st.success("🟢 0.7 - 1.0: Accurate")
    st.warning("🟡 0.4 - 0.6: Sensationalized")
    st.error("🔴 0.0 - 0.3: False / Manipulative")

if run_audit:
    if not unit_id:
        st.warning("Please provide a Unit ID.")
    elif audit_mode == "Date Range" and (not start_dt or not end_dt):
        st.warning("Please select a complete start and end date.")
    elif not api_key:
        st.error("OpenAI API key not found. Please check your secrets.")
    else:
        client = OpenAI(api_key=api_key)
        scraper = NordotApiClient(unit_id)
        
        with st.status("Fetching and Auditing...", expanded=True) as status:
            if audit_mode == "Date Range":
                status.write(f"Querying Nordot API for range: {start_dt.date()} to {end_dt.date()}...")
                stories = scraper.run(start_date=start_dt, end_date=end_dt)
            else:
                status.write(f"Fetching the last {limit_count} articles...")
                stories = scraper.run(limit=limit_count)

            if not stories:
                st.error("No articles found for the selected criteria.")
                status.update(label="Audit Failed", state="error")
            else:
                status.write(f"Found {len(stories)} articles. Evaluating quality...")

                accurate_count = 0
                sensationalized_count = 0
                manipulative_count = 0
                
                results_area = st.container()

                for i, story in enumerate(stories):
                    score, reasoning = get_ai_evaluation(client, story['title'], story['body_text'])

                    if score >= 0.7:
                        label, color = "✅ Accurate", "green"
                        accurate_count += 1
                    elif score >= 0.4:
                        label, color = "⚠️ Sensationalized", "orange"
                        sensationalized_count += 1
                    else:
                        label, color = "🚨 Manipulative", "red"
                        manipulative_count += 1

                    with results_area:
                        with st.expander(f"[{score}] {story['title']}"):
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                st.metric("Score", score, label)
                            with col2:
                                st.markdown(f"**AI Reasoning:**\n{reasoning}")
                                st.caption(f"Published: {story['published_at']}")
                                
                status.update(label="Audit Complete!", state="complete", expanded=False)

                total = len(stories)
                accurate_pct = (accurate_count / total) * 100
                sens_pct = (sensationalized_count / total) * 100
                manip_pct = (manipulative_count / total) * 100

                st.divider()
                st.subheader("Audit Summary")
                c1, c2, c3 = st.columns(3)
                c1.metric("✅ Accurate", accurate_count, f"{accurate_pct:.1f}%")
                c2.metric("⚠️ Sensationalized", sensationalized_count, f"{sens_pct:.1f}%")
                c3.metric("🚨 Manipulative", manipulative_count, f"{manip_pct:.1f}%")
