import re, json, difflib
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END

from backend.app.clinical import (
    query_llm,
    detect_symptom_category,
    detect_emergency_subtype,
    deterministic_emergency_screen,
    strip_markdown_formatting,
    OLLAMA_ASSESSMENT_TOKENS,
    OLLAMA_SYNTHESIS_TOKENS
)
from rag.retrieval import get_rag


def _merge_dicts(left: dict, right: dict) -> dict:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class TriageState(TypedDict, total=False):
    patient_complaint: str
    category: str
    is_emergency: bool
    active_specs: list
    citations: list
    grounding_text: str
    specialists: Annotated[dict, _merge_dicts]
    pharmacist_review: str
    treatment_remedies: dict
    consensus: str
    verification: str
    explainability: str
    confidence_score: float
    risk_level: str


def gather_evidence(state: TriageState) -> dict:
    complaint = state["patient_complaint"]
    is_emergency = deterministic_emergency_screen(complaint)
    category = detect_symptom_category(complaint)

    print(f"[ROUTING] complaint='{complaint}' -> category={category}, is_emergency={is_emergency}")

    active_specs = ["General Physician"]

    if category == "ent":
        active_specs.append("ENT Specialist")
    elif category == "cardio":
        active_specs.append("Cardiologist")
    elif category == "pulm":
        active_specs.append("Pulmonologist")
    elif category == "ortho":
        active_specs.append("Orthopedic Specialist")

    rag = get_rag()

    clinical_docs = rag.retrieve(
        complaint,
        top_k=6
    )

    treatment_query = (
        f"{complaint} treatment management medicines medication "
        f"remedies supportive care dosage precautions contraindications"
    )

    treatment_docs = rag.retrieve(
        treatment_query,
        top_k=6
    )

    merged_docs = []
    seen_ids = set()

    for doc in clinical_docs + treatment_docs:
        doc_id = doc.get("doc_id")

        if doc_id not in seen_ids:
            seen_ids.add(doc_id)
            merged_docs.append(doc)

    citations = merged_docs

    grounding_text = "\n\n".join(
        f"Document [{d['doc_id']}]\n"
        f"Title: {d.get('title', '')}\n"
        f"Source: {d.get('source', '')}\n"
        f"Page: {d.get('page', '')}\n"
        f"Content:\n{d.get('text', '')}"
        for d in merged_docs
    )

    return {
        "category": category,
        "is_emergency": is_emergency,
        "active_specs": active_specs,
        "citations": citations,
        "grounding_text": grounding_text
    }


def node_clinical(state: TriageState) -> dict:
    active_specs = state.get("active_specs", [])
    complaint = state["patient_complaint"]
    grounding_text = state.get("grounding_text", "")

    specialist_name = next(
        (x for x in active_specs if x != "General Physician"),
        None
    )

    if specialist_name is None:
        prompt = f"""System: You are Aegis, an attending General Physician performing a triage assessment.

REFERENCE EVIDENCE:
{grounding_text}

Patient complaint: "{complaint}"

Using the retrieved clinical reference material where relevant, give a concise clinical assessment covering likely cause(s), what to monitor, and when to seek further care. Base the assessment on the retrieved evidence. Do not invent medical facts. Do not name prescription-only medications. Respond in plain sentences only."""

        text = query_llm(
            prompt,
            max_tokens=OLLAMA_ASSESSMENT_TOKENS
        )

        return {
            "specialists": {
                "General Physician": strip_markdown_formatting(text.strip())
            }
        }

    prompt = f"""System: You are Aegis. Produce two short clinical assessments for the same patient complaint: one as a General Physician and one as a {specialist_name}.

REFERENCE EVIDENCE:
{grounding_text}

Patient complaint: "{complaint}"

Base both assessments on the retrieved clinical evidence. Do not invent medical facts.

Respond in EXACTLY this format:

---GP---
<3-4 sentence General Physician assessment>

---SPECIALIST---
<3-4 sentence {specialist_name} assessment>

Do not name prescription-only medications. Respond in plain sentences only."""

    combined = query_llm(
        prompt,
        max_tokens=OLLAMA_ASSESSMENT_TOKENS * 2
    )

    gp_match = re.search(
        r"---GP---\s*(.*?)\s*---SPECIALIST---",
        combined,
        re.DOTALL
    )

    spec_match = re.search(
        r"---SPECIALIST---\s*(.*)",
        combined,
        re.DOTALL
    )

    gp_text = strip_markdown_formatting(
        gp_match.group(1).strip() if gp_match else combined.strip()
    )

    spec_text = strip_markdown_formatting(
        spec_match.group(1).strip() if spec_match else ""
    )

    return {
        "specialists": {
            "General Physician": gp_text,
            specialist_name: spec_text
        }
    }


def emergency_node(state: TriageState) -> dict:
    if not state.get("is_emergency"):
        return {}

    subtype = detect_emergency_subtype(
        state["patient_complaint"]
    )

    prompt = f"""System: You are Aegis emergency triage specialist.

Patient complaint:
{state["patient_complaint"]}

Detected emergency subtype:
{subtype}

Retrieved clinical evidence:
{state.get("grounding_text", "")}

Provide an immediate emergency-risk assessment based on the complaint and retrieved clinical evidence. Clearly state that urgent medical evaluation is required when the presentation indicates an emergency. Do not invent facts. Do not prescribe medication. Respond in plain sentences only."""

    text = query_llm(
        prompt,
        max_tokens=OLLAMA_ASSESSMENT_TOKENS
    )

    return {
        "specialists": {
            "Emergency Specialist": strip_markdown_formatting(text.strip())
        }
    }


def pharmacist_node(state: TriageState) -> dict:
    complaint = state["patient_complaint"]
    grounding_text = state.get("grounding_text", "")

    prompt = f"""System: You are Aegis's Pharmacist Agent.

Your ONLY source of medical treatment information is the retrieved clinical reference evidence below.

PATIENT COMPLAINT:
{complaint}

RETRIEVED CLINICAL REFERENCE EVIDENCE:
{grounding_text}

TASK:

Carefully examine ALL retrieved evidence and extract treatment information that is relevant to the patient's complaint.

MEDICATIONS:
Give the exact medicine names or medicine classes that are explicitly mentioned in the retrieved evidence and are relevant to the complaint.

For every medicine mentioned, include:
- Medicine name
- Purpose or indication
- Dose only if explicitly stated
- Route only if explicitly stated
- Frequency only if explicitly stated
- Duration only if explicitly stated

REMEDIES:
Give non-drug treatments, supportive care, self-care measures, lifestyle measures, or other remedies explicitly supported by the retrieved evidence.

PRECAUTIONS:
Give warnings, contraindications, interactions, precautions, or situations requiring medical attention only when supported by the retrieved evidence.



IMPORTANT RULES:

Use ONLY the retrieved clinical reference evidence.

Do not use outside medical knowledge.

Do not invent medicine names.

Do not invent doses.

Do not invent frequencies.

Do not invent durations.

Do not invent remedies.

Do not create a fallback treatment.

Do not use a hard-coded disease or medicine database.

Do not remove valid medicine names from the retrieved evidence.

If the evidence contains relevant medicines or remedies, provide them clearly instead of giving a generic statement that no medication information was found.

If the evidence genuinely contains no relevant treatment information, state this briefly and do not invent treatment.

Keep all treatment information traceable to the retrieved evidence.

Respond in plain text using exactly these headings:

MEDICATIONS:
<relevant medicines from the evidence>

REMEDIES:
<relevant remedies from the evidence>

PRECAUTIONS:
<relevant precautions from the evidence>


"""

    text = query_llm(
        prompt,
        max_tokens=OLLAMA_ASSESSMENT_TOKENS
    )

    text = strip_markdown_formatting(text.strip())

    return {
        "pharmacist_review": text,
        "treatment_remedies": {
            "pharmacist": text
        }
    }


def consensus_verify_node(state: TriageState) -> dict:
    specialists = state.get("specialists", {})
    grounding_text = state.get("grounding_text", "")
    complaint = state["patient_complaint"]

    specialist_text = json.dumps(specialists)

    prompt = f"""System: You are Aegis's senior clinical synthesis and verification agent.

Patient complaint:
{complaint}

Retrieved clinical reference evidence:
{grounding_text}

Specialist assessments:
{specialist_text}

Pharmacist review:
{state.get("pharmacist_review", "")}

Synthesize the available evidence and assessments. The retrieved clinical references are the grounding source. Do not invent diagnoses, treatments, medicines, or medical facts.

Verify that the pharmacist treatment information is actually supported by the retrieved clinical reference evidence.

Do not remove valid treatment information that is explicitly supported by the evidence.

Respond in EXACTLY this format:

---CONSENSUS---
<2-4 sentences describing the overall clinical impression, risk level, and next step>

---VERIFICATION---
<1-2 sentences explaining whether the assessment and treatment guidance are supported by the retrieved reference evidence>

---EXPLAIN---
<2-3 sentences explaining the result in simple patient-friendly language>

Do not prescribe prescription-only medications. Respond in plain sentences only."""

    combined = query_llm(
        prompt,
        max_tokens=OLLAMA_SYNTHESIS_TOKENS
    )

    consensus_match = re.search(
        r"---CONSENSUS---\s*(.*?)\s*---VERIFICATION---",
        combined,
        re.DOTALL
    )

    verification_match = re.search(
        r"---VERIFICATION---\s*(.*?)\s*---EXPLAIN---",
        combined,
        re.DOTALL
    )

    explain_match = re.search(
        r"---EXPLAIN---\s*(.*)",
        combined,
        re.DOTALL
    )

    consensus = strip_markdown_formatting(
        consensus_match.group(1).strip()
        if consensus_match else combined.strip()
    )

    verification = strip_markdown_formatting(
        verification_match.group(1).strip()
        if verification_match else ""
    )

    explainability = strip_markdown_formatting(
        explain_match.group(1).strip()
        if explain_match else ""
    )

    return {
        "consensus": consensus,
        "verification": verification,
        "explainability": explainability
    }


def finalize_node(state: TriageState) -> dict:
    citations = state.get("citations", [])

    scores = [
        c.get("score", 0.0)
        for c in citations
        if isinstance(c, dict)
    ]

    avg_similarity = (
        sum(scores) / len(scores)
        if scores else 0.0
    )

    specialists = state.get("specialists", {})

    if len(specialists) >= 2:
        texts = list(specialists.values())

        agreement = difflib.SequenceMatcher(
            None,
            texts[0].lower(),
            texts[1].lower()
        ).ratio()

        consensus_score = round(
            0.6 + agreement * 0.4,
            4
        )
    else:
        consensus_score = 0.75

    confidence_score = round(
        min(
            0.99,
            avg_similarity * 0.6 + consensus_score * 0.4
        ),
        4
    )

    if state.get("is_emergency"):
        risk_level = "EMERGENCY"
    else:
        c_upper = state.get("consensus", "").upper()

        if "EMERGENCY" in c_upper or "CRITICAL" in c_upper:
            risk_level = "EMERGENCY"
        elif "HIGH" in c_upper or "URGENT" in c_upper:
            risk_level = "HIGH"
        elif "MEDIUM" in c_upper or "MODERATE" in c_upper:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

    return {
        "confidence_score": confidence_score,
        "risk_level": risk_level
    }


def build_triage_graph():
    graph = StateGraph(TriageState)

    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("clinical", node_clinical)
    graph.add_node("emergency", emergency_node)
    graph.add_node("pharmacist", pharmacist_node)
    graph.add_node("consensus", consensus_verify_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "gather_evidence")
    graph.add_edge("gather_evidence", "clinical")
    graph.add_edge("clinical", "emergency")
    graph.add_edge("emergency", "pharmacist")
    graph.add_edge("pharmacist", "consensus")
    graph.add_edge("consensus", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()