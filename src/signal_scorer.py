from datetime import date, datetime
from src.jd_config import TARGET_CITIES, SIGNAL_WEIGHTS

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
    """Active recently = likely still looking. Stale profile = might have already joined somewhere."""
    days         = _days_since(sig.get("last_active_date"))
    open_to_work = sig.get("open_to_work_flag", False)

    if   days <= 7:   recency = 1.00
    elif days <= 14:  recency = 0.95
    elif days <= 30:  recency = 0.85
    elif days <= 60:  recency = 0.70
    elif days <= 90:  recency = 0.50
    elif days <= 120: recency = 0.35
    elif days <= 180: recency = 0.20
    else:             recency = 0.08

    # open_to_work is a voluntary signal — bump it
    if open_to_work and days <= 90:
        recency = min(recency + 0.10, 1.0)
    elif open_to_work:
        recency = min(recency + 0.05, 1.0)

    apps_30d      = sig.get("applications_submitted_30d", 0)
    profile_views = sig.get("profile_views_received_30d", 0)

    if apps_30d >= 5:       recency = min(recency + 0.05, 1.0)
    if profile_views >= 10: recency = min(recency + 0.03, 1.0)

    return recency


def _score_responsiveness(sig: dict) -> float:
    """Will they actually reply when we reach out?"""
    response_rate = sig.get("recruiter_response_rate", 0.5)
    avg_time_hrs  = sig.get("avg_response_time_hours", 48)
    interview_cmp = sig.get("interview_completion_rate", 0.5)

    if   response_rate >= 0.80: resp_score = 1.00
    elif response_rate >= 0.60: resp_score = 0.85
    elif response_rate >= 0.40: resp_score = 0.65
    elif response_rate >= 0.20: resp_score = 0.40
    else:                       resp_score = 0.15  # nearly unreachable

    if avg_time_hrs <= 4:  resp_score = min(resp_score + 0.05, 1.0)
    elif avg_time_hrs > 72: resp_score = max(resp_score - 0.05, 0.0)

    # ghosting interviews is a red flag
    if interview_cmp >= 0.85: resp_score = min(resp_score + 0.05, 1.0)
    elif interview_cmp < 0.40: resp_score = max(resp_score - 0.10, 0.0)

    return resp_score


def _score_notice_period(sig: dict) -> float:
    notice = sig.get("notice_period_days", 60)

    if   notice == 0:  return 1.00   # immediate joiner
    elif notice <= 15: return 0.98
    elif notice <= 30: return 0.92   # JD says buyable up to 30 days
    elif notice <= 45: return 0.78
    elif notice <= 60: return 0.65
    elif notice <= 90: return 0.45
    elif notice <= 120: return 0.28
    else:              return 0.12   # 120+ days — hard to move


def _score_location(candidate: dict, sig: dict) -> float:
    location     = candidate["profile"].get("location", "").lower()
    country      = candidate["profile"].get("country", "").lower()
    will_relocate = sig.get("willing_to_relocate", False)

    in_target_city = any(city in location for city in TARGET_CITIES)
    in_india       = country == "india"

    if in_india and in_target_city: return 1.00
    elif in_india and will_relocate: return 0.82
    elif in_india:                   return 0.60
    elif will_relocate:              return 0.40
    else:                            return 0.10  # outside India, won't move


def _score_extras(sig: dict, candidate: dict) -> float:
    bonus = 0.5  # neutral baseline

    github = sig.get("github_activity_score", -1)
    if   github >= 70: bonus += 0.15
    elif github >= 40: bonus += 0.08
    elif github >= 10: bonus += 0.03
    # -1 = no GitHub linked, not a negative

    saved = sig.get("saved_by_recruiters_30d", 0)
    if saved >= 5:  bonus += 0.08
    elif saved >= 2: bonus += 0.04

    completeness = sig.get("profile_completeness_score", 50)
    if   completeness >= 85: bonus += 0.06
    elif completeness < 40:  bonus -= 0.08

    if sig.get("verified_email") and sig.get("verified_phone"):
        bonus += 0.04

    if sig.get("linkedin_connected"):
        bonus += 0.02

    offer_acc = sig.get("offer_acceptance_rate", -1)
    if offer_acc >= 0.7:              bonus += 0.05
    elif 0.0 <= offer_acc < 0.3:     bonus -= 0.05  # serial offer ghoster

    return min(max(bonus, 0.0), 1.0)


def score_signals(candidate: dict) -> float:
    """Returns [0, 1] behavioral availability score."""
    sig = candidate["redrob_signals"]

    recency        = _score_recency(sig)
    responsiveness = _score_responsiveness(sig)
    notice         = _score_notice_period(sig)
    location       = _score_location(candidate, sig)
    extras         = _score_extras(sig, candidate)

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
    """Structured context consumed by reasoning.py."""
    sig      = candidate["redrob_signals"]
    location = candidate["profile"].get("location", "")
    country  = candidate["profile"].get("country", "")

    days_inactive = _days_since(sig.get("last_active_date"))
    in_target     = any(city in location.lower() for city in TARGET_CITIES)

    return {
        "days_inactive":     days_inactive,
        "open_to_work":      sig.get("open_to_work_flag", False),
        "response_rate":     sig.get("recruiter_response_rate", 0),
        "notice_days":       sig.get("notice_period_days", 60),
        "willing_to_relocate": sig.get("willing_to_relocate", False),
        "country":           country,
        "location":          location,
        "in_target_city":    in_target,
        "github_score":      sig.get("github_activity_score", -1),
        "interview_completion": sig.get("interview_completion_rate", 0.5),
        "last_active_date":  sig.get("last_active_date", ""),
    }
