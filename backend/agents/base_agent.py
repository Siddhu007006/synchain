"""
Base agent contract for the SynChain multi-agent pipeline.

Every specialist agent must:
  1. Inherit from BaseAgent.
  2. Implement the `name` property and `execute()` method.
  3. Return an AgentStepResult containing: output, confidence, explanation,
     execution time, and status.

AgentStepResult is the standardized envelope that enables the Agent Breakdown
Dashboard on the frontend.
"""

import time
from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


class AgentStepResult(BaseModel):
    """Standardized envelope returned by every agent in the pipeline."""

    agent_name: str = Field(..., description="Human-readable agent identifier")
    input_summary: dict = Field(
        ...,
        description="Concise dict of ONLY the fields this agent consumed",
    )
    output_data: dict = Field(..., description="Agent's computed output values")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0–1.0) computed via documented formula",
    )
    explanation: str = Field(
        ...,
        description="Human-readable reasoning for the output and confidence",
    )
    execution_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall-clock execution time in milliseconds",
    )
    status: Literal["success", "warning", "failed"] = Field(
        default="success",
        description="Agent execution status for monitoring and debugging",
    )


class BaseAgent(ABC):
    """Abstract base class enforcing the agent contract: typed input → AgentStepResult."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, **kwargs) -> AgentStepResult:
        """Execute the agent logic and return a standardized result envelope."""
        ...

    def _timed_execute(self, func, **kwargs) -> tuple:
        """Helper: execute a callable and return (result, elapsed_ms)."""
        start = time.perf_counter()
        result = func(**kwargs)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return result, elapsed_ms
