from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from app.state.state import AgentState
from app.core.config import settings
from app.core.llm import get_llm, get_configured_llm, get_thinking_instructions
from app.core.context import set_context, get_messages, get_context

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

### OUTPUT FORMAT
- Return ONLY raw JSON. No markdown fences.
- **Structure**:
  {
    "nodes": [ { "id": "1", "type": "start", "position": { "x": 0, "y": 0 }, "data": { "label": "Start" } }, ... ],
    "edges": [ { "id": "e1-2", "source": "1", "target": "2", "animated": true, "label": "Success" }, ... ]
  }
"""

@tool
async def create_flow(instruction: str):
    """
    Renders an interactive flowchart using React Flow based on instructions.
    Args:
        instruction: Detailed instruction on what flowchart to create or modify.
    """
    messages = get_messages()
    context = get_context()
    current_code = context.get("current_code", "")
    model_config = context.get("model_config")
    
    # Get configured LLM
    llm = get_llm(
        api_key=model_config.get("api_key") if model_config else None,
        base_url=model_config.get("base_url") if model_config else None,
        model_name=model_config.get("model_id") if model_config else None
    )
    
    # Call LLM to generate the Flow JSON
    system_msg = FLOW_SYSTEM_PROMPT + get_thinking_instructions()
    if current_code:
        system_msg += f"\n\n### CURRENT FLOWCHART CODE (JSON)\n```json\n{current_code}\n```\nApply changes to this code."

    prompt = [SystemMessage(content=system_msg)] + messages
    if instruction:
        prompt.append(HumanMessage(content=f"Instruction: {instruction}"))
    
    full_content = ""
    async for chunk in llm.astream(prompt):
        if chunk.content:
            full_content += chunk.content
    
    json_str = full_content
    
    # Robust JSON Extraction: Find the substring from first '{' to last '}'
    import re
    # Remove any thinking tags first
    json_str = re.sub(r'<think>[\s\S]*?</think>', '', json_str, flags=re.DOTALL)
    
    match = re.search(r'(\{[\s\S]*\})', json_str)
    if match:
        cleaned_json = match.group(1)
    else:
        cleaned_json = re.sub(r'^```\w*\n?', '', json_str.strip())
        cleaned_json = re.sub(r'\n?```$', '', cleaned_json.strip())
    
    return cleaned_json.strip()

tools = [create_flow]

async def flow_agent_node(state: AgentState):
    messages = state['messages']
    model_config = state.get("model_config")
    
    # 动态从历史中提取最新的 flowchart 代码（寻找最后一条 tool 消息且内容包含 nodes/edges）
    current_code = ""
    for msg in reversed(messages):
        if msg.type == "tool" and msg.content:
            stripped = msg.content.strip()
            if '"nodes":' in stripped and '"edges":' in stripped:
                current_code = stripped
                break

    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate a flowchart"

    set_context(messages, current_code=current_code, model_config=model_config)
    
    system_prompt = SystemMessage(content="""You are a World-Class Business Process Analyst.
    YOUR MISSION is to act as a Process Improvement Consultant. When a user describes a flow, don't just "diagram" it—OPTIMIZE and INDUSTRIALIZE it.

    ### ⚠️ CRITICAL REQUIREMENT - MUST USE TOOLS:
    **YOU MUST USE THE `create_flow` TOOL TO GENERATE DIAGRAMS. NEVER OUTPUT DIAGRAM CODE DIRECTLY IN YOUR TEXT RESPONSE.**
    - You MUST call the `create_flow` tool - this is non-negotiable.
    - Do NOT write JSON flowchart data in your response text.
    - Do NOT provide code blocks with diagram syntax in your text.
    - ONLY use the tool call mechanism to generate diagrams.

    ### ORCHESTRATION RULES:
    1. **PROCESS ENRICHMENT**: If the user says "draw a CI/CD pipeline", expand it to "draw a professional enterprise-grade CI/CD workflow including linting, unit testing, security scanning (SAST), staging deployment, UAT approval gate, and production canary release".
    2. **MANDATORY TOOL CALL**: Always use `create_flow`.
    3. **LOGICAL ROBUSTNESS**: Instruct the tool to include decision diamonds for error handling and fallback mechanisms.
    4. **METAPHORICAL THINKING**: Use vertical flows for linear processes and horizontal branches for parallel worker logic.
    
    ### LANGUAGE CONSISTENCY:
    - Respond and call tools in the SAME LANGUAGE as the user.
    
    ### PROACTIVENESS:
    - BE DECISIVE. If a step looks like it needs "Manual Approval" or a "Timeout", include it in the optimized instructions.
    """ + get_thinking_instructions())
    
    llm = get_configured_llm(state)
    llm_with_tools = llm.bind_tools(tools)
    
    full_response = None
    async for chunk in llm_with_tools.astream([system_prompt] + messages):
        if full_response is None:
            full_response = chunk
        else:
            full_response += chunk
    return {"messages": [full_response]}
