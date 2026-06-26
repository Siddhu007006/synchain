"""
Pydantic schemas for Product CRUD + V2.4 Simulation Prefill (V2.3).

The ProductSimulationPrefill schema is the contract for V2.4.
It returns exactly the fields the simulation form needs to auto-populate
stock and demand without any schema changes in V2.4 — the data is
already here, waiting to be consumed.
"""

from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ProductCreateRequest(BaseModel):
    """POST /companies/{id}/products"""

    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(default="", max_length=100)
    current_stock: float = Field(default=0.0, ge=0)
    avg_monthly_demand: float = Field(default=0.0, ge=0)


class ProductUpdateRequest(BaseModel):
    """PATCH /products/{id} — all fields optional"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=100)
    current_stock: Optional[float] = Field(default=None, ge=0)
    avg_monthly_demand: Optional[float] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ProductResponse(BaseModel):
    """Full product record."""

    id: int
    company_id: int
    name: str
    category: str
    current_stock: float
    avg_monthly_demand: float
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Paginated list of products for a company."""

    total: int
    products: list[ProductResponse]


# ---------------------------------------------------------------------------
# V2.4 Simulation Prefill contract
#
# GET /companies/{id}/products returns ProductResponse[] which already
# contains current_stock and avg_monthly_demand. The simulation form
# in V2.4 reads those fields directly — no additional endpoint needed.
#
# Documented here so the intent is explicit:
#   product.name              → SimulationInput.product
#   product.current_stock     → SimulationInput.stock
#   product.avg_monthly_demand → SimulationInput.demand
# ---------------------------------------------------------------------------


class ProductSimulationPrefill(BaseModel):
    """
    Minimal product fields exposed to the simulation form for auto-fill.

    Returned by GET /companies/{id}/products as part of ProductResponse.
    The simulation form uses this to prefill stock and demand when a
    product is selected (V2.4).
    """

    id: int
    name: str
    current_stock: float  # → SimulationInput.stock
    avg_monthly_demand: float  # → SimulationInput.demand
    category: str
