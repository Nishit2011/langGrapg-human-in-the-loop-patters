"""
tools/mock_database.py - Simulated Order Management System

Mock data representing your OMS (Order Management System).
In production, this would be replaced with actual API calls to:
- Shopify / Magento / Custom OMS
- SAP / Oracle ERP
- Your internal order database

This module is isolated so it's easy to swap for real integrations.
"""

from datetime import datetime, timedelta
from typing import Optional  # <-- Add this import

from models import (
    Customer,
    CustomerTier,
    Order,
    OrderItem,
)


def _create_mock_customers() -> dict[str, Customer]:
    """
    Creates sample customers representing different tiers.
    
    Returns:
        Dict mapping customer_id to Customer object
    """
    return {
        "CUST-001": Customer(
            customer_id="CUST-001",
            name="Alice Johnson",
            email="alice@example.com",
            tier=CustomerTier.STANDARD,
            lifetime_value=450.00
        ),
        "CUST-002": Customer(
            customer_id="CUST-002",
            name="Bob Smith",
            email="bob@example.com",
            tier=CustomerTier.VIP,
            lifetime_value=15000.00
        ),
        "CUST-003": Customer(
            customer_id="CUST-003",
            name="Carol Williams",
            email="carol@example.com",
            tier=CustomerTier.PREFERRED,
            lifetime_value=2500.00
        ),
    }


def _create_mock_orders(customers: dict[str, Customer]) -> dict[str, Order]:
    """
    Creates sample orders with varying characteristics.
    Each order is designed to test different HITL scenarios.
    
    Args:
        customers: Dict of available customers
        
    Returns:
        Dict mapping order_id to Order object
    """
    return {
        # Small order - should auto-approve (under $100, standard customer)
        "ORD-1001": Order(
            order_id="ORD-1001",
            customer=customers["CUST-001"],
            items=[
                OrderItem(
                    sku="SKU-A1",
                    name="Basic T-Shirt",
                    quantity=1,
                    unit_price=29.99
                ),
            ],
            order_total=29.99,
            order_date=datetime.now() - timedelta(days=3)
        ),
        
        # Large order - exceeds $100 threshold, needs approval
        "ORD-1002": Order(
            order_id="ORD-1002",
            customer=customers["CUST-001"],
            items=[
                OrderItem(
                    sku="SKU-B1",
                    name="Designer Jacket",
                    quantity=1,
                    unit_price=249.99
                ),
                OrderItem(
                    sku="SKU-B2",
                    name="Premium Jeans",
                    quantity=1,
                    unit_price=89.99
                ),
            ],
            order_total=339.98,
            order_date=datetime.now() - timedelta(days=5)
        ),
        
        # VIP customer - always needs approval regardless of amount
        "ORD-1003": Order(
            order_id="ORD-1003",
            customer=customers["CUST-002"],
            items=[
                OrderItem(
                    sku="SKU-C1",
                    name="Silk Scarf",
                    quantity=1,
                    unit_price=75.00
                ),
            ],
            order_total=75.00,
            order_date=datetime.now() - timedelta(days=2)
        ),
        
        # Multi-item order - needs approval due to complexity (>2 items)
        "ORD-1004": Order(
            order_id="ORD-1004",
            customer=customers["CUST-003"],
            items=[
                OrderItem(
                    sku="SKU-D1",
                    name="Casual Shirt",
                    quantity=2,
                    unit_price=45.00
                ),
                OrderItem(
                    sku="SKU-D2",
                    name="Dress Pants",
                    quantity=1,
                    unit_price=65.00
                ),
                OrderItem(
                    sku="SKU-D3",
                    name="Belt",
                    quantity=1,
                    unit_price=35.00
                ),
            ],
            order_total=190.00,
            order_date=datetime.now() - timedelta(days=7)
        ),
    }


# Initialize mock database on module load
_CUSTOMERS = _create_mock_customers()
_ORDERS = _create_mock_orders(_CUSTOMERS)


def get_all_orders() -> dict[str, Order]:
    """Returns all orders in the mock database"""
    return _ORDERS.copy()


def get_order_by_id(order_id: str) -> Optional[Order]:  # <-- Fixed: Order | None -> Optional[Order]
    """
    Retrieves a single order by ID.
    
    Args:
        order_id: The order identifier
        
    Returns:
        Order if found, None otherwise
    """
    return _ORDERS.get(order_id)


def get_all_customers() -> dict[str, Customer]:
    """Returns all customers in the mock database"""
    return _CUSTOMERS.copy()


def get_customer_by_id(customer_id: str) -> Optional[Customer]:  # <-- Fixed: Customer | None -> Optional[Customer]
    """
    Retrieves a single customer by ID.
    
    Args:
        customer_id: The customer identifier
        
    Returns:
        Customer if found, None otherwise
    """
    return _CUSTOMERS.get(customer_id)