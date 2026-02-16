"""Tests for 3-way ethical guard: pass / guide / block."""

import pytest
import asyncio

from elysia.guardrails.ethical_guard import (
    PreQueryEthicalCheck,
    EthicalGuidanceGenerator,
    run_pre_query_check,
    generate_ethical_guidance,
)


def test_pre_query_check_signature_has_requires_guidance():
    """PreQueryEthicalCheck must have a requires_guidance output field."""
    fields = PreQueryEthicalCheck.output_fields
    assert "requires_guidance" in fields


def test_ethical_guidance_generator_signature_exists():
    """EthicalGuidanceGenerator signature must exist with expected fields."""
    assert hasattr(EthicalGuidanceGenerator, "input_fields")
    assert "user_prompt" in EthicalGuidanceGenerator.input_fields
    assert "relevant_category" in EthicalGuidanceGenerator.input_fields
    assert "rag_context" in EthicalGuidanceGenerator.input_fields
    assert "guidance_message" in EthicalGuidanceGenerator.output_fields


def test_generate_ethical_guidance_is_async_callable():
    """generate_ethical_guidance must be an async function."""
    assert asyncio.iscoroutinefunction(generate_ethical_guidance)


def test_run_pre_query_check_is_async_callable():
    """run_pre_query_check must be an async function."""
    assert asyncio.iscoroutinefunction(run_pre_query_check)
