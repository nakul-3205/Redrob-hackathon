"""
sandbox/app.py — Streamlit demo for HuggingFace Spaces.

Accepts a JSON upload of up to 100 candidates,
runs the full ranking pipeline, shows results in a table,
and offers a CSV download.

Deploy to HuggingFace Spaces (Streamlit SDK).
"""

import json
import sys
import os
import csv
import io
import tempfile

import streamlit as st

# Add parent directory to path so we can import src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.honeypot import is_honeypot, honeypot_reason
from src.skill_scorer import score_skills
from src.career_scorer import score_career
from src.signal_scorer import score_signals
from src.combiner import combine, tiebreak_key
from src.reasoning import build_reasoning


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Redrob Candidate Ranker",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Redrob Candidate Ranker")
st.caption("Hackathon sandbox — upload up to 100 candidates, get ranked output.")

st.markdown("""
This is a demo of the Redrob Hackathon ranker. Upload a JSON array of candidate profiles
(matching `candidate_schema.json`) and the ranker will score and rank them.

**What the ranker does:**
- Detects and removes honeypot profiles (impossible career timelines)
- Hard-kills title mismatches (HR Managers, Accountants, Civil Engineers, etc.)
- Scores skill relevance against the Senior AI Engineer JD
- Scores behavioral signals (recency, response rate, notice period, location)
- Outputs top candidates with specific per-candidate reasoning
""")

st.divider()


def rank_candidates(candidates: list) -> tuple[list, dict]:
    """Run the full scoring pipeline on a list of candidates."""
    results = []
    stats = {
        "total": len(candidates),
        "honeypots": 0,
        "hard_kills": 0,
        "scored": 0,
    }

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
        reasoning = build_reasoning(
            candidate, skill_score, career_score, signal_score, final_score
        )

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
    """Build CSV string for download."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["candidate_id", "rank", "score", "reasoning"]
    )
    writer.writeheader()
    for r in results:
        writer.writerow({
            "candidate_id": r["candidate_id"],
            "rank": r["rank"],
            "score": r["score"],
            "reasoning": r["reasoning"],
        })
    return output.getvalue()


# ── Sidebar: load sample data ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Load data")

    use_sample = st.button("📋 Load sample_candidates.json", use_container_width=True)

    st.markdown("or")

    uploaded_file = st.file_uploader(
        "Upload candidates JSON",
        type=["json"],
        help="JSON array of candidate objects matching candidate_schema.json. Max 100 for this sandbox.",
    )

    st.divider()
    st.markdown("**About this sandbox**")
    st.markdown("""
- Runs full ranking pipeline in-browser
- Accepts up to 100 candidates
- No data is stored or sent anywhere
- Full 100K run happens locally via `rank.py`
    """)


# ── Main area ─────────────────────────────────────────────────────────────────
candidates = None

if use_sample:
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "sample_candidates.json",
    )
    if os.path.exists(sample_path):
        with open(sample_path) as f:
            candidates = json.load(f)
        st.success(f"Loaded {len(candidates)} sample candidates.")
    else:
        st.error("sample_candidates.json not found. Upload your own file.")

elif uploaded_file is not None:
    try:
        candidates = json.load(uploaded_file)
        if not isinstance(candidates, list):
            st.error("File must be a JSON array of candidate objects.")
            candidates = None
        elif len(candidates) > 100:
            st.warning(f"Uploaded {len(candidates)} candidates — capping at 100 for this sandbox.")
            candidates = candidates[:100]
        else:
            st.success(f"Loaded {len(candidates)} candidates.")
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")

if candidates:
    if st.button("🚀 Run Ranker", type="primary", use_container_width=False):
        with st.spinner("Scoring candidates..."):
            results, stats = rank_candidates(candidates)

        # ── Stats ──────────────────────────────────────────────────────────
        st.subheader("Pipeline stats")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total input", stats["total"])
        col2.metric("Honeypots caught", stats["honeypots"],
                    delta=f"{stats['honeypots']/stats['total']*100:.0f}%",
                    delta_color="off")
        col3.metric("Hard kills (wrong title)", stats["hard_kills"])
        col4.metric("Scored & ranked", stats["scored"])

        if not results:
            st.warning("No candidates passed filtering. Try a different dataset.")
        else:
            st.divider()

            # ── Results table ──────────────────────────────────────────────
            st.subheader(f"Ranked results (showing all {len(results)})")

            import pandas as pd
            df = pd.DataFrame([{
                "Rank": r["rank"],
                "Candidate ID": r["candidate_id"],
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
                column_config={
                    "Reasoning": st.column_config.TextColumn(width="large"),
                    "Score": st.column_config.TextColumn(width="small"),
                }
            )

            # ── Download ───────────────────────────────────────────────────
            st.divider()
            csv_str = build_csv(results)
            st.download_button(
                label="⬇️ Download ranked CSV",
                data=csv_str,
                file_name="ranked_candidates.csv",
                mime="text/csv",
                type="secondary",
            )

            # ── Top 3 detail view ──────────────────────────────────────────
            st.subheader("Top 3 — detail")
            for r in results[:3]:
                with st.expander(f"#{r['rank']} {r['candidate_id']} — {r['title']} (score: {r['score']:.4f})"):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Skill score", f"{r['skill_score']:.3f}")
                    col_b.metric("Career score", f"{r['career_score']:.3f}")
                    col_c.metric("Signal score", f"{r['signal_score']:.3f}")
                    st.markdown(f"**Reasoning:** {r['reasoning']}")

else:
    st.info("👈 Load sample data or upload a candidates JSON file to get started.")

    st.markdown("""
### Expected input format

```json
[
  {
    "candidate_id": "CAND_0000001",
    "profile": {
      "current_title": "ML Engineer",
      "years_of_experience": 6.5,
      "location": "Hyderabad, Telangana",
      "country": "India",
      ...
    },
    "skills": [...],
    "career_history": [...],
    "redrob_signals": {...}
  }
]
```

See `candidate_schema.json` in the hackathon bundle for the full schema.
    """)