"""
SQLAlchemy 2.0 model for Product (V2.3).

Products are business data owned by a Company.
They carry the stock and demand figures that will prefill the
simulation form in V2.4, closing the loop:

  Product.current_stock       → SimulationInput.stock
  Product.avg_monthly_demand  → SimulationInput.demand

Design note: product name is intentionally kept as a plain string
(not a FK to a products table) in SimulationInput so existing simulations
remain valid. V2.4 will add an optional product_id field to SimulationInput
for reverse-linking, without breaking anything that already exists.
"""

from datetime import datetime

from database import Base
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class Product(Base):
    """A product owned by a Company."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Ownership — scoped to a company (and therefore to an org via company.org_id)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), index=True, nullable=False
    )

    # Core fields
    name: Mapped[str] = mapped_column(index=True)
    category: Mapped[str] = mapped_column(default="")

    # V2.4 prefill targets — stored so the simulation form can auto-populate
    current_stock: Mapped[float] = mapped_column(default=0.0)
    avg_monthly_demand: Mapped[float] = mapped_column(default=0.0)

    # V3.0: Unit price for financial impact estimation
    unit_price: Mapped[float] = mapped_column(default=0.0)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
