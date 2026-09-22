# Multi-Agent AI System for Collaborative Medical Diagnosis using Local Large Language Models

## Introduction

This project presents a **local Multi-Agent AI system for collaborative medical diagnosis and symptom analysis** using Large Language Models (LLMs). The system combines **Generative AI, Retrieval-Augmented Generation (RAG), and Multi-Agent Architecture** to provide evidence-based medical responses.

The system uses **Ollama with Gemma 3 4B** for local LLM inference and **ChromaDB with Nomic Embeddings** for retrieving relevant information from medical reference documents.

The project is designed with an **offline-oriented architecture**, reducing dependency on external cloud-based AI services.

> **Disclaimer:** This is an academic/research prototype and is not intended to replace professional medical diagnosis or treatment.

---

## Technology Stack

- **Programming Language:** Python
- **LLM:** Gemma 3 4B
- **LLM Runtime:** Ollama
- **Agent Framework:** LangGraph
- **RAG:** Retrieval-Augmented Generation
- **Vector Database:** ChromaDB
- **Embedding Model:** Nomic Embed Text
- **Backend:** FastAPI
- **Frontend:** HTML, CSS, JavaScript
- **Document Processing:** PyMuPDF
- **Communication:** Server-Sent Events (SSE)

---

## Workflow

```text
User
  ↓
Text / Voice Input
  ↓
FastAPI Backend
  ↓
Medical Evidence Retrieval
  ↓
Emergency Screening
  ↓
General Physician Agent
  ↓
Domain Specialist Agent
  ↓
Pharmacist Safety Agent
  ↓
Consensus & Verification
  ↓
Final Response / Report
```
---

## System architecture

The system uses multiple specialized agents instead of relying on a single LLM.

Emergency Specialist: Identifies potential emergency indicators.
General Physician Lead: Performs primary intake and triage.
Domain Specialist: Performs specialized analysis such as ENT, Cardiology, or Pulmonology.
Pharmacist Safety Agent: Performs medication-related safety verification.
Consensus & Verification Agent: Combines agent outputs and retrieved evidence to generate the final response.
Working

The medical reference PDFs are first processed through the RAG pipeline.

Medical PDFs
     ↓
Text Extraction
     ↓
Chunking
     ↓
Nomic Embeddings
     ↓
ChromaDB

When the user provides a medical query, the query is converted into an embedding and relevant medical information is retrieved from ChromaDB.

The retrieved evidence is then passed to the multi-agent workflow along with the user information. The agents collaboratively analyze the case, perform safety checks, verify the evidence, and generate the final response.

The LLM inference is performed locally through Ollama and Gemma 3 4B.

## How to Run
1. Install Ollama

Install Ollama and download the required models:

ollama pull gemma3:4b
ollama pull nomic-embed-text

2. Create Virtual Environment
python -m venv venv

Activate the environment.

Windows:

venv\Scripts\activate

Linux/macOS:

source venv/bin/activate

3. Install Dependencies
cd backend
pip install -r requirements.txt

5. Run RAG Ingestion

Process the required medical reference PDFs using the ingestion script:

python rag/ingestion/pdf_ingest.py

5. Start Backend

From the backend directory:

uvicorn app.main:app --reload

6. Start Frontend

Open another terminal and run:

cd frontend
python -m http.server 5500

Open:

http://localhost:5500

---

## Conclusion

This project demonstrates how Local LLMs, RAG, and Multi-Agent AI can be combined to build an evidence-grounded medical assistance system.

By using specialized agents, local model inference, medical document retrieval, and a stateful LangGraph workflow, the system provides a structured approach to collaborative medical symptom analysis while keeping the core AI processing within the local environment.

This project serves as an academic implementation and foundation for further research in Agentic AI, Generative AI, RAG, and Local Large Language Models.
