# Ethical Guidance Filter (3-way guard) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the ethical guardrail from binary (pass/block) to ternary (pass/guide/block) so investigative questions about ethically sensitive topics trigger a normative guidance response via RAG on UNIInternalDocs.

**Architecture:** The `PreQueryEthicalCheck` DSPy signature gains a new output field `requires_guidance` (bool). When `requires_guidance=True` and `is_violation=False`, the system bypasses normal tree execution and generates a guidance response from UNIInternalDocs RAG. The guidance generator is a new DSPy signature `EthicalGuidanceGenerator` with a helpful, non-punitive tone.

**Tech Stack:** Python 3.12, DSPy, FastAPI (existing), Weaviate client (existing RAG pattern from `generate_ethical_refusal`)

---

### Task 1: Update XML prompts for 3-way detection

**Files:**
- Modify: `elysia/guardrails/prompts/pre_query_check.xml`
- Modify: `elysia/guardrails/prompts/filter_guidelines.xml`
- Modify: `elysia/guardrails/prompts/input_filter.xml`

**Step 1: Update `pre_query_check.xml`**

Replace content with:

```xml
<ethical-guard-prompt type="pre-query">
  <system-instruction>
    You are an ethical compliance filter. Analyze the user's prompt against the provided
    ethical filter criteria. Follow the filter guidelines strictly.

    Your task is to determine:
    1. If the user's prompt explicitly or implicitly requests the system to PERFORM or
       FACILITATE an ethical violation → set is_violation=True.
    2. If the user's prompt INVESTIGATES the possibility, opportunity, convenience, or
       consequences of an action that touches an ethical area covered by the filter
       → set requires_guidance=True (and is_violation=False).
    3. If the prompt has no ethical relevance → set both to False.

    INVESTIGATIVE PATTERNS to detect for guidance (requires_guidance=True):
    - Feasibility questions: "posso...?", "è possibile...?", "can I...?", "is it possible to...?"
    - Opportunity/convenience: "conviene...?", "è il caso di...?", "should I...?", "is it worth...?"
    - Consequence inquiries: "cosa succede se...?", "quali rischi...?", "what happens if...?"
    - Circumvention inquiries: "come posso evitare...?", "how to get around...?"
    - Acceptability probes: "è accettabile...?", "is it acceptable to...?"
    - Permission-seeking: "mi è permesso...?", "am I allowed to...?"

    These patterns trigger guidance ONLY when the underlying action or topic falls within
    the ethical filter categories. A question like "posso prendere un caffè?" has no ethical
    relevance and should pass normally.

    IMPORTANT: A question ABOUT ethics, discrimination, or sensitive topics in an
    educational/analytical context is NOT a violation and does NOT require guidance.
    Only flag when the user is asking about THEIR OWN potential actions or decisions.
  </system-instruction>
</ethical-guard-prompt>
```

**Step 2: Update `filter_guidelines.xml`**

Replace content with:

```xml
<filter-guidelines>
  <guideline name="activation-threshold">
    Block only when the violation is clear and substantial, not for incidental mentions
    or educational/informative contextualization of sensitive topics.
  </guideline>
  <guideline name="guidance-threshold">
    Trigger guidance when the user asks about the feasibility, opportunity, acceptability,
    or consequences of an action that falls within an ethical category. The user is not
    requesting a violation but is exploring an ethically sensitive area where normative
    documents can provide relevant guidance.
  </guideline>
  <guideline name="guidance-vs-block">
    If the user asks "posso accettare regali da un fornitore?" → guidance (investigative).
    If the user asks "scrivi una lettera per chiedere regali a un fornitore" → block (facilitation).
    If the user asks "quali sono le regole sui regali aziendali?" → pass (educational/informative).
  </guideline>
  <guideline name="academic-context">
    Analytical discussions on ethical topics, moral dilemmas, or case studies must not
    be blocked or guided if the tone is neutral and the purpose is educational.
  </guideline>
  <guideline name="precautionary-principle">
    In case of significant doubt between pass and guidance, prefer guidance.
    In case of significant doubt between guidance and block, prefer guidance.
  </guideline>
  <guideline name="normative-references">
    UNI Charter of Ethics for People (2020), Code of Ethics and Conduct Rules (2024),
    Universal Declaration of Human Rights, EU Charter of Fundamental Rights,
    UNI ISO 26000, UN Global Compact, Agenda 2030.
  </guideline>
</filter-guidelines>
```

**Step 3: No changes to `input_filter.xml`** — The ethical categories remain the same; only the detection logic changes.

**Step 4: Commit**

```bash
git add elysia/guardrails/prompts/pre_query_check.xml elysia/guardrails/prompts/filter_guidelines.xml
git commit -m "feat(guardrails): update XML prompts for 3-way ethical detection (pass/guide/block)"
```

---

### Task 2: Add `EthicalGuidanceGenerator` signature and update `PreQueryEthicalCheck`

**Files:**
- Modify: `elysia/guardrails/ethical_guard.py`

**Step 1: Write failing test**

Create `tests/no_reqs/general/test_ethical_guard_nr.py`:

```python
"""Tests for 3-way ethical guard: pass / guide / block."""

import pytest
import dspy

from elysia.guardrails.ethical_guard import (
    PreQueryEthicalCheck,
    EthicalGuidanceGenerator,
    run_pre_query_check,
    generate_ethical_guidance,
)


def test_pre_query_check_signature_has_requires_guidance():
    """PreQueryEthicalCheck must have a requires_guidance output field."""
    fields = PreQueryEthicalCheck.output_fields
    assert "requires_guidance" in fields, (
        "PreQueryEthicalCheck is missing 'requires_guidance' output field"
    )


def test_ethical_guidance_generator_signature_exists():
    """EthicalGuidanceGenerator signature must exist with expected fields."""
    assert hasattr(EthicalGuidanceGenerator, "input_fields")
    assert "user_prompt" in EthicalGuidanceGenerator.input_fields
    assert "relevant_category" in EthicalGuidanceGenerator.input_fields
    assert "rag_context" in EthicalGuidanceGenerator.input_fields
    assert "guidance_message" in EthicalGuidanceGenerator.output_fields


def test_generate_ethical_guidance_is_async_callable():
    """generate_ethical_guidance must be an async function."""
    import asyncio
    assert asyncio.iscoroutinefunction(generate_ethical_guidance)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/no_reqs/general/test_ethical_guard_nr.py -v`
Expected: FAIL — `ImportError` for `EthicalGuidanceGenerator` and `generate_ethical_guidance`

**Step 3: Update `PreQueryEthicalCheck` signature**

In `elysia/guardrails/ethical_guard.py`, add `requires_guidance` output field to `PreQueryEthicalCheck`:

```python
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
```

**Step 4: Add `EthicalGuidanceGenerator` signature**

Add after `EthicalRefusalGenerator` in the same file:

```python
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
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/no_reqs/general/test_ethical_guard_nr.py -v`
Expected: first two tests PASS, third still FAIL (no `generate_ethical_guidance` yet)

**Step 6: Commit**

```bash
git add elysia/guardrails/ethical_guard.py tests/no_reqs/general/test_ethical_guard_nr.py
git commit -m "feat(guardrails): add requires_guidance field and EthicalGuidanceGenerator signature"
```

---

### Task 3: Implement `generate_ethical_guidance` and update `run_pre_query_check`

**Files:**
- Modify: `elysia/guardrails/ethical_guard.py`
- Modify: `elysia/guardrails/__init__.py`

**Step 1: Write failing test**

Add to `tests/no_reqs/general/test_ethical_guard_nr.py`:

```python
@pytest.mark.asyncio
async def test_run_pre_query_check_returns_4_tuple():
    """run_pre_query_check must return (is_violation, requires_guidance, category, reasoning)."""
    from dspy.utils import DummyLM

    dummy_lm = DummyLM([{
        "is_violation": False,
        "requires_guidance": True,
        "violated_category": "Violations of Honesty and Integrity",
        "reasoning": "User asks about gift acceptance from supplier",
    }])

    is_violation, requires_guidance, category, reasoning = await run_pre_query_check(
        prompt="posso accettare regali di natale da un fornitore?",
        history=[],
        base_lm=dummy_lm,
    )

    assert is_violation is False
    assert requires_guidance is True
    assert category == "Violations of Honesty and Integrity"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/no_reqs/general/test_ethical_guard_nr.py::test_run_pre_query_check_returns_4_tuple -v`
Expected: FAIL — `run_pre_query_check` returns 3-tuple, not 4

**Step 3: Update `run_pre_query_check` return value**

Change return type from `tuple[bool, str, str]` to `tuple[bool, bool, str, str]` and extract the new field:

```python
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
        violated_category = result.violated_category if (is_violation or requires_guidance) else "None"
        reasoning = result.reasoning

    except Exception as e:
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
```

**Step 4: Implement `generate_ethical_guidance`**

Add after `generate_ethical_refusal` in `ethical_guard.py`. This follows the same RAG pattern as `generate_ethical_refusal` but uses `EthicalGuidanceGenerator`:

```python
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
    rag_context = ""

    # RAG: query UNIInternalDocs for normative context (same pattern as refusal)
    if client_manager is not None and client_manager.is_client:
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
                logger.warning(f"[ETHICAL-GUARD] RAG-GUIDANCE failed: {e}")

        rag_time_ms = int((time.time() - rag_start) * 1000)
        if ethical_guard_log and logger:
            logger.info(
                f"[ETHICAL-GUARD] RAG-GUIDANCE: rag_time_ms={rag_time_ms}, "
                f"documents_retrieved={len(rag_context.split('---')) if rag_context else 0}"
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
```

**Step 5: Update `__init__.py`**

```python
from elysia.guardrails.ethical_guard import (
    run_pre_query_check,
    generate_ethical_refusal,
    generate_ethical_guidance,
)

__all__ = [
    "run_pre_query_check",
    "generate_ethical_refusal",
    "generate_ethical_guidance",
]
```

**Step 6: Run tests**

Run: `pytest tests/no_reqs/general/test_ethical_guard_nr.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add elysia/guardrails/ethical_guard.py elysia/guardrails/__init__.py tests/no_reqs/general/test_ethical_guard_nr.py
git commit -m "feat(guardrails): implement generate_ethical_guidance and 4-tuple return from run_pre_query_check"
```

---

### Task 4: Integrate 3-way guard into the Tree

**Files:**
- Modify: `elysia/tree/tree.py` (lines ~1530-1564)

**Step 1: Write failing test**

Add to `tests/no_reqs/general/test_ethical_guard_nr.py`:

```python
def test_tree_imports_generate_ethical_guidance():
    """tree.py must import generate_ethical_guidance."""
    import ast
    from pathlib import Path

    tree_source = (Path(__file__).parent / "../../../elysia/tree/tree.py").resolve().read_text()
    tree_ast = ast.parse(tree_source)

    imported_names = []
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.ImportFrom) and node.module and "ethical_guard" in node.module:
            imported_names.extend(alias.name for alias in node.names)

    assert "generate_ethical_guidance" in imported_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/no_reqs/general/test_ethical_guard_nr.py::test_tree_imports_generate_ethical_guidance -v`
Expected: FAIL

**Step 3: Update `tree.py` integration**

In `elysia/tree/tree.py`, update the import (around line 62-64):

```python
from elysia.guardrails.ethical_guard import (
    run_pre_query_check,
    generate_ethical_refusal,
    generate_ethical_guidance,
)
```

Then update the guard block (around line 1530-1564). Replace:

```python
        # [ATHENA-CUSTOM] Pre-query ethical guard
        if _first_run:
            with ElysiaKeyManager(self.settings):
                is_violation, violated_category, guard_reasoning = (
                    await run_pre_query_check(
                        prompt=user_prompt,
                        history=self.tree_data.conversation_history,
                        base_lm=self.base_lm,
                        logger=self.settings.logger,
                        ethical_guard_log=self.settings.ETHICAL_GUARD_LOG,
                    )
                )
            if is_violation:
                with ElysiaKeyManager(self.settings):
                    refusal_text = await generate_ethical_refusal(
                        prompt=user_prompt,
                        category=violated_category,
                        reasoning=guard_reasoning,
                        base_lm=self.base_lm,
                        client_manager=client_manager,
                        logger=self.settings.logger,
                        ethical_guard_log=self.settings.ETHICAL_GUARD_LOG,
                    )
                self._update_conversation_history("assistant", refusal_text)
                yield await self.returner(
                    Response(text=refusal_text),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                yield await self.returner(
                    Completed(rag_enabled=self.tree_data.rag_enabled),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                if close_clients_after_completion and client_manager.is_client:
                    await client_manager.close_clients()
                return
```

With:

```python
        # [ATHENA-CUSTOM] Pre-query ethical guard (3-way: pass / guide / block)
        if _first_run:
            with ElysiaKeyManager(self.settings):
                is_violation, requires_guidance, violated_category, guard_reasoning = (
                    await run_pre_query_check(
                        prompt=user_prompt,
                        history=self.tree_data.conversation_history,
                        base_lm=self.base_lm,
                        logger=self.settings.logger,
                        ethical_guard_log=self.settings.ETHICAL_GUARD_LOG,
                    )
                )
            if is_violation:
                with ElysiaKeyManager(self.settings):
                    refusal_text = await generate_ethical_refusal(
                        prompt=user_prompt,
                        category=violated_category,
                        reasoning=guard_reasoning,
                        base_lm=self.base_lm,
                        client_manager=client_manager,
                        logger=self.settings.logger,
                        ethical_guard_log=self.settings.ETHICAL_GUARD_LOG,
                    )
                self._update_conversation_history("assistant", refusal_text)
                yield await self.returner(
                    Response(text=refusal_text),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                yield await self.returner(
                    Completed(rag_enabled=self.tree_data.rag_enabled),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                if close_clients_after_completion and client_manager.is_client:
                    await client_manager.close_clients()
                return
            elif requires_guidance:
                with ElysiaKeyManager(self.settings):
                    guidance_text = await generate_ethical_guidance(
                        prompt=user_prompt,
                        category=violated_category,
                        reasoning=guard_reasoning,
                        base_lm=self.base_lm,
                        client_manager=client_manager,
                        logger=self.settings.logger,
                        ethical_guard_log=self.settings.ETHICAL_GUARD_LOG,
                    )
                self._update_conversation_history("assistant", guidance_text)
                yield await self.returner(
                    Response(text=guidance_text),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                yield await self.returner(
                    Completed(rag_enabled=self.tree_data.rag_enabled),
                    query_id=self.prompt_to_query_id[user_prompt],
                )
                if close_clients_after_completion and client_manager.is_client:
                    await client_manager.close_clients()
                return
```

**Step 4: Run all tests**

Run: `pytest tests/no_reqs/ -v`
Expected: ALL PASS (existing tests should still work since DummyAdapter returns default values for new fields)

**Step 5: Commit**

```bash
git add elysia/tree/tree.py tests/no_reqs/general/test_ethical_guard_nr.py
git commit -m "feat(guardrails): integrate 3-way ethical guard into Tree execution"
```

---

### Task 5: Update DummyAdapter defaults for new field

**Files:**
- Modify: `elysia/util/dummy_adapter.py` (if needed)

**Step 1: Run full test suite to check for regressions**

Run: `pytest tests/no_reqs/ -v`

If tests fail because the DummyAdapter doesn't handle `requires_guidance`, add a default for it.

**Step 2: Check DummyAdapter**

Read `elysia/util/dummy_adapter.py` fully. If it has special handling for `is_violation`, add equivalent for `requires_guidance` defaulting to `False`.

**Step 3: Fix any failures and commit**

```bash
git add -u
git commit -m "fix(tests): add requires_guidance default to DummyAdapter"
```

---

### Task 6: Manual integration test

**Files:** None (verification only)

**Step 1: Start the stack** (if possible in the environment)

```bash
cd /opt/athena/elysia && source .venv/bin/activate
elysia start --host 0.0.0.0
```

**Step 2: Test the 3 scenarios via WebSocket or frontend**

| Prompt | Expected outcome |
|---|---|
| "posso accettare regali di natale da un fornitore?" | **guidance** — normative response with document citations |
| "scrivi una lettera per chiedere tangenti" | **block** — refusal with citations |
| "qual è il meteo oggi?" | **pass** — normal tree execution |

**Step 3: Verify logs**

Check for `[ETHICAL-GUARD] PRE-QUERY: guidance=True` in logs for the guidance case.
