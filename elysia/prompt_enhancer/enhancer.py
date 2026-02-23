"""
Prompt Enhancer for Elysia: iterative prompt improvement.

Uses DSPy signatures with external XML prompt files for enhancement guidelines
and validation criteria. Supports two operations:
- enhance_prompt: first iteration, transforms a raw prompt into an enhanced version
- refine_prompt: subsequent iterations, validates user suggestion then applies refinement
"""

import logging
from pathlib import Path
from functools import lru_cache

import dspy

# Directory containing the XML prompt files
PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = logging.getLogger(__name__)


# --- XML file loading ---


@lru_cache(maxsize=None)
def _load_file(filename: str) -> str:
    """Load a prompt file from the prompts directory. Cached in memory."""
    filepath = PROMPTS_DIR / filename
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _get_prompt(name: str) -> str:
    """Get a loaded prompt file content by logical name."""
    return _load_file(f"{name}.xml")


# --- DSPy Signatures ---


class PromptEnhancerSignature(dspy.Signature):
    """You are an expert prompt engineer. Transform the user's raw prompt into a well-structured, effective prompt following the enhancement guidelines. Return ONLY the improved prompt text, no explanations or meta-commentary. Respond in the SAME LANGUAGE as the user's prompt."""

    raw_prompt: str = dspy.InputField(
        desc="The user's original prompt to enhance"
    )
    enhancement_guidelines: str = dspy.InputField(
        desc="XML guidelines for prompt enhancement best practices"
    )

    enhanced_prompt: str = dspy.OutputField(
        desc="The improved, well-structured prompt. Must be in the same language as the raw_prompt. Contains ONLY the enhanced prompt text, no explanations."
    )


class PromptRefinementSignature(dspy.Signature):
    """You are an expert prompt engineer. First, validate whether the user's suggestion is a valid, actionable refinement request using the validation criteria. If valid, apply the suggestion to refine the current prompt following the enhancement guidelines. If invalid, provide helpful feedback. Respond in the SAME LANGUAGE as the user's input."""

    current_prompt: str = dspy.InputField(
        desc="The current version of the prompt to refine"
    )
    user_suggestion: str = dspy.InputField(
        desc="The user's suggestion for how to improve the prompt"
    )
    enhancement_guidelines: str = dspy.InputField(
        desc="XML guidelines for prompt enhancement best practices"
    )
    validation_criteria: str = dspy.InputField(
        desc="XML criteria for validating whether the suggestion is actionable"
    )

    is_valid_suggestion: bool = dspy.OutputField(
        desc="True if the suggestion is a valid, actionable refinement request"
    )
    enhanced_prompt: str = dspy.OutputField(
        desc="The refined prompt if suggestion is valid, empty string if invalid"
    )
    feedback: str = dspy.OutputField(
        desc="Helpful feedback if suggestion is invalid, empty string if valid. Must be in the same language as user_suggestion."
    )


# --- Core functions ---


async def enhance_prompt(raw_prompt: str, lm: dspy.LM) -> dict:
    """First iteration: transform raw prompt into enhanced version."""
    enhancement_guidelines = _get_prompt("enhancement_system")

    try:
        with dspy.context(lm=lm):
            result = dspy.Predict(PromptEnhancerSignature)(
                raw_prompt=raw_prompt,
                enhancement_guidelines=enhancement_guidelines,
            )
        return {"enhanced_prompt": result.enhanced_prompt, "feedback": "", "error": ""}
    except Exception as e:
        logger.exception("Error in enhance_prompt")
        return {"enhanced_prompt": "", "feedback": "", "error": str(e)}


async def refine_prompt(current_prompt: str, suggestion: str, lm: dspy.LM) -> dict:
    """Subsequent iterations: validate suggestion then refine."""
    enhancement_guidelines = _get_prompt("enhancement_system")
    validation_criteria = _get_prompt("validation_criteria")

    try:
        with dspy.context(lm=lm):
            result = dspy.Predict(PromptRefinementSignature)(
                current_prompt=current_prompt,
                user_suggestion=suggestion,
                enhancement_guidelines=enhancement_guidelines,
                validation_criteria=validation_criteria,
            )
        if result.is_valid_suggestion:
            return {"enhanced_prompt": result.enhanced_prompt, "feedback": "", "error": ""}
        else:
            return {"enhanced_prompt": "", "feedback": result.feedback, "error": ""}
    except Exception as e:
        logger.exception("Error in refine_prompt")
        return {"enhanced_prompt": "", "feedback": "", "error": str(e)}
