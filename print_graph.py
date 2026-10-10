import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.graph import build_triage_graph

def main():
    print("=" * 60)
    print("AEGIS MULTI-AGENT TRIAGE WORKFLOW GRAPH")
    print("=" * 60)

    graph = build_triage_graph()
    g = graph.get_graph()

    # 1. Mermaid syntax representation (works out of the box, zero dependencies)
    print("\n--- Mermaid Diagram (copy into any markdown viewer / mermaid.live) ---")
    try:
        mermaid_syntax = g.draw_mermaid()
        print(mermaid_syntax)
    except Exception as e:
        print(f"Could not generate Mermaid syntax: {e}")

    # 2. ASCII diagram (requires grandalf if installed)
    print("\n--- ASCII Diagram ---")
    try:
        print(g.draw_ascii())
    except ImportError:
        print("Note: To view ASCII graph layout directly in terminal, run: pip install grandalf")
        print("\nWorkflow Nodes & Execution Flow:")
        print("  START -> [gather_evidence] -> [clinical] -> [emergency] -> [pharmacist] -> [consensus] -> [finalize] -> END")
        print("  - gather_evidence: Deterministic intake, category routing & ChromaDB Vector RAG retrieval")
        print("  - clinical: General Physician + Specialists (Cardio / Pulm / ENT / Orthopedic)")
        print("  - emergency: Fast-path emergency validation")
        print("  - pharmacist: Safety checks & prescription drug stripping")
        print("  - consensus: Specialist agreement scoring & synthesis")
        print("  - finalize: Confidence score calculation & risk classification")

    # 3. Optional PNG export
    try:
        png_data = g.draw_mermaid_png()
        with open("workflow_graph.png", "wb") as f:
            f.write(png_data)
        print("\n[SUCCESS] Exported high-res workflow diagram to 'workflow_graph.png'")
    except Exception:
        # draw_mermaid_png requires internet connection or pygraphviz/mermaid CLI
        pass

    print("=" * 60)

if __name__ == "__main__":
    main()