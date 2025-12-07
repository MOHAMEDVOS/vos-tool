import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    # Optional local LLM backend (user must install llama-cpp-python and provide a model file)
    from llama_cpp import Llama  # type: ignore
    _LLM_AVAILABLE = True
except Exception as e:  # pragma: no cover - safe fallback if dependency is missing
    logger.warning(f"Local LLM backend not available: {e}")
    Llama = None  # type: ignore
    _LLM_AVAILABLE = False


_llm_instance: Optional["Llama"] = None


def _get_llm() -> Optional["Llama"]:
    """Lazy-initialize and return a shared Llama instance.

    The user is expected to place a quantized model file locally and, optionally,
    configure its path via the VOS_AI_MODEL_PATH environment variable.
    """
    global _llm_instance

    if not _LLM_AVAILABLE:
        return None

    if _llm_instance is not None:
        return _llm_instance

    import os

    # Allow overriding model path via environment variable
    model_path = os.getenv("VOS_AI_MODEL_PATH")
    if not model_path:
        # Default relative path under the project root; user can adjust as needed
        model_path = os.path.join("models", "local-campaign-model.gguf")

    try:
        _llm_instance = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=max(1, os.cpu_count() or 1),
        )
        logger.info(f"Initialized local LLM from: {model_path}")
        return _llm_instance
    except Exception as e:  # pragma: no cover - runtime environment dependent
        logger.warning(f"Failed to initialize local LLM at '{model_path}': {e}")
        _llm_instance = None
        return None


def _build_prompt(campaign_metrics: Dict[str, Any]) -> str:
    """Build a focused prompt for a short, direct campaign summary."""
    metrics_json = json.dumps(campaign_metrics, ensure_ascii=False, indent=2)

    prompt = (
        "You are an experienced call-center performance coach. "
        "You receive aggregated audit metrics for a single dialing campaign. "
        "Use ONLY this JSON data to understand the overall performance of the campaign.\n\n"
        f"CAMPAIGN_METRICS_JSON:\n{metrics_json}\n\n"
        "Write a short, clear summary for a team lead. Use simple business English and keep it very direct.\n\n"
        "Output requirements (markdown):\n"
        "- Start with a heading 'Summary'.\n"
        "- Under it, write 2 or 3 short paragraphs (no bullet points, no numbered lists).\n"
        "- Paragraph 1: Describe the campaign size (calls and agents) and overall behavior pattern, including missed rebuttal rate and the share of clean calls.\n"
        "- Paragraph 2: Briefly contrast stronger vs weaker agent behavior (for example, consistent script use vs skipped rebuttals / early endings).\n"
        "- Paragraph 3 (optional): One concise statement about overall risk and what coaching or process focus will help.\n"
        "- Do NOT mention JSON or field names.\n"
        "- Do NOT mention that you are an AI.\n"
        "- Do NOT use bullet points, tables, or extra headings beyond 'Summary'.\n"
    )

    return prompt


def _fallback_summary(campaign_metrics: Dict[str, Any]) -> str:
    """Deterministic short summary if no local LLM is available.

    This keeps the app working even before the user sets up a model, using
    the same "Summary" style as the LLM output.
    """
    total_calls = campaign_metrics.get("total_calls", 0)
    agents = campaign_metrics.get("agents_audited", 0)
    behavioral = campaign_metrics.get("behavioral_metrics", {}) or {}

    campaign_name = campaign_metrics.get("campaign_name") or "this campaign"

    skipped_ratio = behavioral.get("rebuttal_not_attempted_ratio", 0.0)
    releasing_detected = behavioral.get("releasing_detected", 0)
    late_hello_detected = behavioral.get("late_hello_detected", 0)

    total_calls_safe = max(total_calls, 1)
    release_rate = releasing_detected / total_calls_safe
    late_hello_rate = late_hello_detected / total_calls_safe

    # Simple approximation of "clean" calls: calls without obvious detected issues
    clean_calls_rate = max(0.0, 1.0 - max(skipped_ratio, release_rate, late_hello_rate))

    lines: list[str] = []

    # Heading
    lines.append("Summary")
    lines.append("")

    # Paragraph 1 – size and key behavior signals
    missed_pct = skipped_ratio * 100.0
    clean_pct = clean_calls_rate * 100.0
    lines.append(
        f"The {campaign_name} campaign had {total_calls} reviewed calls across {agents} agents. "
        f"Missed rebuttals were common at about {missed_pct:.0f}% of calls. "
        f"Around {clean_pct:.0f}% of calls were generally clean, while the rest showed weaker objection handling or rushed flow."
    )
    lines.append("")

    # Paragraph 2 – contrast stronger vs weaker behavior
    lines.append(
        "Top-performing agents kept their behaviour more consistent and followed the script smoothly. "
        "Lower performers were more likely to skip rebuttals, allow late greetings, or end calls early, "
        "creating clear quality gaps across the team."
    )
    lines.append("")

    # Paragraph 3 – overall risk and coaching focus
    lines.append(
        "Overall, the campaign shows avoidable performance risks. Coaching should focus on stronger rebuttal use, "
        "steady greeting habits, and better pacing. A small weekly sample of calls and light script adjustments "
        "will help stabilise quality across the group."
    )

    return "\n".join(lines)


def generate_ai_campaign_summary(campaign_metrics: Dict[str, Any]) -> str:
    """Generate an overall campaign performance summary.

    If a local LLM is available and initialized, it is used. Otherwise a
    deterministic fallback summary is returned.
    """
    try:
        llm = _get_llm()
        if llm is None:
            return _fallback_summary(campaign_metrics)

        prompt = _build_prompt(campaign_metrics)

        # llama_cpp-python supports calling the instance directly to generate text
        result = llm(
            prompt,
            max_tokens=640,
            temperature=0.7,
            top_p=0.9,
            stop=["\n#", "\n###"],
        )

        text = ""
        try:
            # Newer llama-cpp-python returns a dict-like response
            choices = result.get("choices") or []  # type: ignore[assignment]
            if choices:
                text = choices[0].get("text", "")
        except Exception:
            # Fallback: attempt to treat result as a simple string
            text = str(result)

        text = (text or "").strip()
        if not text:
            return _fallback_summary(campaign_metrics)

        return text
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error generating AI campaign summary, using fallback: {e}")
        return _fallback_summary(campaign_metrics)


def generate_ai_issue_notes(campaign_metrics: Dict[str, Any], issue_table: Dict[str, Any]) -> Dict[str, str]:
    """Generate per-issue "Action needed / Notes" using the local LLM.

    Only issues with feedback == "Yes" are sent to the model. The function
    returns a mapping of issue key -> note string. If the model is not
    available or something fails, an empty dict is returned and existing
    notes should be kept as-is by the caller.
    """
    try:
        # Collect only active issues to keep the prompt focused
        active_issues: Dict[str, Dict[str, Any]] = {}
        for key, row in (issue_table or {}).items():
            if str(row.get("feedback", "")).strip() == "Yes":
                active_issues[key] = {
                    "label": row.get("label", key),
                    "rating": row.get("rating", "N/A"),
                }

        if not active_issues:
            return {}

        llm = _get_llm()
        if llm is None:
            return {}

        metrics_json = json.dumps(campaign_metrics, ensure_ascii=False, indent=2)
        issues_json = json.dumps(active_issues, ensure_ascii=False, indent=2)

        prompt = (
            "You are a call-center performance coach. You see aggregated metrics for a campaign "
            "and a list of issues that were flagged as 'Yes'. For each issue, write one or two "
            "short sentences that describe the most important action needed or coaching note. "
            "Use clear, simple business English.\n\n"
            "CAMPAIGN_METRICS_JSON:\n" + metrics_json + "\n\n"
            "ACTIVE_ISSUES_JSON:\n" + issues_json + "\n\n"
            "Return ONLY a JSON object with this exact shape (no extra text, no markdown):\n"
            "{\n  \"issue_key\": \"short action note\",\n  ...\n}\n"
            "Use the same issue keys that appear in ACTIVE_ISSUES_JSON."
        )

        result = llm(
            prompt,
            max_tokens=512,
            temperature=0.5,
            top_p=0.9,
        )

        text = ""
        try:
            choices = result.get("choices") or []  # type: ignore[assignment]
            if choices:
                text = choices[0].get("text", "")
        except Exception:
            text = str(result)

        text = (text or "").strip()
        if not text:
            return {}

        # Best-effort clean-up: strip markdown fences if present
        if text.startswith("```"):
            # Remove first fence
            text = text.split("```", 2)
            if len(text) == 3:
                text = text[1] if "{" in text[1] else text[2]
        text = text.strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Ensure all values are strings
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception as e:
            logger.warning(f"Failed to parse AI issue notes JSON: {e}")

        return {}
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error generating AI issue notes: {e}")
        return {}
