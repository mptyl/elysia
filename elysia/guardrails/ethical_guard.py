"""
Ethical guardrails for Elysia: pre-query check.

Uses DSPy signatures with external XML prompt files for criteria and guidelines.
"""

import os
import time
import logging
from pathlib import Path
from functools import lru_cache

import dspy


# Directory containing the XML prompt files
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Hardcoded fallback ethical principles (from prompt_templates.py)
FALLBACK_ETHICAL_PRINCIPLES = """\
1. DIGNITY: Always treat people as ends, never as means.
2. FREEDOM: Protect freedom of thought, expression, and work-life balance.
3. EQUALITY: Oppose all discrimination and ensure equal dignity for all.
4. SOLIDARITY: Orient every action toward the common good and social responsibility.
5. CITIZENSHIP AND JUSTICE: Act with honesty, transparency, legality, and impartiality.
"""


# --- XML file loading ---


@lru_cache(maxsize=None)
def _load_file(filename: str) -> str:
    """Load a prompt file from the prompts directory. Cached in memory."""
    filepath = PROMPTS_DIR / filename
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_prompt_files() -> dict[str, str]:
    """Load all XML prompt files. Returns a dict keyed by logical name."""
    return {
        "input_filter": _load_file("input_filter.xml"),
        "filter_guidelines": _load_file("filter_guidelines.xml"),
        "pre_query_check": _load_file("pre_query_check.xml"),
    }


def _get_prompt(name: str) -> str:
    """Get a loaded prompt file content, with fallback for missing files."""
    files = load_prompt_files()
    content = files.get(name, "")
    if not content and name in ("input_filter", "filter_guidelines"):
        return FALLBACK_ETHICAL_PRINCIPLES
    return content


# --- DSPy Signatures ---


class PreQueryEthicalCheck(dspy.Signature):
    """Analyze user prompt for ethical violations. Follow the system instruction and filter guidelines strictly.

    IMPORTANT: You are NOT evaluating the topic — a question ABOUT ethics, discrimination,
    or sensitive topics is NOT itself a violation. Only flag requests that ASK the system
    to PERFORM or FACILITATE a violation."""

    user_prompt: str = dspy.InputField(desc="The user's prompt to check")
    conversation_context: str = dspy.InputField(
        desc="Recent conversation history for context"
    )
    ethical_filter: str = dspy.InputField(
        desc="The ethical filter criteria (XML) to check against"
    )
    filter_guidelines: str = dspy.InputField(
        desc="Guidelines for how to apply the filter"
    )

    is_violation: bool = dspy.OutputField(
        desc="True if the prompt violates the ethical code, False otherwise"
    )
    violated_category: str = dspy.OutputField(
        desc="The name of the violated category, or 'None' if no violation"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation of why this is or is not a violation"
    )



# --- Core guard functions ---


async def run_pre_query_check(
    prompt: str,
    history: list[dict],
    base_lm: dspy.LM,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
) -> tuple[bool, str, str]:
    """
    Run the pre-query ethical guard check.

    Returns:
        (is_violation, violated_category, reasoning)
    """
    start_time = time.time()

    try:
        # Build conversation context from last 6 messages
        recent_history = history[-6:] if len(history) > 6 else history
        conversation_context = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in recent_history
        )

        ethical_filter = _get_prompt("input_filter")
        filter_guidelines = _get_prompt("filter_guidelines")

        with dspy.context(lm=base_lm):
            result = dspy.Predict(PreQueryEthicalCheck)(
                user_prompt=prompt,
                conversation_context=conversation_context,
                ethical_filter=ethical_filter,
                filter_guidelines=filter_guidelines,
            )

        is_violation = result.is_violation
        violated_category = result.violated_category if is_violation else "None"
        reasoning = result.reasoning

    except Exception as e:
        # Fail open: allow the query if the guard fails
        if logger:
            logger.error(f"[ETHICAL-GUARD] PRE-QUERY check failed: {e}")
        return False, "None", ""

    detection_time_ms = int((time.time() - start_time) * 1000)

    if ethical_guard_log and logger:
        logger.info(
            f"[ETHICAL-GUARD] PRE-QUERY: activated=True, detection_time_ms={detection_time_ms}"
        )
        if is_violation:
            logger.info(
                f'[ETHICAL-GUARD] PRE-QUERY: violation=True, category="{violated_category}", '
                f'reasoning="{reasoning}"'
            )
        else:
            logger.info("[ETHICAL-GUARD] PRE-QUERY: violation=False")

    return is_violation, violated_category, reasoning
