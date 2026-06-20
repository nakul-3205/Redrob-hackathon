

import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

from tqdm import tqdm

from honeypot import is_honeypot, honeypot_reason
from skill_scorer import score_skills
from career_scorer import score_career
from signal_scorer import score_signals
from combiner import combine, tiebreak_key
from reasoning import build_reasoning

# ── Output columns (spec mandates this exact order) ─────────────────────────
OUTPUT_FIELDS = ["candidate_id", "rank", "score", "reasoning"]


def open_candidates(path: str):
    """Open .jsonl or .jsonl.gz transparently."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: candidates file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if p.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def stream_candidates(path: str):
    """Yield parsed candidate dicts one at a time (memory-efficient)."""
    with open_candidates(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue  # skip malformed lines silently


def process_all(candidates_path: str, debug: bool = False) -> list[dict]:
    """
    Stream and score all candidates.
    Returns a list of result dicts sorted by tiebreak_key (best first).
    """
    results = []
    honeypot_count = 0
    hard_kill_count = 0
    total = 0

    for candidate in tqdm(stream_candidates(candidates_path), desc="Scoring", unit="cand"):
        total += 1
        cid = candidate.get("candidate_id", f"UNKNOWN_{total}")

        # ── Stage 1: Honeypot filter ─────────────────────────────────────
        if is_honeypot(candidate):
            honeypot_count += 1
            if debug:
                print(f"  [HONEYPOT] {cid}: {honeypot_reason(candidate)}")
            continue

        # ── Stage 2: Score components ────────────────────────────────────
        career_score = score_career(candidate)

        # Hard kill from career (HR Managers, Accountants etc)
        if career_score == 0.0:
            hard_kill_count += 1
            if debug:
                title = candidate["profile"]["current_title"]
                print(f"  [HARD KILL] {cid}: {title}")
            continue

        skill_score = score_skills(candidate)
        signal_score = score_signals(candidate)

        # ── Stage 3: Combine ─────────────────────────────────────────────
        final_score = combine(skill_score, career_score, signal_score)

        # ── Stage 4: Build reasoning ─────────────────────────────────────
        reasoning = build_reasoning(
            candidate, skill_score, career_score, signal_score, final_score
        )

        results.append({
            "candidate_id": cid,
            "score": final_score,
            "reasoning": reasoning,
            # Debug fields (stripped before CSV output)
            "_skill": skill_score,
            "_career": career_score,
            "_signal": signal_score,
        })

    # Sort by score desc, then candidate_id asc for ties
    results.sort(key=tiebreak_key)

    if debug or True:  # always print stats
        print(f"\n── Stats ───────────────────────────────")
        print(f"  Total processed : {total:,}")
        print(f"  Honeypots caught: {honeypot_count:,} ({honeypot_count/total*100:.1f}%)")
        print(f"  Hard kills      : {hard_kill_count:,} ({hard_kill_count/total*100:.1f}%)")
        print(f"  Scored          : {len(results):,}")
        if results:
            print(f"  Top score       : {results[0]['score']}")
            print(f"  Rank-100 score  : {results[99]['score'] if len(results) >= 100 else 'N/A'}")
            print(f"  Bottom score    : {results[-1]['score']}")
        if honeypot_count > 0:
            hp_pct = honeypot_count / total * 100
            if hp_pct > 5:
                print(f"\n  ⚠️  WARNING: Honeypot catch rate {hp_pct:.1f}% — check honeypot.py thresholds")

    return results


def write_csv(results: list[dict], out_path: str) -> None:
    """
    Write top-100 to CSV.
    Validates against spec rules before writing:
    - Exactly 100 rows
    - Ranks 1-100 each exactly once
    - Scores non-increasing
    - UTF-8 encoding
    """
    top100 = results[:100]

    if len(top100) < 100:
        print(f"ERROR: only {len(top100)} candidates scored — cannot produce 100-row submission", file=sys.stderr)
        print("Hint: check that your candidates file has enough data", file=sys.stderr)
        sys.exit(1)

    # Assign ranks
    for i, row in enumerate(top100):
        row["rank"] = i + 1

    # Verify non-increasing scores
    for i in range(len(top100) - 1):
        s1, s2 = top100[i]["score"], top100[i + 1]["score"]
        assert s1 >= s2, f"Score not non-increasing at ranks {i+1} and {i+2}: {s1} < {s2}"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in top100:
            writer.writerow({
                "candidate_id": row["candidate_id"],
                "rank": row["rank"],
                "score": row["score"],
                "reasoning": row["reasoning"],
            })

    print(f"\n✓ Submission written to: {out_path}")
    print(f"  Rows: 100  |  Top score: {top100[0]['score']}  |  Rank-100 score: {top100[99]['score']}")


def show_top10(results: list[dict]) -> None:
    """Print top-10 to console for quick sanity check."""
    print("\n── Top 10 ──────────────────────────────────────────────────────────")
    print(f"{'Rank':<5} {'ID':<14} {'Score':<7} {'Skill':<6} {'Career':<7} {'Signal':<7} Reasoning")
    print("-" * 120)
    for row in results[:10]:
        r = row.get("rank", "?")
        print(
            f"{r:<5} {row['candidate_id']:<14} {row['score']:<7} "
            f"{row.get('_skill', 0):<6.3f} {row.get('_career', 0):<7.3f} "
            f"{row.get('_signal', 0):<7.3f} {row['reasoning'][:80]}..."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rank candidates for the Redrob Hackathon JD"
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates.jsonl or candidates.jsonl.gz",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output CSV path (e.g. team_xxx.csv)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print honeypot/hard-kill details during processing",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use data/sample_candidates.json instead (for quick testing)",
    )
    args = parser.parse_args()

    # ── Sample mode (for development) ────────────────────────────────────────
    if args.sample:
        import json
        candidates_path = "data/sample_candidates.json"
        print(f"[SAMPLE MODE] Using {candidates_path}")

        with open(candidates_path) as f:
            sample_data = json.load(f)

        # Write sample as temp jsonl for reuse
        tmp_path = "/tmp/sample_candidates.jsonl"
        with open(tmp_path, "w") as f:
            for c in sample_data:
                f.write(json.dumps(c) + "\n")

        args.candidates = tmp_path

    t0 = time.time()
    print(f"Reading: {args.candidates}")

    results = process_all(args.candidates, debug=args.debug)
    show_top10(results)
    write_csv(results, args.out)

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")

    if elapsed > 300:
        print("⚠️  WARNING: exceeded 5-minute compute budget!", file=sys.stderr)


if __name__ == "__main__":
    main()