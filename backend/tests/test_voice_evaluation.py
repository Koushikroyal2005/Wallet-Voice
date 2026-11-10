"""Deterministic evaluations only. Live model evaluation is a separate command."""
import asyncio
import pytest
from voice_eval_support import CASES,evaluate_case


@pytest.mark.parametrize('case',CASES,ids=lambda case:case['id'])
def test_deterministic_conversation_case(case):
    asyncio.run(evaluate_case(case))
