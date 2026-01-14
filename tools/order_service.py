"""
tools/order_service.py - Order Management Service

Handles all order-related operations.
In production, this would integrate with your OMS API.
"""

from typing import Optional

from models import Order
from tools.mock_database import get_order_by_id


def get_order_details(order_id: str) -> Optional[Order]:
    """
    Retrieves order details from the Order Management System.
    
    In production, this would:
    - Call your OMS API (e.g., Shopify, Magento, custom system)
    - Handle authentication and error cases
    - Implement retry logic for transient failures
    - Cache frequently accessed orders
    - Map external data to our Order model
    
    Args:
        order_id: The unique order identifier
        
    Returns:
        Order object if found, None otherwise
        
    Example:
        >>> order = get_order_details("ORD-1001")
        >>> if order:
        ...     print(f"Found order for {order.customer.name}")
    """
    # In production, this might look like:
    # response = await oms_client.get(f"/orders/{order_id}")
    # return Order.model_validate(response.json())
    
    return get_order_by_id(order_id)


def check_order_status(order_id: str) -> dict:
    """
    Checks the current status of an order.
    
    Useful for determining if an order can be cancelled
    (e.g., not yet shipped).
    
    Args:
        order_id: The order identifier
        
    Returns:
        Dict with status information
    """
    order = get_order_by_id(order_id)
    
    if not order:
        return {
            "found": False,
            "error": f"Order {order_id} not found"
        }
    
    # Mock status - in production, fetch from OMS
    return {
        "found": True,
        "order_id": order_id,
        "status": "confirmed",
        "can_cancel": True,
        "can_refund": True,
        "shipped": False
    }