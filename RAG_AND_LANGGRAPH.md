# Embeddings + Vector DB + LangGraph integration

This adds two things to the existing pipeline:

1. **Real embeddings in a vector DB**, replacing the old hand-rolled TF-IDF
   retriever, and grounded in two full reference books (Gale Encyclopedia of
   Medicine, WHO Model Formulary 2008) instead of just the 83-entry synthetic
   `clinical_docs.json`.
2. **LangGraph** as the orchestration framework for the triage pipeline,
   replacing the manual `ThreadPoolExecutor` fan-out.

Nothing in `backend/app/main.py`, `backend/app/pdf.py`, `backend/app/doc_reader.py`, or the frontend changed -
`AegisTriagePipeline`'s public methods (`run_intake_router`, `run_pipeline`,
`run_report_chat_assistant`) have the same signatures and return shapes as
before.

## What's new

| File | Purpose |
|---|---|
| `backend/app/clinical.py` | Ollama call, model/timeout config, the deterministic red-flag/category/fallback knowledge base, prescription-drug stripping. Pulled out of `agents.py` so `graph.py` can use it too without a circular import. |
| `rag/retrieval.py` | `VectorRAG` (Chroma + Ollama embeddings) and `get_rag()`, a singleton factory that prefers `VectorRAG` and falls back to the old TF-IDF `SimpleRAG` (`rag/rag.py`, unchanged) if the vector store hasn't been built yet. |
| `backend/app/graph.py` | The LangGraph `StateGraph`: `gather_evidence` -> `clinical` -> `emergency` -> `pharmacist` -> `consensus` -> `verify_explain` -> `finalize`. |
| `rag/ingestion/pdf_ingest.py` | Standalone script that chunks the two PDFs + `clinical_docs.json`, embeds every chunk, and upserts it into a persistent Chroma collection. Idempotent - safe to re-run. |
| `rag/data/sources/*.pdf` | The two source books, read by the ingestion script. |
| `backend/app/agents.py` | Now a thin wrapper: builds the graph once, invokes it per request, and keeps the exact same deterministic fallback behavior as before if the graph run fails. |
| `rag/rag.py` | **Unchanged.** Still the TF-IDF fallback. |

## Setup

```bash
pip install -r backend/requirements.txt

# Pull both models Ollama needs - the chat model you already had, plus an
# embedding model for the vector store:
ollama pull gemma3:4b
ollama pull nomic-embed-text
```

## Build the knowledge base (one-time, re-run whenever sources change)

```bash
python -m rag.ingestion.pdf_ingest
```

This reads `rag/data/sources/gale_encyclopedia_of_medicine.pdf` (759 pages),
`rag/data/sources/who_formulary_2008.pdf` (528 pages), and
`rag/data/clinical_docs.json`, and embeds roughly 2,000 chunks total into
`rag/data/chroma_db/`. On CPU this will take a while the first time -
that's expected. Progress prints every 500 chunks per source.

Useful flags:

```bash
python -m rag.ingestion.pdf_ingest --max-chunks 50   # smoke-test on a small slice first
python -m rag.ingestion.pdf_ingest --only who        # (re)ingest just one source: gale | who | clinical | all
python -m rag.ingestion.pdf_ingest --rebuild          # wipe the collection and re-embed everything
```

It's safe to re-run without `--rebuild` - chunk ids are derived from
`(source, page, chunk index)`, so already-embedded chunks are skipped.

## Running the app

Unchanged - `uvicorn backend.app.main:app --reload` or `docker compose up --build`.
On startup, `AegisTriagePipeline.__init__` calls `get_rag()`, which:

- Uses `VectorRAG` (Chroma + embeddings) if the collection above exists and
  has data, or
- Falls back to the original TF-IDF `SimpleRAG` over `clinical_docs.json`
  if ingestion hasn't been run yet, or Chroma/Ollama aren't reachable.

You'll see which one loaded in the startup logs:

```
[retrieval] Using VectorRAG (Chroma + Ollama embeddings)
```
or
```
[retrieval] VectorRAG unavailable (...); falling back to SimpleRAG (TF-IDF)
```

## Config (env vars, all optional)

| Var | Default | Purpose |
|---|---|---|
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model for both ingestion and query-time retrieval - must match on both sides. |
| `CHROMA_PERSIST_DIR` | `rag/data/chroma_db` | Where the vector store lives on disk. |
| `CHROMA_COLLECTION` | `aegis_medical_kb` | Chroma collection name. |
| `INGEST_CHUNK_WORDS` / `INGEST_CHUNK_OVERLAP` | `400` / `60` | Chunk size for the two PDFs (word-based sliding window). |
| `INGEST_EMBED_BATCH` | `64` | Chunks per embedding API call during ingestion. |

## Why LangGraph here specifically

The old code ran GP / specialist / emergency / pharmacist calls concurrently
via `ThreadPoolExecutor(max_workers=5)`, then ran consensus and
verification+explainability sequentially afterward, with the "wait for
everything before consensus" join written by hand. `backend/app/graph.py` expresses
that triage workflow as a stateful graph where execution flows sequentially through
`gather_evidence`, `clinical`, `emergency`, `pharmacist`, `consensus`, `verify_explain`,
and `finalize`. Chaining nodes sequentially avoids CPU thread contention between concurrent
Ollama calls on local hardware, while LangGraph cleanly manages state propagation across nodes.
If any node raises (e.g. Ollama is down), the exception propagates out of `graph.invoke()`
exactly like the old `future.result()` re-raise did, and `backend/app/agents.py`'s `run_pipeline()`
still catches it and drops to the same deterministic disease-profile fallback as before.

## Performance optimizations (latest update)

The initial LangGraph integration above was functionally correct but slow
on CPU-only Ollama (a full triage report could take 5-15+ minutes). These
changes cut real LLM call count roughly in half and removed hidden network
latency, without changing any public method signature or the frontend:

| Change | File | Effect |
|---|---|---|
| Merged GP + specialist into one call | `graph.py` (`node_clinical`) | 2 calls -> 1 |
| Consensus skips its LLM call with only one opinion | `graph.py` (`consensus_node`) | Saves 1 call on general complaints |
| Intake uses deterministic templates first, LLM only for ambiguous complaints | `agents.py` (`run_intake_router`) | Most intake turns: 0 calls instead of 1 |
| `num_ctx=2048` cap on every Ollama call | `clinical.py` | Faster per-token generation |
| Live PubMed/DuckDuckGo scraping disabled by default | `graph.py` (`gather_evidence`) | Removes up to ~12s of network wait per request; set `ENABLE_LIVE_WEB_EVIDENCE=true` to restore it |
| LLM-calling nodes chained sequentially instead of fanned out | `graph.py` (`build_triage_graph`) | Avoids CPU thread contention between concurrent Ollama calls |
| SSE stream yields its first event before the blocking pipeline runs (via `asyncio.to_thread`) | `main.py` | Progress bar starts moving immediately instead of freezing until the whole request finishes |
| Removed 6 artificial `sleep(0.3)` calls | `main.py` | Trivial but pure waste |
| PDF generation deferred to first download | `main.py` (`GET /api/reports/{case_id}/pdf`, `RESULTS_CACHE`) | Not on the critical path of every triage request |
| `/api/intake`, `/api/triage`, `/api/chat` run their pipeline calls via `asyncio.to_thread` | `main.py` | Event loop stays responsive during CPU-bound calls |

**Resulting LLM call count per triage request** (down from a flat 5-6 before):

| Case | Calls |
|---|---|
| General complaint (no specialist routed) | 3 (clinical, pharmacist, verify+explain) |
| ENT / Cardio / Pulm, non-emergency | 4 (+ consensus) |
| Emergency | 5 (+ emergency) |

**Not done** - these are real further wins from the same source document, but
larger engineering efforts rather than drop-in patches: converting the
pharmacist from an LLM persona into a deterministic drug-lookup tool (removes
one more full LLM call, but needs a structured medication/interaction
dataset first), structured JSON output per agent instead of prose, and an
explicit `INSUFFICIENT_EVIDENCE` abstention path.

## Startup warm-up

`backend/app/main.py` fires a tiny, throwaway Ollama call on server startup
(`warm_up_ollama`) so the chat model's weights are loaded into memory
during startup rather than during the first real patient request. Look for
`[startup] Ollama chat model warmed up and ready.` in the startup log; if
Ollama isn't reachable yet, it logs a fallback message instead and the app
still starts normally (the model just loads lazily on first use, same as
before this existed).

## Chest-pain phrasing fix (category routing + emergency screen)

`detect_symptom_category` and `deterministic_emergency_screen` originally
only recognized cardiac complaints via exact glued phrases like "chest
pain" / "chest pressure" / "chest tightness". Real phrasing varies -
"pain in my chest" doesn't contain the substring "chest pain" - and could
silently fall through to the wrong specialist (observed: "short of breath"
contains "breath", so a chest-pain complaint that also mentioned
breathlessness was misrouted to Pulmonology instead of Cardiology, and
wasn't flagged as an emergency).

Fixed by adding a co-occurrence check: "chest" appearing anywhere in the
complaint alongside a pain/pressure-type word (pain, painful, pressure,
tight, hurts, crushing, etc.) now also routes to cardio / triggers the
emergency screen, checked before the pulm keywords so a complaint
mentioning both chest pain and breathlessness still correctly routes to
cardio. A lightweight negation guard (`_mentions_word_unnegated` /
`_mentions_phrase_unnegated`) prevents "no chest pain" or "denies chest
pain" from being misread as a positive symptom - this also fixed a
pre-existing gap in the *original* literal "chest pain" phrase check,
which had no negation awareness at all.

**Known remaining limitation:** the negation guard only covers "chest
pain" and the qualifier-word checks added here. Other red-flag phrases
(e.g. "difficulty breathing", "loss of consciousness") still use plain
substring matching with no negation awareness - "denies loss of
consciousness" would still incorrectly flag. A full negation rewrite of
every red-flag phrase is a larger, separate follow-up.

All 23 cases in `backend/eval_harness.py` continue to pass unchanged.

## Zero-LLM-call deterministic emergency path

For confirmed emergencies (`is_emergency == True`, decided deterministically
by the red-flag screen before any LLM runs), `emergency_node`,
`pharmacist_node`, and `verify_explain_node` in `graph.py` now return
pre-written deterministic content instead of calling the LLM. This is safe
because those three nodes only ever generated descriptive TEXT after the
emergency decision was already made - they never re-evaluated the decision
itself. `node_clinical` (GP + specialist) and `consensus_node` still make
real LLM calls, so an emergency still gets genuine case-specific clinical
framing and synthesis - only the parts where an LLM call added little
(the emergency assessment text, pharmacist advice, and post-hoc
verification) were removed. Net effect: a confirmed emergency now takes
**2 LLM calls instead of 5**, on the exact path where speed matters most,
with zero hallucination risk on that content.

**Important distinction - `detect_emergency_subtype` vs
`detect_symptom_category`:** the emergency text is keyed by a new,
finer-grained `detect_emergency_subtype()` (cardiac / airway_respiratory /
airway_allergic / neuro_stroke / psychiatric / toxicology / trauma_bleeding
/ meningitis / general) in `clinical.py` - NOT by the existing
cardio/pulm/ent/general specialist-routing category. Those categories
exist to pick which specialist reasons about a complaint, and this app has
no Neurology, Psychiatry, or Toxicology specialist at all, so "stroke" and
"numbness" are bucketed under "cardio" purely for keyword-detection
convenience. Using that category for the deterministic emergency text
would tell a stroke patient "Emergency ECG and troponin testing
indicated" - clinically wrong, not just generic. `detect_emergency_subtype`
fixes this, and also gives previously-generic red flags (anaphylaxis, loss
of consciousness, suicidal ideation, severe poison, active bleeding,
meningitis signs) their own accurate, purpose-written content instead of
all falling through to one generic "acute high-risk symptoms" line.

**Known structural gap, not fixed here:** this app still has no
Neurology/Psychiatry/Toxicology *specialist* - a non-emergency numbness
complaint still routes to "Cardiologist" for its real LLM clinical
assessment via `detect_symptom_category`. Fixing that would mean adding
new specialist types throughout the app, a larger change than this fix's
scope.

All 23 cases in `backend/eval_harness.py` continue to pass unchanged.

## Minimal emergency alert UI (frontend-only)

Confirmed emergencies (`risk_level === "EMERGENCY"`) now render a short,
urgent alert instead of the full multi-section triage report - no
specialist breakdown, no RAG citations, no remedy table. Showing the full
"still figuring things out" report UI for a genuine emergency is the wrong
UX; the only thing that matters is telling the patient to seek care
immediately, with nothing to browse first.

This required no backend changes - `risk_level` and a clear
`explainability` message were already present on every response,
including the emergency-subtype-specific text from the fix above.
Everything changed in `frontend/`:

- `index.html` - added a new `#emergency-alert-box` element, a sibling of
  `#report-content`, initially hidden.
- `app.js` (`renderTriageReport`) - checks `risk_level === "EMERGENCY"`
  first; if true, shows `#emergency-alert-box` (populated with
  `data.explainability` and the case ID) and returns immediately, without
  touching `#report-content`'s child elements at all. `startNewSession`
  also resets the new alert box so it doesn't persist into a later
  non-emergency session.
- `style.css` - new `.emergency-alert-box` styling, reusing the existing
  `--danger` CSS variable for visual consistency with the rest of the app.

**Why the alert box is a separate DOM element instead of overwriting
`#report-content`'s innerHTML:** the full report's rendering code
(specialist cards, citations, remedies table) all target specific child
element IDs inside `#report-content` on every call. Destroying that
structure once for an emergency case would break the *next* non-emergency
report rendered in the same browser session (`getElementById` calls
returning null). Toggling visibility between two sibling containers avoids
this entirely.

## Session cross-talk fix (frontend)

A pre-existing bug, not introduced by today's changes but much easier to
trigger now that real triage calls take real time: `triggerTriagePipeline`
had no check for whether the user was still on the same session by the
time a triage response arrived. If you switched to a different case (or
started a new session) while a request was still in flight, the
late-arriving response would render into whatever session was now on
screen - and overwrite THAT session's saved data with the old result.

Fixed by capturing the session's identity (`chatHistory` array reference +
`activeSessionId`) at the moment a request starts, and checking it again
when the response arrives. If the user has navigated away, the result is
saved directly into its own correct session record in the background
(`saveCompletedSessionInBackground`) instead of being applied to whatever
is currently on screen - so a real result (including a completed
emergency case) is never silently lost, it just lands in the right place.
Applies to both the SSE streaming path and the REST fallback path used
when the stream errors out.

## File attachment feature removed (frontend)

The 📎 "attach a report" button (between the mic and Send buttons),
its file input, preview chip, and all associated JS
(`setupDocumentUpload`, `attachedDocument` state, the `/api/upload-doc`
call) were removed from the frontend per request. The backend
`/api/upload-doc` endpoint and `doc_reader.py` were left untouched (not
in scope) - they're just no longer reachable from the UI. `/api/chat`
still accepts optional `document_text`/`document_image_b64` fields for
backward compatibility; the frontend simply never sends them anymore.

## Session cross-talk fix, part 2 (intake messages)

The earlier session cross-talk fix only guarded the final triage report
stream (`triggerTriagePipeline`). `handleSend` - which handles EVERY
intake message and post-report chat message, not just the one-time final
report - had no such guard at all, and was the easier path to actually
trigger: switching sidebar sessions while a single intake question was
still in flight would inject that reply into whichever session was now on
screen.

Fixed with the same pattern: `handleSend` captures the session's identity
(`chatHistory` array reference + `activeSessionId`) before making either
the `/api/intake` or `/api/chat` request, and checks it again when the
response returns. If the user has navigated away, the reply is filed into
its own session's saved history in the background
(`saveReplyIntoOwnSession`) instead of being applied to whatever is
currently displayed - and if the intake response signals "ready" to
proceed to triage, no triage pipeline is launched into the wrong session
either. Verified against a standalone simulation of the exact race
condition (two sessions, a slow response, a switch mid-flight) before
shipping, not just read through.

Known limitation: this only works once a session has already been saved
at least once. A session abandoned before its very first exchange ever
completes has no existing sidebar entry to file a late reply into.
