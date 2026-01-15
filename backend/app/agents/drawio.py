from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from app.core.config import settings
from app.core.llm import get_llm, get_configured_llm, get_thinking_instructions
from app.state.state import AgentState
from app.core.context import get_messages, get_context, set_context

DRAWIO_SYSTEM_PROMPT = """You are a Principal Cloud Solutions Architect and Draw.io (mxGraph) Master. Your goal is to generate professional, high-fidelity, and architecturally accurate Draw.io XML.

### ARCHITECTURAL PRINCIPLES
- **Structural Integrity**: Don't just draw blocks. Design complete systems. For "Microservices", include API Gateways, Service Discovery, Load Balancers, and dedicated Data Stores.
- **Logical Zonation**: Use containers, swimlanes, or VPC boundaries to group related components. Clearly separate Frontend, Backend, Data, and Sidecar layers.
- **Visual Professionalism**: Align elements on a clean grid. Use standard architectural symbols (cylinders for DBs, clouds for VPCs, gear for processing). Use professional, unified color palettes (e.g., AWS/Azure/GCP standard colors).

### XML TECHNICAL RULES
1. Root structure: `<mxfile>` -> `<diagram>` -> `<mxGraphModel>` -> `<root>`.
2. Base cells: `<mxCell id="0" />` and `<mxCell id="1" parent="0" />`.
3. All components MUST have `parent="1"`.
4. **NO COMPRESSION**: Output raw, uncompressed, human-readable XML. Use `style` attributes for all visual properties.

### EXECUTION & ENRICHMENT
- **MANDATORY ENRICHMENT**: Transform high-level requests into detailed blueprints. If a user asks for "Next.js on AWS", generate a diagram showing Vercel (or AWS Amplify), Edge Functions, S3 buckets, Lambda, and DynamoDB.
- **LANGUAGE**: All labels must match the user's input language.

RETURN ONLY THE RAW XML STRING. NO PREAMBLE. NO MARKDOWN FENCES.
"""

@tool
async def render_drawio_xml(instruction: str):
    """
    Renders a Draw.io XML diagram based on instructions.
    Args:
        instruction: Detailed instruction on what diagram to create or modify.
    """
    messages = get_messages()
    
    # Call LLM to generate the Draw.io XML
    system_msg = DRAWIO_SYSTEM_PROMPT + get_thinking_instructions()

    prompt = [SystemMessage(content=system_msg)] + messages
    if instruction:
        prompt.append(HumanMessage(content=f"Instruction: {instruction}"))
    
    full_content = ""
    context = get_context()
    model_config = context.get("model_config")
    llm = get_llm(
        model_name=model_config.get("model_id") if model_config else None,
        api_key=model_config.get("api_key") if model_config else None,
        base_url=model_config.get("base_url") if model_config else None
    )
    async for chunk in llm.astream(prompt):
        if chunk.content:
            full_content += chunk.content
    
    xml_content = full_content
    
    if not xml_content:
        return "Error: No XML content generated."
    
    # Robustly strip markdown code blocks
    import re
    # Remove any thinking tags first
    xml_content = re.sub(r'<think>[\s\S]*?</think>', '', xml_content, flags=re.DOTALL)

    xml_content = re.sub(r'^```[a-zA-Z]*\n', '', xml_content)
    xml_content = re.sub(r'\n```$', '', xml_content)
    
    return xml_content.strip()

tools = [render_drawio_xml]

async def drawio_agent_node(state: AgentState):
    messages = state['messages']
    
    # Safety: Ensure no empty text content blocks reach the LLM
    for msg in messages:
        if hasattr(msg, 'content') and not msg.content:
            msg.content = "Generate a diagram"
    set_context(messages, model_config=state.get("model_config"))

    llm = get_configured_llm(state)
    llm_with_tools = llm.bind_tools(tools)
    
    system_prompt = SystemMessage(content="""You are a Visionary Principal System Architect.
    YOUR MISSION is to act as a Chief Technical Lead. When a user asks for a diagram, don't just "draw" components—SOLVE for scalability, security, and flow.

    ### ⚠️ CRITICAL REQUIREMENT - MUST USE TOOLS:
    **YOU MUST USE THE `render_drawio_xml` TOOL TO GENERATE DIAGRAMS. NEVER OUTPUT DIAGRAM CODE DIRECTLY IN YOUR TEXT RESPONSE.**
    - You MUST call the `render_drawio_xml` tool - this is non-negotiable.
    - Do NOT write Draw.io XML in your response text.
    - Do NOT provide code blocks with diagram syntax in your text.
    - ONLY use the tool call mechanism to generate diagrams.

    ### ORCHESTRATION RULES:
    1. **ARCHITECTURAL EXPANSION**: If the user says "draw a login flow", expand it to "draw a high-fidelity system architecture for an authentication service, including Frontend, API Gateway, Auth Microservice, Session Cache (Redis), and User Database, with proper connectors and professional styling".
    2. **MANDATORY TOOL CALL**: Always use `render_drawio_xml`.
    3. **HI-FI SPECIFICATIONS**: Instruct the tool to include specific XML properties and shapes that represent professional architecture (e.g., cloud provider icons, database cylinders, cloud boundaries).
    4. **METAPHORICAL THINKING**: Use layouts that represent the flow (e.g., Top-to-Bottom for layers, Left-to-Right for streams).
    
    ### LANGUAGE CONSISTENCY:
    - Respond and call tools in the SAME LANGUAGE as the user.
    
    ### PROACTIVENESS:
    - BE DECISIVE. If you see an opportunity to add a "CDN" or "Security Layer", include it in the architect's instructions.
    """ + get_thinking_instructions())
    
    full_response = None
    async for chunk in llm_with_tools.astream([system_prompt] + messages):
        if full_response is None:
            full_response = chunk
        else:
            full_response += chunk
    return {"messages": [full_response]}
