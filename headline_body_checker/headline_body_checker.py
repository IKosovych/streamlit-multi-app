import os
import re

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="News Title Fact-Checker", page_icon="📰", layout="wide")
api_key = st.secrets.get("OPENAI_API_KEY")

with st.sidebar:
    st.header("Settings")
    st.markdown("---")
    st.markdown("### Scoring Criteria")
    st.markdown("🟢 **0.7 - 1.0**: Factually accurate, objective, and aligns perfectly with the text's nuance.")
    st.markdown("🟡 **0.4 - 0.6**: Partially true but sensationalized, omits crucial context, or uses emotionally manipulative framing.")
    st.markdown("🔴 **0.0 - 0.3**: Factually FALSE or highly manipulative.")

st.title("News Title and Body Text Fact-Checker")

col1, col2 = st.columns([1, 1])

with col1:
    title_input = st.text_input("Enter the Article Title:", placeholder="Title...")

with col2:
    body_input = st.text_area("Enter the Article Body:", height=250, placeholder="Body text...")

if st.button("Evaluate Title", type="primary", use_container_width=True):
    if not title_input or not body_input:
        st.warning("Please provide both a Title and Article Body.")
    else:
        with st.spinner("Analyzing logical entailment and manipulation..."):
            try:
                client = OpenAI(api_key=api_key)

                prompt = f"""You are an expert journalism fact-checker. 
Your task is to score how accurately and objectively the Title represents the Article Body.

Scoring criteria (from 0.0 to 1.0):
- 0.0 to 0.3: Factually FALSE (e.g., wrong killer/victim), or highly manipulative (e.g., claiming deliberate murder when the text explicitly states accidental discharge or lack of indictment).
- 0.4 to 0.6: Partially true but sensationalized, omits crucial context, or uses emotionally manipulative framing (e.g., clickbait).
- 0.7 to 1.0: Factually accurate, non-manipulative, objective, and aligns perfectly with the text's nuance.

Article Body:
{body_input}

Title to Evaluate:
{title_input}

You MUST respond in this exact format:
Reasoning: [1-2 sentences explaining the logical check]
Score: [a single float between 0.0 and 1.0]"""

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a precise, logical, and unbiased fact-checking AI."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )

                response_text = response.choices[0].message.content.strip()

                try:
                    score_match = re.search(r"Score:\s*([0-9.]+)", response_text)
                    score = float(score_match.group(1)) if score_match else 0.0
                except ValueError:
                    score = 0.0

                reasoning_match = re.search(r"Reasoning:\s*(.*?)(?=\nScore:|$)", response_text, re.DOTALL | re.IGNORECASE)
                reasoning = reasoning_match.group(1).strip() if reasoning_match else response_text

                st.markdown("---")
                st.subheader("Results")

                if score >= 0.7:
                    st.success(f"### 🟢 Score: {score} \n**Verdict: Accurate & Objective**")
                elif score >= 0.4:
                    st.warning(f"### 🟡 Score: {score} \n**Verdict: Sensationalized / Omitted Context**")
                else:
                    st.error(f"### 🔴 Score: {score} \n**Verdict: False / Manipulative**")

                st.info(f"**AI Reasoning:**\n\n{reasoning}")

            except Exception as e:
                st.error(f"An API error occurred: {e}")
