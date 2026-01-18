from langgraph.graph import StateGraph, END
from app.state.state import AgentState
from app.agents.dispatcher import router_node, route_decision
from app.agents.mindmap import mindmap_agent_node as mindmap_agent
from app.agents.flow import flow_agent_node as flow_agent
from app.agents.mermaid import mermaid_agent_node as mermaid_agent
from app.agents.charts import charts_agent_node as charts_agent
from app.agents.drawio import drawio_agent_node as drawio_agent
from app.agents.infographic import infographic_agent_node as infographic_agent
from app.agents.general import general_agent_node as general_agent

# Define the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("router", router_node)
workflow.add_node("mindmap_agent", mindmap_agent)
workflow.add_node("flow_agent", flow_agent)
workflow.add_node("mermaid_agent", mermaid_agent)
workflow.add_node("charts_agent", charts_agent)
workflow.add_node("drawio_agent", drawio_agent)
workflow.add_node("infographic_agent", infographic_agent)
workflow.add_node("general_agent", general_agent)

# Entry point
workflow.set_entry_point("router")

# Router edges
workflow.add_conditional_edges(
    "router",
    route_decision,
    {
        "mindmap_agent": "mindmap_agent",
        "flow_agent": "flow_agent",
        "mermaid_agent": "mermaid_agent",
        "charts_agent": "charts_agent",
        "drawio_agent": "drawio_agent",
        "infographic_agent": "infographic_agent",
        "general_agent": "general_agent"
    }
)

# All agents now directly output JSON and end (no tool calls needed)
workflow.add_edge("mindmap_agent", END)
workflow.add_edge("flow_agent", END)
workflow.add_edge("mermaid_agent", END)
workflow.add_edge("charts_agent", END)
workflow.add_edge("drawio_agent", END)
workflow.add_edge("infographic_agent", END)
workflow.add_edge("general_agent", END)

# Compile
graph = workflow.compile()
