from src.jd_config import (
    TITLE_TIERS,
    CONSULTING_COMPANIES,
    TECH_INDUSTRIES,
    PRODUCT_COMPANY_SIZES,
    YOE_SCORES,
    CAREER_WEIGHTS,
)


def _score_title(title: str) -> float:
    # first match wins; TITLE_TIERS is ordered by relevance
    title_lower = title.lower().strip()
    for keywords, score in TITLE_TIERS:
        if any(kw in title_lower for kw in keywords):
            return score
    return 0.30  # unrecognised title — neutral, not a kill


def _score_yoe(yoe: float) -> float:
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
    """Weighted average of job scores; current role counts double."""
    if not career_history:
        return 0.5

    total_weight   = 0.0
    weighted_score = 0.0

    for job in career_history:
        company    = job.get("company", "")
        industry   = job.get("industry", "")
        size       = job.get("company_size", "")
        is_current = job.get("is_current", False)
        duration   = job.get("duration_months", 12)

        weight    = (duration * 2) if is_current else duration
        job_score = 0.5  # neutral baseline

        if _is_consulting(company):
            job_score = 0.20
        elif _is_tech_industry(industry):
            if size in PRODUCT_COMPANY_SIZES:
                job_score = 0.95   # product company, right size
            elif size in {"5001-10000", "10001+"}:
                job_score = 0.70   # big tech
            elif size in {"1-10", "11-50"}:
                job_score = 0.65   # small startup
            else:
                job_score = 0.75
        else:
            job_score = 0.35   # non-tech industry

        weighted_score += job_score * weight
        total_weight   += weight

    if total_weight == 0:
        return 0.5

    return min(max(weighted_score / total_weight, 0.0), 1.0)


def score_career(candidate: dict) -> float:
    """
    Returns [0, 1]. Title score of 0.0 is a hard kill — HR Managers,
    accountants, civil engineers etc can never reach the top-100.
    """
    profile        = candidate["profile"]
    career_history = candidate.get("career_history", [])

    title_score = _score_title(profile["current_title"])
    if title_score == 0.0:
        return 0.0  # hard kill

    yoe_score     = _score_yoe(profile["years_of_experience"])
    company_score = _score_company_background(career_history)

    w = CAREER_WEIGHTS
    final = (
        w["title"]   * title_score +
        w["yoe"]     * yoe_score +
        w["company"] * company_score
    )
    return round(min(max(final, 0.0), 1.0), 4)


def get_career_context(candidate: dict) -> dict:
    """Structured context consumed by reasoning.py."""
    profile        = candidate["profile"]
    career_history = candidate.get("career_history", [])

    product_companies    = []
    consulting_companies = []

    for job in career_history:
        company  = job.get("company", "")
        industry = job.get("industry", "")
        size     = job.get("company_size", "")
        if _is_consulting(company):
            consulting_companies.append(company)
        elif _is_tech_industry(industry) and size in PRODUCT_COMPANY_SIZES:
            product_companies.append(company)

    return {
        "title_score":           _score_title(profile["current_title"]),
        "product_companies":     product_companies,
        "consulting_companies":  consulting_companies,
        "yoe":                   profile["years_of_experience"],
        "current_company":       profile["current_company"],
        "current_industry":      profile["current_industry"],
    }
