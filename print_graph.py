from backend.app.graph import build_triage_graph

graph = build_triage_graph()

# Simple text version - works everywhere, no extra installs
print(graph.get_graph().draw_ascii())