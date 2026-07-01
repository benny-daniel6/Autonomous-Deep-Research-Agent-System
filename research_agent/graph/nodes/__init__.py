"""
LangGraph node functions for each agent in the research pipeline.

Provides a shared ``get_llm()`` helper so every node uses the same
Gemini model configuration without duplicating setup logic.
"""

from __future__ import annotations

import os

from langchain_google_genai import ChatGoogleGenerativeAI

_LLM_MODEL = "gemini-3.1-flash-lite"


def get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Return a configured ``ChatGoogleGenerativeAI`` instance.

    Centralised here so model name and key lookup are defined once.
    Nodes that need structured output call
    ``get_llm().with_structured_output(MyModel)``.
    """
    return ChatGoogleGenerativeAI(
        model=_LLM_MODEL,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=temperature,
    )
