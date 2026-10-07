"""Bundled sample Business Central records for key-less testing.

These mimic the JSON shape the real Business Central API returns (the standard
``api/v2.0`` entities) so the ingest → embed → Qdrant → RAG pipeline can be
exercised end-to-end without an Azure AD app or a BC subscription. As soon as
real ``BC_*`` credentials are configured, :mod:`app.bc.client` fetches live data
instead and these are ignored.

Each list is keyed by its BC entity name in :data:`SAMPLE_DATA`.
"""

from __future__ import annotations

_ITEMS = [
    {
        "number": "1000",
        "displayName": "Bicycle",
        "type": "Inventory",
        "unitPrice": 4000.0,
        "priceIncludesTax": False,
        "inventory": 32,
        "baseUnitOfMeasureCode": "PCS",
        "itemCategoryCode": "SPORTS",
        "description": "Touring bicycle, aluminium frame, 21-speed.",
    },
    {
        "number": "1100",
        "displayName": "Front Wheel",
        "type": "Inventory",
        "unitPrice": 1000.0,
        "priceIncludesTax": False,
        "inventory": 120,
        "baseUnitOfMeasureCode": "PCS",
        "itemCategoryCode": "SPARE",
        "description": "Spare front wheel, 26 inch.",
    },
    {
        "number": "1200",
        "displayName": "Chain Assy",
        "type": "Inventory",
        "unitPrice": 350.0,
        "priceIncludesTax": False,
        "inventory": 8,
        "baseUnitOfMeasureCode": "PCS",
        "itemCategoryCode": "SPARE",
        "description": "Bicycle chain assembly, rust-resistant.",
    },
    {
        "number": "1900",
        "displayName": "Paris Guest Chair, black",
        "type": "Inventory",
        "unitPrice": 1200.0,
        "priceIncludesTax": False,
        "inventory": 45,
        "baseUnitOfMeasureCode": "PCS",
        "itemCategoryCode": "CHAIR",
        "description": "Ergonomic guest chair with black upholstery.",
    },
]

_CUSTOMERS = [
    {
        "number": "10000",
        "displayName": "Adatum Corporation",
        "email": "robert.townes@adatum.com",
        "phoneNumber": "+91 22 5550 100",
        "addressLine1": "192 Market Square",
        "city": "Mumbai",
        "country": "IN",
        "balanceDue": 12500.0,
        "creditLimit": 100000.0,
        "blocked": " ",
    },
    {
        "number": "20000",
        "displayName": "Trey Research",
        "email": "helen.ray@treyresearch.net",
        "phoneNumber": "+91 80 5550 200",
        "addressLine1": "38 Rockwell Lane",
        "city": "Bengaluru",
        "country": "IN",
        "balanceDue": 0.0,
        "creditLimit": 50000.0,
        "blocked": " ",
    },
    {
        "number": "30000",
        "displayName": "School of Fine Art",
        "email": "meagan.bond@sofa.edu",
        "phoneNumber": "+91 11 5550 300",
        "addressLine1": "10 Kings Road",
        "city": "New Delhi",
        "country": "IN",
        "balanceDue": 4200.0,
        "creditLimit": 25000.0,
        "blocked": " ",
    },
]

_SALES_ORDERS = [
    {
        "number": "SO-000001",
        "orderDate": "2026-06-14",
        "customerNumber": "10000",
        "customerName": "Adatum Corporation",
        "itemNumber": "1000",
        "itemDescription": "Bicycle",
        "quantity": 5,
        "unitPrice": 4000.0,
        "totalAmountExcludingTax": 20000.0,
        "totalAmountIncludingTax": 23600.0,
        "status": "Open",
    },
    {
        "number": "SO-000002",
        "orderDate": "2026-06-20",
        "customerNumber": "20000",
        "customerName": "Trey Research",
        "itemNumber": "1900",
        "itemDescription": "Paris Guest Chair, black",
        "quantity": 12,
        "unitPrice": 1200.0,
        "totalAmountExcludingTax": 14400.0,
        "totalAmountIncludingTax": 16992.0,
        "status": "Released",
    },
    {
        "number": "SO-000003",
        "orderDate": "2026-07-02",
        "customerNumber": "30000",
        "customerName": "School of Fine Art",
        "itemNumber": "1200",
        "itemDescription": "Chain Assy",
        "quantity": 40,
        "unitPrice": 350.0,
        "totalAmountExcludingTax": 14000.0,
        "totalAmountIncludingTax": 16520.0,
        "status": "Open",
    },
]

# Keyed by the standard BC API entity name.
SAMPLE_DATA: dict[str, list[dict]] = {
    "items": _ITEMS,
    "customers": _CUSTOMERS,
    "salesOrders": _SALES_ORDERS,
}


def sample_records(entity: str) -> list[dict]:
    """Return bundled sample records for ``entity`` (empty list if unknown)."""
    return SAMPLE_DATA.get(entity, [])
