"""
tools/payment_service.py - Payment Processing Service

Handles all payment-related operations:
- Refunds
- Order cancellations (with refund)
- Price adjustments

In production, this would integrate with payment gateways:
- Stripe
- Adyen
- PayPal
- Square
"""

import random
from datetime import datetime
from typing import Optional

from models import Order
from tools.mock_database import get_order_by_id


def _generate_transaction_id(prefix: str) -> str:
    """Generates a unique transaction ID"""
    return f"{prefix}-{random.randint(10000, 99999)}"


def process_refund(
    order_id: str,
    amount: float,
    reason: str,
    approved_by: Optional[str] = None
) -> dict:
    """
    Executes a refund through the payment gateway.
    
    In production, this would:
    - Call payment gateway API (Stripe, Adyen, etc.)
    - Handle partial vs full refunds
    - Update order status in OMS
    - Trigger customer notification email
    - Create audit trail in compliance system
    
    Args:
        order_id: Order to refund
        amount: Refund amount in dollars
        reason: Reason for refund (stored for records)
        approved_by: Employee ID if human-approved, None for auto-approved
        
    Returns:
        Dict with refund confirmation details
        
    Example:
        >>> result = process_refund("ORD-1001", 29.99, "Item didn't fit")
        >>> print(result["refund_id"])
        REF-12345
    """
    refund_id = _generate_transaction_id("REF")
    
    # In production, validate the order exists and can be refunded
    order = get_order_by_id(order_id)
    if not order:
        return {
            "success": False,
            "error": f"Order {order_id} not found"
        }
    
    # In production, call payment gateway:
    # refund = stripe.Refund.create(
    #     payment_intent=order.payment_intent_id,
    #     amount=int(amount * 100)  # Stripe uses cents
    # )
    
    return {
        "success": True,
        "refund_id": refund_id,
        "order_id": order_id,
        "amount": amount,
        "currency": "USD",
        "reason": reason,
        "approved_by": approved_by or "AUTO",
        "processed_at": datetime.now().isoformat(),
        "message": f"Refund of ${amount:.2f} processed successfully"
    }


def cancel_order(
    order_id: str,
    reason: str,
    approved_by: Optional[str] = None
) -> dict:
    """
    Cancels an order in the Order Management System.
    
    This is a complex operation that in production would:
    - Verify order can be cancelled (not yet shipped)
    - Update OMS status to 'cancelled'
    - Cancel any pending fulfillment tasks
    - Release inventory holds
    - Process full refund if payment was captured
    - Notify warehouse/fulfillment center
    - Send customer cancellation email
    - Update analytics/reporting
    
    Args:
        order_id: Order to cancel
        reason: Cancellation reason
        approved_by: Employee ID if human-approved
        
    Returns:
        Dict with cancellation confirmation
    """
    order = get_order_by_id(order_id)
    
    if not order:
        return {
            "success": False,
            "error": f"Order {order_id} not found"
        }
    
    cancellation_id = _generate_transaction_id("CAN")
    
    return {
        "success": True,
        "cancellation_id": cancellation_id,
        "order_id": order_id,
        "previous_status": "confirmed",
        "new_status": "cancelled",
        "refund_initiated": True,
        "refund_amount": order.order_total,
        "reason": reason,
        "approved_by": approved_by or "AUTO",
        "cancelled_at": datetime.now().isoformat(),
        "message": f"Order {order_id} cancelled. Refund of ${order.order_total:.2f} initiated."
    }


def apply_price_adjustment(
    order_id: str,
    adjustment_amount: float,
    reason: str,
    approved_by: Optional[str] = None
) -> dict:
    """
    Applies a price adjustment (partial refund) to an order.
    
    Common scenarios:
    - Price match guarantee (competitor had lower price)
    - Goodwill gesture for service issues
    - Promotional code applied retroactively
    - Damaged item partial refund (customer keeps item)
    - Loyalty program credit
    
    Args:
        order_id: Order to adjust
        adjustment_amount: Amount to credit back
        reason: Adjustment reason
        approved_by: Employee ID if human-approved
        
    Returns:
        Dict with adjustment confirmation
    """
    order = get_order_by_id(order_id)
    
    if not order:
        return {
            "success": False,
            "error": f"Order {order_id} not found"
        }
    
    # Validate adjustment doesn't exceed order total
    if adjustment_amount > order.order_total:
        return {
            "success": False,
            "error": f"Adjustment ${adjustment_amount:.2f} exceeds order total ${order.order_total:.2f}"
        }
    
    adjustment_id = _generate_transaction_id("ADJ")
    
    return {
        "success": True,
        "adjustment_id": adjustment_id,
        "order_id": order_id,
        "adjustment_amount": adjustment_amount,
        "adjustment_type": "credit",
        "original_order_total": order.order_total,
        "new_effective_total": order.order_total - adjustment_amount,
        "reason": reason,
        "approved_by": approved_by or "AUTO",
        "applied_at": datetime.now().isoformat(),
        "message": f"Price adjustment of ${adjustment_amount:.2f} applied to order {order_id}"
    }