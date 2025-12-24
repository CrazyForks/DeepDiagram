from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.graph import graph
from app.core.database import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from app.services.chat import ChatService
import json
from typing import AsyncGenerator
from app.core.logger import logger
from datetime import datetime

router = APIRouter()

class ChatRequest(BaseModel):
    session_id: int | None = None
    agent_id: str | None = None
    prompt: str
    images: list[str] = []
    history: list[dict] = []
    context: dict = {}
    parent_id: int | None = None
    is_retry: bool = False

async def event_generator(request: ChatRequest, db: AsyncSession) -> AsyncGenerator[str, None]:
    chat_service = ChatService(db)
    
    # 1. Manage Session
    session_id = request.session_id
    if not session_id:
        chat_session = await chat_service.create_session(title=request.prompt[:30])
        session_id = chat_session.id
        yield f"event: session_created\ndata: {json.dumps({'session_id': session_id})}\n\n"
    
    # 2. Manage User Message
    last_user_msg_id = None
    if request.is_retry and request.parent_id:
        # If retrying, the parent_id IS the user message we are retrying
        last_user_msg_id = request.parent_id
    else:
        # Save new User Message
        user_msg = await chat_service.add_message(
            session_id, "user", request.prompt, 
            images=request.images,
            parent_id=request.parent_id
        )
        last_user_msg_id = user_msg.id
    
    yield f"event: message_created\ndata: {json.dumps({'id': last_user_msg_id, 'role': 'user'})}\n\n"
    
    # 3. Load History
    history = await chat_service.get_history(session_id)
    formatted_history = []
    
    # We exclude the content we just added (the last user message) to avoid duplication if we re-append it
    # Actually, get_history returns ALL, including the one we just added? 
    # Let's check get_history order. It says order_by(created_at).
    # Since we await add_message above, it SHOULD be in history.
    # But we want to separate the "current input" (message variable) from "history".
    # Or we can just pass the whole thing as "history" and inputs['messages'] = history?
    # LangGraph usually takes partial updates, but if we are stateless, we pass everything?
    
    # Let's separate "previous history" and "current message".
    # But simplicity: Just filter out the very last one if it matches? 
    # Or cleaner: Fetch history BEFORE adding current? No, get_history might render better?
    
    # Implementation:
    # 1. Fetch all history (including current)
    # 2. Convert to LC messages
    # 3. separate last one as 'current'? Or just pass all?
    # For router, passing all is fine.
    
    from langchain_core.messages import AIMessage, HumanMessage

    for msg in history:
        # Skip the current message we just added to properly treat it as "new input" if needed?
        # Actually safer to construct "previous history" + "current message request object".
        # But ChatMessage db object content is string.
        
        # If it's the message we just added ... skip?
        if msg.role == "user" and msg.content == request.prompt and msg == history[-1]: 
             continue

        if msg.role == "user":
            formatted_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            formatted_history.append(AIMessage(content=msg.content))
            
    # Current Message Construction (same as before)
    if request.images:
        content = [{"type": "text", "text": request.prompt}]
        for image_data in request.images:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_data}
            })
        message = HumanMessage(content=content)
    else:
        message = HumanMessage(content=request.prompt)

    # Combine
    full_messages = formatted_history + [message]

    inputs = {
        "messages": full_messages,
        "current_code": request.context.get("current_code", ""),
    }
    
    full_response_content = ""
    accumulated_steps = []
    selected_agent = None

    try:
        # Stateless execution: No thread_id, so it runs fresh with provided history
        async for event in graph.astream_events(inputs, version="v1"):
            event_type = event["event"]
            data = event["data"]
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node", "")
            
            # Filter internal Router LLM stream
            if node_name == "router":
                # We do NOT want to stream the router's internal thought process or result as content
                # But we DO want to capture its final output (handled below in on_chain_end)
                if event_type == "on_chain_end" and event["name"] == "router":
                     pass # Fall through to the handler below
                else: 
                     continue
            
            # Detect Router Output to notify frontend
            if event_type == "on_chain_end" and event["name"] == "router":
                # The router returns {"intent": "..."}
                output = data.get("output")
                if output and "intent" in output:
                    intent = output["intent"]
                    selected_agent = intent
                    yield f"event: agent_selected\ndata: {json.dumps({'agent': intent})}\n\n"
                    
                    # Also add a pseudo-step for history
                    accumulated_steps.append({
                        "type": "agent_select",
                        "name": intent,
                        "status": "done",
                        "timestamp": int(datetime.utcnow().timestamp() * 1000)
                    })
            
            if event_type == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk:
                    content = chunk.content
                    if content:
                        is_tool_stream = node_name.endswith("_tools")
                        if is_tool_stream:
                            yield f"event: tool_code\ndata: {json.dumps({'content': content})}\n\n"
                        else:
                            full_response_content += content
                            yield f"event: thought\ndata: {json.dumps({'content': content})}\n\n"
                    
                    if hasattr(chunk, 'tool_call_chunks'):
                        for tool_chunk in chunk.tool_call_chunks or []:
                            if tool_chunk and tool_chunk.get('args'):
                                args_chunk = tool_chunk['args']
                                yield f"event: tool_args_stream\ndata: {json.dumps({'args': args_chunk})}\n\n"

            elif event_type == "on_tool_start":
                # Add tool start step
                step = {
                    "type": "tool_start",
                    "name": event["name"],
                    "content": json.dumps(data.get("input")),
                    "status": "running",
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }
                accumulated_steps.append(step)
                yield f"event: tool_start\ndata: {json.dumps({'tool': event['name'], 'input': data.get('input')})}\n\n"

            elif event_type == "on_tool_end":
                output = data.get('output')
                if hasattr(output, 'content'):
                    output = output.content
                elif not isinstance(output, (dict, list, str, int, float, bool, type(None))):
                    output = str(output)
                
                # Update steps
                if accumulated_steps:
                    accumulated_steps.append({
                        "type": "tool_end",
                        "name": "Result",
                        "content": output if isinstance(output, str) else json.dumps(output),
                        "status": "done",
                        "timestamp": int(datetime.utcnow().timestamp() * 1000)
                    })
                    for s in reversed(accumulated_steps):
                        if s["type"] == "tool_start" and s["status"] == "running":
                            s["status"] = "done"
                            break

                yield f"event: tool_end\ndata: {json.dumps({'output': output})}\n\n"
        
        # 4. Save Assistant Message
        if full_response_content or accumulated_steps:
            assistant_msg = await chat_service.add_message(
                session_id, "assistant", 
                full_response_content, 
                steps=accumulated_steps,
                agent=selected_agent,
                parent_id=last_user_msg_id
            )
            yield f"event: message_created\ndata: {json.dumps({'id': assistant_msg.id, 'role': 'assistant'})}\n\n"
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"Error in chat stream: {error_msg}")
        logger.error(traceback.format_exc())
        yield f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"

@router.post("/chat/completions")
async def chat_completions(request: ChatRequest, db: AsyncSession = Depends(get_session)):
    return StreamingResponse(event_generator(request, db), media_type="text/event-stream")

@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_session)):
    chat_service = ChatService(db)
    sessions = await chat_service.get_all_sessions()
    return sessions

@router.get("/sessions/{session_id}")
async def get_session_history(session_id: int, db: AsyncSession = Depends(get_session)):
    chat_service = ChatService(db)
    history = await chat_service.get_history(session_id)
    return history

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: AsyncSession = Depends(get_session)):
    chat_service = ChatService(db)
    await chat_service.delete_session(session_id)
    return {"status": "success"}
