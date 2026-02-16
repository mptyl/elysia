"""
Ethical guardrails for Elysia: pre-query and post-response checks.

Uses DSPy signatures with external XML prompt files for criteria and guidelines.
When a violation is detected, performs RAG escalation against UNIInternalDocs
to generate a refusal with normative citations.
"""

import os
import time
import logging
from pathlib import Path
from functools import lru_cache

import dspy

from elysia.util.client import ClientManager
from elysia.util.embedding import embed_query

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

RAG_COLLECTION_NAME = "UNIInternalDocs"


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
        "output_filter": _load_file("output_filter.xml"),
        "filter_guidelines": _load_file("filter_guidelines.xml"),
        "pre_query_check": _load_file("pre_query_check.xml"),
        "post_response_check": _load_file("post_response_check.xml"),
        "refusal_generator": _load_file("refusal_generator.xml"),
    }


def _get_prompt(name: str) -> str:
    """Get a loaded prompt file content, with fallback for missing files."""
    files = load_prompt_files()
    content = files.get(name, "")
    if not content and name in ("input_filter", "output_filter", "filter_guidelines"):
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


class PostResponseEthicalCheck(dspy.Signature):
    """Analyze AI-generated response for ethical violations. Determine if the response
    CONTAINS content that violates the ethical code, regardless of the user's original intent."""

    response_text: str = dspy.InputField(desc="The AI-generated response to check")
    user_prompt: str = dspy.InputField(desc="The user's original prompt for context")
    ethical_filter: str = dspy.InputField(
        desc="The ethical filter criteria (XML) to check against"
    )
    filter_guidelines: str = dspy.InputField(
        desc="Guidelines for how to apply the filter"
    )

    is_violation: bool = dspy.OutputField(
        desc="True if the response violates the ethical code, False otherwise"
    )
    violated_category: str = dspy.OutputField(
        desc="The name of the violated category, or 'None' if no violation"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation of why this is or is not a violation"
    )


class EthicalRefusalGenerator(dspy.Signature):
    """Generate a clear, respectful refusal message explaining why the request cannot be fulfilled.

    MANDATORY RULES:
    1. Respond in the SAME LANGUAGE as the user's prompt (e.g. Italian if the user wrote in Italian).
    2. You MUST quote the EXACT passages from the RAG context documents that are relevant to the violation.
       Format each citation as: "«quoted text»" (Nome Documento, sezione N).
       Include at least one direct quote if RAG context is available.
    3. Clearly state WHICH specific article, principle, or rule from the normative documents is violated.
    4. Explain WHY the user's request conflicts with that specific principle.
    5. Do NOT be preachy or condescending. Be factual, precise, and constructive.
    6. Suggest alternative ways the user could rephrase their request if applicable.
    7. Structure the refusal as:
       - Brief statement that the request cannot be fulfilled
       - The specific violated principle with direct quote from the document
       - Why this applies to the user's request
       - (Optional) Suggestion for rephrasing"""

    user_prompt: str = dspy.InputField(desc="The user's original prompt")
    violated_category: str = dspy.InputField(
        desc="The ethical category that was violated"
    )
    guard_reasoning: str = dspy.InputField(
        desc="The reasoning from the ethical guard check"
    )
    rag_context: str = dspy.InputField(
        desc="Passages retrieved from normative PDF documents (filename and content). "
        "You MUST cite these directly with exact quotes."
    )

    refusal_message: str = dspy.OutputField(
        desc="The refusal message in the user's language. MUST include direct quotes "
        "from the RAG context documents with source attribution (document name, section)."
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


async def run_post_response_check(
    response: str,
    prompt: str,
    base_lm: dspy.LM,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
) -> tuple[bool, str, str]:
    """
    Run the post-response ethical guard check.

    Returns:
        (is_violation, violated_category, reasoning)
    """
    start_time = time.time()

    try:
        ethical_filter = _get_prompt("output_filter")
        filter_guidelines = _get_prompt("filter_guidelines")

        with dspy.context(lm=base_lm):
            result = dspy.Predict(PostResponseEthicalCheck)(
                response_text=response,
                user_prompt=prompt,
                ethical_filter=ethical_filter,
                filter_guidelines=filter_guidelines,
            )

        is_violation = result.is_violation
        violated_category = result.violated_category if is_violation else "None"
        reasoning = result.reasoning

    except Exception as e:
        # Fail open
        if logger:
            logger.error(f"[ETHICAL-GUARD] POST-RESPONSE check failed: {e}")
        return False, "None", ""

    detection_time_ms = int((time.time() - start_time) * 1000)

    if ethical_guard_log and logger:
        logger.info(
            f"[ETHICAL-GUARD] POST-RESPONSE: activated=True, detection_time_ms={detection_time_ms}"
        )
        if is_violation:
            logger.info(
                f'[ETHICAL-GUARD] POST-RESPONSE: violation=True, category="{violated_category}", '
                f'reasoning="{reasoning}"'
            )
        else:
            logger.info("[ETHICAL-GUARD] POST-RESPONSE: violation=False")

    return is_violation, violated_category, reasoning


async def generate_ethical_refusal(
    prompt: str,
    category: str,
    reasoning: str,
    base_lm: dspy.LM,
    client_manager: ClientManager | None = None,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
) -> str:
    """
    Generate an ethical refusal message, optionally enriched with RAG context
    from the UNIInternalDocs Weaviate collection.

    Returns:
        The refusal message string.
    """
    rag_context = ""

    # RAG escalation: query UNIInternalDocs for normative context
    if client_manager is not None and client_manager.is_client:
        rag_start = time.time()
        try:
            async with client_manager.connect_to_async_client() as client:
                if await client.collections.exists(RAG_COLLECTION_NAME):
                    collection = client.collections.get(RAG_COLLECTION_NAME)
                    # Include user prompt for better keyword matching
                    # (documents are often in Italian, categories in English)
                    rag_query = f"{category} {reasoning} {prompt}"
                    try:
                        query_vector = embed_query(rag_query)
                        results = await collection.query.hybrid(
                            query=rag_query,
                            vector=query_vector,
                            limit=5,
                            alpha=0.5,
                        )
                    except Exception:
                        results = await collection.query.bm25(
                            query=rag_query,
                            limit=5,
                        )
                    if results.objects:
                        context_parts = []
                        for obj in results.objects:
                            props = obj.properties
                            filename = props.get("filename", "documento sconosciuto")
                            content = props.get("content", "")
                            chunk_id = props.get("chunk_id", "")
                            if content:
                                entry = (
                                    f"[Documento: {filename}, sezione {chunk_id}]\n"
                                    f"{content}"
                                )
                                context_parts.append(entry)
                        rag_context = "\n\n---\n\n".join(context_parts)
        except Exception as e:
            if logger:
                logger.warning(
                    f"[ETHICAL-GUARD] RAG-ESCALATION failed: {e}"
                )

        rag_time_ms = int((time.time() - rag_start) * 1000)
        if ethical_guard_log and logger:
            logger.info(
                f"[ETHICAL-GUARD] RAG-ESCALATION: rag_time_ms={rag_time_ms}, "
                f"documents_retrieved={len(rag_context.split('---')) if rag_context else 0}"
            )

    # Generate the refusal message
    try:
        with dspy.context(lm=base_lm):
            result = dspy.Predict(EthicalRefusalGenerator)(
                user_prompt=prompt,
                violated_category=category,
                guard_reasoning=reasoning,
                rag_context=rag_context if rag_context else "No normative documents available.",
            )
        refusal = result.refusal_message
    except Exception as e:
        if logger:
            logger.error(f"[ETHICAL-GUARD] Refusal generation failed: {e}")
        # Generic fallback refusal (bilingual)
        refusal = (
            "Questa richiesta non può essere soddisfatta in quanto in conflitto con le linee guida etiche dell'organizzazione. "
            "Si prega di riformulare la richiesta nel rispetto dei principi di dignità, uguaglianza, onestà e rispetto. / "
            "This request cannot be fulfilled as it conflicts with our ethical guidelines. "
            "Please rephrase your request in a way that aligns with principles of dignity, "
            "equality, honesty, and respect."
        )

    if ethical_guard_log and logger:
        logger.info("[ETHICAL-GUARD] REFUSAL: sent to user")

    return refusal
