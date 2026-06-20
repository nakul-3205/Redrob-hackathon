"""
career_scorer.py — Score title, years of experience, and company background.

This is the component that kills keyword stuffers.
An HR Manager with 9 AI skills gets career_score = 0.0
and therefore final_score = 0.0 regardless of skill_score.
"""

from jd_config import (
    TITLE_TIERS,
    CONSULTING_COMPANIES,
    TECH_INDUSTRIES,
    PRODUCT_COMPANY_SIZES,
    YOE_SCORES,
    CAREER_WEIGHTS,
)


def _score_title(title: str) -> float:
    """
    Match title string against TITLE_TIERS.
    First match wins (tiers are priority-ordered in jd_config).
    """
    title_lower = title.lower().strip()
    for keywords, score in TITLE_TIERS:
        if any(kw in title_lower for kw in keywords):
            return score
    # No match — neutral
    return 0.30


def _score_yoe(yoe: float) -> float:
    """Score years of experience against the JD's preferred band."""
    for condition, score in YOE_SCORES:
        if condition(yoe):
            return score
    return 0.15


def _is_consulting(company_name: str) -> bool:
    name_lower = company_name.lower()
    return any(c in name_lower for c in CONSULTING_COMPANIES)


def _is_tech_industry(industry: str) -> bool:
    industry_lower = industry.lower()
    return any(kw in industry_lower for kw in TECH_INDUSTRIES)


def _score_company_background(career_history: list) -> float:
    """
    Score based on company types in career history.

    Product company in tech industry → positive
    Consulting company (TCS, Infosys etc) → penalty
    Current job gets double weight.
    """
    if not career_history:
        return 0.5

    total_weight = 0.0
    weighted_score = 0.0

    for job in career_history:
        company = job.get("company", "")
        industry = job.get("industry", "")
        size = job.get("company_size", "")
        is_current = job.get("is_current", False)
        duration = job.get("duration_months", 12)

        # Current job weighs more than past jobs
        weight = (duration * 2) if is_current else duration

        # Score this specific job
        job_score = 0.5  # neutral baseline

        if _is_consulting(company):
            job_score = 0.20  # explicit JD penalty

        elif _is_tech_industry(industry):
            if size in PRODUCT_COMPANY_SIZES:
                job_score = 0.95  # ideal: product company, right size, tech
            elif size in {"5001-10000", "10001+"}:
                job_score = 0.70  # big tech — fine, not ideal
            elif size in {"1-10", "11-50"}:
                job_score = 0.65  # small startup — fine
            else:
                job_score = 0.75
        else:
            # Non-tech industry
            job_score = 0.35

        weighted_score += job_score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.5

    return min(max(weighted_score / total_weight, 0.0), 1.0)


def score_career(candidate: dict) -> float:
    """
    Returns float in [0, 1].

    IMPORTANT: if title_score == 0.0 (hard kill), we return 0.0 immediately.
    This ensures HR Managers / Accountants etc can never reach top-100
    regardless of how many AI skills they claim.
    """
    profile = candidate["profile"]
    career_history = candidate.get("career_history", [])

    title_score = _score_title(profile["current_title"])

    # Hard kill — no point scoring further
    if title_score == 0.0:
        return 0.0

    yoe_score = _score_yoe(profile["years_of_experience"])
    company_score = _score_company_background(career_history)

    w = CAREER_WEIGHTS
    final = (
        w["title"]   * title_score +
        w["yoe"]     * yoe_score +
        w["company"] * company_score
    )
    return round(min(max(final, 0.0), 1.0), 4)


def get_career_context(candidate: dict) -> dict:
    """
    Return structured career context for the reasoning builder.
    """
    profile = candidate["profile"]
    career_history = candidate.get("career_history", [])

    title_score = _score_title(profile["current_title"])
    product_companies = []
    consulting_companies = []

    for job in career_history:
        company = job.get("company", "")
        industry = job.get("industry", "")
        size = job.get("company_size", "")
        if _is_consulting(company):
            consulting_companies.append(company)
        elif _is_tech_industry(industry) and size in PRODUCT_COMPANY_SIZES:
            product_companies.append(company)

    return {
        "title_score": title_score,
        "product_companies": product_companies,
        "consulting_companies": consulting_companies,
        "yoe": profile["years_of_experience"],
        "current_company": profile["current_company"],
        "current_industry": profile["current_industry"],
    }