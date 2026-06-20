

from jd_config import WEIGHTS


def combine(skill_score: float, career_score: float, signal_score: float) -> float:
    """
    Returns final score in [0, 1].

    Hard rules:
    - career_score == 0.0 → final = 0.0 (HR Managers, Accountants etc)
    - signal_score is used both as a weighted component AND as a multiplier
      to penalize truly unavailable candidates
    """
    # Hard kill from career scorer
    if career_score == 0.0:
        return 0.0

    w = WEIGHTS

    # Weighted sum of components
    base_score = (
        w["skill"]  * skill_score +
        w["career"] * career_score +
        w["signal"] * signal_score
    )


    availability_multiplier = 0.55 + 0.45 * signal_score

    final = base_score * availability_multiplier

    return round(min(max(final, 0.0), 1.0), 4)


def tiebreak_key(result: dict) -> tuple:
    """
    Sort key for final ranking.
    Primary: score descending
    Tiebreak: candidate_id ascending (per spec section 3)
    """
    return (-result["score"], result["candidate_id"])