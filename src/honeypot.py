

from datetime import datetime

SKILL_DURATION_TOLERANCE = 1.20
SKILL_DURATION_BUFFER_MONTHS = 3

EXPERT_SKILL_THRESHOLD = 8
EXPERT_SKILL_MAX_YOE = 3.0

IMPOSSIBLE_SKILL_COUNT_THRESHOLD = 2


def _yoe_months(candidate: dict) -> float:
    return candidate["profile"]["years_of_experience"] * 12.0


def _check_impossible_skill_durations(candidate: dict) -> list[str]:
    """Return list of skill names whose duration exceeds total experience."""
    yoe_m = _yoe_months(candidate)
    ceiling = yoe_m * SKILL_DURATION_TOLERANCE + SKILL_DURATION_BUFFER_MONTHS
    flagged = []
    for skill in candidate.get("skills", []):
        dm = skill.get("duration_months", 0)
        if dm > ceiling:
            flagged.append(skill["name"])
    return flagged


def _check_expert_inflation(candidate: dict) -> bool:
    """Too many 'expert' skills for too little experience."""
    yoe = candidate["profile"]["years_of_experience"]
    if yoe >= EXPERT_SKILL_MAX_YOE:
        return False  # Not suspicious if they have real experience
    expert_count = sum(
        1 for s in candidate.get("skills", [])
        if s.get("proficiency") == "expert"
    )
    return expert_count >= EXPERT_SKILL_THRESHOLD


def _check_career_timeline_overlap(candidate: dict) -> bool:
    """
    Detect candidates whose career_history durations sum to wildly more
    than their stated years_of_experience.

    Small overlaps are real (e.g., consulting + side job). We only flag
    egregious over-claims (>50% more months than stated YoE).
    """
    yoe_months = _yoe_months(candidate)
    # Only look at non-current jobs summed up
    # Current job is always "open" so we exclude it from the sum
    past_months = sum(
        j["duration_months"]
        for j in candidate.get("career_history", [])
        if not j.get("is_current", False)
    )
    if yoe_months == 0:
        return False
    # If past jobs alone account for >1.6x stated YoE, something's off
    return past_months > yoe_months * 1.6


def _check_start_date_before_birth_possible(candidate: dict) -> bool:
  
    yoe = candidate["profile"]["years_of_experience"]
    history = candidate.get("career_history", [])
    if not history:
        return False

    start_dates = []
    for job in history:
        try:
            start_dates.append(datetime.strptime(job["start_date"], "%Y-%m-%d").year)
        except (ValueError, KeyError):
            pass

    if not start_dates:
        return False

    earliest_start = min(start_dates)
    implied_birth = earliest_start - 22
    implied_work_start = implied_birth + 14
    return earliest_start < implied_work_start


def is_honeypot(candidate: dict) -> bool:
    """
    Returns True if this candidate profile has impossible signals.
    Honeypots get score 0.0 and never enter the top-100.
    """
    impossible_skills = _check_impossible_skill_durations(candidate)
    if len(impossible_skills) >= IMPOSSIBLE_SKILL_COUNT_THRESHOLD:
        return True

    if _check_expert_inflation(candidate):
        return True

    if _check_career_timeline_overlap(candidate):
        return True

    if _check_start_date_before_birth_possible(candidate):
        return True

    return False


def honeypot_reason(candidate: dict) -> str:
    """Return human-readable reason for flagging (for debugging only)."""
    impossible_skills = _check_impossible_skill_durations(candidate)
    if len(impossible_skills) >= IMPOSSIBLE_SKILL_COUNT_THRESHOLD:
        return f"impossible skill durations: {impossible_skills}"
    if _check_expert_inflation(candidate):
        return "too many expert skills for YoE"
    if _check_career_timeline_overlap(candidate):
        return "career months >> stated YoE"
    if _check_start_date_before_birth_possible(candidate):
        return "career start implies impossible age"
    return "not a honeypot"