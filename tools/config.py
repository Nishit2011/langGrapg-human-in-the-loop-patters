"""
tools/config.py - Configuration for HITL thresholds

Centralized configuration for human-in-the-loop triggers.
In production, these would come from:
- Environment variables
- Configuration service (Consul, AWS Parameter Store)
- Database-driven feature flags
"""

from typing import TypedDict


class HITLConfigType(TypedDict):
    """Type definition for HITL configuration"""
    max_auto_approve_amount: float
    vip_always_approve: bool
    multi_item_threshold: int


# Human-in-the-Loop trigger thresholds
HITL_CONFIG: HITLConfigType = {
    # Refunds above this amount require human approval
    "max_auto_approve_amount": 100.00,
    
    # VIP customers always get human review for personalized service
    "vip_always_approve": True,
    
    # Orders with more than this many items need review due to complexity
    "multi_item_threshold": 2,
}


def get_config() -> HITLConfigType:
    """
    Returns current HITL configuration.
    
    In production, this might:
    - Fetch from environment variables
    - Call a configuration service
    - Apply A/B test variations
    """
    return HITL_CONFIG.copy()


def update_config(updates: dict) -> None:
    """
    Updates HITL configuration at runtime.
    
    Useful for:
    - Feature flag changes
    - A/B testing different thresholds
    - Emergency threshold adjustments
    
    Args:
        updates: Dict of config keys to new values
    """
    for key, value in updates.items():
        if key in HITL_CONFIG:
            HITL_CONFIG[key] = value  # type: ignore