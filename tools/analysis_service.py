"""
tools/analysis_service.py - Exception Analysis Service

Core business logic for analyzing exception requests.
This is where HITL (Human-in-the-Loop) decisions are made.

This module determines:
1. Whether a request should be approved
2. Whether human review is required
3. The recommended amount for refunds/adjustments
"""

from typing import Optional, Tuple  # <-- Add Tuple import

from models import (
    ExceptionRequest,
    ExceptionType,
    AgentDecision,
    CustomerTier,
)
from tools.config import HITL_CONFIG


def _check_amount_threshold(amount: float) -> Tuple[bool, Optional[str]]:  # <-- Fixed
    """
    Checks if amount exceeds auto-approval threshold.
    
    Args:
        amount: The requested refund/adjustment amount
        
    Returns:
        Tuple of (exceeds_threshold, reason_if_exceeded)
    """
    threshold = HITL_CONFIG["max_auto_approve_amount"]
    
    if amount > threshold:
        return (
            True,
            f"Amount ${amount:.2f} exceeds auto-approve limit of ${threshold:.2f}"
        )
    
    return (False, None)


def _check_vip_status(tier: CustomerTier, customer_name: str) -> Tuple[bool, Optional[str]]:  # <-- Fixed
    """
    Checks if customer is VIP and requires special handling.
    
    Args:
        tier: Customer's loyalty tier
        customer_name: Customer's name for the reason message
        
    Returns:
        Tuple of (is_vip_requiring_approval, reason_if_required)
    """
    if tier == CustomerTier.VIP and HITL_CONFIG["vip_always_approve"]:
        return (
            True,
            f"Customer {customer_name} is VIP tier - requires personalized handling"
        )
    
    return (False, None)


def _check_item_complexity(item_count: int) -> Tuple[bool, Optional[str]]:  # <-- Fixed
    """
    Checks if order has too many items for auto-processing.
    
    Args:
        item_count: Total number of items in the order
        
    Returns:
        Tuple of (exceeds_threshold, reason_if_exceeded)
    """
    threshold = HITL_CONFIG["multi_item_threshold"]
    
    if item_count > threshold:
        return (
            True,
            f"Order has {item_count} items - complex exception needs review"
        )
    
    return (False, None)


def _analyze_request_reason(reason: str) -> Tuple[bool, Optional[str]]:  # <-- Fixed
    """
    Analyzes the request reason for concerning signals.
    
    In production, this could use:
    - NLP/sentiment analysis
    - Fraud detection models
    - Pattern matching against known issues
    
    Args:
        reason: Customer's stated reason for the exception
        
    Returns:
        Tuple of (has_concerning_signals, description_if_found)
    """
    reason_lower = reason.lower()
    
    # Keywords that suggest potential issues
    negative_signals = ["fraud", "unauthorized", "dispute", "chargeback", "stolen"]
    
    for signal in negative_signals:
        if signal in reason_lower:
            return (True, f"Request contains concerning keyword: '{signal}'")
    
    return (False, None)


def _calculate_recommended_amount(
    request: ExceptionRequest
) -> Tuple[float, Optional[str]]:  # <-- Fixed
    """
    Calculates the recommended refund/adjustment amount.
    
    Applies business rules like:
    - Full refund for returns
    - Capped percentages for price adjustments
    - Prorated refunds for partial returns
    
    Args:
        request: The exception request
        
    Returns:
        Tuple of (recommended_amount, explanation_if_adjusted)
    """
    amount = request.effective_amount
    order_total = request.order.order_total
    
    # Price adjustments are typically capped
    if request.exception_type == ExceptionType.PRICE_ADJUSTMENT:
        max_adjustment = order_total * 0.20  # Max 20% of order total
        
        if amount > max_adjustment:
            return (
                max_adjustment,
                f"Price adjustment capped at 20% of order total (${max_adjustment:.2f})"
            )
    
    return (amount, None)


def analyze_exception_request(request: ExceptionRequest) -> AgentDecision:
    """
    Core analysis logic - determines if request should be approved
    and whether human review is required.
    
    This function orchestrates all the individual checks and
    compiles them into a final decision.
    
    Args:
        request: The exception request to analyze
        
    Returns:
        AgentDecision with recommendation and HITL requirements
        
    Example:
        >>> decision = analyze_exception_request(request)
        >>> if decision.requires_human_approval:
        ...     print(f"Needs review: {decision.approval_reasons}")
    """
    approval_reasons: list[str] = []
    reasoning_parts: list[str] = []
    
    order = request.order
    customer = order.customer
    amount = request.effective_amount
    
    # ----- Check 1: Amount threshold -----
    exceeds_amount, amount_reason = _check_amount_threshold(amount)
    if exceeds_amount and amount_reason:
        approval_reasons.append(amount_reason)
        reasoning_parts.append(f"High-value request (${amount:.2f})")
    
    # ----- Check 2: VIP status -----
    is_vip, vip_reason = _check_vip_status(customer.tier, customer.name)
    if is_vip and vip_reason:
        approval_reasons.append(vip_reason)
        reasoning_parts.append("VIP customer requires white-glove service")
    
    # ----- Check 3: Item complexity -----
    is_complex, complexity_reason = _check_item_complexity(order.item_count)
    if is_complex and complexity_reason:
        approval_reasons.append(complexity_reason)
        reasoning_parts.append(f"Multi-item order ({order.item_count} items)")
    
    # ----- Check 4: Reason analysis -----
    has_concerns, concern_description = _analyze_request_reason(request.reason)
    should_approve = not has_concerns
    
    if has_concerns and concern_description:
        reasoning_parts.append(concern_description)
    
    # ----- Calculate recommended amount -----
    recommended_amount, amount_note = _calculate_recommended_amount(request)
    if amount_note:
        reasoning_parts.append(amount_note)
    
    # ----- Build final reasoning -----
    if not reasoning_parts:
        reasoning_parts.append("Standard request within normal parameters")
    
    reasoning = ". ".join(reasoning_parts) + "."
    
    # ----- Compile decision -----
    return AgentDecision(
        should_approve=should_approve,
        recommended_amount=recommended_amount,
        reasoning=reasoning,
        requires_human_approval=len(approval_reasons) > 0,
        approval_reasons=approval_reasons
    )