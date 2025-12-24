from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from app.state.state import AgentState
from app.core.config import settings
from app.core.llm import get_llm
from app.core.context import set_context, get_messages, get_context

llm = get_llm()

FLOW_SYSTEM_PROMPT = """You are an expert Flowchart Generator.
Your goal is to generate high-end, professional flowcharts in JSON format for React Flow.

### NODE TYPES (V4 MODERN CARD)
- `start`: Flow entry point (Pill shape).
- `end`: Flow exit point (Pill shape).
- `process`: Action step (Modern Card with accent bar).
- `decision`: Logic branch (Amber SVG Diamond). ALWAYS has multiple outgoing edges.

### DESIGN PRINCIPLES (CRITICAL)
1. **NO MANUAL STYLING**: NEVER include "style", "className", or "transform" in the JSON. The system handles all appearance natively.
2. **NO ROTATION**: NEVER rotate nodes. The "decision" diamond is handled by the system geometry.
3. **Clarity**: Keep labels concise and professional.

### LAYOUT & GRID
Nodes MUST be placed on a clean grid.
- **Vertical spacing**: Exactly **250px** between sequential nodes.
- **Horizontal spacing**: Exactly **400px** for parallel branches.
- **Positioning**: Start at { "x": 0, "y": 0 }.

### OUTPUT FORMAT (JSON)
{
  "nodes": [
    { "id": "1", "type": "start", "data": { "label": "START" }, "position": { "x": 0, "y": 0 } },
    { "id": "2", "type": "process", "data": { "label": "STEP 1" }, "position": { "x": 0, "y": 250 } }
  ],
  "edges": [
    { "id": "e1-2", "source": "1", "target": "2", "animated": true }
  ]
}

Return ONLY raw JSON. NO markdown code blocks.
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
    
    # Call LLM to generate the Flow JSON
    system_msg = FLOW_SYSTEM_PROMPT
    if current_code:
        system_msg += f"\n\n### CURRENT FLOWCHART CODE (JSON)\n```json\n{current_code}\n```\nApply changes to this code."

    prompt = [SystemMessage(content=system_msg)] + messages
    if instruction:
        prompt.append(HumanMessage(content=f"Instruction: {instruction}"))
    
    response = await llm.ainvoke(prompt)
    json_str = response.content
    
    # Strip potential markdown boxes
    import re
    cleaned_json = re.sub(r'^```[a-zA-Z]*\n', '', json_str)
    cleaned_json = re.sub(r'\n```$', '', cleaned_json)
    
    return cleaned_json.strip()

tools = [create_flow]
llm_with_tools = llm.bind_tools(tools)

async def flow_agent_node(state: AgentState):
    messages = state['messages']
    current_code = state.get("current_code", "")
    set_context(messages, current_code=current_code)
    
    system_prompt = SystemMessage(content="""You are an expert Flowchart Orchestrator.
    Your goal is to understand the user's request and call the `create_flow` tool with the appropriate instructions.
    
    Interpret the flowchart requirements and provide a clear instruction to the tool.
    """)
    
    response = await llm_with_tools.ainvoke([system_prompt] + messages)
    return {"messages": [response]}
