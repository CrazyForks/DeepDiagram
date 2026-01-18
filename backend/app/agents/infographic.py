from langchain_core.messages import SystemMessage
from app.state.state import AgentState
from app.core.llm import get_configured_llm, get_thinking_instructions

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

### OUTPUT FORMAT - CRITICAL
You MUST output a valid JSON object with exactly this structure:
{"design_concept": "<your creative direction and template selection rationale>", "code": "<the AntV Infographic DSL>"}

Rules:
1. The JSON must be valid - escape all special characters properly (newlines as \\n, quotes as \\", etc.)
2. "design_concept" should briefly explain your creative direction, template choice, and visual storytelling approach
3. "code" contains ONLY the raw AntV Infographic DSL (no markdown fences)
4. Output ONLY the JSON object, nothing else before or after
"""

def extract_current_code_from_messages(messages) -> str:
    """Extract the latest infographic code from message history."""
    for msg in reversed(messages):
        # Check for tool messages (legacy format)
        if msg.type == "tool" and msg.content:
            stripped = msg.content.strip()
            if stripped.startswith('infographic '):
                return stripped
        # Check for AI messages with steps containing tool_end
        if msg.type == "ai" and hasattr(msg, 'additional_kwargs'):
            steps = msg.additional_kwargs.get('steps', [])
            for step in reversed(steps):
                if step.get('type') == 'tool_end' and step.get('content'):
                    content = step['content'].strip()
                    if content.startswith('infographic '):
                        return content
    return ""

async def infographic_agent_node(state: AgentState):
    messages = state['messages']

    # Extract current code from history
    current_code = extract_current_code_from_messages(messages)

    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate an infographic"

    # Build system prompt
    system_content = INFOGRAPHIC_SYSTEM_PROMPT + get_thinking_instructions()
    if current_code:
        system_content += f"\n\n### CURRENT INFOGRAPHIC CODE\n```\n{current_code}\n```\nApply changes to this code based on the user's request."

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
