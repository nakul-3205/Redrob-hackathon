import math
from src.jd_config import (
    MUST_HAVE_SKILLS,
    NICE_TO_HAVE_SKILLS,
    NEGATIVE_SKILLS,
    DOMAIN_MISMATCH_SKILL_KEYS,
    LANGCHAIN_WRAPPER_SKILLS,
)

PROFICIENCY_WEIGHT = {
    "beginner":     0.30,
    "intermediate": 0.60,
    "advanced":     0.85,
    "expert":       1.00,
}

# Tuned so a candidate with 3-4 expert must-have skills at ~2yr each lands near 1.0
MUST_HAVE_NORM    = 3.5
NICE_TO_HAVE_NORM = 2.0
MAX_NICE_BONUS       = 0.20
MAX_NEGATIVE_PENALTY = 0.30


def _log_duration_bonus(duration_months: int) -> float:
    # log scale — early months of a skill matter more than later ones
    return math.log(max(duration_months, 1) + 1) / math.log(13)


def _trust_multiplier(skill: dict, assessment_scores: dict) -> float:
    # platform assessment > peer endorsements > self-claimed
    name_lower = skill["name"].lower()
    endorsements = skill.get("endorsements", 0)

    if name_lower in assessment_scores:
        assessed = assessment_scores[name_lower]
        if assessed >= 70:   return 1.00
        elif assessed >= 50: return 0.80
        elif assessed >= 30: return 0.55
        else:                return 0.30  # assessed badly — overstating

    if endorsements >= 10:  return 0.95
    elif endorsements >= 5: return 0.88
    elif endorsements >= 1: return 0.75
    else:                   return 0.60  # self-claimed only


def score_skills(candidate: dict) -> float:
    """Returns [0, 1] skill match score against the JD."""
    skills = candidate.get("skills", [])
    assessment_scores = {
        k.lower(): v
        for k, v in candidate["redrob_signals"]
        .get("skill_assessment_scores", {})
        .items()
    }

    must_have_raw      = 0.0
    nice_to_have_raw   = 0.0
    negative_penalty   = 0.0
    domain_penalty     = 0.0  # CV/speech/robotics — conditional
    has_wrapper_skill  = False

    for skill in skills:
        name_lower   = skill["name"].lower()
        proficiency  = PROFICIENCY_WEIGHT.get(skill.get("proficiency", "beginner"), 0.30)
        duration     = skill.get("duration_months", 1)
        trust        = _trust_multiplier(skill, assessment_scores)
        dur_bonus    = _log_duration_bonus(duration)
        skill_value  = proficiency * trust * dur_bonus

        if name_lower in MUST_HAVE_SKILLS:
            must_have_raw += skill_value * MUST_HAVE_SKILLS[name_lower]

        elif name_lower in NICE_TO_HAVE_SKILLS:
            nice_to_have_raw += skill_value * NICE_TO_HAVE_SKILLS[name_lower]

        elif name_lower in NEGATIVE_SKILLS:
            weight = NEGATIVE_SKILLS[name_lower]
            if name_lower in DOMAIN_MISMATCH_SKILL_KEYS:
                # track separately — only applied below if no NLP/IR found
                domain_penalty += proficiency * weight
            else:
                negative_penalty += proficiency * weight

        if name_lower in LANGCHAIN_WRAPPER_SKILLS:
            has_wrapper_skill = True

    must_have_score = min(must_have_raw / MUST_HAVE_NORM, 1.0)
    has_nlp_ir      = must_have_raw > 0

    nice_bonus = min((nice_to_have_raw / NICE_TO_HAVE_NORM) * MAX_NICE_BONUS, MAX_NICE_BONUS)

    # CV/speech/robotics only counts against them if they have zero NLP/IR depth
    if not has_nlp_ir:
        negative_penalty += domain_penalty

    penalty = min(negative_penalty, MAX_NEGATIVE_PENALTY)

    final = must_have_score + nice_bonus - penalty

    # LangChain/LlamaIndex without foundational IR skills = wrapper engineer
    if has_wrapper_skill and not has_nlp_ir:
        final -= 0.15

    return round(max(min(final, 1.0), 0.0), 4)


def top_relevant_skills(candidate: dict, n: int = 3) -> list[dict]:
    """Return top N must-have skills by quality score, for reasoning output."""
    skills = candidate.get("skills", [])
    assessment_scores = {
        k.lower(): v
        for k, v in candidate["redrob_signals"]
        .get("skill_assessment_scores", {})
        .items()
    }
    relevant = []
    for skill in skills:
        name_lower = skill["name"].lower()
        if name_lower in MUST_HAVE_SKILLS:
            prof      = PROFICIENCY_WEIGHT.get(skill.get("proficiency", "beginner"), 0.3)
            dur       = skill.get("duration_months", 0)
            trust     = _trust_multiplier(skill, assessment_scores)
            quality   = prof * trust * _log_duration_bonus(dur)
            relevant.append({**skill, "_quality": quality})

    relevant.sort(key=lambda s: s["_quality"], reverse=True)
    return relevant[:n]
