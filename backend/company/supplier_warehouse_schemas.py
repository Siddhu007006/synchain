"""
Pydantic schemas for Supplier and Warehouse CRUD + Simulation Prefill (V2.5).

Prefill contract (same pattern as V2.3 Products):
  supplier.lead_time_days  → SimulationInput.supplier_delay
  supplier.supply_status   → SimulationInput.supply_status
  warehouse.warehouse_id   → SimulationInput.warehouse
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    lead_time_days: float = Field(
        default=0.0, ge=0, description="Prefills supplier_delay"
    )
    supply_status: Literal["High", "Medium", "Low"] = Field(
        default="Medium", description="Prefills supply_status"
    )
    reliability_pct: float = Field(default=100.0, ge=0, le=100)


class SupplierUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    lead_time_days: Optional[float] = Field(default=None, ge=0)
    supply_status: Optional[Literal["High", "Medium", "Low"]] = None
    reliability_pct: Optional[float] = Field(default=None, ge=0, le=100)


class SupplierResponse(BaseModel):
    id: int
    company_id: int
    name: str
    lead_time_days: float  # → SimulationInput.supplier_delay
    supply_status: str  # → SimulationInput.supply_status
    reliability_pct: float
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    total: int
    suppliers: list[SupplierResponse]


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------


class WarehouseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    warehouse_id: Literal["W1", "W2", "W3"] = Field(
        ..., description="Prefills SimulationInput.warehouse"
    )
    location: str = Field(default="", max_length=200)
    capacity: float = Field(default=10000.0, ge=0)


class WarehouseUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    warehouse_id: Optional[Literal["W1", "W2", "W3"]] = None
    location: Optional[str] = Field(default=None, max_length=200)
    capacity: Optional[float] = Field(default=None, ge=0)


class WarehouseResponse(BaseModel):
    id: int
    company_id: int
    name: str
    warehouse_id: str  # → SimulationInput.warehouse
    location: str
    capacity: float
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class WarehouseListResponse(BaseModel):
    total: int
    warehouses: list[WarehouseResponse]
