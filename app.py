
import json
import sys
import os
import csv
import io

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.honeypot import is_honeypot
from src.skill_scorer import score_skills
from src.career_scorer import score_career
from src.signal_scorer import score_signals
from src.combiner import combine, tiebreak_key
from src.reasoning import build_reasoning

st.set_page_config(page_title="Redrob Candidate Ranker", page_icon="🎯", layout="wide")
st.title("🎯 Redrob Candidate Ranker")
st.caption("Hackathon sandbox — upload up to 100 candidates, get ranked output.")

st.markdown("""
Upload a JSON array of candidate profiles and the ranker will score and rank them.

**Pipeline:**
- Honeypot detection (impossible timelines → score 0)
- Title hard-kill (HR Managers, Accountants, etc → excluded)
- Skill scoring vs JD must-haves with trust multipliers
- Behavioral signals (recency, response rate, notice, location)
- Weighted combination + availability multiplier
""")

st.divider()


def rank_candidates(candidates: list) -> tuple[list, dict]:
    results = []
    stats = {"total": len(candidates), "honeypots": 0, "hard_kills": 0, "scored": 0}

    for candidate in candidates:
        if is_honeypot(candidate):
            stats["honeypots"] += 1
            continue

        career_score = score_career(candidate)
        if career_score == 0.0:
            stats["hard_kills"] += 1
            continue

        skill_score = score_skills(candidate)
        signal_score = score_signals(candidate)
        final_score = combine(skill_score, career_score, signal_score)
        reasoning = build_reasoning(candidate, skill_score, career_score, signal_score, final_score)

        results.append({
            "candidate_id": candidate.get("candidate_id", "UNKNOWN"),
            "score": final_score,
            "reasoning": reasoning,
            "skill_score": skill_score,
            "career_score": career_score,
            "signal_score": signal_score,
            "title": candidate["profile"]["current_title"],
            "yoe": candidate["profile"]["years_of_experience"],
            "location": candidate["profile"].get("location", ""),
            "country": candidate["profile"].get("country", ""),
        })

    results.sort(key=tiebreak_key)
    stats["scored"] = len(results)

    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results, stats


def build_csv(results: list) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["candidate_id", "rank", "score", "reasoning"])
    writer.writeheader()
    for r in results:
        writer.writerow({
            "candidate_id": r["candidate_id"],
            "rank": r["rank"],
            "score": r["score"],
            "reasoning": r["reasoning"],
        })
    return output.getvalue()


with st.sidebar:
    st.header("Load data")
    use_sample = st.button("📋 Load sample_candidates.json", use_container_width=True)
    st.markdown("or")
    uploaded_file = st.file_uploader(
        "Upload candidates JSON",
        type=["json"],
        help="JSON array of candidates. Max 100 for this sandbox.",
    )
    st.divider()
    st.markdown("""
**About**
- Runs full pipeline client-side
- Max 100 candidates in sandbox
- No data stored or sent anywhere
- Full 100K run: `python rank.py --candidates ./candidates.jsonl --out ./submission.csv`
    """)


candidates = None

if use_sample:
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "sample_candidates.json",
    )
    if os.path.exists(sample_path):
        with open(sample_path) as f:
            candidates = json.load(f)
        st.success(f"Loaded {len(candidates)} sample candidates.")
    else:
        st.error("sample_candidates.json not found.")

elif uploaded_file is not None:
    try:
        candidates = json.load(uploaded_file)
        if not isinstance(candidates, list):
            st.error("File must be a JSON array.")
            candidates = None
        elif len(candidates) > 100:
            st.warning(f"Capping at 100 (uploaded {len(candidates)}).")
            candidates = candidates[:100]
        else:
            st.success(f"Loaded {len(candidates)} candidates.")
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")

if candidates:
    if st.button("🚀 Run Ranker", type="primary"):
        with st.spinner("Scoring..."):
            results, stats = rank_candidates(candidates)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total", stats["total"])
        col2.metric("Honeypots", stats["honeypots"])
        col3.metric("Hard kills", stats["hard_kills"])
        col4.metric("Scored", stats["scored"])

        if not results:
            st.warning("No candidates passed filtering.")
        else:
            st.divider()

            import pandas as pd
            df = pd.DataFrame([{
                "Rank": r["rank"],
                "ID": r["candidate_id"],
                "Score": f"{r['score']:.4f}",
                "Title": r["title"],
                "YoE": f"{r['yoe']:.1f}",
                "Location": f"{r['location']}, {r['country']}",
                "Skill": f"{r['skill_score']:.3f}",
                "Career": f"{r['career_score']:.3f}",
                "Signal": f"{r['signal_score']:.3f}",
                "Reasoning": r["reasoning"],
            } for r in results])

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={"Reasoning": st.column_config.TextColumn(width="large")},
            )

            st.divider()
            st.download_button(
                "⬇️ Download CSV",
                data=build_csv(results),
                file_name="ranked_candidates.csv",
                mime="text/csv",
            )

            st.subheader("Top 3 detail")
            for r in results[:3]:
                with st.expander(f"#{r['rank']} {r['candidate_id']} — {r['title']} ({r['score']:.4f})"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Skill", f"{r['skill_score']:.3f}")
                    c2.metric("Career", f"{r['career_score']:.3f}")
                    c3.metric("Signal", f"{r['signal_score']:.3f}")
                    st.write(r["reasoning"])
else:
    st.info("👈 Load sample data or upload a candidates JSON file.")