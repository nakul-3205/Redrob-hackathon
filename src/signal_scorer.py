

from datetime import date, datetime
from jd_config import TARGET_CITIES, SIGNAL_WEIGHTS

# Hardcode evaluation date (present during competition)
TODAY = date(2026, 6, 19)


def _days_since(date_str: str | None) -> int:
    if not date_str:
        return 9999
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return max((TODAY - d).days, 0)
    except ValueError:
        return 9999


def _score_recency(sig: dict) -> float:
    """
    How recently was the candidate active on platform?

    This is the strongest availability signal. A candidate who logged in
    yesterday is actively looking; one who hasn't logged in in 6 months
    might have already taken another job.
    """
    days = _days_since(sig.get("last_active_date"))
    open_to_work = sig.get("open_to_work_flag", False)

    # Base recency score
    if days <= 7:
        recency = 1.00
    elif days <= 14:
        recency = 0.95
    elif days <= 30:
        recency = 0.85
    elif days <= 60:
        recency = 0.70
    elif days <= 90:
        recency = 0.50
    elif days <= 120:
        recency = 0.35
    elif days <= 180:
        recency = 0.20
    else:
        recency = 0.08

    # open_to_work flag boosts recency slightly — they've explicitly said they want to move
    if open_to_work and days <= 90:
        recency = min(recency + 0.10, 1.0)
    elif open_to_work and days > 90:
        recency = min(recency + 0.05, 1.0)

    # Extra signals that suggest active job searching
    apps_30d = sig.get("applications_submitted_30d", 0)
    profile_views = sig.get("profile_views_received_30d", 0)

    if apps_30d >= 5:
        recency = min(recency + 0.05, 1.0)  # actively applying
    if profile_views >= 10:
        recency = min(recency + 0.03, 1.0)  # recruiters are noticing them

    return recency


def _score_responsiveness(sig: dict) -> float:
    """
    Will they actually respond to our recruiter outreach?

    recruiter_response_rate is the key signal.
    avg_response_time_hours is secondary.
    """
    response_rate = sig.get("recruiter_response_rate", 0.5)
    avg_time_hours = sig.get("avg_response_time_hours", 48)
    interview_completion = sig.get("interview_completion_rate", 0.5)

    # Response rate
    if response_rate >= 0.80:
        resp_score = 1.00
    elif response_rate >= 0.60:
        resp_score = 0.85
    elif response_rate >= 0.40:
        resp_score = 0.65
    elif response_rate >= 0.20:
        resp_score = 0.40
    else:
        resp_score = 0.15  # under 20% — nearly unreachable

    # Response time modifier
    if avg_time_hours <= 4:
        resp_score = min(resp_score + 0.05, 1.0)
    elif avg_time_hours > 72:
        resp_score = max(resp_score - 0.05, 0.0)

    # Interview completion rate is a strong trust signal
    # If they schedule interviews and ghost — that's a red flag
    if interview_completion >= 0.85:
        resp_score = min(resp_score + 0.05, 1.0)
    elif interview_completion < 0.40:
        resp_score = max(resp_score - 0.10, 0.0)

    return resp_score


def _score_notice_period(sig: dict) -> float:
    """
    JD says: sub-30 day preferred; can buy out up to 30 days;
    30+ day candidates 'still in scope but bar gets higher'.
    """
    notice = sig.get("notice_period_days", 60)

    if notice == 0:
        return 1.00   # immediate joiner — ideal
    elif notice <= 15:
        return 0.98
    elif notice <= 30:
        return 0.92   # JD says they can buy out up to 30 days
    elif notice <= 45:
        return 0.78
    elif notice <= 60:
        return 0.65
    elif notice <= 90:
        return 0.45
    elif notice <= 120:
        return 0.28
    else:
        return 0.12   # 120+ days — very hard to hire


def _score_location(candidate: dict, sig: dict) -> float:
    """
    JD: Pune/Noida preferred; Hyderabad, Mumbai, Delhi NCR, Bangalore welcome.
    Outside India: case-by-case, no visa sponsorship.
    """
    location = candidate["profile"].get("location", "").lower()
    country = candidate["profile"].get("country", "").lower()
    will_relocate = sig.get("willing_to_relocate", False)

    in_target_city = any(city in location for city in TARGET_CITIES)
    in_india = country == "india"

    if in_india and in_target_city:
        return 1.00   # already in a target city
    elif in_india and will_relocate:
        return 0.82   # in India, will move to Pune/Noida
    elif in_india:
        return 0.60   # in India, won't relocate — ok but not ideal
    elif will_relocate:
        return 0.40   # outside India, willing to relocate (JD: case-by-case)
    else:
        return 0.10   # outside India, won't relocate — unlikely to work out


def _score_extras(sig: dict, candidate: dict) -> float:
    """
    Bonus signals:
    - GitHub activity (JD cares about "external validation")
    - Saved by recruiters (social proof)
    - Profile completeness (incomplete profile = less serious)
    - Salary range (sanity check — not used to discriminate)
    - Email/phone verified (trust)
    """
    bonus = 0.5  # neutral baseline for extras

    # GitHub — JD mentions "open-source contributions" as nice-to-have
    github = sig.get("github_activity_score", -1)
    if github >= 70:
        bonus += 0.15
    elif github >= 40:
        bonus += 0.08
    elif github >= 10:
        bonus += 0.03
    # -1 means no GitHub linked — neutral, not a negative

    # Saved by recruiters in last 30 days — social proof
    saved = sig.get("saved_by_recruiters_30d", 0)
    if saved >= 5:
        bonus += 0.08
    elif saved >= 2:
        bonus += 0.04

    # Profile completeness — incomplete profiles signal less serious candidates
    completeness = sig.get("profile_completeness_score", 50)
    if completeness >= 85:
        bonus += 0.06
    elif completeness < 40:
        bonus -= 0.08

    # Verified identity — small trust signal
    if sig.get("verified_email") and sig.get("verified_phone"):
        bonus += 0.04

    # LinkedIn connected — another trust signal for an AI engineer
    if sig.get("linkedin_connected"):
        bonus += 0.02

    # Offer acceptance rate — if they keep rejecting offers, they're hard to close
    offer_acceptance = sig.get("offer_acceptance_rate", -1)
    if offer_acceptance >= 0.7:
        bonus += 0.05
    elif 0.0 <= offer_acceptance < 0.3:
        bonus -= 0.05  # serial offer ghoster

    return min(max(bonus, 0.0), 1.0)


def score_signals(candidate: dict) -> float:
    """
    Returns float in [0, 1] representing behavioral availability and
    engagement of this candidate.
    """
    sig = candidate["redrob_signals"]

    recency = _score_recency(sig)
    responsiveness = _score_responsiveness(sig)
    notice = _score_notice_period(sig)
    location = _score_location(candidate, sig)
    extras = _score_extras(sig, candidate)

    w = SIGNAL_WEIGHTS
    final = (
        w["recency"]        * recency +
        w["responsiveness"] * responsiveness +
        w["notice"]         * notice +
        w["location"]       * location +
        w["extras"]         * extras
    )
    return round(min(max(final, 0.0), 1.0), 4)


def get_signal_context(candidate: dict) -> dict:
    """
    Return structured signal context for the reasoning builder.
    """
    sig = candidate["redrob_signals"]
    location = candidate["profile"].get("location", "")
    country = candidate["profile"].get("country", "")

    days_inactive = _days_since(sig.get("last_active_date"))
    in_target = any(city in location.lower() for city in TARGET_CITIES)

    return {
        "days_inactive": days_inactive,
        "open_to_work": sig.get("open_to_work_flag", False),
        "response_rate": sig.get("recruiter_response_rate", 0),
        "notice_days": sig.get("notice_period_days", 60),
        "willing_to_relocate": sig.get("willing_to_relocate", False),
        "country": country,
        "location": location,
        "in_target_city": in_target,
        "github_score": sig.get("github_activity_score", -1),
        "interview_completion": sig.get("interview_completion_rate", 0.5),
        "last_active_date": sig.get("last_active_date", ""),
    }