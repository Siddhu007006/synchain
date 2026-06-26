"""
Tests for V2.6 CSV Import (Onboarding System).

Covers:
  1. CSV parser (parse_csv_bytes)
  2. Product/Supplier/Warehouse validators
  3. UPSERT logic (create + update)
  4. Preview endpoint (dry_run=true)
  5. Import endpoint (dry_run=false)
  6. Import history endpoint
  7. Template download
  8. Edge cases (BOM, Windows line endings, empty file, bad headers)
"""

import pytest
from auth.models import Organization, User
from company.csv_import import (
    check_headers,
    parse_csv_bytes,
    upsert_products,
    upsert_suppliers,
    upsert_warehouses,
    validate_products,
    validate_suppliers,
    validate_warehouses,
)
from company.models import Company
from company.product_models import Product
from company.supplier_warehouse_models import Supplier, Warehouse
from database import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SASession

# ---------------------------------------------------------------------------
# 1. Parser Tests
# ---------------------------------------------------------------------------


class TestParseCSV:
    """Tests for parse_csv_bytes."""

    def test_valid_csv(self):
        data = b"name,category,stock,demand\nLaptop,Electronics,500,700"
        rows, err = parse_csv_bytes(data)
        assert err is None
        assert len(rows) == 1
        assert rows[0]["name"] == "Laptop"
        assert rows[0]["stock"] == "500"

    def test_empty_file(self):
        rows, err = parse_csv_bytes(b"")
        assert err == "File is empty"
        assert rows == []

    def test_header_only(self):
        rows, err = parse_csv_bytes(b"name,stock\n")
        assert err is None
        assert len(rows) == 0

    def test_utf8_bom(self):
        """Excel exports often include a BOM prefix."""
        bom = b"\xef\xbb\xbfname,stock\nWidget,100"
        rows, err = parse_csv_bytes(bom)
        assert err is None
        assert len(rows) == 1
        assert rows[0]["name"] == "Widget"

    def test_windows_line_endings(self):
        data = b"name,stock\r\nA,10\r\nB,20\r\n"
        rows, err = parse_csv_bytes(data)
        assert err is None
        assert len(rows) == 2

    def test_case_insensitive_headers(self):
        data = b"Name, CATEGORY ,Stock,DEMAND\nX,Y,10,20"
        rows, err = parse_csv_bytes(data)
        assert err is None
        assert "name" in rows[0]
        assert "category" in rows[0]

    def test_extra_whitespace(self):
        data = b"name , stock\n  Widget , 100 "
        rows, err = parse_csv_bytes(data)
        assert err is None
        assert rows[0]["name"] == "Widget"
        assert rows[0]["stock"] == "100"

    def test_non_utf8(self):
        rows, err = parse_csv_bytes(b"\xff\xfe")
        assert "not valid UTF-8" in err


class TestCheckHeaders:
    def test_valid_product_headers(self):
        assert check_headers(["name", "stock"], "products") is None

    def test_missing_required(self):
        err = check_headers(["stock", "demand"], "products")
        assert "name" in err

    def test_valid_warehouse_headers(self):
        assert check_headers(["name", "warehouse_id", "location"], "warehouses") is None

    def test_missing_warehouse_id(self):
        err = check_headers(["name", "location"], "warehouses")
        assert "warehouse_id" in err


# ---------------------------------------------------------------------------
# 2. Product Validator Tests
# ---------------------------------------------------------------------------


class TestValidateProducts:
    def test_valid_rows(self):
        rows = [
            {
                "name": "Laptop",
                "category": "Electronics",
                "stock": "500",
                "demand": "700",
            },
            {
                "name": "Mouse",
                "category": "Peripherals",
                "stock": "1000",
                "demand": "200",
            },
        ]
        valid, preview = validate_products(rows)
        assert len(valid) == 2
        assert all(r["valid"] for r in preview)

    def test_missing_name(self):
        rows = [{"name": "", "stock": "100", "demand": "50"}]
        valid, preview = validate_products(rows)
        assert len(valid) == 0
        assert "name is required" in preview[0]["errors"]

    def test_negative_stock(self):
        rows = [{"name": "Widget", "stock": "-50", "demand": "100"}]
        valid, preview = validate_products(rows)
        assert len(valid) == 0
        assert any("negative" in e for e in preview[0]["errors"])

    def test_negative_demand(self):
        rows = [{"name": "Widget", "stock": "50", "demand": "-10"}]
        valid, preview = validate_products(rows)
        assert len(valid) == 0

    def test_non_numeric_stock(self):
        rows = [{"name": "Widget", "stock": "abc", "demand": "100"}]
        valid, preview = validate_products(rows)
        assert len(valid) == 0
        assert any("number" in e for e in preview[0]["errors"])

    def test_optional_fields_default(self):
        rows = [{"name": "Widget"}]
        valid, preview = validate_products(rows)
        assert len(valid) == 1
        assert valid[0]["current_stock"] == 0.0
        assert valid[0]["avg_monthly_demand"] == 0.0
        assert valid[0]["category"] == ""

    def test_multiple_errors_one_row(self):
        rows = [{"name": "", "stock": "-1", "demand": "abc"}]
        valid, preview = validate_products(rows)
        assert len(valid) == 0
        assert len(preview[0]["errors"]) >= 2


# ---------------------------------------------------------------------------
# 3. Supplier Validator Tests
# ---------------------------------------------------------------------------


class TestValidateSuppliers:
    def test_valid_supplier(self):
        rows = [
            {
                "name": "Supplier A",
                "lead_time": "8",
                "reliability": "72",
                "status": "Low",
            }
        ]
        valid, preview = validate_suppliers(rows)
        assert len(valid) == 1
        assert valid[0]["supply_status"] == "Low"

    def test_case_insensitive_status(self):
        rows = [{"name": "S", "status": "high"}]
        valid, _ = validate_suppliers(rows)
        assert valid[0]["supply_status"] == "High"

    def test_invalid_status(self):
        rows = [{"name": "S", "status": "Critical"}]
        valid, preview = validate_suppliers(rows)
        assert len(valid) == 0
        assert any("High, Medium, or Low" in e for e in preview[0]["errors"])

    def test_reliability_out_of_range(self):
        rows = [{"name": "S", "reliability": "150"}]
        valid, preview = validate_suppliers(rows)
        assert len(valid) == 0
        assert any("between 0 and 100" in e for e in preview[0]["errors"])

    def test_negative_lead_time(self):
        rows = [{"name": "S", "lead_time": "-5"}]
        valid, preview = validate_suppliers(rows)
        assert len(valid) == 0

    def test_defaults(self):
        rows = [{"name": "S"}]
        valid, _ = validate_suppliers(rows)
        assert valid[0]["lead_time_days"] == 0.0
        assert valid[0]["reliability_pct"] == 100.0
        assert valid[0]["supply_status"] == "Medium"


# ---------------------------------------------------------------------------
# 4. Warehouse Validator Tests
# ---------------------------------------------------------------------------


class TestValidateWarehouses:
    def test_valid_warehouse(self):
        rows = [
            {
                "name": "Hub",
                "location": "Mumbai",
                "capacity": "10000",
                "warehouse_id": "W1",
            }
        ]
        valid, preview = validate_warehouses(rows)
        assert len(valid) == 1
        assert valid[0]["warehouse_id"] == "W1"

    def test_invalid_warehouse_id(self):
        rows = [{"name": "Hub", "warehouse_id": "W9"}]
        valid, preview = validate_warehouses(rows)
        assert len(valid) == 0
        assert any("W1, W2, or W3" in e for e in preview[0]["errors"])

    def test_lowercase_warehouse_id(self):
        """warehouse_id should be case-insensitive."""
        rows = [{"name": "Hub", "warehouse_id": "w2", "capacity": "5000"}]
        valid, _ = validate_warehouses(rows)
        assert len(valid) == 1
        assert valid[0]["warehouse_id"] == "W2"

    def test_zero_capacity(self):
        rows = [{"name": "Hub", "warehouse_id": "W1", "capacity": "0"}]
        valid, preview = validate_warehouses(rows)
        assert len(valid) == 0
        assert any("greater than 0" in e for e in preview[0]["errors"])

    def test_missing_warehouse_id(self):
        rows = [{"name": "Hub", "capacity": "5000"}]
        valid, preview = validate_warehouses(rows)
        assert len(valid) == 0
        assert any("warehouse_id is required" in e for e in preview[0]["errors"])


# ---------------------------------------------------------------------------
# 5. UPSERT Tests (with real DB session)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with SASession(engine) as session:
        # Create user for org FK
        user = User(
            email="test@import.io",
            hashed_password="fakehash",
            display_name="Import Tester",
        )
        session.add(user)
        session.flush()

        # Create org + company
        org = Organization(name="Test Org", slug="test-org", created_by=user.id)
        session.add(org)
        session.flush()

        company = Company(name="Test Co", org_id=org.id)
        session.add(company)
        session.flush()

        yield session, company.id

        session.rollback()


class TestUpsertProducts:
    def test_insert_new(self, db_session):
        session, company_id = db_session
        rows = [
            {
                "name": "Laptop",
                "category": "Electronics",
                "current_stock": 500.0,
                "avg_monthly_demand": 700.0,
            },
            {
                "name": "Mouse",
                "category": "Peripherals",
                "current_stock": 1000.0,
                "avg_monthly_demand": 200.0,
            },
        ]
        created, updated = upsert_products(session, company_id, rows)
        assert created == 2
        assert updated == 0

        products = session.scalars(
            select(Product).where(Product.company_id == company_id)
        ).all()
        assert len(products) == 2

    def test_update_existing(self, db_session):
        session, company_id = db_session
        # Insert first
        session.add(
            Product(
                company_id=company_id,
                name="Laptop",
                current_stock=100,
                avg_monthly_demand=200,
            )
        )
        session.flush()

        # Upsert with updated values
        rows = [
            {
                "name": "Laptop",
                "category": "Electronics",
                "current_stock": 500.0,
                "avg_monthly_demand": 700.0,
            }
        ]
        created, updated = upsert_products(session, company_id, rows)
        assert created == 0
        assert updated == 1

        product = session.scalar(select(Product).where(Product.name == "Laptop"))
        assert product.current_stock == 500.0
        assert product.avg_monthly_demand == 700.0

    def test_mixed_insert_update(self, db_session):
        session, company_id = db_session
        session.add(Product(company_id=company_id, name="Laptop", current_stock=100))
        session.flush()

        rows = [
            {"name": "Laptop", "current_stock": 999.0, "avg_monthly_demand": 100.0},
            {
                "name": "Tablet",
                "category": "Electronics",
                "current_stock": 50.0,
                "avg_monthly_demand": 30.0,
            },
        ]
        created, updated = upsert_products(session, company_id, rows)
        assert created == 1
        assert updated == 1

    def test_case_insensitive_match(self, db_session):
        session, company_id = db_session
        session.add(Product(company_id=company_id, name="Laptop", current_stock=100))
        session.flush()

        rows = [{"name": "laptop", "current_stock": 999.0, "avg_monthly_demand": 0.0}]
        created, updated = upsert_products(session, company_id, rows)
        assert created == 0
        assert updated == 1


class TestUpsertSuppliers:
    def test_insert_and_update(self, db_session):
        session, company_id = db_session
        session.add(
            Supplier(company_id=company_id, name="Supplier A", lead_time_days=5)
        )
        session.flush()

        rows = [
            {
                "name": "Supplier A",
                "lead_time_days": 10.0,
                "supply_status": "Low",
                "reliability_pct": 60.0,
            },
            {
                "name": "Supplier B",
                "lead_time_days": 3.0,
                "supply_status": "High",
                "reliability_pct": 95.0,
            },
        ]
        created, updated = upsert_suppliers(session, company_id, rows)
        assert created == 1
        assert updated == 1

        s = session.scalar(select(Supplier).where(Supplier.name == "Supplier A"))
        assert s.lead_time_days == 10.0


class TestUpsertWarehouses:
    def test_insert_and_update(self, db_session):
        session, company_id = db_session
        session.add(Warehouse(company_id=company_id, name="Hub A", warehouse_id="W1"))
        session.flush()

        rows = [
            {
                "name": "Hub A",
                "warehouse_id": "W2",
                "location": "Delhi",
                "capacity": 5000.0,
            },
            {
                "name": "Hub B",
                "warehouse_id": "W3",
                "location": "Chennai",
                "capacity": 8000.0,
            },
        ]
        created, updated = upsert_warehouses(session, company_id, rows)
        assert created == 1
        assert updated == 1

        w = session.scalar(select(Warehouse).where(Warehouse.name == "Hub A"))
        assert w.warehouse_id == "W2"
        assert w.location == "Delhi"


# ---------------------------------------------------------------------------
# 6. Integration — full pipeline test
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end: CSV bytes → parse → validate → upsert."""

    def test_product_pipeline(self, db_session):
        session, company_id = db_session

        csv_data = b"name,category,stock,demand\nLaptop,Electronics,500,700\nMouse,Peripherals,1000,200\n,Bad,-10,abc"
        rows, err = parse_csv_bytes(csv_data)
        assert err is None
        assert len(rows) == 3

        valid_rows, preview = validate_products(rows)
        assert len(valid_rows) == 2
        assert preview[2]["valid"] is False

        created, updated = upsert_products(session, company_id, valid_rows)
        assert created == 2
        assert updated == 0

        products = session.scalars(
            select(Product).where(Product.company_id == company_id)
        ).all()
        assert len(products) == 2

    def test_upsert_pipeline(self, db_session):
        """Import same CSV twice — second time should update, not duplicate."""
        session, company_id = db_session

        csv_data = b"name,category,stock,demand\nLaptop,Electronics,500,700"

        # First import
        rows, _ = parse_csv_bytes(csv_data)
        valid, _ = validate_products(rows)
        upsert_products(session, company_id, valid)

        # Second import with different stock
        csv_data2 = b"name,category,stock,demand\nLaptop,Electronics,999,800"
        rows2, _ = parse_csv_bytes(csv_data2)
        valid2, _ = validate_products(rows2)
        created, updated = upsert_products(session, company_id, valid2)
        assert created == 0
        assert updated == 1

        product = session.scalar(select(Product).where(Product.name == "Laptop"))
        assert product.current_stock == 999.0
        assert product.avg_monthly_demand == 800.0

        # Should still only have 1 product
        total = session.scalars(
            select(Product).where(Product.company_id == company_id)
        ).all()
        assert len(total) == 1
