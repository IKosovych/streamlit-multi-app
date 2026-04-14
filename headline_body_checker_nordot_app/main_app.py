import re
import streamlit as st
from openai import OpenAI
from scraper import NordotAppScraper

st.set_page_config(page_title="News Title Fact-Checker", layout="wide")
api_key = st.secrets.get("OPENAI_API_KEY")
URL = "https://nordot.app/-/units/{}"

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

st.title("News Title Fact-Checker")
st.markdown("Analyze headlines from Nordot units for accuracy and manipulation.")

with st.sidebar:
    st.header("Control Panel")
    unit_id = st.text_input("Enter Nordot Unit ID:", placeholder="e.g. 1152735748281303040")
    run_audit = st.button("Start Audit", type="primary", use_container_width=True)
    
    st.divider()
    st.markdown("### Scoring Guide")
    st.success("🟢 0.7 - 1.0: Accurate")
    st.warning("🟡 0.4 - 0.6: Sensationalized")
    st.error("🔴 0.0 - 0.3: False / Manipulative")

if run_audit:
    if not unit_id:
        st.warning("Please provide a Unit ID.")
    elif not api_key:
        st.error("OpenAI API key not found in secrets.")
    else:
        client = OpenAI(api_key=api_key)
        scraper = NordotAppScraper(URL.format(unit_id))
        
        with st.status("Auditing Nordot Unit...", expanded=True) as status:
            status.write("Scraping articles...")
            stories = scraper.run()

            if not stories:
                st.error("No articles found for this Unit ID.")
                status.update(label="Audit Failed", state="error")
            else:
                status.write(f"Found {len(stories)} articles. Evaluating with AI...")

                for i, story in enumerate(stories):
                    score, reasoning = get_ai_evaluation(client, story['title'], story['body_text'])

                    if score >= 0.7:
                        label, color = "✅ Accurate", "green"
                    elif score >= 0.4:
                        label, color = "⚠️ Sensationalized", "orange"
                    else:
                        label, color = "🚨 Manipulative", "red"

                    with st.expander(f"[{score}] {story['title']}"):
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            st.metric("Score", score, label)
                        with col2:
                            st.markdown(f"**AI Reasoning:**\n{reasoning}")
                                
                status.update(label="Audit Complete!", state="complete", expanded=False)
