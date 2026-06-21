# reasoning.py — builds per-candidate reasoning strings from scored data.
# No LLM calls, no templates with placeholder text. Pure fact assembly.

from src.skill_scorer import top_relevant_skills
from src.career_scorer import get_career_context
from src.signal_scorer import get_signal_context
from src.jd_config import LANGCHAIN_WRAPPER_SKILLS, MUST_HAVE_SKILLS


def _describe_skill(skill: dict) -> str:
    name         = skill["name"]
    prof         = skill.get("proficiency", "intermediate")
    dur          = skill.get("duration_months", 0)
    endorsements = skill.get("endorsements", 0)

    s = f"{name} ({prof}"
    if dur > 0:
        s += f", {dur}mo"
    s += ")"

    if endorsements >= 5:
        s += f", {endorsements} endorsements"

    return s


def _build_skill_phrase(candidate: dict) -> str:
    top = top_relevant_skills(candidate, n=3)

    if not top:
        # check for wrapper-only pattern
        skill_names = {s["name"].lower() for s in candidate.get("skills", [])}
        has_wrapper = skill_names & LANGCHAIN_WRAPPER_SKILLS
        has_real    = any(n in MUST_HAVE_SKILLS for n in skill_names)
        if has_wrapper and not has_real:
            return "LangChain/LlamaIndex wrapper skills only — no foundational IR/search depth"
        return "no direct retrieval/search/embeddings skills identified"

    if len(top) == 1:
        return _describe_skill(top[0])
    if len(top) == 2:
        return f"{_describe_skill(top[0])} + {_describe_skill(top[1])}"

    s1 = _describe_skill(top[0])
    s2 = _describe_skill(top[1])
    return f"{s1} + {s2} (+{len(top)-2} more relevant)"


def _build_company_phrase(ctx: dict) -> str:
    if ctx["product_companies"]:
        return f"product co. background ({ctx['product_companies'][0]})"
    elif ctx["consulting_companies"]:
        return f"consulting background ({ctx['consulting_companies'][0]}) — flag"
    else:
        return f"{ctx['current_company']} ({ctx['current_industry']})"


def _build_availability_phrases(sig_ctx: dict) -> tuple[list[str], list[str]]:
    """Returns (positives, concerns) lists."""
    positives = []
    concerns  = []

    days = sig_ctx["days_inactive"]
    if   days <= 14: positives.append(f"active {days}d ago")
    elif days <= 30: positives.append(f"active ~{days}d ago")
    elif days <= 60: concerns.append(f"inactive {days}d")
    elif days <= 90: concerns.append(f"inactive {days}d — possibly passive")
    else:            concerns.append(f"inactive {days}d — likely passive/unavailable")

    if sig_ctx["open_to_work"]:
        positives.append("open to work")

    notice = sig_ctx["notice_days"]
    if   notice == 0:   positives.append("immediate joiner")
    elif notice <= 30:  positives.append(f"{notice}d notice (buyable)")
    elif notice <= 90:  concerns.append(f"{notice}d notice")
    else:               concerns.append(f"{notice}d notice — long")

    resp = sig_ctx["response_rate"]
    if   resp >= 0.75:  positives.append(f"{int(resp*100)}% recruiter response rate")
    elif resp < 0.20:   concerns.append(f"low response rate ({int(resp*100)}%)")

    country      = sig_ctx["country"]
    location     = sig_ctx["location"].split(",")[0].strip() if sig_ctx["location"] else ""
    in_target    = sig_ctx["in_target_city"]
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
    Two sentences:
    1. Who they are + top skills + company context
    2. Availability signals with explicit concerns flagged
    """
    profile     = candidate["profile"]
    career_ctx  = get_career_context(candidate)
    sig_ctx     = get_signal_context(candidate)

    title = profile["current_title"]
    yoe   = profile["years_of_experience"]

    skill_phrase   = _build_skill_phrase(candidate)
    company_phrase = _build_company_phrase(career_ctx)
    sentence1      = f"{title}, {yoe:.1f}y; {skill_phrase}; {company_phrase}"

    positives, concerns = _build_availability_phrases(sig_ctx)

    if positives and concerns:
        sentence2 = ", ".join(positives) + ". concern: " + "; ".join(concerns)
    elif positives:
        sentence2 = ", ".join(positives)
    elif concerns:
        sentence2 = "concern: " + "; ".join(concerns)
    else:
        sentence2 = "no strong availability signals either way"

    if final_score < 0.30:
        if career_score < 0.30:
            sentence2 += ". Title/career mismatch for this JD"
        elif skill_score < 0.20:
            sentence2 += ". Limited relevant AI/search skills"

    return f"{sentence1}. {sentence2}."
