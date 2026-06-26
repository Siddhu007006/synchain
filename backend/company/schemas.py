"""
Pydantic schemas for Company CRUD API (V2 Phase 1).
"""

from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CompanyCreateRequest(BaseModel):
    """Request body for POST /companies."""

    name: str = Field(..., min_length=1, max_length=200, description="Company name")
    industry: str = Field(default="", max_length=100, description="Industry vertical")
    country: str = Field(default="", max_length=100, description="Country of operation")


class CompanyUpdateRequest(BaseModel):
    """Request body for PATCH /companies/{id} — all fields optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    industry: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)


class CreateTwinForCompanyRequest(BaseModel):
    """Request body for POST /companies/{id}/twins (V2.2)."""

    name: str = Field(default="Default Supply Chain", max_length=200)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CompanyResponse(BaseModel):
    """Full company record returned by all endpoints."""

    id: int
    name: str
    industry: str
    country: str
    is_archived: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    """Paginated list of companies."""

    total: int
    companies: list[CompanyResponse]


class CompanyDependencyCounts(BaseModel):
    """Dependency counts returned with 409 when a company has data."""

    products: int
    suppliers: int
    warehouses: int
    twins: int
    simulations: int


class CompanyArchiveResponse(BaseModel):
    """Returned when a company is successfully archived."""

    id: int
    name: str
    is_archived: bool
    message: str
