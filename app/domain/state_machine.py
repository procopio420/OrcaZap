"""Conversation state machine."""

from enum import Enum
from typing import Callable

from app.db.models import ConversationState


class Event(str, Enum):
    """State machine events."""

    FIRST_MESSAGE_RECEIVED = "first_message_received"
    MINIMAL_DATA_RECEIVED = "minimal_data_received"
    APPROVAL_REQUIRED = "approval_required"
    QUOTE_APPROVED = "quote_approved"
    QUOTE_AUTO_OK = "quote_auto_ok"
    USER_REPLIED = "user_replied"
    SCHEDULE_CONFIRMED = "schedule_confirmed"
    USER_DECLINED = "user_declined"
    WINDOW_EXPIRED = "window_expired"
    ADMIN_APPROVED = "admin_approved"
    ADMIN_REJECTED = "admin_rejected"


# Valid state transitions
VALID_TRANSITIONS: dict[tuple[ConversationState, Event], ConversationState] = {
    (ConversationState.INBOUND, Event.FIRST_MESSAGE_RECEIVED): ConversationState.CAPTURE_MIN,
    (ConversationState.CAPTURE_MIN, Event.MINIMAL_DATA_RECEIVED): ConversationState.QUOTE_READY,
    (ConversationState.QUOTE_READY, Event.APPROVAL_REQUIRED): ConversationState.HUMAN_APPROVAL,
    (ConversationState.QUOTE_READY, Event.QUOTE_APPROVED): ConversationState.QUOTE_SENT,
    (ConversationState.QUOTE_READY, Event.QUOTE_AUTO_OK): ConversationState.QUOTE_SENT,
    (ConversationState.QUOTE_SENT, Event.USER_REPLIED): ConversationState.WAITING_REPLY,
    (ConversationState.WAITING_REPLY, Event.SCHEDULE_CONFIRMED): ConversationState.WON,
    (ConversationState.WAITING_REPLY, Event.USER_DECLINED): ConversationState.LOST,
    (ConversationState.WAITING_REPLY, Event.WINDOW_EXPIRED): ConversationState.LOST,
    (ConversationState.HUMAN_APPROVAL, Event.ADMIN_APPROVED): ConversationState.QUOTE_SENT,
    (ConversationState.HUMAN_APPROVAL, Event.ADMIN_REJECTED): ConversationState.LOST,
    (ConversationState.QUOTE_SENT, Event.WINDOW_EXPIRED): ConversationState.LOST,
}


class StateMachineError(Exception):
    """State machine error."""

    pass


def can_transition(current_state: ConversationState, event: Event) -> bool:
    """Check if a state transition is valid.

    Args:
        current_state: Current conversation state
        event: Event to process

    Returns:
        True if transition is valid, False otherwise
    """
    return (current_state, event) in VALID_TRANSITIONS


def get_next_state(current_state: ConversationState, event: Event) -> ConversationState:
    """Get the next state for a valid transition.

    Args:
        current_state: Current conversation state
        event: Event to process

    Returns:
        Next state

    Raises:
        StateMachineError: If transition is not valid
    """
    if not can_transition(current_state, event):
        valid_events = [str(k[1]) for k in VALID_TRANSITIONS.keys() if k[0] == current_state]
        raise StateMachineError(
            f"Invalid transition from {current_state} with event {event}. "
            f"Valid events from {current_state}: {valid_events if valid_events else 'none'}"
        )

    return VALID_TRANSITIONS[(current_state, event)]


def transition(
    current_state: ConversationState,
    event: Event,
    on_transition: Callable[[ConversationState, ConversationState], None] | None = None,
) -> ConversationState:
    """Perform a state transition.

    Args:
        current_state: Current conversation state
        event: Event to process
        on_transition: Optional callback called after successful transition
                      (old_state, new_state)

    Returns:
        New state

    Raises:
        StateMachineError: If transition is not valid
    """
    new_state = get_next_state(current_state, event)

    if on_transition:
        on_transition(current_state, new_state)

    return new_state

