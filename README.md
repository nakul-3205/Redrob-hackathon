# Redrob Hackathon — Candidate Ranker

Rule-based ranker for the India Runs Data & AI Challenge (Track 1).
Ranks 100,000 candidates for a Senior AI Engineer JD and outputs the top 100.

## Reproduce the submission

```bash
git clone https://github.com/YOUR_USERNAME/redrob-ranker.git
cd redrob-ranker
pip install -r requirements.txt

# place candidates.jsonl in the project root, then:
python rank.py --candidates ./candidates.jsonl --out ./team_xxx.csv

# validate before submitting
python validate_submission.py team_xxx.csv
```

**Runtime:** ~25s on CPU. No GPU, no network, no API calls.

## Quick test on sample data

```bash
python3 -c "
import json
with open('data/sample_candidates.json') as f:
    data = json.load(f)
with open('/tmp/sample.jsonl', 'w') as f:
    for c in data:
        f.write(json.dumps(c) + '\n')
"
python rank.py --candidates /tmp/sample.jsonl --out /tmp/sample_out.csv --debug
```

## How it works

Five components run in sequence:

**1. Honeypot detection** — flags profiles with impossible skill durations or expert inflation. Scored 0, never enter top-100.

**2. Career scorer** — title match first. HR Managers, Accountants, Civil Engineers get hard-killed immediately regardless of skills. Prevents keyword stuffers from ranking. Also scores YoE band and company type (product vs consulting).

**3. Skill scorer** — weights must-have skills (FAISS, Qdrant, Weaviate, embeddings, NDCG, learning-to-rank) by `proficiency × log(duration) × trust`. Trust is determined by platform assessment score > endorsements > self-claimed.

**4. Signal scorer** — behavioral availability: recency, recruiter response rate, notice period, location relative to Pune/Noida.

**5. Combiner** — `(0.40 × skill + 0.35 × career + 0.25 × signal) × availability_multiplier`. Signal score used twice to penalize ghost candidates.

Reasoning strings are assembled from the same features that drove the score — specific skill names, durations, company names, availability signals. No LLM calls.

## File structure

```
redrob-ranker/
├── rank.py                  ← entry point
├── validate_submission.py   ← from bundle
├── requirements.txt
├── submission_metadata.yaml
├── README.md
├── src/
│   ├── jd_config.py         ← all JD weights in one place
│   ├── honeypot.py
│   ├── skill_scorer.py
│   ├── career_scorer.py
│   ├── signal_scorer.py
│   ├── combiner.py
│   └── reasoning.py
├── data/
│   └── sample_candidates.json
└── sandbox/
    └── app.py               ← Streamlit demo for HuggingFace Spaces
```

## Sandbox

[HuggingFace Spaces link here]