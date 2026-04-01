from collections import defaultdict

import streamlit as st
import feedparser


def get_rss_feed_data(url):
    feed = feedparser.parse(url)
    valid_entries = []
    invalid_entries = []

    REQUIRED_FIELDS = [
        "title",
        "guid",
        "link",
        "published",
        "updated",
        "authors",
        "category",
        "media_content",
        "media_credit"
    ]

    if hasattr(feed, 'status') and feed.status == 200:
        for entry in feed.entries:
            missing = [field for field in REQUIRED_FIELDS if field not in entry]

            if not missing:
                valid_entries.append(entry)
            else:
                invalid_entries.append({
                    "entry": entry,
                    "missing": sorted(missing)
                })

        if len(valid_entries) > 0 and len(invalid_entries) == 0:
            st.success(f"✅ PASS: All {len(valid_entries)} entries meet the requirements!")
        elif len(valid_entries) > 0 and len(invalid_entries) > 0:
            st.warning(f"⚠️ PARTIAL: {len(valid_entries)} passed, but {len(invalid_entries)} failed.")
        else:
            st.error(f"❌ FAIL: All {len(invalid_entries)} entries are missing required fields.")

        if valid_entries:
            with st.expander("Show Valid Entries"):
                for e in valid_entries:
                    st.markdown(f"🟢 **{e.title}**")
        
        if invalid_entries:
            st.subheader("Failed Entries by Reason")
            
            grouped_errors = defaultdict(list)
            for item in invalid_entries:
                reason_key = ", ".join(item["missing"])
                entry_title = item["entry"].get('title', '⚠️ [TITLE MISSING]')
                grouped_errors[reason_key].append(entry_title)

            for reason, titles in grouped_errors.items():
                st.markdown(f"#### ❌ Missing: :red[{reason}]")
                
                for title in titles:
                    st.markdown(f"- {title}")
                
                st.divider()
                
    else:
        st.error(f"Failed to fetch RSS feed. Status code: {getattr(feed, 'status', 'Unknown')}")

st.title("RSS Feed Checker")

user_input = st.text_input("Enter rss link:", placeholder="https://example.com/feed.xml")
clicked = st.button("Check")

if clicked:
    if user_input:
        get_rss_feed_data(user_input)
    else:
        st.warning("Please enter a link before submitting.")