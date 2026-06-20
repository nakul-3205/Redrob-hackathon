"""
skill_scorer.py — Score how well a candidate's skills match the JD.

Key design decisions:
- Must-have skills are weighted by proficiency × duration × trust
- Duration is log-scaled (diminishing returns past 2 years)
- Trust multiplier: platform assessment > endorsed > self-claimed
- Negative skills subtract from score (but can't push below 0)
- Final score normalized to [0, 1]
"""

import math
from jd_config import (
    MUST_HAVE_SKILLS,
    NICE_TO_HAVE_SKILLS,
    NEGATIVE_SKILLS,
)

# Proficiency level → numeric weight
PROFICIENCY_WEIGHT = {
    "beginner":     0.30,
    "intermediate": 0.60,
    "advanced":     0.85,
    "expert":       1.00,
}

# Normalization denominators — tuned so a "perfect" candidate scores ~1.0
# A perfect candidate might have 3-4 must-have skills at advanced/expert level
# with 24-48 months each. This is what that adds up to roughly.
MUST_HAVE_NORM = 3.5
NICE_TO_HAVE_NORM = 2.0

# Max bonus from nice-to-have (keeps it from dominating)
MAX_NICE_BONUS = 0.20

# Max penalty from negative skills
MAX_NEGATIVE_PENALTY = 0.30


def _log_duration_bonus(duration_months: int) -> float:
    """
    Logarithmic duration bonus.
    1 month  → 0.32
    6 months → 0.71
    12 months → 0.89
    24 months → 1.07
    36 months → 1.17
    60 months → 1.31

    Rationale: first 6 months of using a skill matters a lot; 
    going from 4 to 5 years barely matters.
    """
    return math.log(max(duration_months, 1) + 1) / math.log(13)


def _trust_multiplier(skill: dict, assessment_scores: dict) -> float:
    """
    How much do we trust this skill claim?

    Platform assessment > endorsed by peers > self-claimed
    Assessment score of 70+ → high trust
    Assessment score 40-70  → moderate trust  
    Assessment score <40    → the candidate is overstating
    """
    name_lower = skill["name"].lower()
    endorsements = skill.get("endorsements", 0)

    if name_lower in assessment_scores:
        assessed = assessment_scores[name_lower]
        if assessed >= 70:
            return 1.00
        elif assessed >= 50:
            return 0.80
        elif assessed >= 30:
            return 0.55
        else:
            # Assessed but scored poorly — overstating
            return 0.30

    if endorsements >= 10:
        return 0.95
    elif endorsements >= 5:
        return 0.88
    elif endorsements >= 1:
        return 0.75
    else:
        # Self-claimed only
        return 0.60


def score_skills(candidate: dict) -> float:
    """
    Returns a float in [0, 1] representing how well this candidate's
    skills match the JD's requirements.
    """
    skills = candidate.get("skills", [])
    assessment_scores = {
        k.lower(): v
        for k, v in candidate["redrob_signals"]
        .get("skill_assessment_scores", {})
        .items()
    }

    must_have_raw = 0.0
    nice_to_have_raw = 0.0
    negative_penalty = 0.0

    for skill in skills:
        name_lower = skill["name"].lower()
        proficiency = PROFICIENCY_WEIGHT.get(skill.get("proficiency", "beginner"), 0.30)
        duration = skill.get("duration_months", 1)
        trust = _trust_multiplier(skill, assessment_scores)
        duration_bonus = _log_duration_bonus(duration)

        skill_value = proficiency * trust * duration_bonus

        if name_lower in MUST_HAVE_SKILLS:
            importance = MUST_HAVE_SKILLS[name_lower]
            must_have_raw += skill_value * importance

        elif name_lower in NICE_TO_HAVE_SKILLS:
            importance = NICE_TO_HAVE_SKILLS[name_lower]
            nice_to_have_raw += skill_value * importance

        elif name_lower in NEGATIVE_SKILLS:
            penalty_weight = NEGATIVE_SKILLS[name_lower]
            negative_penalty += proficiency * penalty_weight

    # Normalize must-have to [0, 1]
    must_have_score = min(must_have_raw / MUST_HAVE_NORM, 1.0)

    # Nice-to-have adds up to MAX_NICE_BONUS
    nice_bonus = min((nice_to_have_raw / NICE_TO_HAVE_NORM) * MAX_NICE_BONUS, MAX_NICE_BONUS)

    # Penalty capped
    penalty = min(negative_penalty, MAX_NEGATIVE_PENALTY)

    final = must_have_score + nice_bonus - penalty
    return round(max(min(final, 1.0), 0.0), 4)


def top_relevant_skills(candidate: dict, n: int = 3) -> list[dict]:
    """
    Return the top N must-have skills this candidate has, sorted by quality.
    Used by the reasoning builder.
    """
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
            prof = PROFICIENCY_WEIGHT.get(skill.get("proficiency", "beginner"), 0.3)
            dur = skill.get("duration_months", 0)
            trust = _trust_multiplier(skill, assessment_scores)
            quality = prof * trust * _log_duration_bonus(dur)
            relevant.append({**skill, "_quality": quality})

    relevant.sort(key=lambda s: s["_quality"], reverse=True)
    return relevant[:n]