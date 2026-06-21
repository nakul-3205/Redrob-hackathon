from src.jd_config import WEIGHTS


def combine(skill_score: float, career_score: float, signal_score: float) -> float:
    """
    Weighted sum with an availability multiplier.
    A great candidate who's unreachable (signal=0) still gets heavily penalised.
    """
    if career_score == 0.0:
        return 0.0  # hard kill from career scorer

    w = WEIGHTS
    base_score = (
        w["skill"]  * skill_score +
        w["career"] * career_score +
        w["signal"] * signal_score
    )

    # multiplier floors at 0.55 so unavailability can't zero out an otherwise great profile
    availability_multiplier = 0.55 + 0.45 * signal_score

    final = base_score * availability_multiplier
    return round(min(max(final, 0.0), 1.0), 4)


def tiebreak_key(result: dict) -> tuple:
    # spec section 3: score desc, then candidate_id asc
    return (-result["score"], result["candidate_id"])
