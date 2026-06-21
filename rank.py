import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

from tqdm import tqdm

from src.honeypot import is_honeypot, honeypot_reason
from src.skill_scorer import score_skills
from src.career_scorer import score_career
from src.signal_scorer import score_signals
from src.combiner import combine, tiebreak_key
from src.reasoning import build_reasoning

OUTPUT_FIELDS = ["candidate_id", "rank", "score", "reasoning"]


def open_candidates(path: str):
    p = Path(path)
    if not p.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if p.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def stream_candidates(path: str):
    with open_candidates(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def process_all(candidates_path: str, debug: bool = False) -> list[dict]:
    results       = []
    honeypot_count = 0
    hard_kill_count = 0
    total         = 0

    for candidate in tqdm(stream_candidates(candidates_path), desc="Scoring", unit="cand"):
        total += 1
        cid    = candidate.get("candidate_id", f"UNKNOWN_{total}")

        if is_honeypot(candidate):
            honeypot_count += 1
            if debug:
                print(f"  [HONEYPOT] {cid}: {honeypot_reason(candidate)}")
            continue

        career_score = score_career(candidate)
        if career_score == 0.0:
            hard_kill_count += 1
            if debug:
                print(f"  [HARD KILL] {cid}: {candidate['profile']['current_title']}")
            continue

        skill_score  = score_skills(candidate)
        signal_score = score_signals(candidate)
        final_score  = combine(skill_score, career_score, signal_score)
        reasoning    = build_reasoning(
            candidate, skill_score, career_score, signal_score, final_score
        )

        results.append({
            "candidate_id": cid,
            "score":        final_score,
            "reasoning":    reasoning,
            "_skill":       skill_score,
            "_career":      career_score,
            "_signal":      signal_score,
        })

    results.sort(key=tiebreak_key)

    print(f"\n── Stats ───────────────────────────────")
    print(f"  Total      : {total:,}")
    print(f"  Honeypots  : {honeypot_count:,} ({honeypot_count/total*100:.1f}%)")
    print(f"  Hard kills : {hard_kill_count:,} ({hard_kill_count/total*100:.1f}%)")
    print(f"  Scored     : {len(results):,}")
    if results:
        print(f"  Top score  : {results[0]['score']}")
        print(f"  Rank-100   : {results[99]['score'] if len(results) >= 100 else 'N/A'}")

    return results


def write_csv(results: list[dict], out_path: str) -> None:
    top100 = results[:100]

    if len(top100) < 100:
        print(f"ERROR: only {len(top100)} candidates scored.", file=sys.stderr)
        sys.exit(1)

    for i, row in enumerate(top100):
        row["rank"] = i + 1

    # sanity check scores are non-increasing
    for i in range(len(top100) - 1):
        s1, s2 = top100[i]["score"], top100[i + 1]["score"]
        assert s1 >= s2, f"Score not non-increasing at ranks {i+1} and {i+2}"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in top100:
            writer.writerow({
                "candidate_id": row["candidate_id"],
                "rank":         row["rank"],
                "score":        row["score"],
                "reasoning":    row["reasoning"],
            })

    print(f"\n✓ Written: {out_path}")
    print(f"  Top: {top100[0]['score']}  |  Rank-100: {top100[99]['score']}")


def show_top10(results: list[dict]) -> None:
    print("\n── Top 10 ──────────────────────────────────────────────────────────")
    print(f"{'Rank':<5} {'ID':<14} {'Score':<7} {'Skill':<6} {'Career':<7} {'Signal':<7} Reasoning")
    print("-" * 120)
    for row in results[:10]:
        print(
            f"{row.get('rank', '?'):<5} {row['candidate_id']:<14} {row['score']:<7} "
            f"{row.get('_skill', 0):<6.3f} {row.get('_career', 0):<7.3f} "
            f"{row.get('_signal', 0):<7.3f} {row['reasoning'][:80]}..."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank candidates for the Redrob Hackathon JD")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl or .jsonl.gz")
    parser.add_argument("--out",        required=True, help="Output CSV path")
    parser.add_argument("--debug",      action="store_true", help="Print honeypot/hard-kill details")
    parser.add_argument("--sample",     action="store_true", help="Use data/sample_candidates.json")
    args = parser.parse_args()

    if args.sample:
        candidates_path = "data/sample_candidates.json"
        print(f"[SAMPLE MODE] {candidates_path}")
        with open(candidates_path) as f:
            sample_data = json.load(f)
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
