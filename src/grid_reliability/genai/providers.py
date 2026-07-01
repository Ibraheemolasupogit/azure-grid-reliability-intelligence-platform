"""Provider abstraction for assistant generation."""

from __future__ import annotations

from typing import Protocol

from grid_reliability.genai.models import GenerationRequest, GenerationResult


class AssistantProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a response from grounded evidence."""


class AzureAIFoundryProvider:
    """Future integration seam that intentionally performs no network calls."""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise RuntimeError("Azure AI Foundry provider is not configured for local execution.")
