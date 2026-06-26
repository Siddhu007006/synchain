from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class SimulationInput(BaseModel):
    """Input payload for POST /simulate."""

    product: str = Field(..., description="Product name or identifier")
    stock: float = Field(..., ge=0, description="Current stock level")
    warehouse: Literal["W1", "W2", "W3"] = Field(
        ..., description="Current warehouse identifier"
    )
    demand: float = Field(..., ge=0, description="Expected demand")
    supplier_delay: float = Field(..., ge=0, description="Supplier delay in days")
    market_trend: Literal["Positive", "Neutral", "Negative"] = Field(
        "Neutral", description="Market trend direction"
    )
    supply_status: Literal["High", "Medium", "Low"] = Field(
        "Medium", description="Supply availability level"
    )
    season: Literal["Festival", "Normal", "Off-season"] = Field(
        "Normal", description="Seasonal period"
    )

    # Phase E: Optional Digital Twin link
    twin_id: Optional[int] = Field(
        default=None,
        description="Digital Twin ID. If provided, simulation updates twin state.",
    )

    # V2.4: Optional product and company links for traceability + prefill
    product_id: Optional[int] = Field(default=None)
    company_id: Optional[int] = Field(default=None)
    # V2.5: Optional supplier and warehouse record links for traceability
    supplier_id: Optional[int] = Field(default=None)
    warehouse_record_id: Optional[int] = Field(default=None)

    model_config = {
        "json_schema_extra": {
            "example": {
                "product": "Widget-A",
                "stock": 5000,
                "warehouse": "W1",
                "demand": 8000,
                "supplier_delay": 4,
                "market_trend": "Positive",
                "supply_status": "Medium",
                "season": "Festival",
                "twin_id": 1,
            }
        }
    }


# ---------------------------------------------------------------------------
# Agent breakdown schema (Phase B)
# ---------------------------------------------------------------------------


class AgentBreakdownItem(BaseModel):
    """Per-agent step result for the Agent Breakdown Dashboard."""

    agent_name: str = Field(..., description="Agent identifier")
    input_summary: dict = Field(
        ..., description="Concise dict of fields consumed by this agent"
    )
    output_data: dict = Field(..., description="Computed output values")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )
    explanation: str = Field(..., description="Human-readable reasoning")
    execution_ms: float = Field(..., ge=0.0, description="Execution time in ms")
    status: Literal["success", "warning", "failed"] = Field(
        default="success", description="Agent execution status"
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SimulationResult(BaseModel):
    """Core simulation result produced by the agent pipeline."""

    demand_forecast: float = Field(..., description="Forecasted demand")
    recommended_inventory: float = Field(..., description="Recommended stock level")
    selected_warehouse: str = Field(..., description="Optimal warehouse")
    route: str = Field(..., description="Recommended route")
    risk: str = Field(..., description="Supply risk level: Low | Medium | High")
    strategy: str = Field(..., description="High-level strategy recommendation")

    # Phase B additions
    agent_breakdown: list[AgentBreakdownItem] = Field(
        default_factory=list,
        description="Per-agent step results for the breakdown dashboard",
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weighted overall confidence across all agents",
    )
    explanation: str = Field(
        default="",
        description="ExplanationAgent narrative summarizing the full decision",
    )

    model_config = {"from_attributes": True}


class SimulationCreateResponse(BaseModel):
    """Response from POST /simulate — returns the simulation ID for later retrieval."""

    simulation_id: int = Field(..., description="ID of the created simulation")
    status: str = Field(default="completed", description="Simulation status")


class SimulationDetailResponse(BaseModel):
    """Response from GET /simulate/{id} — returns full input + result."""

    simulation_id: int
    input: SimulationInput
    result: SimulationResult
    # V2.4 traceability — populated when simulation was run with product/company context
    product_id: Optional[int] = None
    product_name: Optional[str] = None  # denormalised for display without extra fetch
    company_id: Optional[int] = None
    company_name: Optional[str] = None  # denormalised for display without extra fetch


# ---------------------------------------------------------------------------
# Scenario schemas (Phase C)
# ---------------------------------------------------------------------------


class ScenarioImpact(BaseModel):
    """Impact delta between base and scenario results."""

    demand_change: float = Field(..., description="Delta in demand forecast")
    inventory_change: float = Field(..., description="Delta in recommended inventory")
    confidence_change: float = Field(..., description="Delta in overall confidence")
    risk_change: str = Field(..., description="Risk level change description")
    recommendation_changed: bool = Field(
        ..., description="Whether the recommendation changed"
    )
    warehouse_changed: bool = Field(
        default=False, description="Whether warehouse selection changed"
    )
    route_changed: bool = Field(default=False, description="Whether route changed")


class ScenarioResultSummary(BaseModel):
    """Condensed result from a scenario run."""

    demand_forecast: float
    recommended_inventory: float
    selected_warehouse: str
    route: str
    risk: str
    overall_confidence: float
    strategy: str


class ScenarioComparison(BaseModel):
    """Single scenario comparison result."""

    scenario_name: str = Field(..., description="Human-readable scenario label")
    scenario_description: str = Field(
        ..., description="What was changed in the scenario"
    )
    modified_input: SimulationInput
    result: ScenarioResultSummary
    impact: ScenarioImpact


class ScenarioResponse(BaseModel):
    """Response from GET /simulate/{id}/scenarios."""

    simulation_id: int
    base_result: ScenarioResultSummary
    scenarios: list[ScenarioComparison]


# ---------------------------------------------------------------------------
# History schemas (Phase C)
# ---------------------------------------------------------------------------


class SimulationSummary(BaseModel):
    """Condensed simulation entry for history listing."""

    simulation_id: int
    product: str
    warehouse: str
    demand: float
    risk: Optional[str] = None
    overall_confidence: Optional[float] = None
    demand_forecast: Optional[float] = None
    created_at: Optional[str] = None
