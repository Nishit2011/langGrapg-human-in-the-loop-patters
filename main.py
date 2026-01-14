"""
main.py - Order Exception Resolution Agent Demo

This script demonstrates the Human-in-the-Loop (HITL) pattern with LangGraph.
It shows how the graph:
1. Processes requests automatically when thresholds aren't exceeded
2. Pauses and waits for human approval when needed
3. Resumes execution after human input

Run with: python main.py
"""

import uuid
from datetime import datetime
from typing import Optional

from models import AgentState, RequestStatus, HumanReview
from tools import get_sample_requests, analyze_exception_request
from graph import compile_graph_with_hitl


# =============================================================================
# HELPER: Print formatted output
# =============================================================================

def print_header(title: str) -> None:
    """Prints a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_state_summary(state: AgentState) -> None:
    """Prints a summary of the current agent state"""
    print(f"\n📋 State Summary:")
    print(f"   Status: {state.status.value}")
    
    if state.decision:
        print(f"   Agent Recommendation: {'✅ APPROVE' if state.decision.should_approve else '❌ REJECT'}")
        print(f"   Recommended Amount: ${state.decision.recommended_amount:.2f}")
        print(f"   Requires Human: {'Yes' if state.decision.requires_human_approval else 'No'}")
    
    if state.human_review:
        print(f"   Human Decision: {'✅ APPROVED' if state.human_review.approved else '❌ REJECTED'}")
        print(f"   Reviewer: {state.human_review.reviewer_id}")
    
    if state.final_amount is not None:
        print(f"   Final Amount: ${state.final_amount:.2f}")
    
    if state.result_message:
        print(f"   Result: {state.result_message}")


def print_processing_log(state: AgentState) -> None:
    """Prints the processing log from state"""
    print(f"\n📜 Processing Log:")
    for entry in state.processing_log:
        print(f"   {entry}")


def print_request_info(request) -> None:
    """Prints details about an exception request"""
    print(f"\n📦 Request Details:")
    print(f"   Request ID: {request.request_id}")
    print(f"   Order ID: {request.order.order_id}")
    print(f"   Customer: {request.order.customer.name} ({request.order.customer.tier.value})")
    print(f"   Exception Type: {request.exception_type.value}")
    print(f"   Amount: ${request.effective_amount:.2f}")
    print(f"   Reason: {request.reason}")


# =============================================================================
# DEMO 1: Auto-Approved Request (No HITL)
# =============================================================================

def demo_auto_approve() -> None:
    """
    Demonstrates a request that gets auto-approved.
    
    This request doesn't trigger HITL because:
    - Amount is under $100
    - Customer is not VIP
    - Single item order
    """
    print_header("DEMO 1: Auto-Approved Request (No HITL)")
    
    # Get the small order request (should auto-approve)
    requests = get_sample_requests()
    request = requests[0]  # REQ-001: $29.99, standard customer
    
    print_request_info(request)
    
    # Create the graph
    graph, _ = compile_graph_with_hitl()
    
    # Create unique thread ID for this run
    thread_id = f"demo-auto-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Create initial state
    initial_state = AgentState(request=request)
    
    print("\n🚀 Starting graph execution...")
    
    # Run the graph - should complete without interruption
    final_state_dict = graph.invoke(initial_state, config)
    
    # Convert dict back to AgentState for nice printing
    final_state = AgentState(**final_state_dict)
    
    print_state_summary(final_state)
    print_processing_log(final_state)
    
    print("\n✅ Request processed automatically - no human intervention needed!")


# =============================================================================
# DEMO 2: HITL Request with Approval
# =============================================================================

def demo_hitl_approved() -> None:
    """
    Demonstrates a request that requires human approval.
    
    This request triggers HITL because the amount exceeds $100.
    We'll simulate a human approving the request.
    """
    print_header("DEMO 2: HITL Request - Human Approves")
    
    # Get the high-value request
    requests = get_sample_requests()
    request = requests[1]  # REQ-002: $339.98, exceeds threshold
    
    print_request_info(request)
    
    # Create the graph
    graph, _ = compile_graph_with_hitl()
    
    # Create unique thread ID
    thread_id = f"demo-hitl-approve-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Create initial state
    initial_state = AgentState(request=request)
    
    print("\n🚀 Starting graph execution...")
    
    # First invocation - graph will pause at human_review node
    paused_state_dict = graph.invoke(initial_state, config)
    paused_state = AgentState(**paused_state_dict)
    
    print("\n⏸️  GRAPH PAUSED - Waiting for human review")
    print_state_summary(paused_state)
    
    # Show why human approval is needed
    if paused_state.decision and paused_state.decision.approval_reasons:
        print(f"\n🔍 Approval Required Because:")
        for reason in paused_state.decision.approval_reasons:
            print(f"   • {reason}")
    
    # Simulate human review process
    print("\n" + "-" * 40)
    print("👤 HUMAN REVIEWER ACTION")
    print("-" * 40)
    print("   Reviewer: MGR-JANE-001")
    print("   Decision: APPROVE")
    print("   Notes: 'Verified quality issue with photos. Approved for full refund.'")
    print("-" * 40)
    
    # Create the human review
    human_review = HumanReview(
        reviewer_id="MGR-JANE-001",
        approved=True,
        adjusted_amount=None,  # Accept the recommended amount
        notes="Verified quality issue with photos. Approved for full refund.",
        reviewed_at=datetime.now()
    )
    
    # Update the state with human review
    # This is how external input gets into the graph
    graph.update_state(
        config,
        {"human_review": human_review}
    )
    
    print("\n▶️  Resuming graph execution...")
    
    # Resume the graph - pass None to continue from where we left off
    final_state_dict = graph.invoke(None, config)
    final_state = AgentState(**final_state_dict)
    
    print_state_summary(final_state)
    print_processing_log(final_state)
    
    print("\n✅ Request approved by human and processed successfully!")


# =============================================================================
# DEMO 3: HITL Request with Rejection
# =============================================================================

def demo_hitl_rejected() -> None:
    """
    Demonstrates a request that gets rejected by human reviewer.
    
    This shows how the graph handles rejection gracefully.
    """
    print_header("DEMO 3: HITL Request - Human Rejects")
    
    # Get the VIP customer request
    requests = get_sample_requests()
    request = requests[2]  # REQ-003: VIP customer cancellation
    
    print_request_info(request)
    
    # Create the graph
    graph, _ = compile_graph_with_hitl()
    
    # Create unique thread ID
    thread_id = f"demo-hitl-reject-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Create initial state
    initial_state = AgentState(request=request)
    
    print("\n🚀 Starting graph execution...")
    
    # First invocation - graph will pause
    paused_state_dict = graph.invoke(initial_state, config)
    paused_state = AgentState(**paused_state_dict)
    
    print("\n⏸️  GRAPH PAUSED - Waiting for human review")
    print_state_summary(paused_state)
    
    # Show why human approval is needed
    if paused_state.decision and paused_state.decision.approval_reasons:
        print(f"\n🔍 Approval Required Because:")
        for reason in paused_state.decision.approval_reasons:
            print(f"   • {reason}")
    
    # Simulate human rejection
    print("\n" + "-" * 40)
    print("👤 HUMAN REVIEWER ACTION")
    print("-" * 40)
    print("   Reviewer: MGR-BOB-002")
    print("   Decision: REJECT")
    print("   Notes: 'VIP customer - called directly to offer exchange instead. Customer accepted.'")
    print("-" * 40)
    
    # Create rejection review
    human_review = HumanReview(
        reviewer_id="MGR-BOB-002",
        approved=False,
        adjusted_amount=None,
        notes="VIP customer - called directly to offer exchange instead. Customer accepted.",
        reviewed_at=datetime.now()
    )
    
    # Update state with rejection
    graph.update_state(
        config,
        {"human_review": human_review}
    )
    
    print("\n▶️  Resuming graph execution...")
    
    # Resume the graph
    final_state_dict = graph.invoke(None, config)
    final_state = AgentState(**final_state_dict)
    
    print_state_summary(final_state)
    print_processing_log(final_state)
    
    print("\n❌ Request rejected - alternative resolution provided to VIP customer!")


# =============================================================================
# DEMO 4: HITL with Adjusted Amount
# =============================================================================

def demo_hitl_adjusted() -> None:
    """
    Demonstrates a human reviewer adjusting the recommended amount.
    
    This shows how humans can modify the agent's recommendation.
    """
    print_header("DEMO 4: HITL Request - Human Adjusts Amount")
    
    # Get the multi-item price adjustment request
    requests = get_sample_requests()
    request = requests[3]  # REQ-004: Multi-item, price adjustment
    
    print_request_info(request)
    
    # Create the graph
    graph, _ = compile_graph_with_hitl()
    
    # Create unique thread ID
    thread_id = f"demo-hitl-adjust-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Create initial state
    initial_state = AgentState(request=request)
    
    print("\n🚀 Starting graph execution...")
    
    # First invocation
    paused_state_dict = graph.invoke(initial_state, config)
    paused_state = AgentState(**paused_state_dict)
    
    print("\n⏸️  GRAPH PAUSED - Waiting for human review")
    print_state_summary(paused_state)
    
    # Show the agent's recommendation
    recommended = paused_state.decision.recommended_amount if paused_state.decision else 0
    print(f"\n💡 Agent recommended: ${recommended:.2f}")
    
    # Simulate human adjusting the amount
    adjusted_amount = 35.00  # Human decides on a different amount
    
    print("\n" + "-" * 40)
    print("👤 HUMAN REVIEWER ACTION")
    print("-" * 40)
    print("   Reviewer: MGR-CAROL-003")
    print("   Decision: APPROVE (with adjustment)")
    print(f"   Original Recommendation: ${recommended:.2f}")
    print(f"   Adjusted Amount: ${adjusted_amount:.2f}")
    print("   Notes: 'Partial price match - only 2 items were actually on sale.'")
    print("-" * 40)
    
    # Create review with adjusted amount
    human_review = HumanReview(
        reviewer_id="MGR-CAROL-003",
        approved=True,
        adjusted_amount=adjusted_amount,  # Human overrides the amount
        notes="Partial price match - only 2 items were actually on sale.",
        reviewed_at=datetime.now()
    )
    
    # Update state
    graph.update_state(
        config,
        {"human_review": human_review}
    )
    
    print("\n▶️  Resuming graph execution...")
    
    # Resume
    final_state_dict = graph.invoke(None, config)
    final_state = AgentState(**final_state_dict)
    
    print_state_summary(final_state)
    print_processing_log(final_state)
    
    print(f"\n✅ Request approved with adjusted amount: ${adjusted_amount:.2f} (was ${recommended:.2f})")


# =============================================================================
# INTERACTIVE DEMO
# =============================================================================

def demo_interactive() -> None:
    """
    Interactive demo where you can provide real input.
    """
    print_header("DEMO 5: Interactive HITL")
    
    # Get the high-value request
    requests = get_sample_requests()
    request = requests[1]
    
    print_request_info(request)
    
    # Create the graph
    graph, _ = compile_graph_with_hitl()
    
    thread_id = f"demo-interactive-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = AgentState(request=request)
    
    print("\n🚀 Starting graph execution...")
    
    paused_state_dict = graph.invoke(initial_state, config)
    paused_state = AgentState(**paused_state_dict)
    
    print("\n⏸️  GRAPH PAUSED - Waiting for YOUR review")
    print_state_summary(paused_state)
    
    if paused_state.decision:
        print(f"\n💡 Agent recommends: ${paused_state.decision.recommended_amount:.2f}")
        print(f"   Reasoning: {paused_state.decision.reasoning}")
    
    # Get user input
    print("\n" + "-" * 40)
    print("👤 YOUR TURN TO DECIDE")
    print("-" * 40)
    
    while True:
        decision = input("\nApprove this request? (yes/no): ").strip().lower()
        if decision in ["yes", "no", "y", "n"]:
            break
        print("Please enter 'yes' or 'no'")
    
    approved = decision in ["yes", "y"]
    
    adjusted_amount: Optional[float] = None
    if approved:
        adjust = input("Adjust the amount? (enter new amount or press Enter to accept): ").strip()
        if adjust:
            try:
                adjusted_amount = float(adjust)
            except ValueError:
                print("Invalid amount, using recommended amount")
    
    notes = input("Add any notes (or press Enter to skip): ").strip() or None
    reviewer_id = input("Your reviewer ID (or press Enter for 'USER-001'): ").strip() or "USER-001"
    
    # Create review from user input
    human_review = HumanReview(
        reviewer_id=reviewer_id,
        approved=approved,
        adjusted_amount=adjusted_amount,
        notes=notes,
        reviewed_at=datetime.now()
    )
    
    # Update and resume
    graph.update_state(config, {"human_review": human_review})
    
    print("\n▶️  Resuming graph execution...")
    
    final_state_dict = graph.invoke(None, config)
    final_state = AgentState(**final_state_dict)
    
    print_state_summary(final_state)
    print_processing_log(final_state)
    
    if final_state.status == RequestStatus.COMPLETED:
        print("\n✅ Request processed successfully!")
    elif final_state.status == RequestStatus.REJECTED:
        print("\n❌ Request rejected!")
    else:
        print(f"\n⚠️  Final status: {final_state.status.value}")


# =============================================================================
# MAIN MENU
# =============================================================================

def main():
    """Main entry point with demo menu"""
    
    print("\n" + "=" * 60)
    print("  🛒 ORDER EXCEPTION RESOLUTION AGENT")
    print("  Human-in-the-Loop Demo with LangGraph")
    print("=" * 60)
    
    print("\nAvailable demos:")
    print("  1. Auto-Approved Request (no HITL)")
    print("  2. HITL Request - Human Approves")
    print("  3. HITL Request - Human Rejects")
    print("  4. HITL Request - Human Adjusts Amount")
    print("  5. Interactive Demo (you decide!)")
    print("  6. Run All Demos")
    print("  0. Exit")
    
    while True:
        choice = input("\nSelect demo (0-6): ").strip()
        
        if choice == "0":
            print("\nGoodbye! 👋")
            break
        elif choice == "1":
            demo_auto_approve()
        elif choice == "2":
            demo_hitl_approved()
        elif choice == "3":
            demo_hitl_rejected()
        elif choice == "4":
            demo_hitl_adjusted()
        elif choice == "5":
            demo_interactive()
        elif choice == "6":
            demo_auto_approve()
            demo_hitl_approved()
            demo_hitl_rejected()
            demo_hitl_adjusted()
        else:
            print("Invalid choice. Please enter 0-6.")


if __name__ == "__main__":
    main()