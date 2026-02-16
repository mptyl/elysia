"""
Ethical guardrails for Elysia: pre-query check.

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
    """Analyze user prompt for ethical violations or guidance needs.
    Follow the system instruction and filter guidelines strictly.

    Three possible outcomes:
    - is_violation=True: the user asks the system to PERFORM or FACILITATE a violation
    - requires_guidance=True (and is_violation=False): the user investigates the feasibility,
      opportunity, or consequences of an ethically sensitive action
    - Both False: no ethical relevance"""

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
        desc="True if the prompt asks the system to perform or facilitate a violation"
    )
    requires_guidance: bool = dspy.OutputField(
        desc="True if the prompt investigates feasibility/opportunity/consequences of an ethically sensitive action (and is_violation is False)"
    )
    violated_category: str = dspy.OutputField(
        desc="The name of the relevant ethical category, or 'None' if neither violation nor guidance"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation of the classification decision"
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


class EthicalGuidanceGenerator(dspy.Signature):
    """Generate a helpful, informative guidance message about what the organization's
    normative documents say regarding the user's question.

    MANDATORY RULES:
    1. Respond in the SAME LANGUAGE as the user's prompt.
    2. You MUST quote EXACT passages from the RAG context documents that are relevant.
       Format each citation as: "«quoted text»" (Nome Documento, sezione N).
    3. Be helpful and informative, NOT punitive or preachy.
    4. Explain what the normative documents say about the topic.
    5. If the documents allow the action under certain conditions, explain those conditions.
    6. If the documents prohibit the action, explain why clearly.
    7. Structure the guidance as:
       - Acknowledge the user's question
       - Present what the normative documents say, with direct quotes
       - Summarize the key takeaway or recommendation"""

    user_prompt: str = dspy.InputField(desc="The user's original prompt")
    relevant_category: str = dspy.InputField(
        desc="The ethical category relevant to the question"
    )
    guard_reasoning: str = dspy.InputField(
        desc="The reasoning from the ethical guard check"
    )
    rag_context: str = dspy.InputField(
        desc="Passages retrieved from normative PDF documents (filename and content). "
        "You MUST cite these directly with exact quotes."
    )

    guidance_message: str = dspy.OutputField(
        desc="The guidance message in the user's language. MUST include direct quotes "
        "from the RAG context documents with source attribution."
    )


# --- RAG helper ---


async def _retrieve_normative_context(
    prompt: str,
    category: str,
    reasoning: str,
    client_manager,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
    log_label: str = "RAG",
) -> str:
    """
    Query UNIInternalDocs Weaviate collection for normative context.
    Shared by both refusal and guidance generators.

    Returns:
        Formatted RAG context string, or empty string if unavailable.
    """
    if client_manager is None or not client_manager.is_client:
        return ""

    rag_context = ""
    rag_start = time.time()
    try:
        async with client_manager.connect_to_async_client() as client:
            if await client.collections.exists(RAG_COLLECTION_NAME):
                collection = client.collections.get(RAG_COLLECTION_NAME)
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
            logger.warning(f"[ETHICAL-GUARD] {log_label} failed: {e}")

    rag_time_ms = int((time.time() - rag_start) * 1000)
    if ethical_guard_log and logger:
        logger.info(
            f"[ETHICAL-GUARD] {log_label}: rag_time_ms={rag_time_ms}, "
            f"documents_retrieved={len(rag_context.split('---')) if rag_context else 0}"
        )

    return rag_context


# --- Core guard functions ---


async def run_pre_query_check(
    prompt: str,
    history: list[dict],
    base_lm: dspy.LM,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
) -> tuple[bool, bool, str, str]:
    """
    Run the pre-query ethical guard check.

    Returns:
        (is_violation, requires_guidance, violated_category, reasoning)
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
        requires_guidance = result.requires_guidance if not is_violation else False
        violated_category = (
            result.violated_category
            if is_violation or requires_guidance
            else "None"
        )
        reasoning = result.reasoning

    except Exception as e:
        # Fail open: allow the query if the guard fails
        if logger:
            logger.error(f"[ETHICAL-GUARD] PRE-QUERY check failed: {e}")
        return False, False, "None", ""

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
        elif requires_guidance:
            logger.info(
                f'[ETHICAL-GUARD] PRE-QUERY: guidance=True, category="{violated_category}", '
                f'reasoning="{reasoning}"'
            )
        else:
            logger.info("[ETHICAL-GUARD] PRE-QUERY: violation=False, guidance=False")

    return is_violation, requires_guidance, violated_category, reasoning


async def generate_ethical_refusal(
    prompt: str,
    category: str,
    reasoning: str,
    base_lm: dspy.LM,
    client_manager=None,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
) -> str:
    """
    Generate an ethical refusal message, optionally enriched with RAG context
    from the UNIInternalDocs Weaviate collection.

    Returns:
        The refusal message string.
    """
    rag_context = await _retrieve_normative_context(
        prompt, category, reasoning, client_manager,
        logger=logger, ethical_guard_log=ethical_guard_log,
        log_label="RAG-ESCALATION",
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
        refusal_text = result.refusal_message
    except Exception as e:
        if logger:
            logger.error(f"[ETHICAL-GUARD] Refusal generation failed: {e}")
        refusal_text = (
            "Questa richiesta non può essere soddisfatta in quanto in conflitto con le linee guida etiche dell'organizzazione. "
            "Si prega di riformulare la richiesta nel rispetto dei principi di dignità, uguaglianza, onestà e rispetto. / "
            "This request cannot be fulfilled as it conflicts with our ethical guidelines. "
            "Please rephrase your request in a way that aligns with principles of dignity, "
            "equality, honesty, and respect."
        )

    if ethical_guard_log and logger:
        logger.info("[ETHICAL-GUARD] REFUSAL: sent to user")

    return refusal_text


async def generate_ethical_guidance(
    prompt: str,
    category: str,
    reasoning: str,
    base_lm: dspy.LM,
    client_manager=None,
    logger: logging.Logger | None = None,
    ethical_guard_log: bool = False,
) -> str:
    """
    Generate an ethical guidance message, enriched with RAG context
    from the UNIInternalDocs Weaviate collection.

    Returns:
        The guidance message string.
    """
    rag_context = await _retrieve_normative_context(
        prompt, category, reasoning, client_manager,
        logger=logger, ethical_guard_log=ethical_guard_log,
        log_label="RAG-GUIDANCE",
    )

    # Generate the guidance message
    try:
        with dspy.context(lm=base_lm):
            result = dspy.Predict(EthicalGuidanceGenerator)(
                user_prompt=prompt,
                relevant_category=category,
                guard_reasoning=reasoning,
                rag_context=rag_context if rag_context else "No normative documents available.",
            )
        guidance_text = result.guidance_message
    except Exception as e:
        if logger:
            logger.error(f"[ETHICAL-GUARD] Guidance generation failed: {e}")
        guidance_text = (
            "La tua domanda tocca un'area regolata dalle linee guida etiche dell'organizzazione. "
            "Ti consiglio di consultare la Carta Etica e il Codice di Condotta per informazioni specifiche. / "
            "Your question touches an area covered by the organization's ethical guidelines. "
            "Please consult the Ethics Charter and Code of Conduct for specific information."
        )

    if ethical_guard_log and logger:
        logger.info("[ETHICAL-GUARD] GUIDANCE: sent to user")

    return guidance_text
