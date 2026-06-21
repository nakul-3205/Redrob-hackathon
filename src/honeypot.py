from datetime import datetime

SKILL_DURATION_TOLERANCE       = 1.20
SKILL_DURATION_BUFFER_MONTHS   = 3
EXPERT_SKILL_THRESHOLD         = 8
EXPERT_SKILL_MAX_YOE           = 3.0
IMPOSSIBLE_SKILL_COUNT_THRESHOLD = 2


def _yoe_months(candidate: dict) -> float:
    return candidate["profile"]["years_of_experience"] * 12.0


def _check_impossible_skill_durations(candidate: dict) -> list[str]:
    """Skill duration > total experience is a fabrication signal."""
    yoe_m   = _yoe_months(candidate)
    ceiling = yoe_m * SKILL_DURATION_TOLERANCE + SKILL_DURATION_BUFFER_MONTHS
    flagged = []
    for skill in candidate.get("skills", []):
        if skill.get("duration_months", 0) > ceiling:
            flagged.append(skill["name"])
    return flagged


def _check_expert_inflation(candidate: dict) -> bool:
    """8+ expert skills with <3 years experience doesn't add up."""
    yoe = candidate["profile"]["years_of_experience"]
    if yoe >= EXPERT_SKILL_MAX_YOE:
        return False
    expert_count = sum(
        1 for s in candidate.get("skills", [])
        if s.get("proficiency") == "expert"
    )
    return expert_count >= EXPERT_SKILL_THRESHOLD


def _check_career_timeline_overlap(candidate: dict) -> bool:
    """Past job months summing to >1.6x stated YoE is suspicious."""
    yoe_months  = _yoe_months(candidate)
    past_months = sum(
        j["duration_months"]
        for j in candidate.get("career_history", [])
        if not j.get("is_current", False)
    )
    if yoe_months == 0:
        return False
    return past_months > yoe_months * 1.6


def _check_start_date_before_birth_possible(candidate: dict) -> bool:
    """Career started before they could plausibly have been working age."""
    yoe     = candidate["profile"]["years_of_experience"]
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

    earliest_start     = min(start_dates)
    implied_birth      = earliest_start - 22
    implied_work_start = implied_birth + 14
    return earliest_start < implied_work_start


def is_honeypot(candidate: dict) -> bool:
    """Returns True if the profile contains impossible signals — auto-score 0."""
    if len(_check_impossible_skill_durations(candidate)) >= IMPOSSIBLE_SKILL_COUNT_THRESHOLD:
        return True
    if _check_expert_inflation(candidate):
        return True
    if _check_career_timeline_overlap(candidate):
        return True
    if _check_start_date_before_birth_possible(candidate):
        return True
    return False


def honeypot_reason(candidate: dict) -> str:
    """Human-readable flag reason — for debug output only."""
    impossible = _check_impossible_skill_durations(candidate)
    if len(impossible) >= IMPOSSIBLE_SKILL_COUNT_THRESHOLD:
        return f"impossible skill durations: {impossible}"
    if _check_expert_inflation(candidate):
        return "too many expert skills for YoE"
    if _check_career_timeline_overlap(candidate):
        return "career months >> stated YoE"
    if _check_start_date_before_birth_possible(candidate):
        return "career start implies impossible age"
    return "not a honeypot"
