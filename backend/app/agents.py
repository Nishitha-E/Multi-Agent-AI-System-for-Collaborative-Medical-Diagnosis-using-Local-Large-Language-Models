import os,re,json,difflib
from backend.app.clinical import (
    query_llm,detect_symptom_category,deterministic_emergency_screen,
    strip_prescription_drugs,strip_markdown_formatting,OLLAMA_CHAT_MAX_TOKENS
)
from rag.retrieval import get_rag
from backend.app.graph import build_triage_graph

class AegisTriagePipeline:
    def __init__(self):
        self.rag=get_rag()
        self.graph=build_triage_graph()

    def run_intake_router(self,user_message:str,chat_history:list)->dict:
        user_message=(user_message or "").strip()
        user_messages=[
            m.get("content","").strip()
            for m in chat_history
            if isinstance(m,dict) and m.get("role")=="user" and m.get("content","").strip()
        ]
        user_messages.append(user_message)
        full_complaint=". ".join(user_messages)

        if deterministic_emergency_screen(full_complaint):
            return {"status":"ready","summary":full_complaint,"engine":"safety-first-intake"}

        count=sum(
            1 for m in chat_history
            if isinstance(m,dict) and m.get("role")=="user"
        )

        if count>=2:
            return {"status":"ready","summary":full_complaint,"engine":"dynamic-intake"}

        c=user_message.lower()

        if "ear" in c:
            q="Understood. For your ear pain, how long has this been present, and have you noticed any fluid drainage, ringing, or muffled hearing?" if count==0 else "Got it. On a scale of 1 to 10, how severe is the ear pain, and does swallowing or lying down make it worse?"
        elif any(k in c for k in ["nose bleed","nosebleed","bleeding nose","nose bleeding"]):
            q="Understood. For your nosebleed, how long has it been bleeding, and is it from one nostril or both?" if count==0 else "Got it. Are you currently taking any blood thinners, and have you had frequent nosebleeds before?"
        elif any(k in c for k in ["hoarse","lost my voice","losing my voice","voice change","laryngitis"]):
            q="Understood. How long has your voice been hoarse or affected, and did it come on suddenly or gradually?" if count==0 else "Got it. Are you experiencing any throat pain alongside the voice change, or have you been straining your voice recently?"
        elif any(k in c for k in ["throat","swallow","tonsil"]):
            q="Understood. For your throat symptoms, how many days have you felt this, and do you have a fever or visible swelling/redness?" if count==0 else "Got it. On a scale of 1 to 10, how painful is it to swallow right now?"
        elif any(k in c for k in ["nasal congestion","stuffy nose","blocked nose","runny nose","post nasal","postnasal","sinus","congestion"]):
            q="Understood. For your nasal and sinus symptoms, how many days have you felt this, and do you have thick nasal discharge or facial pressure?" if count==0 else "Got it. On a scale of 1 to 10, how severe is the facial pressure or congestion right now?"
        elif any(k in c for k in ["chest","heart","palpitation"]):
            q="Understood. For your chest discomfort, does the pain spread to your left arm or jaw, and do you feel lightheaded or short of breath?" if count==0 else "On a scale of 1 to 10, how intense is the pressure, and does physical exertion make it worse?"
        elif any(k in c for k in ["cough","breath","wheeze","lung"]):
            q="Understood. For your cough or breathing difficulty, is the cough dry or producing phlegm, and how long has it lasted?" if count==0 else "Got it. Are you experiencing any wheezing or chest tightness when you breathe in deeply?"
        elif any(k in c for k in ["wrist","joint","sprain","strain","carpal","tendon","ligament","elbow","knee","ankle","shoulder","fracture","muscle pain","muscle ache","back pain"]):
            q="Understood. For your joint or muscle discomfort, how long has it been present, and did it start after a specific injury, movement, or repetitive activity?" if count==0 else "Got it. On a scale of 1 to 10, how severe is it, and have you noticed any numbness, tingling, weakness, or visible swelling/deformity?"
        elif any(k in c for k in ["dizzy","dizziness","vertigo","balance","spinning","lightheaded"]):
            q="Understood. How long have you been feeling dizzy, and does it feel like the room is spinning or more like you might faint?" if count==0 else "Got it. Does the dizziness get worse with any specific movement, like turning your head or standing up quickly?"
        elif any(k in c for k in ["smell","anosmia","cant taste","can't taste","loss of taste"]):
            q="Understood. How long have you noticed this change in your sense of smell or taste, and did it start after a cold or injury?" if count==0 else "Got it. Has it affected both smell and taste together, or just one of them?"
        elif any(k in c for k in ["fever","chills","body ache","fatigue"]):
            q="Understood. How high has your temperature been, and have you taken anything to bring it down?" if count==0 else "Got it. Are you experiencing any other symptoms alongside the fever, such as body aches, chills, or a rash?"
        else:
            prompt=f"""You are the Aegis Intake Router, an empathetic and professional medical doctor with 30 years of clinical experience.
Conduct a focused clinical interview. Ask at most 2 clear relevant follow-up questions about duration, severity, onset or triggers.

Current User Message: {user_message}
Chat History: {json.dumps(chat_history)}
Questions asked so far: {count}

If sufficient information is available or 2 questions have been reached, respond with exactly PROCEED_TO_TRIAGE.
Otherwise ask one supportive follow-up question."""
            response=strip_markdown_formatting(
                query_llm(prompt,max_tokens=1110).strip()
            )
            if "PROCEED_TO_TRIAGE" in response.upper():
                return {"status":"ready","summary":full_complaint,"engine":"dynamic-intake"}
            return {"status":"interviewing","question":response,"engine":"dynamic-intake"}

        return {"status":"interviewing","question":q,"engine":"dynamic-intake"}

    def run_pipeline(self,patient_complaint:str)->dict:
        results={
            "case_id":os.urandom(4).hex().upper(),
            "patient_complaint":patient_complaint,
            "risk_level":"LOW",
            "engine":"Aegis AI Engine (Gemma 3 4B)",
            "specialists":{},
            "consensus":"",
            "verification":"",
            "explainability":"",
            "pharmacist_review":"",
            "citations":[],
            "confidence_score":0.0,
            "treatment_remedies":{}
        }

        is_emergency=deterministic_emergency_screen(patient_complaint)

        graph_state=self.graph.invoke({
            "patient_complaint":patient_complaint
        })

        results["citations"]=graph_state.get("citations",[])
        results["specialists"]=graph_state.get("specialists",{})
        results["consensus"]=graph_state.get("consensus","")
        results["verification"]=graph_state.get("verification","")
        results["explainability"]=graph_state.get("explainability","")
        results["pharmacist_review"]=graph_state.get("pharmacist_review","")
        results["treatment_remedies"]=graph_state.get("treatment_remedies",{})
        results["confidence_score"]=graph_state.get("confidence_score",0.0)
        results["risk_level"]="EMERGENCY" if is_emergency else graph_state.get("risk_level","LOW")
        results["engine"]=graph_state.get("engine","Aegis AI Engine (Gemma 3 4B)")

        results["consensus"]=strip_prescription_drugs(results["consensus"])
        results["explainability"]=strip_prescription_drugs(results["explainability"])

        for name,text in results["specialists"].items():
            results["specialists"][name]=strip_prescription_drugs(text)

        for citation in results["citations"]:
            if isinstance(citation,dict) and "text" in citation:
                citation["text"]=strip_prescription_drugs(citation["text"])

        return results

    def _deterministic_emergency_screen(self,complaint:str)->bool:
        return deterministic_emergency_screen(complaint)

    def run_report_chat_assistant(
        self,user_message:str,
        chat_history:list,
        report_data:dict,
        document_text:str=None,
        document_image_b64:str=None
    )->str:
        msg=user_message.lower().strip(".,!? ")

        closing=re.compile(
            r"^(no+|nah|nope)?[\s,]*"
            r"(thanks?( you)?( so much| a lot| very much| doctor)?|thankyou|thank u|tq|"
            r"bye|goodbye|see you|appreciate it|great|good|all good|i'?m good|"
            r"that'?s all|that'?s it|nothing else|no more questions)[\s,.!?]*$"
        )

        if closing.match(msg):
            return "You are very welcome! Please get plenty of rest, monitor your symptoms, and reach back out if anything changes. Take care!"

        report_section=f"""
TRIAGE REPORT CONTEXT:
Risk: {report_data.get("risk_level")}
Complaint: {report_data.get("patient_complaint")}
Consensus: {report_data.get("consensus")}
Remedies: {report_data.get("treatment_remedies")}
""" if report_data else ""

        transcript="\n".join(
            f'{m.get("role","").upper()}: {(m.get("content","") or "").strip()}'
            for m in chat_history
            if isinstance(m,dict) and (m.get("content","") or "").strip()
        )

        prompt=f"""System: You are Aegis, a helpful attending medical assistant having an ongoing conversation with this patient.

{report_section}
CONVERSATION SO FAR:
{transcript}

Patient's latest message: "{user_message}"

Reply in plain spoken sentences only. Do not use Markdown.
Give practical, actionable advice based on the patient's complaint, symptoms and triage report.
Read the conversation before answering and do not unnecessarily repeat previous advice.

Answer:"""

        response=query_llm(
            prompt,
            max_tokens=OLLAMA_CHAT_MAX_TOKENS
        )

        return strip_markdown_formatting(response)