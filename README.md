---
title: Redrob Candidate Ranker
emoji: 🎯
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: false
---

# Redrob Candidate Ranker

**India Runs Data & AI Challenge — Intelligent Candidate Discovery & Ranking**  
Built by **Nakul Kejriwal** · Team `nakul-builds`

---

## What this is

A rule-based candidate ranking pipeline that scores 100,000 candidate profiles against a specific job description (Senior AI Engineer — Founding Team, Redrob AI) and outputs a ranked top-100 CSV. Runs in ~13 seconds on CPU. No LLMs, no embeddings, no GPU.

The core idea: the JD doesn't just say what skills to look for — it signals what kind of engineer to avoid. The pipeline encodes both sides: what to reward and what to penalise.

---

## Reproduce the submission

```bash
pip install -r requirements.txt

python src/rank.py \
  --candidates ./candidates.jsonl \
  --out ./submission.csv
```

Output: `submission.csv` with exactly 100 rows, validated against the official spec.

To validate:
```bash
python validate_submission.py submission.csv
# → Submission is valid.
```

---

## Repo structure

```
├── app.py                  # Streamlit sandbox (upload ≤100 candidates, see live output)
├── requirements.txt
├── submission_metadata.yaml
└── src/
    ├── rank.py             # Entry point — streams JSONL, calls all scorers, writes CSV
    ├── jd_config.py        # All JD-derived constants: skill weights, title tiers, thresholds
    ├── honeypot.py         # Detects fabricated profiles before scoring
    ├── skill_scorer.py     # Skill match score with proficiency × trust × duration weighting
    ├── career_scorer.py    # Title relevance, YoE band, product vs consulting background
    ├── signal_scorer.py    # Behavioral signals: recency, notice period, response rate, location
    ├── combiner.py         # Weighted combination with availability multiplier
    └── reasoning.py        # Per-candidate reasoning string — assembled from actual data
```

---

## Pipeline

Every candidate goes through six stages in order:

### 1. Honeypot detection (`honeypot.py`)

Catches fabricated profiles before any scoring. Four checks:

- **Impossible skill durations** — skill duration > 1.2× total YoE (+ 3-month buffer). If ≥2 skills fail this, it's a honeypot.
- **Expert inflation** — 8+ "expert" skills with < 3 years total experience.
- **Career timeline overlap** — sum of past job months > 1.6× stated YoE.
- **Age impossibility** — inferred career start implies working before age 14.

Any one of these flags the profile as a honeypot. It gets score 0 and is excluded from ranking.

### 2. Hard title kill (`career_scorer.py`)

A lookup against `TITLE_TIERS` in `jd_config.py`. Titles mapped to a score of `0.0` — HR managers, accountants, civil engineers, sales executives, graphic designers, customer support — are eliminated immediately. They never reach the skill scorer.

This is not a soft penalty. A career score of `0.0` short-circuits the entire pipeline for that candidate.

### 3. Skill score (`skill_scorer.py`)

For each candidate skill:
```
skill_value = proficiency_weight × trust_multiplier × log_duration_bonus
```

- **Proficiency weights**: `beginner=0.30`, `intermediate=0.60`, `advanced=0.85`, `expert=1.00`
- **Trust multiplier**: platform assessment score > peer endorsements > self-claimed. Ranges from `0.60` (self-claimed, no endorsements) to `1.00` (assessed ≥70).
- **Duration bonus**: `log(duration_months + 1) / log(13)` — logarithmic so early months matter more than later ones.

Skills are bucketed into three groups from `jd_config.py`:

| Group | Examples | Effect |
|---|---|---|
| `MUST_HAVE_SKILLS` | FAISS, Weaviate, Qdrant, sentence-transformers, NDCG, BM25, LTR | Positive — weighted by relevance score (0.8–1.0) |
| `NICE_TO_HAVE_SKILLS` | LoRA, QLoRA, XGBoost, A/B testing, Kafka | Bonus up to +0.20 |
| `NEGATIVE_SKILLS` | React, Figma, AutoCAD, CSS | Penalty up to -0.30 |

Two special penalties on top:
- **LangChain/LlamaIndex wrapper penalty** (`-0.15`): fires only if the candidate has wrapper skills but zero `MUST_HAVE_SKILLS`. Encodes the JD's explicit "no wrapper engineers" signal.
- **Domain mismatch penalty**: CV/speech/robotics skills are only penalised if the candidate has no NLP/IR depth at all. A CV engineer who also does RAG is fine; a pure CV engineer is not.

### 4. Career score (`career_scorer.py`)

Three sub-components, combined with fixed weights:

```
career_score = 0.50 × title_score + 0.30 × yoe_score + 0.20 × company_score
```

**Title score**: tiered lookup — ML Engineer / AI Engineer / Search Engineer / NLP Engineer = 1.0; Data Scientist = 0.75; Backend Engineer = 0.45; Data Engineer = 0.38; and so on.

**YoE score**: sweet spot is 5–9 years (score 1.0). Below 3 years = 0.30. Above 15 years = 0.50. Flanks score proportionally.

**Company score**: duration-weighted average over career history (current role counts double). Product company in tech = 0.95; big tech = 0.70; pure consulting firm (TCS, Infosys, Wipro, etc.) = 0.20; non-tech industry = 0.35.

### 5. Signal score (`signal_scorer.py`)

Behavioral availability signals, weighted:

```
signal_score = 0.30 × recency + 0.25 × responsiveness + 0.20 × notice + 0.15 × location + 0.10 × extras
```

- **Recency**: days since last active — 1.0 if ≤7 days, 0.08 if >180. Bumped +0.10 if `open_to_work` and active within 90 days.
- **Responsiveness**: recruiter response rate + avg response time + interview completion rate. Low interview completion (<40%) is a red flag.
- **Notice period**: immediate = 1.0; ≤30 days = 0.92 (JD calls this "buyable"); >120 days = 0.12.
- **Location**: target cities (Pune, Noida, Delhi NCR, Gurgaon, Mumbai, Hyderabad, Bangalore) = 1.0; India + willing to relocate = 0.82; India, no relocation = 0.60; outside India = 0.10–0.40.
- **Extras**: GitHub activity score, saved by recruiters, profile completeness, verified contact, offer acceptance rate.

### 6. Combine (`combiner.py`)

```
base = 0.40 × skill + 0.35 × career + 0.25 × signal
availability_multiplier = 0.55 + 0.45 × signal_score
final = base × availability_multiplier
```

The availability multiplier means an unreachable candidate (signal=0) is capped at 55% of their base score — not zeroed, but meaningfully penalised. A recruiter's time has cost; a great candidate who won't respond is still a risk.

Scores are clipped to `[0, 1]` and rounded to 4 decimal places. Ties are broken by `candidate_id` ascending (per spec section 3).

### Reasoning (`reasoning.py`)

Every ranked candidate gets a two-sentence reasoning string assembled entirely from their actual profile data — no LLM, no templates with placeholder text:

1. `{Title}, {YoE}y; {top 3 skills with proficiency + duration + endorsements}; {company background}`
2. Availability positives and concerns drawn from signal context

Example:
```
Search Engineer, 7.6y; Python (expert, 60mo), 25 endorsements + Weaviate (expert, 51mo), 
47 endorsements (+1 more relevant); product co. background (Sarvam AI). active 29d ago, 
open to work, 30d notice (buyable), 94% recruiter response rate, India-based (Gurgaon).
```

---

## Performance

Measured on the full 100K candidate dataset:

| Metric | Value |
|---|---|
| Total candidates | 100,000 |
| Honeypots caught | 6,628 (6.6%) |
| Hard kills (title) | 54,796 (54.8%) |
| Scored & ranked | 38,576 |
| Top score | 0.9441 |
| Rank-100 cutoff | 0.7938 |
| Runtime | ~13 seconds |

---

## Sandbox

The Streamlit app at the link above lets you upload up to 100 candidates (`.json` array or `.jsonl`) and run the same pipeline interactively. It shows the full ranked table, score breakdown per candidate, honeypot/hard-kill details, and a download button for the ranked CSV.

This is a reproducibility demo — the same code that generated `submission.csv`.

---

## Dependencies

```
tqdm
streamlit>=1.35.0
pandas
```

Python standard library only beyond that. No model weights, no embedding APIs, no external calls during ranking.