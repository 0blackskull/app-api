from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sse_starlette import EventSourceResponse
from sqlalchemy.orm import Session
from typing import AsyncGenerator, List

import json
from app.utils.logger import get_logger
import time
from uuid import UUID

from app import crud, schemas
from app.database import get_db
from app.auth import get_current_user
from app.agents.astrology_agent import AstrologyAgent
from app.models import User
from app.middleware.rate_limit import rate_limit_chat
from app.llm.client import LLMClient
from app.crud.message import get_last_thread_messages


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}}
)

# Configure logging
logger = get_logger(__name__)

# Simple 1-minute in-process cache for friendship checks
_friend_cache: dict[tuple[str, str], tuple[bool, float]] = {}
_CACHE_TTL_SECONDS = 60.0

def _are_friends_cached(db: Session, current_user_id: str, other_user_id: str) -> bool:
    """Return friendship status using a 60s in-process cache to reduce DB hits."""
    key = (current_user_id, other_user_id)
    now = time.time()
    cached = _friend_cache.get(key)
    if cached and now - cached[1] < _CACHE_TTL_SECONDS:
        return cached[0]
    res = crud.FriendsCRUD._are_friends(db, current_user_id, other_user_id)
    _friend_cache[key] = (res, now)
    return res

def format_sse_event(
    data: str | list[str] | dict,
    event_name: str,
    message: str | None = None,
    name: str | None = None,
) -> dict:
    """Format a Server-Sent Event payload as a dict for EventSourceResponse."""
    event_data = {"data": data}
    if message:
        event_data["message"] = message
    if name:
        event_data["name"] = name
    return {"event": event_name, "data": json.dumps(event_data)}

def format_close_event():
    """Return a standard close event for the SSE stream."""
    return {"event": "close", "data": json.dumps({"data": "Stream closed."})}

def extract_final_answer_content(content: str, last_agent_output: str = "") -> str:
    """
    Extract content between <Final Answer> and </Final Answer> tags.
    If tags are not found, returns the last_agent_output as fallback.
    """
    start_tag = "<Final Answer>"
    end_tag = "</Final Answer>"
    
    start_idx = content.find(start_tag)
    if start_idx == -1:
        # If no final answer tags found, return last agent output as fallback
        return last_agent_output.strip() if last_agent_output else ""
    
    end_idx = content.find(end_tag, start_idx)
    if end_idx == -1:
        # If start tag found but no end tag, return last agent output as fallback
        return last_agent_output.strip() if last_agent_output else ""
    
    # Extract content between tags, excluding the tags themselves
    start_content = start_idx + len(start_tag)
    return content[start_content:end_idx].strip()


def extract_streaming_final_answer(content: str, accumulated_content: str = "", last_sent_position: int = 0, streaming_complete: bool = False, pending_buffer: str = "") -> tuple[str, str, int, bool, str]:
    """
    Extract content within Final Answer tags for streaming, handling partial content and partial closing tags.
    Returns (content_to_send, new_accumulated_content, new_last_sent_position, streaming_complete, new_pending_buffer).
    
    Args:
        content: Current chunk of content
        accumulated_content: Previously accumulated content to check for complete tags
        last_sent_position: Position in accumulated content where we last sent content
        streaming_complete: Whether streaming has already been completed
        pending_buffer: Buffer holding potential partial closing tag from previous chunk
    
    Returns:
        Tuple of (content to send to UI, new accumulated content, new last sent position, streaming complete flag, new pending buffer)
    """
    start_tag = "<Final Answer>"
    end_tag = "</Final Answer>"
    
    # If streaming is already complete, don't send anything more
    if streaming_complete:
        return "", accumulated_content + content, last_sent_position, True, ""
    
    # Update accumulated content
    new_accumulated = accumulated_content + content
    
    # Find start tag position
    start_pos = new_accumulated.find(start_tag)
    if start_pos == -1:
        # No start tag found yet, don't send anything
        return "", new_accumulated, last_sent_position, False, ""
    
    # Calculate content start position (after start tag)
    content_start = start_pos + len(start_tag)
    
    # Check if we're inside the Final Answer tags
    if last_sent_position < content_start:
        # We haven't started streaming yet, move to content start
        last_sent_position = content_start
    
    # Find end tag position
    end_pos = new_accumulated.find(end_tag, start_pos)
    
    if end_pos != -1:
        # Complete end tag found, send remaining content up to end tag and mark as complete
        content_to_send = new_accumulated[last_sent_position:end_pos]
        return content_to_send, new_accumulated, end_pos, True, ""
    
    # End tag not found yet, need to handle potential partial closing tag
    current_content = new_accumulated[last_sent_position:]
    content_to_send = ""
    new_pending_buffer = ""
    
    # Add any pending buffer from previous chunk
    if pending_buffer:
        current_content = pending_buffer + current_content
        # When we have a pending buffer, don't send any content until we can determine if it's a complete closing tag
        # Just accumulate the content and continue
        return "", new_accumulated, last_sent_position, False, ""
    # Look for potential start of closing tag
    i = 0
    while i < len(current_content):
        char = current_content[i]
        
        if char == '<':
            # Found '<', check if it could be start of closing tag
            remaining = current_content[i:]
            
            # Check if remaining content matches any prefix of the end tag
            is_potential_closing = False
            for j in range(1, min(len(end_tag) + 1, len(remaining) + 1)):
                if end_tag.startswith(remaining[:j]):
                    is_potential_closing = True
                    if j == len(end_tag) and remaining[:j] == end_tag:
                        # Complete closing tag found
                        content_to_send += current_content[:i]
                        return content_to_send, new_accumulated, last_sent_position + len(content_to_send), True, ""
                    break
            
            if is_potential_closing:
                # This could be a partial closing tag, buffer it
                content_to_send += current_content[:i]
                new_pending_buffer = remaining
                break
            else:
                # Not a closing tag, continue
                i += 1
        else:
            i += 1
    
    if not new_pending_buffer:
        # No potential closing tag found, send all content
        content_to_send = current_content
        new_pending_buffer = ""
    
    # Update last sent position
    new_last_sent = last_sent_position + len(content_to_send)
    
    return content_to_send, new_accumulated, new_last_sent, False, new_pending_buffer

async def generate_stream(user: User, message: str, db: Session, thread_id: UUID = None, additional_users: List[User] | None = None, ashtakoota_raw: dict | None = None) -> AsyncGenerator[dict, None]:
    """Generate streaming response for chat."""
    
    # Check if user can chat (has credits or subscription)
    if not crud.can_user_chat(db, user.id):
        yield format_sse_event(
            {"error": "Insufficient credits. Please purchase more credits to continue chatting."},
            "error"
        )
        yield format_close_event()
        return
    
    # Deduct credits only for non-active subscribers
    if user.subscription_status != "active":
        crud.deduct_credits(db, user.id, 1)
    
    try:
        # The AstrologyAgent handles person data creation and context internally
        
        # Use the actual AstrologyAgent with proper streaming
        agent = AstrologyAgent(user, thread_id=str(thread_id) if thread_id else None, additional_users=additional_users, ashtakoota_raw=ashtakoota_raw, db=db)
        
        # Stream the response using the agent's team
        accumulated_content = ""
        last_sent_position = 0
        final_answer = ""
        last_agent_output = ""
        streaming_complete = False
        pending_buffer = ""
        full_streaming_output = ""  # Track complete streaming output
        
        try:
            async for event in agent.team.run_stream(task=message):
                event_type = type(event).__name__

                
                if event_type == "ModelClientStreamingChunkEvent":
                    if hasattr(event, 'content') and event.content:
                        content_str = str(event.content)
                        
                        # Capture the complete streaming output
                        full_streaming_output += content_str
                        
                        # Capture the last agent output for fallback
                        last_agent_output += content_str
                        
                        # Extract content within Final Answer tags for streaming UI display
                        content_to_send, accumulated_content, last_sent_position, streaming_complete, pending_buffer = extract_streaming_final_answer(
                            content_str, accumulated_content, last_sent_position, streaming_complete, pending_buffer
                        )
                        
                        if content_to_send:
                            yield format_sse_event(content_to_send, "data")
            
            # After streaming is complete, send any remaining buffer content if it wasn't a closing tag
            if pending_buffer and not streaming_complete:
                yield format_sse_event(pending_buffer, "data")
            
            # Extract final answer from accumulated content, with fallback to last agent output
            final_answer = extract_final_answer_content(accumulated_content, last_agent_output)
            
            if not final_answer:
                final_answer = "I apologize, but I wasn't able to generate a proper response. Please try asking your question again."
                
        except Exception as e:
            logger.exception(f"Error in agent streaming: {e}")
            final_answer = "I apologize, but I encountered an error while processing your request. Please try again."

        # Save the conversation to database
        if thread_id:
            # Only save assistant message - it contains both query and answer
            crud.create_message(db, user.id, "assistant", message, final_answer, str(thread_id))
        
        yield format_close_event()
        
    except Exception as e:
        logger.exception(f"Error in chat stream: {e}")
        yield format_sse_event(
            {"error": "An internal error occurred. Please try again."},
            "error"
        )
        yield format_close_event()

@router.get("/stream")
@rate_limit_chat
async def chat_stream(
    request: Request,
    message: str = Query(..., description="The message to send to the assistant"),
    thread_id: UUID = Query(None, description="The ID of the thread to chat in (optional)"),
    participant_user_ids: str | None = Query(None, description="CSV of participant user IDs to include (override, not persisted)"),
    participant_partner_ids: str | None = Query(None, description="CSV of partner IDs to include (override, not persisted)"),

    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """SSE chat endpoint.
    - Uses thread participants unless overridden via query params (ephemeral, not persisted).
    - Always rechecks friendship (cached 60s) for user participants before streaming.
    - Deducts 1 credit per request.
    """
    
    # Get current user with full data
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if thread_id:
        thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
    else:
        threads = crud.get_user_threads(db, current_user.id, 0, 1)
        if threads:
            thread = threads[0]
            thread_id = thread.id
        else:
            default_thread = crud.create_chat_thread(db, current_user.id, "Default Chat")
            thread = default_thread
            thread_id = default_thread.id

            # Build filter object from overrides when provided; otherwise from thread
    filter_obj = schemas.ProfileFilter()

    if participant_user_ids is not None:
        csv = participant_user_ids.strip()
        filter_obj.participant_user_ids = [s for s in csv.split(',') if s] if csv else []
    else:
        filter_obj.participant_user_ids = getattr(thread, 'participant_user_ids', None) or []

    if participant_partner_ids is not None:
        csvp = participant_partner_ids.strip()
        filter_obj.participant_partner_ids = [s for s in csvp.split(',') if s] if csvp else []
    else:
        filter_obj.participant_partner_ids = getattr(thread, 'participant_partner_ids', None) or []

    # Validate and get additional participants
    additional_users = []

    # Add user participants (friends)
    for user_id in filter_obj.participant_user_ids:
        if user_id == current_user.id:
            continue  # Skip self
        
        # Check friendship with caching
        if not _are_friends_cached(db, current_user.id, user_id):
            raise HTTPException(status_code=403, detail=f"Not authorized to include user {user_id} - not friends")
        
        friend_user = crud.get_user(db, user_id)
        if friend_user:
            additional_users.append(friend_user)

    # Add partner participants
    for partner_id in filter_obj.participant_partner_ids:
        partner_obj = crud.get_partner(db, partner_id)
        if not partner_obj or partner_obj.user_id != current_user.id:
            raise HTTPException(status_code=403, detail=f"Not authorized to include partner {partner_id}")
        additional_users.append(partner_obj)  # Intentionally mixing User and Partner objects

    # Get ashtakoota data if needed
    ashtakoota_raw = None
    if hasattr(thread, 'ashtakoota_raw_json') and thread.ashtakoota_raw_json:
        try:
            ashtakoota_raw = json.loads(thread.ashtakoota_raw_json)
        except (json.JSONDecodeError, TypeError):
            ashtakoota_raw = None

    return EventSourceResponse(
        generate_stream(user, message, db, thread_id, additional_users, ashtakoota_raw),
        media_type="text/plain"
    )


@router.get("/suggestions")
async def get_suggested_questions(
    thread_id: UUID = Query(..., description="The ID of the thread to base suggestions on"),
    db: Session = Depends(get_db),
    current_user: schemas.CurrentUser = Depends(get_current_user)
):
    """Return suggested follow-up questions based on the last Q/A in the thread.
    - Fetch latest assistant message in the thread as the prior answer and its stored query.
    - Verify ownership of the thread.
    """
    thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    assistant_msgs = get_last_thread_messages(db, str(thread_id), n=1)
    if not assistant_msgs:
        raise HTTPException(status_code=400, detail="No assistant answer found to base suggestions on")

    last_message = assistant_msgs[0]
    previous_query = last_message.query or "No previous query found"
    previous_answer = last_message.content or "No previous answer found"

    llm = LLMClient()
    result = await llm.generate_suggested_questions(previous_query, previous_answer, max_items=3)
    return result
