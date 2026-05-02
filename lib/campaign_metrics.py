"""
Pure computation helpers for campaign performance report generation.
No external dependencies — all logic is deterministic and testable.
"""

from typing import Dict, List, Any, Literal


# Dispositions categorised by engagement quality
_LOW_ENGAGEMENT = {"dead call", "unknown", "voicemail"}
_GOOD_ENGAGEMENT = {"decision maker – nyi", "dnc – decision maker", "dnc – unknown", "wrong number"}


def calculate_issue_ratios(rows: List[Dict[str, Any]], total: int) -> Dict[str, float]:
    """Return per-issue percentages (0–100) based on detection flags."""
    if total == 0:
        return {"releasing_pct": 0.0, "late_hello_pct": 0.0, "no_rebuttal_pct": 0.0}

    releasing = sum(1 for r in rows if str(r.get("Releasing Detection", "")).strip() == "Yes")
    late_hello = sum(1 for r in rows if str(r.get("Late Hello Detection", "")).strip() == "Yes")
    no_rebuttal = sum(1 for r in rows if str(r.get("Rebuttal Detection", "")).strip() == "No")

    return {
        "releasing_pct": round(releasing / total * 100, 1),
        "late_hello_pct": round(late_hello / total * 100, 1),
        "no_rebuttal_pct": round(no_rebuttal / total * 100, 1),
        "releasing_count": releasing,
        "late_hello_count": late_hello,
        "no_rebuttal_count": no_rebuttal,
    }


def classify_issue_rating(pct: float) -> Literal["Low", "Medium", "High"]:
    """Map a percentage to a named severity tier."""
    if pct < 30:
        return "Low"
    if pct <= 50:
        return "Medium"
    return "High"


def feedback_from_rating(rating: str) -> Literal["Yes", "No"]:
    """Low → No issue; Medium/High → Yes, there is an issue."""
    return "No" if rating == "Low" else "Yes"


def categorize_engagement(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Split dispositions into low-engagement vs good-engagement buckets.
    Returns counts, a human-readable summary string, and a Yes/No flag.
    Low-engagement dominates (>50% of total) → campaign_list_issue = Yes.
    """
    low: Dict[str, int] = {}
    good: Dict[str, int] = {}
    total = len(rows)

    for r in rows:
        disp = str(r.get("Disposition", "")).strip().lower()
        if any(d in disp for d in _LOW_ENGAGEMENT):
            bucket_key = disp.title()
            low[bucket_key] = low.get(bucket_key, 0) + 1
        elif any(d in disp for d in _GOOD_ENGAGEMENT):
            bucket_key = disp.title()
            good[bucket_key] = good.get(bucket_key, 0) + 1

    low_total = sum(low.values())
    good_total = sum(good.values())
    campaign_list_issue = "Yes" if total > 0 and (low_total / total) > 0.5 else "No"

    lines = [f"Low Engagement ({low_total} calls):"]
    for name, count in sorted(low.items()):
        lines.append(f"  • {name}: {count}")
    lines.append(f"Good Engagement ({good_total} calls):")
    for name, count in sorted(good.items()):
        lines.append(f"  • {name}: {count}")

    return {
        "campaign_list_issue": campaign_list_issue,
        "low_engagement": low,
        "good_engagement": good,
        "low_total": low_total,
        "good_total": good_total,
        "summary": "\n".join(lines),
    }


def build_doc_field_mapping(
    rows: List[Dict[str, Any]],
    campaign_name: str,
    sheet_url: str,
    start_date: str = "",
    end_date: str = "",
) -> Dict[str, str]:
    """
    Produce the full {{placeholder}} → value mapping for the Doc template.
    Subjective fields with no data backing are left as 'N/A'.
    """
    total = len(rows)
    ratios = calculate_issue_ratios(rows, total)
    engagement = categorize_engagement(rows)

    releasing_rating = classify_issue_rating(ratios["releasing_pct"])
    late_hello_rating = classify_issue_rating(ratios["late_hello_pct"])
    no_rebuttal_rating = classify_issue_rating(ratios["no_rebuttal_pct"])

    releasing_feedback = feedback_from_rating(releasing_rating)
    late_hello_feedback = feedback_from_rating(late_hello_rating)
    no_rebuttal_feedback = feedback_from_rating(no_rebuttal_rating)

    # Agents need coaching when any issue is Medium or High
    coaching_feedback = "Yes" if any(
        r in ("Medium", "High")
        for r in (releasing_rating, late_hello_rating, no_rebuttal_rating)
    ) else "No"

    dialer = rows[0].get("Dialer Name", "") if rows else ""

    return {
        "{{campaign_name}}": campaign_name,
        "{{dialer}}": str(dialer),
        "{{date_from}}": start_date,
        "{{date_to}}": end_date,
        "{{effort_feedback}}": "N/A",
        "{{rebuttals_feedback}}": no_rebuttal_feedback,
        "{{releasing_feedback}}": releasing_feedback,
        "{{late_hello_feedback}}": late_hello_feedback,
        "{{tonality_feedback}}": "N/A",
        "{{rebuttals_rating}}": no_rebuttal_rating,
        "{{releasing_rating}}": releasing_rating,
        "{{late_hello_rating}}": late_hello_rating,
        "{{coaching_feedback}}": coaching_feedback,
        "{{allocation_feedback}}": "N/A",
        "{{campaign_list_issue}}": engagement["campaign_list_issue"],
        "{{campaign_list_summary}}": engagement["summary"],
        "{{releasing_count}}": str(ratios["releasing_count"]),
        "{{late_hello_count}}": str(ratios["late_hello_count"]),
        "{{no_rebuttal_count}}": str(ratios["no_rebuttal_count"]),
        "{{sheet_url}}": sheet_url,
    }
