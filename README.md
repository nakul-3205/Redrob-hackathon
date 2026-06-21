# Redrob Candidate Ranker

**India Runs Data & AI Challenge — Intelligent Candidate Discovery & Ranking**  
Built by **Nakul Kejriwal** · Team `nakul-builds`

---

## What this is

A rule-based multi-signal ranking pipeline that scores 100,000 candidate profiles against a specific job description (Senior AI Engineer — Founding Team, Redrob AI) and outputs a ranked top-100 CSV. Runs in ~26 seconds on CPU. No LLMs, no embeddings, no GPU, no network calls during ranking.

The core insight driving this approach: the JD doesn't just say what skills to look for — it signals what kind of engineer to avoid. The pipeline encodes both sides: what to reward and what to penalise. A candidate with perfect AI keywords whose title is "Marketing Manager" is not a hire. A candidate who built a production recommendation system without ever writing "RAG" in their profile might be exactly right.

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/nakul-3205/Redrob-hackathon
cd Redrob-hackathon
pip install -r requirements.txt

# 2. Run the ranker
python rank.py --candidates ./candidates.jsonl --out ./submission.csv

# 3. Validate output
python validate_submission.py submission.csv
# → Submission is valid.
```

Single command to reproduce the exact submission:

```bash
python rank.py --candidates ./candidates.jsonl --out ./team_nakul-builds.csv
```

---

## Repo structure

```
├── rank.py                     # Entry point — streams JSONL, calls all scorers, writes CSV
├── app.py                      # Streamlit sandbox (upload ≤100 candidates, see live output)
├── requirements.txt
├── submission_metadata.yaml    # Hackathon metadata per spec section 10
├── validate_submission.py      # Submission validator (from hackathon bundle)
├── team_nakul-builds.csv       # Submitted top-100 CSV
└── src/
    ├── __init__.py
    ├── jd_config.py            # All JD-derived constants — skill weights, title tiers, thresholds
    ├── honeypot.py             # Detects fabricated profiles before scoring
    ├── skill_scorer.py         # Skill match: proficiency × trust × log(duration)
    ├── career_scorer.py        # Title tier + YoE band + company background
    ├── signal_scorer.py        # 23 behavioral signals: recency, notice, responsiveness, location
    ├── combiner.py             # Weighted combination with availability multiplier
    └── reasoning.py            # Per-candidate reasoning — assembled from real data, no LLM
```

---

## Pipeline

Every candidate passes through six sequential stages. The first two are elimination gates; the remaining four are scoring modules.

### Stage 1 — Honeypot Detection (`honeypot.py`)

Runs before any scoring. Four logical impossibility checks identify fabricated profiles:

| Check | Condition | Threshold |
|---|---|---|
| **Impossible skill durations** | Skill duration > 1.2× total YoE + 3-month buffer | ≥2 skills flagged |
| **Expert inflation** | 8+ `expert`-level skills with < 3 years total experience | Instant flag |
| **Career timeline overlap** | Sum of past job months > 1.6× stated YoE | Instant flag |
| **Age impossibility** | Career start date implies working before age 14 | Instant flag |

Any single flag disqualifies the profile. Flagged candidates receive score `0` and are excluded from ranking entirely.

**Result:** 6,628 honeypots caught (6.6% of the 100K pool).

---

### Stage 2 — Hard Title Kill (`career_scorer.py`)

A lookup against `TITLE_TIERS` in `jd_config.py`. Titles mapped to score `0.0` — HR managers, accountants, civil engineers, sales executives, graphic designers, customer support agents — are eliminated immediately via a hard short-circuit. They never reach the skill scorer.

This is not a soft penalty. A `career_score` of `0.0` stops all further processing for that candidate.

**Result:** 54,796 hard kills (54.8% of the pool).

---

### Stage 3 — Skill Score (`skill_scorer.py`)

For each candidate skill, a quality value is computed:

```
skill_value = proficiency_weight × trust_multiplier × log_duration_bonus
```

**Proficiency weights:**

| Level | Weight |
|---|---|
| beginner | 0.30 |
| intermediate | 0.60 |
| advanced | 0.85 |
| expert | 1.00 |

**Trust multiplier** (platform assessment > peer endorsements > self-claimed):

| Signal | Multiplier |
|---|---|
| Self-claimed only | 0.60 |
| 1+ endorsements | 0.75 |
| 5+ endorsements | 0.88 |
| 10+ endorsements | 0.95 |
| Platform assessment ≥70 | 1.00 |
| Platform assessment 50–69 | 0.80 |
| Platform assessment < 30 | 0.30 |

**Duration bonus:** `log(months + 1) / log(13)` — logarithmic so early months carry more signal than later ones.

Skills are bucketed from `jd_config.py` into three groups:

| Group | Examples | Effect |
|---|---|---|
| `MUST_HAVE_SKILLS` | FAISS, Weaviate, Qdrant, sentence-transformers, NDCG, BM25, LTR, Information Retrieval | Positive — weighted 0.8–1.0 by relevance |
| `NICE_TO_HAVE_SKILLS` | LoRA, QLoRA, XGBoost, A/B testing, Kafka, MLflow | Bonus, capped at +0.20 |
| `NEGATIVE_SKILLS` | React, Figma, AutoCAD, CSS, sales, accounting | Penalty, capped at −0.30 |

**Special penalties on top:**

- **LangChain/LlamaIndex wrapper penalty (−0.15):** fires only when the candidate has wrapper skills but zero `MUST_HAVE_SKILLS`. Encodes the JD's explicit "no wrapper engineers" warning.
- **Domain mismatch:** CV/speech/robotics skills are penalised only if the candidate has no NLP/IR signal. A CV engineer who also does RAG is fine; a pure CV engineer applying for a search role is not.

---

### Stage 4 — Career Score (`career_scorer.py`)

Three sub-components, combined with fixed weights:

```
career_score = 0.50 × title_score + 0.30 × yoe_score + 0.20 × company_score
```

**Title score** is a tiered lookup — first match wins:

| Title pattern | Score |
|---|---|
| ML / AI / Search / NLP / Ranking Engineer | 1.00 |
| Applied Scientist / Applied ML | 0.92 |
| Research Engineer | 0.88 |
| Data Scientist | 0.75 |
| Senior / Staff / Principal Engineer | 0.65 |
| Software Engineer / SDE | 0.50 |
| Data Engineer | 0.38 |
| Full Stack / Frontend | 0.15–0.20 |
| HR / Accountant / Civil Eng. / Sales / Marketing | **0.00 → HARD KILL** |

**YoE score** — sweet spot is 5–9 years per the JD:

| Band | Score |
|---|---|
| < 2 years | 0.15 |
| 2–3 years | 0.30 |
| 3–4 years | 0.60 |
| 4–5 years | 0.82 |
| **5–9 years** | **1.00** |
| 9–12 years | 0.85 |
| 12–15 years | 0.70 |
| > 15 years | 0.50 |

**Company score** — duration-weighted average over career history (current role counts double):

| Company type | Score |
|---|---|
| Product tech company, mid-size (51–5000 employees) | 0.95 |
| Big tech (10,000+) | 0.70 |
| Small startup (< 50) | 0.65 |
| Non-tech industry | 0.35 |
| Pure consulting (TCS, Infosys, Wipro, Accenture, Cognizant, etc.) | 0.20 |

---

### Stage 5 — Signal Score (`signal_scorer.py`)

Behavioral availability signals, weighted:

```
signal_score = 0.30 × recency + 0.25 × responsiveness + 0.20 × notice + 0.15 × location + 0.10 × extras
```

**Recency** — days since `last_active_date`:

| Days inactive | Score | Adjustment |
|---|---|---|
| ≤ 7 | 1.00 | |
| ≤ 14 | 0.95 | |
| ≤ 30 | 0.85 | |
| ≤ 60 | 0.70 | +0.10 if `open_to_work` and active ≤90d |
| ≤ 90 | 0.50 | |
| ≤ 120 | 0.35 | |
| ≤ 180 | 0.20 | |
| > 180 | 0.08 | |

**Responsiveness** — `recruiter_response_rate`, `avg_response_time_hours`, `interview_completion_rate`:

| Response rate | Base | Adjustments |
|---|---|---|
| ≥ 80% | 1.00 | +0.05 if avg response time ≤4h |
| 60–80% | 0.85 | −0.05 if avg response time > 72h |
| 40–60% | 0.65 | +0.05 if interview completion ≥85% |
| 20–40% | 0.40 | −0.10 if interview completion < 40% |
| < 20% | 0.15 | |

**Notice period:**

| Days | Score | Note |
|---|---|---|
| 0 (immediate) | 1.00 | |
| ≤ 15 | 0.98 | |
| ≤ 30 | 0.92 | JD says this is "buyable" |
| ≤ 45 | 0.78 | |
| ≤ 60 | 0.65 | |
| ≤ 90 | 0.45 | |
| ≤ 120 | 0.28 | |
| > 120 | 0.12 | Hard to move |

**Location:**

| Situation | Score |
|---|---|
| India, target city (Pune, Noida, Delhi NCR, Mumbai, Hyderabad, Bangalore, Gurgaon) | 1.00 |
| India, willing to relocate | 0.82 |
| India, no relocation | 0.60 |
| Outside India, willing to relocate | 0.40 |
| Outside India, no relocation | 0.10 |

**Extras (bonus/penalty factors from redrob_signals):**
- GitHub activity score ≥ 70: +0.15
- Saved by ≥ 5 recruiters in 30d: +0.08
- Profile completeness ≥ 85: +0.06
- Verified email + verified phone: +0.04
- Offer acceptance rate ≥ 0.7: +0.05
- Offer acceptance rate < 0.3: −0.05
- Profile completeness < 40: −0.08

---

### Stage 6 — Combine (`combiner.py`)

```python
base_score = 0.40 × skill_score + 0.35 × career_score + 0.25 × signal_score
availability_multiplier = 0.55 + 0.45 × signal_score
final_score = base_score × availability_multiplier
```

The availability multiplier is why this isn't just an additive weighted sum. A purely additive weight for signals can be swamped by strong skill and career scores. By multiplying the entire base score by a signal-derived factor, an unreachable candidate is always meaningfully penalised regardless of how strong their skills are.

The multiplier floors at `0.55` (when `signal = 0`) rather than `0` — a brilliant candidate who's slightly hard to reach shouldn't be zeroed. But at `signal = 0` they're capped at 55% of their base score.

Scores are clipped to `[0, 1]`, rounded to 4 decimal places. Ties are broken by `candidate_id` ascending (per spec Section 3).

---

### Reasoning (`reasoning.py`)

Every ranked candidate receives a two-sentence reasoning string assembled from their actual profile data — no LLM call, no template with placeholder text:

**Sentence 1:** `{Title}, {YoE}y; {top 3 skills with proficiency + duration + endorsements}; {company background}`

**Sentence 2:** Availability positives and concerns drawn from signal context — active/inactive days, notice period, response rate, location, and any flags.

Example (Rank 2, CAND_0064326):
```
Search Engineer, 7.6y; Python (expert, 60mo), 25 endorsements + Weaviate (expert, 51mo),
47 endorsements (+1 more relevant); product co. background (Sarvam AI). active 29d ago,
open to work, 30d notice (buyable), 94% recruiter response rate, India-based (Gurgaon).
```

If a concern exists (long notice, low response rate, location mismatch), it appears explicitly — the reasoning doesn't hide it.

---

## Results

Full 100K run on local machine (Windows 11, 4-core CPU, 16 GB RAM):

| Metric | Value |
|---|---|
| Total candidates | 100,000 |
| Honeypots caught | 6,628 (6.6%) |
| Hard kills (title) | 54,796 (54.8%) |
| Candidates scored | 38,576 |
| Top score | 0.9441 |
| Rank-100 cutoff | 0.7938 |
| Runtime | 26.1 seconds |

**Top 10 candidates:**

| Rank | ID | Score | Title | YoE |
|---|---|---|---|---|
| 1 | CAND_0043860 | 0.9441 | Junior ML Engineer | 6.1y |
| 2 | CAND_0064326 | 0.9381 | Search Engineer | 7.6y |
| 3 | CAND_0011687 | 0.9136 | Senior NLP Engineer | 7.8y |
| 4 | CAND_0046525 | 0.9091 | Senior ML Engineer | 6.1y |
| 5 | CAND_0018499 | 0.9085 | Senior ML Engineer | 7.2y |
| 6 | CAND_0077337 | 0.9082 | Staff ML Engineer | 7.0y |
| 7 | CAND_0048558 | 0.9049 | Data Scientist | 6.7y |
| 8 | CAND_0004402 | 0.9042 | AI Research Engineer | 6.0y |
| 9 | CAND_0008295 | 0.9024 | AI Research Engineer | 6.5y |
| 10 | CAND_0002025 | 0.8997 | Senior AI Engineer | 5.9y |

---

## Design decisions

### Why no LLMs?

An LLM call per candidate takes ~2 seconds on CPU. For 100K candidates: 2s × 100K = ~55 hours. The spec's 5-minute constraint makes it physically impossible. Rule-based scoring of the full pool completes in 26 seconds.

Beyond the compute constraint: LLM-based reasoning for 100K candidates risks hallucination in the per-candidate reasoning column. A candidate's reasoning should be provably grounded in their actual data — this system guarantees it.

### Why rule-based rather than an ML ranking model?

No labeled training data is available. Ground truth is hidden until after submissions close. Rules derived directly from reading the JD carefully are more defensible, auditable, and reproducible than a black-box model trained on unknown data.

The JD is also unusually explicit about both what it wants and what it doesn't — the "explicit do NOT want" and "disqualifiers we actually apply" sections are rare engineering inputs that translate directly into code.

### Why an availability multiplier instead of additive signal weight?

A purely additive signal weight can be dominated by strong skill and career scores. If signal contributes 0.25 additively and is zero, the candidate still scores 0.75 of a perfect skill+career combo. The multiplier ensures that behavioral unavailability is always felt, regardless of other scores. It floors at 0.55 to avoid zeroing brilliant but passive candidates entirely — a recruiter reaching out to a passive candidate isn't wasted effort; it's just a lower-probability bet.

### Why is skill weight 40% and not higher?

The JD says explicitly: "A perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% recruiter response rate is, for hiring purposes, not actually available." That's a product requirement, not a nice-to-have. The 40/35/25 split reflects that signal matters as a hiring predictor, not just as a tiebreaker.

### Why log-scale for skill duration?

Experience gained in the first 6 months of using a tool is more informative than experience gained between year 3 and year 4. The log scale compresses extreme durations and amplifies early signal. `log(13) = 2.565` is the normalizer because one year (12 months + 1) was chosen as the "full bonus" reference point.

### Why is consulting background scored 0.20, not 0.00?

The JD says "if you're currently at one of these companies but have prior product-company experience, that's fine." 0.20 is not zero — it's a significant penalty that won't eliminate a fundamentally good candidate who happens to currently be at a consulting firm while their career history shows product experience. The company score is duration-weighted, so recent product experience overrides a consulting role.

---

## Sandbox

The Streamlit app (`app.py`) provides a hosted reproducibility demo. Upload a `.json` or `.jsonl` file (up to 100 candidates) and run the exact same pipeline interactively. The app shows:

- Pipeline summary stats (honeypots, hard kills, scored count, runtime)
- Score distribution chart
- Full ranked table with skill/career/signal breakdown
- Top 5 candidate spotlight cards
- Download button for the ranked CSV

**Hosted at:** [https://huggingface.co/spaces/nakul-3205/nakul-builds](https://huggingface.co/spaces/nakul-3205/nakul-builds)

---

## Dependencies

```
tqdm
streamlit>=1.35.0
pandas
altair
```

Python standard library only beyond that (`json`, `csv`, `math`, `datetime`, `pathlib`, `gzip`). No model weights, no embedding APIs, no external network calls during ranking.

```bash
pip install -r requirements.txt
```

---

## Compute environment (as tested)

| Parameter | Value |
|---|---|
| OS | Windows 11 |
| CPU | 4 cores |
| RAM | 16 GB |
| GPU | None (CPU only) |
| Python | 3.11 |
| Network during ranking | No |
| Pre-computation required | No |
| Runtime (100K candidates) | ~26 seconds |

---

## File outputs

The ranking step produces a single CSV:

```
candidate_id,rank,score,reasoning
CAND_0043860,1,0.9441,"Junior ML Engineer, 6.1y; ..."
CAND_0064326,2,0.9381,"Search Engineer, 7.6y; ..."
...
CAND_0002025,100,0.7938,"..."
```

- Exactly 100 rows (ranks 1–100), no duplicates
- Scores non-increasing with rank
- Reasoning assembled from actual candidate data, no templates

---

## AI tools declaration

Used Claude for code review, architectural discussion, and debugging. No candidate data was fed to any LLM. All scoring logic is deterministic and rule-based. The ranking pipeline makes zero API calls during execution.

---

## Team

**Nakul Kejriwal**  
Email: nakulkejriwal@gmail.com  
Phone: +91-8104864063  
GitHub: [nakul-3205](https://github.com/nakul-3205)  
Team: `nakul-builds`