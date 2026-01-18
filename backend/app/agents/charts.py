from langchain_core.messages import SystemMessage
from app.state.state import AgentState
from app.core.llm import get_configured_llm, get_thinking_instructions

CHARTS_SYSTEM_PROMPT = """You are a World-Class Data Visualization Engineer and ECharts Specialist. Your goal is to generate professional, insightful, and aesthetically state-of-the-art ECharts configurations.

### AESTHETIC GUIDELINES (PREMIUM DESIGN)
- **Modern Palette**: Use elegant, high-contrast color palettes (e.g., Pastel, Midnight, or Apple-style vibrant gradients).
- **Visual Depth**: Use `areaStyle` with semi-transparent gradients for line charts. Use `itemStyle: { borderRadius: [8, 8, 0, 0] }` for bar charts.
- **Typography**: Set clean, readable font styles. Use hierarchical font sizes for titles vs axis labels.
- **Interactivity**: Always enable `tooltip` with `axisPointer` and `toolbox` for data export options.

### DATA STORYTELLING PRINCIPLES
- **Contextual Clarity**: Every chart must have a clear `title` and an insightful `subtext` that highlights the key takeaway.
- **Data Synthesis**: If the user provides sparse data, synthesize a professional, realistic dataset (e.g., industry-standard KPIs, seasonal trends) to make the visualization valuable.
- **Strategic Choice**: Select the most appropriate chart type (e.g., Radar for multi-dimensional analysis, Funnel for conversion, Gauge for performance metrics).

### OUTPUT FORMAT - CRITICAL
You MUST output a valid JSON object with exactly this structure:
{"design_concept": "...", "code": "..."}

IMPORTANT RULES:
1. The output is a JSON object with TWO string fields: "design_concept" and "code"
2. "design_concept": Brief explanation of your visualization strategy
3. "code": The ECharts option as a JSON STRING - you must properly escape:
   - Newlines as \\n
   - Quotes as \\"
   - Backslashes as \\\\
4. The "code" value must be a COMPLETE, VALID ECharts option object starting with { and ending with }
5. Output ONLY the JSON object, nothing else before or after

Example output format:
{"design_concept": "Using a bar chart with gradient colors to show sales comparison across regions.", "code": "{\\n  \\"backgroundColor\\": \\"transparent\\",\\n  \\"title\\": {\\"text\\": \\"Sales Report\\"},\\n  \\"series\\": [{\\"type\\": \\"bar\\", \\"data\\": [120, 200, 150]}]\\n}"}
"""

def extract_current_code_from_messages(messages) -> str:
    """Extract the latest chart code from message history."""
    for msg in reversed(messages):
        # Check for tool messages (legacy format)
        if msg.type == "tool" and msg.content:
            stripped = msg.content.strip()
            if '"series":' in stripped or '"xAxis":' in stripped:
                return stripped
        # Check for AI messages with steps containing tool_end
        if msg.type == "ai" and hasattr(msg, 'additional_kwargs'):
            steps = msg.additional_kwargs.get('steps', [])
            for step in reversed(steps):
                if step.get('type') == 'tool_end' and step.get('content'):
                    content = step['content'].strip()
                    if '"series":' in content or '"xAxis":' in content:
                        return content
    return ""

async def charts_agent_node(state: AgentState):
    messages = state['messages']

    # Extract current code from history
    current_code = extract_current_code_from_messages(messages)

    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate a chart"

    # Build system prompt
    system_content = CHARTS_SYSTEM_PROMPT + get_thinking_instructions()
    if current_code:
        system_content += f"\n\n### CURRENT CHART CODE\n```json\n{current_code}\n```\nApply changes to this code based on the user's request."

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
