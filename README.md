# AEGIS: Multi-Agent AI System for Collaborative Medical Diagnosis & Triage

AEGIS is an offline-first, stateful multi-agent clinical decision-support and triage system powered by local Large Language Models (**Gemma 3 4B via Ollama**) and Vector Retrieval-Augmented Generation (**ChromaDB + Nomic Embeddings**). It supports speech input via **OpenAI Whisper** and generates structured clinical triage reports in PDF format with evidence grounding citations.

---

## 🌟 Key Features

- **Stateful Multi-Agent Orchestration**: Built with **LangGraph**, coordinating specialized agents:
  - **General Physician Agent**: Performs preliminary assessment and clinical reasoning.
  - **Domain Specialist Agents**: Condition-specific clinical analysis (**Cardiology**, **Pulmonology**, **ENT**, and **Orthopedics**).
  - **Emergency Fast-Path Node**: Deterministic rule-based detection for critical cases (e.g., stroke, myocardial infarction) that reduces latency and bypasses non-essential generative steps.
  - **Pharmacist Safety Filter**: Adversarial validation layer that enforces OTC-only rules, flags contraindications, and strips prescription-only medication.
  - **Consensus Coordinator**: Evaluates specialist concordance, computes semantic agreement, and calculates risk urgency (**LOW**, **MEDIUM**, **HIGH**, **EMERGENCY**).
- **Vector RAG Pipeline**:
  - Embedded medical knowledge base containing clinical documents and medical reference books (**Gale Encyclopedia of Medicine** and **WHO IMAI District Clinician Manual**).
  - Indexed using **ChromaDB** with **Nomic Embed Text** embeddings.
  - Grounded citations with source titles, page numbers, and cosine similarity scores.
- **Speech Recognition**: Offline-ready speech-to-text input via **OpenAI Whisper**, converted to 16 kHz mono PCM WAV format.
- **Privacy & Local Execution**: Fully on-premise execution using **Ollama** and local vector databases—no patient data is sent to external cloud APIs.
- **Interactive Web UI & Reports**: Real-time triage updates streamed via **Server-Sent Events (SSE)** and automated PDF triage report generation using **fpdf2**.

---

## 🏗️ System Architecture

```
[Patient Speech / Text Input]
               │
               ▼
     [Whisper Transcription]
               │
               ▼
    [Dynamic Intake Router]
               │
               ▼
[Deterministic Emergency & Negation Screen]
               │
               ▼
 [ChromaDB Vector Retrieval (RAG)] <─── [WHO IMAI & Gale Knowledge Base]
               │
               ▼
    [LangGraph StateGraph]
    ├── General Physician Agent
    ├── Specialist (Cardio / Pulm / ENT / Ortho)
    ├── Emergency Node
    ├── Pharmacist Safety Agent (OTC Filter)
    └── Consensus Coordinator
               │
               ▼
 [Confidence Scoring & Risk Classification]
               │
               ▼
  [FastAPI Backend + SSE Streaming Web UI] ───> [Automated PDF Report]
```

---

## 📂 Project Structure

```
AGENTIC-Med/
├── backend/
│   ├── app/
│   │   ├── agents.py           # Aegis triage pipeline & intake router
│   │   ├── clinical.py         # LLM query runner, emergency rules, and prompts
│   │   ├── graph.py            # LangGraph multi-agent workflow definition
│   │   ├── main.py             # FastAPI server, endpoints, SSE & Whisper handler
│   │   └── pdf.py              # Downloadable triage PDF report generator
│   ├── eval_harness.py         # Clinical benchmark validation harness (23 cases)
│   └── requirements.txt        # Python backend dependencies
├── frontend/
│   ├── index.html              # Web interface structure
│   ├── style.css               # Clinical UI styling
│   ├── app.js                  # Frontend interaction, audio recording, and SSE
│   └── reports/                # Output directory for generated PDF reports
├── rag/
│   ├── retrieval.py            # VectorRAG client with ChromaDB & Ollama embeddings
│   ├── ingestion/
│   │   └── pdf_ingest.py       # Knowledge base ingestion script for source PDFs
│   └── data/
│       ├── chroma_db/          # Persistent Chroma vector store
│       ├── sources/            # Reference medical source PDFs (WHO IMAI, Gale)
│       └── clinical_docs.json  # Structured clinical reference items
├── docker/
│   ├── Dockerfile              # Container configuration
│   └── docker-compose.yml      # Service orchestration
├── .env.example                # Sample environment variables
├── .gitignore                  # Git ignore rules
└── RAG_AND_LANGGRAPH.md        # Technical architecture documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running locally
- FFmpeg (for audio handling)

### 2. Pull Required Models
```bash
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Vector Knowledge Base Ingestion (One-time)
If the Chroma vector store is not already initialized, run:
```bash
python -m rag.ingestion.pdf_ingest
```

### 5. Run the Application
Start the FastAPI server:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 5000 --reload
```
Open your browser and navigate to:
```
http://localhost:5000
```

---

## 📊 Benchmark & Evaluation
Run the automated clinical benchmark harness (tested on 23 clinical cases):
```bash
python backend/eval_harness.py
```
Evaluation metrics:
- **Symptom Category Routing Accuracy**: 100% (23/23 cases)
- **Deterministic Emergency Screening Accuracy**: 100% (23/23 cases)

---
## Screenshots:
<img width="1917" height="963" alt="Screenshot 2026-10-10 210812" src="https://github.com/user-attachments/assets/b0d0867e-dff8-4ee7-bf94-9006e5c290ae" />
<img width="1917" height="965" alt="Screenshot 2026-10-10 210703" src="https://github.com/user-attachments/assets/2ef5eadd-9094-474c-9768-2a6fa2b333ef" />

<img width="1917" height="967" alt="image" src="https://github.com/user-attachments/assets/7d2c3ef9-0c29-4689-b05c-9824754d0251" />
---
## Report
[triage_report_2A5E3922.pdf](https://github.com/user-attachments/files/33285348/triage_report_2A5E3922.pdf)

---
## ⚖️ Disclaimer
*Aegis is an artificial intelligence-based clinical decision-support and triage prototype designed for research and educational purposes. It does NOT provide official medical diagnosis or treatment. Always consult a qualified physician for clinical decisions.*
