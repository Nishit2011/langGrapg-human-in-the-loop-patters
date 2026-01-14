"""
graph.py - LangGraph workflow for Order Exception Resolution

This module defines the state machine that processes exception requests.
The key feature is the HUMAN-IN-THE-LOOP pattern using LangGraph's
interrupt mechanism.

Flow:
    ┌─────────────┐
    │   START     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  analyze    │  ← Evaluates request, determines if HITL needed
    └──────┬──────┘
           │
           ▼
    ┌─────────────────┐
    │ requires_human? │  ← Conditional routing
    └────┬───────┬────┘
         │       │
    NO   │       │  YES
         │       │
         ▼       ▼
    ┌────────┐  ┌──────────────┐
    │execute │  │ human_review │  ← INTERRUPT HAPPENS HERE
    └───┬────┘  └──────┬───────┘
        │              │
        │              ▼
        │       ┌─────────────────┐
        │       │ process_review  │  ← Handles approval/rejection
        │       └────────┬────────┘
        │                │
        │       ┌────────┴────────┐
        │       │                 │
        │   APPROVED          REJECTED
        │       │                 │
        │       ▼                 ▼
        │  ┌─────────┐     ┌──────────┐
        │  │ execute │     │ rejected │
        │  └────┬────┘     └────┬─────┘
        │       │               │
        └───────┴───────┬───────┘
                        │
                        ▼
                 ┌─────────────┐
                 │     END     │
                 └─────────────┘
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from models import (
    AgentState,
    RequestStatus,
    ExceptionType,
    HumanReview,
)
from tools import (
    analyze_exception_request,
    process_refund,
    cancel_order,
    apply_price_adjustment,
)


# =============================================================================
# NODE: Analyze Request
# =============================================================================

def analyze_node(state: AgentState) -> dict:
    """
    Analyzes the exception request and determines next steps.
    
    This node:
    1. Runs the analysis logic from our tools
    2. Updates state with the decision
    3. Logs the analysis for audit trail
    
    Args:
        state: Current workflow state
        
    Returns:
        Dict of state updates (LangGraph merges this with existing state)
    """
    state.add_log(f"Analyzing request {state.request.request_id}")
    
    # Run our analysis service
    decision = analyze_exception_request(state.request)
    
    # Log the decision
    state.add_log(f"Analysis complete: recommend_approve={decision.should_approve}")
    state.add_log(f"Requires human approval: {decision.requires_human_approval}")
    
    if decision.requires_human_approval:
        for reason in decision.approval_reasons:
            state.add_log(f"  → {reason}")
    
    # Return state updates
    # LangGraph will merge these into the existing state
    return {
        "status": RequestStatus.PENDING_APPROVAL if decision.requires_human_approval else RequestStatus.APPROVED,
        "decision": decision,
        "processing_log": state.processing_log  # Include updated log
    }


# =============================================================================
# NODE: Human Review (INTERRUPT POINT)
# =============================================================================

def human_review_node(state: AgentState) -> dict:
    """
    INTERRUPT POINT - Pauses execution for human input.
    
    This node doesn't do any processing itself. It serves as a marker
    where the graph will pause and wait for human input.
    
    When the graph is interrupted here:
    1. The current state is persisted (via checkpointer)
    2. Control returns to the calling code
    3. Human provides their review via `graph.update_state()`
    4. Graph resumes from this point
    
    The actual human review data comes from outside the graph
    via state updates, not from this function.
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates (just logging in this case)
    """
    state.add_log("Awaiting human review...")
    state.add_log(f"Recommended amount: ${state.decision.recommended_amount:.2f}")
    state.add_log(f"Agent recommendation: {'APPROVE' if state.decision.should_approve else 'REJECT'}")
    
    return {
        "processing_log": state.processing_log
    }


# =============================================================================
# NODE: Process Human Review
# =============================================================================

def process_review_node(state: AgentState) -> dict:
    """
    Processes the human reviewer's decision.
    
    This node runs AFTER the human has provided their review.
    It updates the state based on whether they approved or rejected.
    
    Args:
        state: Current workflow state (now includes human_review)
        
    Returns:
        State updates with final amounts and status
    """
    review = state.human_review
    
    if review is None:
        # This shouldn't happen if graph is used correctly
        state.add_log("ERROR: No human review found")
        return {
            "status": RequestStatus.FAILED,
            "result_message": "Human review was required but not provided",
            "processing_log": state.processing_log
        }
    
    state.add_log(f"Human review received from {review.reviewer_id}")
    state.add_log(f"Decision: {'APPROVED' if review.approved else 'REJECTED'}")
    
    if review.approved:
        # Use adjusted amount if provided, otherwise use recommended
        final_amount = review.adjusted_amount or state.decision.recommended_amount
        state.add_log(f"Final approved amount: ${final_amount:.2f}")
        
        if review.notes:
            state.add_log(f"Reviewer notes: {review.notes}")
        
        return {
            "status": RequestStatus.APPROVED,
            "final_amount": final_amount,
            "processing_log": state.processing_log
        }
    else:
        # Rejected
        state.add_log(f"Rejection reason: {review.notes or 'No reason provided'}")
        
        return {
            "status": RequestStatus.REJECTED,
            "result_message": f"Request rejected by {review.reviewer_id}: {review.notes or 'No reason provided'}",
            "processing_log": state.processing_log
        }


# =============================================================================
# NODE: Execute Action
# =============================================================================

def execute_node(state: AgentState) -> dict:
    """
    Executes the approved action (refund, cancel, or adjust).
    
    This node is reached when:
    - Request was auto-approved (no HITL needed), OR
    - Human approved the request
    
    Args:
        state: Current workflow state
        
    Returns:
        State updates with execution results
    """
    request = state.request
    
    # Determine final amount
    final_amount = state.final_amount or state.decision.recommended_amount
    
    # Get approver info (if human approved)
    approved_by = state.human_review.reviewer_id if state.human_review else None
    
    state.add_log(f"Executing {request.exception_type.value} for ${final_amount:.2f}")
    
    # Execute the appropriate action based on exception type
    if request.exception_type == ExceptionType.REFUND:
        result = process_refund(
            order_id=request.order.order_id,
            amount=final_amount,
            reason=request.reason,
            approved_by=approved_by
        )
        
    elif request.exception_type == ExceptionType.CANCELLATION:
        result = cancel_order(
            order_id=request.order.order_id,
            reason=request.reason,
            approved_by=approved_by
        )
        
    elif request.exception_type == ExceptionType.PRICE_ADJUSTMENT:
        result = apply_price_adjustment(
            order_id=request.order.order_id,
            adjustment_amount=final_amount,
            reason=request.reason,
            approved_by=approved_by
        )
    else:
        result = {"success": False, "error": f"Unknown exception type: {request.exception_type}"}
    
    # Log result
    if result.get("success"):
        state.add_log(f"Action completed successfully: {result.get('message')}")
        return {
            "status": RequestStatus.COMPLETED,
            "final_amount": final_amount,
            "result_message": result.get("message"),
            "processing_log": state.processing_log
        }
    else:
        state.add_log(f"Action failed: {result.get('error')}")
        return {
            "status": RequestStatus.FAILED,
            "result_message": result.get("error"),
            "processing_log": state.processing_log
        }


# =============================================================================
# NODE: Rejected Handler
# =============================================================================

def rejected_node(state: AgentState) -> dict:
    """
    Handles rejected requests.
    
    This node is reached when human reviewer rejects the request.
    In production, this might:
    - Send notification to customer
    - Log for compliance
    - Trigger escalation workflow
    
    Args:
        state: Current workflow state
        
    Returns:
        Final state updates
    """
    state.add_log("Request rejected - no action taken")
    state.add_log(f"Final status: {state.status.value}")
    
    return {
        "processing_log": state.processing_log
    }


# =============================================================================
# ROUTING: Conditional Edge Logic
# =============================================================================

def route_after_analysis(state: AgentState) -> Literal["human_review", "execute"]:
    """
    Determines next step after analysis.
    
    Routes to:
    - human_review: If HITL is required
    - execute: If auto-approval is allowed
    
    Args:
        state: Current workflow state
        
    Returns:
        Name of the next node
    """
    if state.decision and state.decision.requires_human_approval:
        return "human_review"
    return "execute"


def route_after_review(state: AgentState) -> Literal["execute", "rejected"]:
    """
    Determines next step after human review.
    
    Routes to:
    - execute: If human approved
    - rejected: If human rejected
    
    Args:
        state: Current workflow state
        
    Returns:
        Name of the next node
    """
    if state.human_review and state.human_review.approved:
        return "execute"
    return "rejected"


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def create_exception_graph() -> StateGraph:
    """
    Creates and compiles the exception handling workflow graph.
    
    This function:
    1. Defines all nodes (processing steps)
    2. Defines edges (transitions between nodes)
    3. Sets up conditional routing
    4. Configures the interrupt point for HITL
    
    Returns:
        Compiled StateGraph ready for execution
    """
    
    # Initialize the graph with our state schema
    # AgentState defines what data flows through the graph
    builder = StateGraph(AgentState)
    
    # ----- Add Nodes -----
    # Each node is a function that takes state and returns updates
    builder.add_node("analyze", analyze_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("process_review", process_review_node)
    builder.add_node("execute", execute_node)
    builder.add_node("rejected", rejected_node)
    
    # ----- Add Edges -----
    
    # START → analyze (entry point)
    builder.add_edge(START, "analyze")
    
    # analyze → (conditional) → human_review OR execute
    builder.add_conditional_edges(
        "analyze",
        route_after_analysis,
        {
            "human_review": "human_review",
            "execute": "execute"
        }
    )
    
    # human_review → process_review
    # This is where HITL happens - graph pauses at human_review
    builder.add_edge("human_review", "process_review")
    
    # process_review → (conditional) → execute OR rejected
    builder.add_conditional_edges(
        "process_review",
        route_after_review,
        {
            "execute": "execute",
            "rejected": "rejected"
        }
    )
    
    # Terminal nodes → END
    builder.add_edge("execute", END)
    builder.add_edge("rejected", END)
    
    return builder


def compile_graph_with_hitl():
    """
    Compiles the graph with checkpointing and interrupt configuration.
    
    Key components:
    - MemorySaver: Persists state so we can resume after interrupt
    - interrupt_before: Specifies which nodes pause for human input
    
    Returns:
        Tuple of (compiled_graph, checkpointer)
    """
    
    # Create the graph structure
    builder = create_exception_graph()
    
    # MemorySaver stores state in memory (use PostgresSaver/SQLiteSaver for production)
    checkpointer = MemorySaver()
    
    # Compile with interrupt configuration
    # interrupt_before=["human_review"] means:
    # "Pause execution BEFORE entering the human_review node"
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"]  # <-- THIS IS THE HITL MAGIC
    )
    
    return graph, checkpointer


# =============================================================================
# CONVENIENCE: Create default graph instance
# =============================================================================

def get_graph():
    """
    Returns a ready-to-use graph instance.
    
    Usage:
        graph = get_graph()
        result = graph.invoke(initial_state, config)
    """
    graph, _ = compile_graph_with_hitl()
    return graph


## What We've Built

### Key Concepts:

# | Concept | Implementation | Purpose |
# |---------|---------------|---------|
# | **Nodes** | Functions like `analyze_node()` | Processing steps in the workflow |
# | **Edges** | `add_edge()`, `add_conditional_edges()` | Define flow between nodes |
# | **State** | `AgentState` Pydantic model | Data that flows through the graph |
# | **Checkpointer** | `MemorySaver()` | Persists state for interrupts |
# | **Interrupt** | `interrupt_before=["human_review"]` | **Pauses graph for human input** |

### The HITL Flow:

# 1. Graph starts → analyze_node runs
# 2. If HITL needed → graph routes to human_review
# 3. interrupt_before triggers → GRAPH PAUSES ⏸️
# 4. State is saved by checkpointer
# 5. Control returns to your code
# 6. You get human input (approval/rejection)
# 7. You call graph.update_state() with HumanReview
# 8. You call graph.invoke() to resume → GRAPH CONTINUES ▶️
# 9. process_review_node handles the decision
# 10. execute_node or rejected_node runs
# 11. Graph ends
