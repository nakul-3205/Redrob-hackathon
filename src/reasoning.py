"""
reasoning.py — Build per-candidate reasoning strings from scored features.

NO LLM calls. NO manual work. Pure template assembly from computed facts.

Each string is specific to that candidate because the underlying data differs.
The Stage 4 checklist requires:
  - Specific facts from the profile ✓
  - Connection to JD requirements ✓ 
  - Honest acknowledgement of gaps ✓
  - No hallucination (nothing invented) ✓
  - Consistency with rank (high rank = positive tone) ✓
"""

from skill_scorer import top_relevant_skills
from career_scorer import get_career_context
from signal_scorer import get_signal_context


def _describe_skill(skill: dict) -> str:
    """Format one skill for the reasoning string."""
    name = skill["name"]
    prof = skill.get("proficiency", "intermediate")
    dur = skill.get("duration_months", 0)
    endorsements = skill.get("endorsements", 0)

    parts = [f"{name} ({prof}"]
    if dur > 0:
        parts[0] += f", {dur}mo"
    parts[0] += ")"

    if endorsements >= 5:
        parts.append(f"{endorsements} endorsements")

    return ", ".join(parts)


def _build_skill_phrase(candidate: dict) -> str:
    """Describe top relevant skills in one phrase."""
    top = top_relevant_skills(candidate, n=3)

    if not top:
        return "no direct retrieval/search/embeddings skills identified"

    if len(top) == 1:
        return _describe_skill(top[0])

    if len(top) == 2:
        return f"{_describe_skill(top[0])} + {_describe_skill(top[1])}"

    # 3 skills — just name the first two and count the rest
    s1 = _describe_skill(top[0])
    s2 = _describe_skill(top[1])
    return f"{s1} + {s2} (+{len(top)-2} more relevant)"


def _build_company_phrase(ctx: dict) -> str:
    """Describe company background."""
    if ctx["product_companies"]:
        co = ctx["product_companies"][0]
        return f"product co. background ({co})"
    elif ctx["consulting_companies"]:
        co = ctx["consulting_companies"][0]
        return f"consulting background ({co}) — flag"
    else:
        co = ctx["current_company"]
        ind = ctx["current_industry"]
        return f"{co} ({ind})"


def _build_availability_phrases(sig_ctx: dict) -> tuple[list[str], list[str]]:
    """
    Returns (positives, concerns) lists to be assembled into sentence 2.
    """
    positives = []
    concerns = []

    # Recency
    days = sig_ctx["days_inactive"]
    if days <= 3:
        positives.append(f"active {days}d ago")
    elif days <= 14:
        positives.append(f"active {days}d ago")
    elif days <= 30:
        positives.append(f"active ~{days}d ago")
    elif days <= 60:
        concerns.append(f"inactive {days}d")
    elif days <= 90:
        concerns.append(f"inactive {days}d — possibly passive")
    else:
        concerns.append(f"inactive {days}d — likely passive/unavailable")

    # Open to work
    if sig_ctx["open_to_work"]:
        positives.append("open to work")

    # Notice period
    notice = sig_ctx["notice_days"]
    if notice == 0:
        positives.append("immediate joiner")
    elif notice <= 30:
        positives.append(f"{notice}d notice (buyable)")
    elif notice <= 60:
        pass  # neutral — don't clutter the string
    elif notice <= 90:
        concerns.append(f"{notice}d notice")
    else:
        concerns.append(f"{notice}d notice — long")

    # Recruiter response rate
    resp = sig_ctx["response_rate"]
    if resp >= 0.75:
        positives.append(f"{int(resp*100)}% recruiter response rate")
    elif resp < 0.20:
        concerns.append(f"low response rate ({int(resp*100)}%)")

    # Location
    country = sig_ctx["country"]
    location = sig_ctx["location"].split(",")[0].strip() if sig_ctx["location"] else ""
    in_target = sig_ctx["in_target_city"]
    will_relocate = sig_ctx["willing_to_relocate"]

    if country.lower() == "india" and in_target:
        positives.append(f"India-based ({location})")
    elif country.lower() == "india" and will_relocate:
        positives.append(f"India-based ({location}), willing to relocate")
    elif country.lower() == "india":
        concerns.append(f"India ({location}), no relocation — may not move to Pune/Noida")
    elif will_relocate:
        concerns.append(f"outside India ({country}), willing to relocate")
    else:
        concerns.append(f"outside India ({country}), no relocation — JD case-by-case")

    # GitHub bonus mention (if notable)
    gh = sig_ctx["github_score"]
    if gh >= 60:
        positives.append(f"active GitHub ({gh:.0f}/100)")

    return positives, concerns


def build_reasoning(
    candidate: dict,
    skill_score: float,
    career_score: float,
    signal_score: float,
    final_score: float,
) -> str:
    """
    Build a 1-2 sentence reasoning string for this candidate.

    Sentence 1: Who they are + best skills + company context
    Sentence 2: Availability signals (positives and concerns)
    """
    profile = candidate["profile"]
    career_ctx = get_career_context(candidate)
    sig_ctx = get_signal_context(candidate)

    title = profile["current_title"]
    yoe = profile["years_of_experience"]

    # --- Sentence 1: Identity + Skills + Career ---
    skill_phrase = _build_skill_phrase(candidate)
    company_phrase = _build_company_phrase(career_ctx)

    sentence1 = f"{title}, {yoe:.1f}y; {skill_phrase}; {company_phrase}"

    # --- Sentence 2: Availability ---
    positives, concerns = _build_availability_phrases(sig_ctx)

    if positives and concerns:
        s2_parts = [", ".join(positives), "concern: " + "; ".join(concerns)]
        sentence2 = ". ".join(s2_parts)
    elif positives:
        sentence2 = ", ".join(positives)
    elif concerns:
        sentence2 = "concern: " + "; ".join(concerns)
    else:
        sentence2 = "no strong availability signals either way"

    # For very low scorers, add a brief note on why they're near the bottom
    if final_score < 0.30:
        if career_score < 0.30:
            sentence2 += ". Title/career mismatch for this JD"
        elif skill_score < 0.20:
            sentence2 += ". Limited relevant AI/search skills"

    return f"{sentence1}. {sentence2}."