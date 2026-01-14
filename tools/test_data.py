"""
tools/test_data.py - Test Data Generator

Provides sample exception requests for testing the agent.
Each request is designed to test a specific HITL scenario.
"""

from models import ExceptionRequest, ExceptionType
from tools.mock_database import get_all_orders


def get_sample_requests() -> list[ExceptionRequest]:
    """
    Returns sample exception requests for testing the agent.
    
    These cover the four main scenarios:
    1. Auto-approve: Small amount, standard customer
    2. HITL (amount): Large refund exceeds threshold
    3. HITL (VIP): VIP customer requires personal touch
    4. HITL (complexity): Multi-item order needs review
    
    Returns:
        List of ExceptionRequest objects
        
    Example:
        >>> requests = get_sample_requests()
        >>> for req in requests:
        ...     print(f"{req.request_id}: {req.exception_type.value}")
    """
    orders = get_all_orders()
    
    return [
        # ----- Scenario 1: AUTO-APPROVE -----
        # Small refund ($29.99), standard customer
        # Should process automatically without human intervention
        ExceptionRequest(
            request_id="REQ-001",
            order=orders["ORD-1001"],
            exception_type=ExceptionType.REFUND,
            reason="Item didn't fit as expected, requesting full refund",
            requested_amount=None  # None = full refund
        ),
        
        # ----- Scenario 2: HITL - Amount Threshold -----
        # Large refund ($339.98) exceeds $100 threshold
        # Needs human approval due to financial impact
        ExceptionRequest(
            request_id="REQ-002",
            order=orders["ORD-1002"],
            exception_type=ExceptionType.REFUND,
            reason="Quality not as expected, items had loose threads",
            requested_amount=None
        ),
        
        # ----- Scenario 3: HITL - VIP Customer -----
        # VIP customer ($75.00 order - under threshold)
        # Still needs approval for white-glove service
        ExceptionRequest(
            request_id="REQ-003",
            order=orders["ORD-1003"],
            exception_type=ExceptionType.CANCELLATION,
            reason="Changed my mind, found similar item elsewhere",
            requested_amount=None
        ),
        
        # ----- Scenario 4: HITL - Multi-Item Complexity -----
        # 4 items in order, requesting price adjustment
        # Complex case needs human judgment
        ExceptionRequest(
            request_id="REQ-004",
            order=orders["ORD-1004"],
            exception_type=ExceptionType.PRICE_ADJUSTMENT,
            reason="Saw items on sale a week after purchase, requesting price match",
            requested_amount=50.00
        ),
    ]


def get_auto_approve_request() -> ExceptionRequest:
    """Returns a single request that should auto-approve"""
    return get_sample_requests()[0]


def get_high_value_request() -> ExceptionRequest:
    """Returns a request that triggers HITL due to amount"""
    return get_sample_requests()[1]


def get_vip_request() -> ExceptionRequest:
    """Returns a request that triggers HITL due to VIP status"""
    return get_sample_requests()[2]


def get_complex_request() -> ExceptionRequest:
    """Returns a request that triggers HITL due to item count"""
    return get_sample_requests()[3]