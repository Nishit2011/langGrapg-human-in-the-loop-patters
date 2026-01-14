"""
models.py - Domain models for the Order Exception Resolution Agent

These models represent the core business objects in our retail HITL system.
Using Pydantic ensures data validation and clear contracts between components.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CustomerTier(str, Enum):
    """
    Customer loyalty tiers - VIP customers require human approval
    for any exception handling to maintain relationship quality.
    """
    STANDARD = "standard"
    PREFERRED = "preferred"
    VIP = "vip"


class ExceptionType(str, Enum):
    """
    Types of order exceptions our agent can handle.
    Each type has different approval thresholds and workflows.
    """
    REFUND = "refund"           # Money back to customer
    CANCELLATION = "cancel"      # Cancel order before shipment
    PRICE_ADJUSTMENT = "adjust"  # Partial refund for price match/complaint


class RequestStatus(str, Enum):
    """
    Tracks the lifecycle of an exception request through our system.
    PENDING_APPROVAL is the key state for human-in-the-loop.
    """
    RECEIVED = "received"                    # Just came in
    ANALYZING = "analyzing"                  # Agent is evaluating
    PENDING_APPROVAL = "pending_approval"    # Waiting for human decision
    APPROVED = "approved"                    # Human said yes
    REJECTED = "rejected"                    # Human said no
    COMPLETED = "completed"                  # Action executed
    FAILED = "failed"                        # Something went wrong


class Customer(BaseModel):
    """
    Customer information relevant to exception handling decisions.
    VIP status and lifetime value influence approval requirements.
    """
    customer_id: str = Field(..., description="Unique customer identifier")
    name: str = Field(..., description="Customer full name")
    email: str = Field(..., description="Customer email for notifications")
    tier: CustomerTier = Field(default=CustomerTier.STANDARD)
    lifetime_value: float = Field(
        default=0.0, 
        description="Total spend - high LTV customers get priority handling"
    )


class OrderItem(BaseModel):
    """
    Individual item within an order.
    We track this separately because multi-item exceptions need approval.
    """
    sku: str = Field(..., description="Product SKU")
    name: str = Field(..., description="Product display name")
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    
    @property
    def total_price(self) -> float:
        """Calculate line item total"""
        return self.quantity * self.unit_price


class Order(BaseModel):
    """
    Order details needed for exception processing.
    Contains the items and financial info for refund calculations.
    """
    order_id: str = Field(..., description="Unique order identifier")
    customer: Customer
    items: list[OrderItem] = Field(default_factory=list)
    order_total: float = Field(..., ge=0)
    order_date: datetime = Field(default_factory=datetime.now)
    
    @property
    def item_count(self) -> int:
        """Total number of items (considering quantities)"""
        return sum(item.quantity for item in self.items)


class ExceptionRequest(BaseModel):
    """
    The incoming request from customer service or automated systems.
    This is the primary input to our HITL agent.
    """
    request_id: str = Field(..., description="Unique request tracking ID")
    order: Order
    exception_type: ExceptionType
    reason: str = Field(..., description="Customer's stated reason")
    requested_amount: Optional[float] = Field(
        None, 
        description="Amount requested for refund/adjustment (None = full refund)"
    )
    
    @property
    def effective_amount(self) -> float:
        """
        The actual amount we're considering for this exception.
        If not specified, defaults to full order total.
        """
        return self.requested_amount or self.order.order_total


class AgentDecision(BaseModel):
    """
    The agent's recommendation after analyzing the request.
    This gets sent to humans for approval when thresholds are exceeded.
    """
    should_approve: bool = Field(..., description="Agent's recommendation")
    recommended_amount: float = Field(..., description="Suggested refund/adjustment")
    reasoning: str = Field(..., description="Explanation for the decision")
    requires_human_approval: bool = Field(
        default=False,
        description="True if this exceeds auto-approval thresholds"
    )
    approval_reasons: list[str] = Field(
        default_factory=list,
        description="Why human approval is needed"
    )


class HumanReview(BaseModel):
    """
    Captures the human reviewer's decision.
    This is the core of our human-in-the-loop pattern.
    """
    reviewer_id: str = Field(..., description="Employee ID of reviewer")
    approved: bool
    adjusted_amount: Optional[float] = Field(
        None, 
        description="Human can modify the amount"
    )
    notes: Optional[str] = Field(None, description="Reviewer comments")
    reviewed_at: datetime = Field(default_factory=datetime.now)


class AgentState(BaseModel):
    """
    The complete state that flows through our LangGraph.
    This is the central data structure the graph nodes read and write.
    
    LangGraph uses this state to:
    1. Pass data between nodes
    2. Persist state for human-in-the-loop interrupts
    3. Resume execution after human input
    """
    # Input
    request: ExceptionRequest
    
    # Processing state
    status: RequestStatus = Field(default=RequestStatus.RECEIVED)
    
    # Agent's analysis
    decision: Optional[AgentDecision] = None
    
    # Human review (populated when HITL is triggered)
    human_review: Optional[HumanReview] = None
    
    # Output
    final_amount: Optional[float] = None
    result_message: Optional[str] = None
    
    # Audit trail
    processing_log: list[str] = Field(default_factory=list)
    
    def add_log(self, message: str) -> None:
        """Add timestamped entry to processing log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.processing_log.append(f"[{timestamp}] {message}")