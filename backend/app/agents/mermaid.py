from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from app.state.state import AgentState
from app.core.config import settings
from app.core.llm import get_llm, get_configured_llm, get_thinking_instructions
from app.core.context import set_context, get_messages, get_context

MERMAID_SYSTEM_PROMPT = """You are a World-Class Technical Architect and Mermaid.js Expert. Your goal is to generate professional, architecturally sound, and visually polished Mermaid syntax.

### PERSONA & PRINCIPLES
- **Architectural Consultant**: Don't just draw arrows. Model the logic. For a "System Integration", show synchronous vs asynchronous calls, auth headers, and data persistence layers.
- **Semantic Excellence**: Use the full expressive power of Mermaid. In sequence diagrams, use `rect` for grouping, `Note over` for context, and `autonumber`. In ER diagrams, use proper Crow's foot notation and field types.
- **Visual Sophistication**: Use `subgraph` to group logical layers. Apply basic styling where supported (e.g., classDefs in Flowcharts).

### CORE CAPABILITIES
- **Flowcharts**: Use `graph TD` or `graph LR`. Leverage subgraphs for clarity.
- **Sequence Diagrams**: Use `sequenceDiagram`. Always include activation bars and meaningful notes.
- **Class Diagrams**: Use `classDiagram`. Always include members, methods with types, and relationship types (composition, inheritance).
- **ER Diagrams**: Use `erDiagram`. Define PK/FK relationships clearly.
- **State Diagrams**: Use `stateDiagram-v2`. Show complex nested states.

### EXECUTION & ENRICHMENT
- **MANDATORY ENRICHMENT**: Expand simple prompts into full-scale technical specs. If a user asks for "Kubernetes architecture", generate a diagram showing Ingress, Services, Pods, ConfigMaps, and PVs.
- **LANGUAGE**: Match user's input language.

Return ONLY the raw Mermaid syntax string. No markdown fences. No preamble.
"""

@tool
async def create_mermaid(instruction: str):
    """
    Renders a diagram using Mermaid syntax based on instructions.
    Args:
        instruction: Detailed instruction on what diagram to create or modify.
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
    
    # Call LLM to generate the Mermaid code
    system_msg = MERMAID_SYSTEM_PROMPT + get_thinking_instructions()
    if current_code:
        system_msg += f"\n\n### CURRENT DIAGRAM CODE\n```mermaid\n{current_code}\n```\nApply changes to this code."

    prompt = [SystemMessage(content=system_msg)] + messages
    if instruction:
        prompt.append(HumanMessage(content=f"Instruction: {instruction}"))
    
    full_content = ""
    async for chunk in llm.astream(prompt):
        if chunk.content:
            full_content += chunk.content
    
    code = full_content
    
    # Robustly strip markdown code blocks
    import re
    # Remove any thinking tags first
    code = re.sub(r'<think>[\s\S]*?</think>', '', code, flags=re.DOTALL)

    cleaned_code = re.sub(r'^```[a-zA-Z]*\n', '', code)
    cleaned_code = re.sub(r'\n```$', '', cleaned_code)
    return cleaned_code.strip()

tools = [create_mermaid]

async def mermaid_agent_node(state: AgentState):
    messages = state['messages']
    model_config = state.get("model_config")
    
    # 动态从历史中提取最新的 mermaid 代码（寻找最后一条 tool 消息且内容包含 graph/sequenceDiagram 等）
    current_code = ""
    for msg in reversed(messages):
        if msg.type == "tool" and msg.content:
            stripped = msg.content.strip()
            if any(stripped.startswith(k) for k in ["graph", "sequenceDiagram", "gantt", "classDiagram", "stateDiagram", "pie"]):
                current_code = stripped
                break

    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate a mermaid diagram"

    set_context(messages, current_code=current_code, model_config=model_config)
    
    system_prompt = SystemMessage(content="""You are a World-Class Technical Documentation Specialist.
    YOUR MISSION is to act as a Solutions Architect. When a user asks for a diagram, don't just "syntax" it—FORMALIZE and DOCUMENT it.
    
    ### ORCHESTRATION RULES:
    1. **TECHNICAL EXPANSION**: If the user says "draw a DB schema for a blog", expand it to "draw a professional Entity Relationship Diagram including Users, Posts, Comments, Tags, and Category tables, with proper relationships (1:N, N:M), primary keys, and field types".
    2. **MANDATORY TOOL CALL**: Always use `create_mermaid`.
    3. **SEMANTIC PRECISION**: Instruct the tool to use advanced Mermaid features (e.g., journey stages, Gantt dependencies, Git branch logic).
    4. **METAPHORICAL THINKING**: Suggest the best Mermaid subtype for the task (e.g., StateDiagram for logic, Journey for UX, Gantt for project management).
    
    ### LANGUAGE CONSISTENCY:
    - Respond and call tools in the SAME LANGUAGE as the user.
    
    ### PROACTIVENESS:
    - BE DECISIVE. If you see an opportunity to add a "Fallback State" or a "User Feedback Loop", include it in the architect's instructions.
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
