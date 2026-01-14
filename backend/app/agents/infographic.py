from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from app.state.state import AgentState
from app.core.config import settings
from app.core.llm import get_llm, get_configured_llm, get_thinking_instructions
from app.core.context import set_context, get_messages, get_context

INFOGRAPHIC_SYSTEM_PROMPT = """You are a World-Class Graphic Designer and Infographic Consultant. Your goal is to generate professional, visually stunning AntV Infographic DSL syntax.

### DESIGN PHILOSOPHY
- **Narrative Flow**: Don't just present data; tell a story. Use `data.desc` to provide context, "Why it matters", and "Key Insights".
- **Visual Metaphor**: Carefully select icons (`icon`) and illustrations (`illus`) that provide metaphorical depth, not just literal labels.
- **Aesthetic Balance**: Ensure a harmony between titles, descriptions, and visual elements. Use professional, industry-standard color palettes.

### TEMPLATE SELECTION (SELECT THE MOST IMPACTFUL)
- **Processes**: `sequence-snake-steps-compact-card` (Modern), `sequence-zigzag-steps-underline-text` (Professional).
- **Comparisons**: `compare-binary-horizontal-badge-card-arrow` (High-contrast), `compare-swot` (Strategic).
- **Dashboards**: `chart-pie-compact-card`, `list-grid-candy-card-lite` (Premium Grid).
- **Hierarchies**: `hierarchy-tree-tech-style-badge-card` (Enterprise), `relation-circle-icon-badge` (Dynamic).

### DSL SYNTAX RULES
- Start with `infographic <template-name>`.
- Use two-space indentation for blocks (`data`, `theme`).
- `data` block: `title`, `desc`, and `items` array.
- Items can have: `label`, `value`, `desc`, `icon` (format: `<collection>/<name>`), `illus` (unDraw filename).
- `theme` block: `theme dark`, `theme hand-drawn`, or `palette` array of hex codes.

### EXECUTION & ENRICHMENT
- **MANDATORY ENRICHMENT**: Transform simple inputs into a complete narrative. If a user says "Coffee process", expand to "The Art of the Perfect Brew", covering Selection, Roasting, Grinding, and Extraction with professional terminology.
- **DATA SYNTHESIS**: Conceptualize realistic, data-driven values (`value`) that add weight and authority to the visualization.
- **LANGUAGE**: Match user's input language.

OUTPUT ONLY THE DSL. NO PREAMBLE. NO MARKDOWN FENCES.
"""

@tool
async def create_infographic(instruction: str):
    """
    Renders an Infographic using AntV Infographic DSL based on instructions.
    Args:
        instruction: Detailed instruction on what infographic to create or modify.
    """
    messages = get_messages()
    context = get_context()
    current_code = context.get("current_code", "")
    
    # Call LLM to generate the Infographic DSL
    system_msg = INFOGRAPHIC_SYSTEM_PROMPT + get_thinking_instructions()
    if current_code:
        system_msg += f"\n\n### CURRENT INFOGRAPHIC CODE\n```\n{current_code}\n```\nApply changes to this code."
        
    prompt = [SystemMessage(content=system_msg)] + messages
    if instruction:
        prompt.append(HumanMessage(content=f"Instruction: {instruction}"))
    
    # Using astream to allow the graph's astream_events to catch it
    full_content = ""
    model_config = context.get("model_config")
    llm = get_llm(
        model_name=model_config.get("model_id") if model_config else None,
        api_key=model_config.get("api_key") if model_config else None,
        base_url=model_config.get("base_url") if model_config else None
    )
    async for chunk in llm.astream(prompt):
        content = chunk.content
        if content:
            full_content += content
    
    dsl_str = full_content
    
    # Robust Stripping: Extract from ``` blocks if present
    import re
    # Remove any thinking tags first
    dsl_str = re.sub(r'<think>[\s\S]*?</think>', '', dsl_str, flags=re.DOTALL)

    code_block_match = re.search(r'```(?:\w+)?\n([\s\S]*?)```', dsl_str)
    if code_block_match:
        dsl_str = code_block_match.group(1).strip()
    
    # Further ensure it starts with infographic keyword
    if 'infographic' in dsl_str and not dsl_str.strip().startswith('infographic'):
        infographic_match = re.search(r'infographic[\s\S]*', dsl_str)
        if infographic_match:
            dsl_str = infographic_match.group(0).strip()
    
    return dsl_str.strip()

tools = [create_infographic]

async def infographic_agent_node(state: AgentState):
    messages = state['messages']
    
    # 动态从历史中提取最新的 infographic 代码（寻找最后一条 tool 消息且内容包含 infographic）
    current_code = ""
    for msg in reversed(messages):
        if msg.type == "tool" and msg.content:
            stripped = msg.content.strip()
            if stripped.startswith('infographic '):
                current_code = stripped
                break

    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate an infographic"

    set_context(messages, current_code=current_code, model_config=state.get("model_config"))
    
    system_prompt = SystemMessage(content="""You are an expert Infographic Orchestrator. 
    YOUR MISSION is to act as a Consultative Creative Director. When a user provides a request, don't just pass it through—EXPAND and ENRICH it.
    
    ### ORCHESTRATION RULES:
    1. **CREATIVE EXPANSION**: If the user says "draw a timeline for AI", don't just send that. Expand it to "draw a professional timeline of AI development from 1950 to 2024, including key milestones, Turing test, deep learning era, and GenAI explosion, with professional descriptions and icons".
    2. **MANDATORY TOOL CALL**: Always use `create_infographic`.
    3. **DATA SYNTHESIS**: If the user lacks data, conceptualize professional data points that make the infographic insightful.
    4. **METAPHORICAL THINKING**: Suggest templates that fit the "Vibe" of the content (e.g., roadmap for strategy, pyramid for hierarchy, high-contrast comparison for VS).
    
    ### LANGUAGE CONSISTENCY:
    - Respond and call tools in the SAME LANGUAGE as the user.
    
    ### PROACTIVENESS:
    - BE DECISIVE. If you see an opportunity to add a "Did you know?" section or a "Key Metric", include it in the tool instruction.
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
