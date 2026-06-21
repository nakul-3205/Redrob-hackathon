import json
import csv
import io
import os
import sys
import time

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from honeypot import is_honeypot, honeypot_reason
from skill_scorer import score_skills
from career_scorer import score_career
from signal_scorer import score_signals
from combiner import combine, tiebreak_key
from reasoning import build_reasoning

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Redrob Ranker · Nakul Kejriwal",
    page_icon="🎯",
    layout="wide",
)

st.markdown("""
<style>
.tag {
    display: inline-block;
    background: #f1f5f9;
    color: #475569;
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 12px;
    margin: 2px;
}
.reasoning-box {
    background: #f8fafc;
    border-left: 3px solid #38bdf8;
    padding: 10px 14px;
    border-radius: 4px;
    font-size: 14px;
    color: #334155;
    margin-top: 6px;
}
.stat-label {
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stat-value {
    font-size: 26px;
    font-weight: 700;
    line-height: 1.1;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def parse_file(uploaded) -> list | None:
    raw = uploaded.read().decode("utf-8").strip()
    # JSONL: first char is `{` or filename ends .jsonl
    if uploaded.name.endswith(".jsonl") or raw.startswith("{"):
        out = []
        for i, line in enumerate(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                st.error(f"Bad JSON on line {i+1}: {e}")
                return None
        return out
    # JSON array
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return None
    if not isinstance(data, list):
        st.error("File must be a JSON array [ {...}, {...} ] or a .jsonl file.")
        return None
    return data


def run_pipeline(candidates: list) -> tuple:
    results, honeypots, hard_kills = [], [], []
    for c in candidates:
        cid = c.get("candidate_id", "UNKNOWN")
        if is_honeypot(c):
            honeypots.append({"ID": cid, "Title": c["profile"].get("current_title", "?"), "Reason": honeypot_reason(c)})
            continue
        career_score = score_career(c)
        if career_score == 0.0:
            hard_kills.append({"ID": cid, "Title": c["profile"].get("current_title", "?")})
            continue
        skill_score  = score_skills(c)
        signal_score = score_signals(c)
        final        = combine(skill_score, career_score, signal_score)
        results.append({
            "candidate_id": cid,
            "score":        final,
            "reasoning":    build_reasoning(c, skill_score, career_score, signal_score, final),
            "skill":        round(skill_score, 3),
            "career":       round(career_score, 3),
            "signal":       round(signal_score, 3),
            "title":        c["profile"].get("current_title", ""),
            "yoe":          c["profile"].get("years_of_experience", 0),
            "location":     c["profile"].get("location", ""),
        })
    results.sort(key=tiebreak_key)
    results = results[:100]
    for i, r in enumerate(results):
        r["rank"] = i + 1
    stats = {
        "total":      len(candidates),
        "honeypots":  len(honeypots),
        "hard_kills": len(hard_kills),
        "scored":     len(results),
    }
    return results, stats, honeypots, hard_kills


def to_csv(results: list) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["candidate_id", "rank", "score", "reasoning"])
    w.writeheader()
    for r in results:
        w.writerow({"candidate_id": r["candidate_id"], "rank": r["rank"],
                    "score": r["score"], "reasoning": r["reasoning"]})
    return buf.getvalue()


# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {"candidates": None, "results": None, "stats": None,
             "honeypots": None, "hard_kills": None,
             "elapsed": 0, "loaded_file": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Header ────────────────────────────────────────────────────────────────────
col_h, col_meta = st.columns([3, 1])
with col_h:
    st.markdown("## 🎯 Redrob Candidate Ranker")
    st.caption("India Runs Data & AI Challenge · Intelligent Candidate Discovery & Ranking")
with col_meta:
    st.markdown("""
<div style='text-align:right;padding-top:6px'>
<span style='font-size:12px;color:#94a3b8'>Built by</span><br>
<strong style='font-size:15px'>Nakul Kejriwal</strong><br>
<span style='font-size:12px;color:#94a3b8'>Team: nakul-builds</span>
</div>""", unsafe_allow_html=True)

st.divider()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Upload Candidates")
    st.caption("Accepts .json (array) or .jsonl.")

    uploaded = st.file_uploader("", type=["json", "jsonl"], label_visibility="collapsed")

    # Parse only when a new file is uploaded (compare by name+size)
    if uploaded is not None:
        file_key = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.loaded_file != file_key:
            parsed = parse_file(uploaded)
            # if parsed is not None:
            #     if len(parsed) > 100:
            #         parsed = parsed[:100]
            #         st.warning("Capped at 100 candidates.")
                # store everything and clear previous results
            st.session_state.candidates  = parsed
            st.session_state.results     = None
            st.session_state.loaded_file = file_key

    if st.session_state.candidates:
        st.success(f"✅ {len(st.session_state.candidates)} candidates ready")
        if st.button("✕ Clear", use_container_width=True):
            for k in ("candidates", "results", "stats", "honeypots", "hard_kills", "loaded_file"):
                st.session_state[k] = None
            st.rerun()

    st.divider()
    st.markdown("**Pipeline steps**")
    st.markdown("""
1. 🕵️ Honeypot filter
2. 🔪 Hard title kill
3. 🧠 Skill score
4. 💼 Career score
5. 📡 Signal score
6. ⚖️ Combine & rank
""")
    st.divider()
    st.markdown("""<div style='font-size:11px;color:#94a3b8'>
Full 100K run:<br>
<code>python rank.py<br>--candidates candidates.jsonl<br>--out submission.csv</code>
</div>""", unsafe_allow_html=True)


# ── Main area ─────────────────────────────────────────────────────────────────
if st.session_state.candidates is None:
    st.markdown("""
<div style='text-align:center;padding:80px 20px;color:#94a3b8'>
<div style='font-size:52px'>🎯</div>
<div style='font-size:22px;font-weight:600;color:#334155;margin-top:16px'>Upload candidates to begin</div>
<div style='margin-top:8px;font-size:15px'>Drop a .json or .jsonl file in the sidebar</div>
<div style='margin-top:24px;font-size:13px;background:#f8fafc;display:inline-block;
            padding:14px 24px;border-radius:8px;text-align:left;color:#475569;line-height:1.8'>
<b>JSON array</b> (.json):<br>
<code>[{"candidate_id": "CAND_0000001", ...}, ...]</code><br><br>
<b>JSONL</b> (.jsonl) — one object per line:<br>
<code>{"candidate_id": "CAND_0000001", ...}</code><br>
<code>{"candidate_id": "CAND_0000002", ...}</code>
</div>
</div>""", unsafe_allow_html=True)

else:
    # ── Run button (only shown before results exist) ───────────────────────
    if st.session_state.results is None:
        n = len(st.session_state.candidates)
        c1, c2 = st.columns([1, 4])
        with c1:
            run = st.button(f"🚀 Run on {n} candidates", type="primary", use_container_width=True)
        with c2:
            st.markdown(f"<div style='padding-top:10px;color:#64748b'>{n} candidates loaded · click to score</div>",
                        unsafe_allow_html=True)

        if run:
            with st.spinner("Scoring..."):
                t0 = time.time()
                results, stats, honeypots, hard_kills = run_pipeline(st.session_state.candidates)
                st.session_state.results    = results
                st.session_state.stats      = stats
                st.session_state.honeypots  = honeypots
                st.session_state.hard_kills = hard_kills
                st.session_state.elapsed    = round(time.time() - t0, 2)
            st.rerun()

    # ── Results ───────────────────────────────────────────────────────────
    if st.session_state.results is not None:
        results    = st.session_state.results
        stats      = st.session_state.stats
        honeypots  = st.session_state.honeypots
        hard_kills = st.session_state.hard_kills
        elapsed    = st.session_state.elapsed

        # ── Stats row ─────────────────────────────────────────────────
        st.markdown("### Pipeline Summary")
        c1, c2, c3, c4, c5 = st.columns(5)
        def stat(col, label, val, color="#0f172a"):
            col.markdown(
                f"<div class='stat-label'>{label}</div>"
                f"<div class='stat-value' style='color:{color}'>{val}</div>",
                unsafe_allow_html=True)

        stat(c1, "Input",      stats["total"])
        stat(c2, "Honeypots",  stats["honeypots"],  "#f59e0b")
        stat(c3, "Hard kills", stats["hard_kills"], "#ef4444")
        stat(c4, "Ranked",     stats["scored"],     "#10b981")
        stat(c5, "Time",       f"{elapsed}s",       "#6366f1")

        if not results:
            st.warning("No candidates passed filtering.")
            st.stop()

        st.divider()

        # ── Filter detail ──────────────────────────────────────────────
        fc1, fc2 = st.columns(2)
        with fc1:
            with st.expander(f"🕵️ Honeypots ({len(honeypots)})"):
                if honeypots:
                    st.dataframe(pd.DataFrame(honeypots), use_container_width=True, hide_index=True)
                else:
                    st.write("None caught.")
        with fc2:
            with st.expander(f"🔪 Hard kills ({len(hard_kills)})"):
                if hard_kills:
                    st.dataframe(pd.DataFrame(hard_kills), use_container_width=True, hide_index=True)
                else:
                    st.write("None caught.")

        st.divider()

        # ── Score distribution ─────────────────────────────────────────
        st.markdown("### Score Distribution")
        scores = [r["score"] for r in results]
        bins = {}
        for s in scores:
            b = f"{int(s * 10) / 10:.1f}"
            bins[b] = bins.get(b, 0) + 1
        st.bar_chart(
            pd.DataFrame({"bucket": list(bins.keys()), "count": list(bins.values())})
              .sort_values("bucket").set_index("bucket")["count"],
            height=150
        )

        st.divider()

        # ── Full ranked table ──────────────────────────────────────────
        st.markdown(f"### Ranked Results — {len(results)} candidates")
        st.dataframe(
            pd.DataFrame([{
                "Rank":      r["rank"],
                "ID":        r["candidate_id"],
                "Score":     r["score"],
                "Title":     r["title"],
                "YoE":       f"{r['yoe']:.1f}",
                "Location":  r["location"],
                "Skill":     r["skill"],
                "Career":    r["career"],
                "Signal":    r["signal"],
                "Reasoning": r["reasoning"],
            } for r in results]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score":     st.column_config.NumberColumn(format="%.4f"),
                "Skill":     st.column_config.NumberColumn(format="%.3f"),
                "Career":    st.column_config.NumberColumn(format="%.3f"),
                "Signal":    st.column_config.NumberColumn(format="%.3f"),
                "Reasoning": st.column_config.TextColumn(width="large"),
            },
        )

        st.download_button(
            "⬇️ Download CSV",
            data=to_csv(results),
            file_name="ranked_candidates.csv",
            mime="text/csv",
        )

        st.divider()

        # ── Top 5 spotlight ────────────────────────────────────────────
        top_n = min(len(results), 5)
        st.markdown(f"### 🏆 Top {top_n} Candidates")

        for r in results[:top_n]:
            sp = int(r["score"]  * 100)
            kp = int(r["skill"]  * 100)
            cp = int(r["career"] * 100)
            gp = int(r["signal"] * 100)

            with st.expander(
                f"#{r['rank']}  ·  {r['candidate_id']}  ·  {r['title']}  ·  {r['score']:.4f}",
                expanded=(r["rank"] <= 3)
            ):
                left, right = st.columns([2, 1])
                with left:
                    st.markdown(
                        f"<div class='reasoning-box'>{r['reasoning']}</div>",
                        unsafe_allow_html=True)
                    st.markdown(
                        f"<span class='tag'>📍 {r['location']}</span>"
                        f"<span class='tag'>🗓 {r['yoe']:.1f} yrs</span>",
                        unsafe_allow_html=True)
                with right:
                    for label, pct, val, color in [
                        ("Overall", sp, f"{r['score']:.4f}", "#0ea5e9"),
                        ("Skill",   kp, f"{r['skill']:.3f}",  "#8b5cf6"),
                        ("Career",  cp, f"{r['career']:.3f}", "#10b981"),
                        ("Signal",  gp, f"{r['signal']:.3f}", "#f59e0b"),
                    ]:
                        st.markdown(f"""
<div style='margin-bottom:10px'>
  <div class='stat-label'>{label}</div>
  <div style='background:#e2e8f0;border-radius:4px;height:6px;margin:3px 0'>
    <div style='background:{color};width:{pct}%;height:6px;border-radius:4px'></div>
  </div>
  <div style='font-size:12px;font-weight:600;color:#334155'>{val}</div>
</div>""", unsafe_allow_html=True)