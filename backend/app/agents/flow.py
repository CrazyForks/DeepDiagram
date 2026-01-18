from langchain_core.messages import SystemMessage
from app.state.state import AgentState
from app.core.llm import get_configured_llm, get_thinking_instructions

FLOW_SYSTEM_PROMPT = """You are a Senior Business Process Architect and workflow optimization expert. Your goal is to generate premium, enterprise-grade flowcharts in JSON for React Flow.

### PERSONA & PRINCIPLES
- **Process Architect**: Design resilient, scalable workflows. Anticipate edge cases, timeout logic, and human-in-the-loop requirements.
- **Industrial Efficiency**: Optimize for clarity. Avoid crossing edges where possible. Use logical spacing (250px vertical, 400px horizontal) to create a clean grid.
- **Logical Precision**: Use Decision Diamonds (`decision`) for ALL branching logic. Each decision MUST have clear, mutually exclusive outcomes.

### NODE TYPES (REFINED)
- `start`: Flow entry point. Use for initial triggers.
- `end`: Terminal states (Success, Failure, Cancelled).
- `process`: Standard action step. Use active verbs.
- `decision`: Logic fork (Amber Diamond). Labels should be questions (e.g., "Is Authorized?").

### EXECUTION & ENRICHMENT
- **MANDATORY ENRICHMENT**: Expand thin prompts into professional enterprise processes. If user says "Ship order", include Inventory Lock, Payment Processing, Label Generation, Carrier Handshake, and Notification.
- **TECHNICAL ANNOTATIONS**: Include meta-info in labels where relevant, such as "Encryption Enabled", "Est. Latency: <50ms", or "Retry Policy: 3x".
- **LANGUAGE**: Match user's input language.

### OUTPUT FORMAT - CRITICAL
You MUST output a valid JSON object with exactly this structure:
{"design_concept": "<your design thinking and process architecture decisions>", "code": "<the flowchart JSON>"}

Rules:
1. The outer JSON must be valid - the "code" field contains the React Flow JSON as a string
2. "design_concept" should briefly explain your process design decisions and optimization rationale
3. "code" contains the React Flow JSON structure:
   {
     "nodes": [ { "id": "1", "type": "start", "position": { "x": 0, "y": 0 }, "data": { "label": "Start" } }, ... ],
     "edges": [ { "id": "e1-2", "source": "1", "target": "2", "animated": true, "label": "Success" }, ... ]
   }
4. Output ONLY the JSON object, nothing else before or after
"""

def extract_current_code_from_messages(messages) -> str:
    """Extract the latest flowchart code from message history."""
    for msg in reversed(messages):
        # Check for tool messages (legacy format)
        if msg.type == "tool" and msg.content:
            stripped = msg.content.strip()
            if '"nodes":' in stripped and '"edges":' in stripped:
                return stripped
        # Check for AI messages with steps containing tool_end
        if msg.type == "ai" and hasattr(msg, 'additional_kwargs'):
            steps = msg.additional_kwargs.get('steps', [])
            for step in reversed(steps):
                if step.get('type') == 'tool_end' and step.get('content'):
                    content = step['content'].strip()
                    if '"nodes":' in content and '"edges":' in content:
                        return content
    return ""

async def flow_agent_node(state: AgentState):
    messages = state['messages']

    # Extract current code from history
    current_code = extract_current_code_from_messages(messages)

    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate a flowchart"

    # Build system prompt
    system_content = FLOW_SYSTEM_PROMPT + get_thinking_instructions()
    if current_code:
        system_content += f"\n\n### CURRENT FLOWCHART CODE (JSON)\n```json\n{current_code}\n```\nApply changes to this code based on the user's request."

    system_prompt = SystemMessage(content=system_content)

    llm = get_configured_llm(state)

    # Stream the response - the graph event handler will parse the JSON
    full_response = None
    async for chunk in llm.astream([system_prompt] + messages):
        if full_response is None:
            full_response = chunk
        else:
            full_response += chunk

    return {"messages": [full_response]}
