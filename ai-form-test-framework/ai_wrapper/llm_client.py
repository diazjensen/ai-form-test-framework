"""
Light LLM wrapper for ai_wrapper module, sharing the implementation from quality_suite.
"""
import os
import sys

QUALITY_SUITE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "quality_suite"))
sys.path.insert(0, QUALITY_SUITE)

from llm_client import complete, active_provider  # noqa: E402, F401
