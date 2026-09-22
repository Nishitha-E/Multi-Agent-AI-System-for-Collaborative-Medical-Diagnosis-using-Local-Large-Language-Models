import os,json,asyncio
from pydub import AudioSegment
from contextlib import asynccontextmanager
import whisper
from typing import List
from fastapi import FastAPI,HTTPException,UploadFile,File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.app.agents import AegisTriagePipeline,detect_symptom_category
from backend.app.clinical import query_llm
from backend.app.pdf import generate_triage_pdf

_whisper_model=None

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model=whisper.load_model("base")
    return _whisper_model

@asynccontextmanager
async def lifespan(app:FastAPI):
    try:
        await asyncio.wait_for(
            asyncio.to_thread(query_llm,"Reply with OK.",max_tokens=5),
            timeout=3
        )
        print("[startup] Ollama ready.")
    except Exception:
        print("[startup] Ollama warm-up skipped.")

    try:
        await asyncio.to_thread(_get_whisper_model)
        print("[startup] Whisper ready.")
    except Exception as e:
        print(f"[startup] Whisper warm-up skipped: {e}")

    yield

app=FastAPI(
    title="Aegis AI Medical Triage",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class IntakeRequest(BaseModel):
    message:str
    chat_history:List[dict]

class TriageRequest(BaseModel):
    complaint:str

class ChatRequest(BaseModel):
    message:str
    chat_history:List[dict]
    report_data:dict={}

FRONTEND_DIR=os.path.abspath(
    os.path.join(os.path.dirname(__file__),"..","..","frontend")
)
REPORTS_DIR=os.path.join(FRONTEND_DIR,"reports")
os.makedirs(REPORTS_DIR,exist_ok=True)

RESULTS_CACHE={}

FFMPEG_PATH = r"C:\Users\Prime\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
AudioSegment.converter=FFMPEG_PATH

def _transcribe_with_whisper(webm_bytes:bytes)->str:
    tmp_in=os.path.join(
        REPORTS_DIR,f"_tmp_{os.urandom(4).hex()}.webm"
    )
    tmp_wav=os.path.join(
        REPORTS_DIR,f"_tmp_{os.urandom(4).hex()}.wav"
    )

    try:
        with open(tmp_in,"wb") as f:
            f.write(webm_bytes)

        audio=AudioSegment.from_file(
            tmp_in,format="webm"
        ).set_channels(1).set_frame_rate(16000).set_sample_width(2)

        audio=audio.high_pass_filter(80)

        if audio.dBFS!=float("-inf"):
            gain=max(-3,min(12,-16-audio.dBFS))
            if abs(gain)>0.1:
                audio=audio.apply_gain(gain)

        audio=audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

        audio.export(
            tmp_wav,
            format="wav",
            parameters=["-ac","1","-ar","16000","-sample_fmt","s16"]
        )

        result=_get_whisper_model().transcribe(
            tmp_wav,
            language="en",
            fp16=False,
            temperature=0
        )

        return result.get("text","").strip()

    finally:
        for p in (tmp_in,tmp_wav):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass

async def run_pipeline_stream(complaint:str):
    pipeline=AegisTriagePipeline()

    results={
        "case_id":os.urandom(4).hex().upper(),
        "patient_complaint":complaint,
        "risk_level":"LOW",
        "engine":"Ollama LLM",
        "specialists":{},
        "consensus":"",
        "verification":"",
        "explainability":"",
        "pharmacist_review":"",
        "citations":[],
        "confidence_score":0.0,
        "treatment_remedies":{}
    }

    yield {
        "event":"status",
        "data":json.dumps({
            "msg":"Initializing Aegis Multi-Agent Triage Architecture...",
            "pct":5
        })
    }

    is_emergency=pipeline._deterministic_emergency_screen(complaint)
    category=detect_symptom_category(complaint)

    spec_name={
        "ent":"ENT Specialist",
        "cardio":"Cardiologist",
        "pulm":"Pulmonologist",
        "ortho":"Orthopedic Specialist"
    }.get(category,"General Physician")

    yield {
        "event":"status",
        "data":json.dumps({
            "msg":f"Routing to {category.upper()} - dispatching clinical, pharmacist & safety agents...",
            "pct":15
        })
    }

    task=asyncio.create_task(
        asyncio.to_thread(pipeline.run_pipeline,complaint)
    )

    progress=[
        (30,f"Agent: {spec_name} performing evidence-grounded clinical analysis..."),
        (55,"Agent: Pharmacist Safety Agent checking OTC safety..."),
        (75,"Agent: Consensus Coordinator synthesizing clinical findings..."),
        (90,"Agent: Verification & Rationale Agent scoring evidence...")
    ]

    i=0

    while not task.done():
        await asyncio.sleep(2)

        if not task.done():
            pct,msg=progress[i] if i<len(progress) else (95,"Still processing...")
            i+=1

            yield {
                "event":"status",
                "data":json.dumps({"msg":msg,"pct":pct})
            }

    full_res=task.result()

    results["risk_level"]="EMERGENCY" if is_emergency else full_res.get("risk_level","LOW")
    results["specialists"]=full_res.get("specialists",{})
    results["citations"]=full_res.get("citations") or pipeline.rag.retrieve(complaint,top_k=2)
    results["consensus"]=full_res.get("consensus","")
    results["engine"]=full_res.get("engine","Aegis AI Engine")
    results["verification"]=full_res.get("verification","")
    results["explainability"]=full_res.get("explainability","")
    results["confidence_score"]=full_res.get("confidence_score",0.0)
    results["pharmacist_review"]=full_res.get("pharmacist_review","")
    results["treatment_remedies"]=full_res.get("treatment_remedies",{})

    yield {
        "event":"status",
        "data":json.dumps({
            "msg":"Finalizing report...",
            "pct":99
        })
    }

    RESULTS_CACHE[results["case_id"]]=results
    results["pdf_url"]=f"/api/reports/{results['case_id']}/pdf"

    yield {
        "event":"complete",
        "data":json.dumps(results)
    }

@app.post("/api/transcribe")
async def transcribe_audio(file:UploadFile=File(...)):
    contents=await file.read()

    if not contents:
        raise HTTPException(status_code=400,detail="Empty audio.")

    text=await asyncio.to_thread(
        _transcribe_with_whisper,
        contents
    )

    print(f"[WHISPER] Transcript: {repr(text)}")

    return {"text":text}

@app.post("/api/intake")
async def post_intake(req:IntakeRequest):
    pipeline=AegisTriagePipeline()

    return await asyncio.to_thread(
        pipeline.run_intake_router,
        req.message,
        req.chat_history
    )

@app.get("/api/triage/stream")
async def get_triage_stream(complaint:str):
    return EventSourceResponse(
        run_pipeline_stream(complaint)
    )

@app.post("/api/triage")
async def post_triage(req:TriageRequest):
    pipeline=AegisTriagePipeline()

    results=await asyncio.to_thread(
        pipeline.run_pipeline,
        req.complaint
    )

    RESULTS_CACHE[results["case_id"]]=results
    results["pdf_url"]=f"/api/reports/{results['case_id']}/pdf"

    return results

@app.get("/api/reports/{case_id}/pdf")
async def get_report_pdf(case_id:str):
    results=RESULTS_CACHE.get(case_id)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="Report not found or expired."
        )

    filename=f"triage_report_{case_id}.pdf"
    path=os.path.join(REPORTS_DIR,filename)

    if not os.path.exists(path):
        generate_triage_pdf(results,path)

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename
    )

@app.post("/api/chat")
async def post_chat(req:ChatRequest):
    pipeline=AegisTriagePipeline()

    response=await asyncio.to_thread(
        pipeline.run_report_chat_assistant,
        req.message,
        req.chat_history,
        req.report_data,
        None,
        None
    )

    return {"response":response}

if os.path.exists(FRONTEND_DIR):
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR),
        name="static"
    )

@app.get("/")
async def get_index():
    return FileResponse(
        os.path.join(FRONTEND_DIR,"index.html")
    )