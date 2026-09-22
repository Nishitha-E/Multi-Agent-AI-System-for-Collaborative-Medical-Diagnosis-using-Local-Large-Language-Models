import os,re,requests

OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL","http://localhost:11434")
OLLAMA_MODEL=os.getenv("OLLAMA_MODEL","gemma3:4b")
OLLAMA_TIMEOUT_SECONDS=int(os.getenv("OLLAMA_TIMEOUT_SECONDS","120"))

_CPU_THREADS=os.cpu_count() or 4

_OLLAMA_SPEED_OPTIONS={
    "num_predict":80,
    "num_thread":_CPU_THREADS,
    "num_ctx":int(os.getenv("OLLAMA_NUM_CTX","2048"))
}

OLLAMA_CHAT_MAX_TOKENS=int(os.getenv("OLLAMA_CHAT_MAX_TOKENS","500"))
OLLAMA_ASSESSMENT_TOKENS=int(os.getenv("OLLAMA_ASSESSMENT_TOKENS","220"))
OLLAMA_SYNTHESIS_TOKENS=int(os.getenv("OLLAMA_SYNTHESIS_TOKENS","300"))
OLLAMA_STRUCTURED_TOKENS=int(os.getenv("OLLAMA_STRUCTURED_TOKENS","450"))
OLLAMA_KEEP_ALIVE="24h"

def query_llm(prompt:str,image_b64:str=None,max_tokens:int=None)->str:
    options=dict(_OLLAMA_SPEED_OPTIONS)
    if max_tokens is not None:
        options["num_predict"]=max_tokens

    try:
        if image_b64:
            payload={
                "model":OLLAMA_MODEL,
                "messages":[
                    {
                        "role":"user",
                        "content":prompt,
                        "images":[image_b64]
                    }
                ],
                "stream":False,
                "options":options,
                "keep_alive":OLLAMA_KEEP_ALIVE
            }
            res=requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=OLLAMA_TIMEOUT_SECONDS
            )
            res.raise_for_status()
            return res.json()["message"]["content"]

        payload={
            "model":OLLAMA_MODEL,
            "prompt":prompt,
            "stream":False,
            "options":options,
            "keep_alive":OLLAMA_KEEP_ALIVE
        }

        res=requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS
        )
        res.raise_for_status()
        return res.json()["response"]

    except Exception as e:
        raise RuntimeError(f"Ollama unavailable: {e}")

def _has_word(text:str,word:str)->bool:
    return re.search(r"\b"+re.escape(word)+r"\b",text) is not None

_NEGATION_WORDS={
    "no","not","denies","denying","without","non","negative","never"
}

def _mentions_word_unnegated(text:str,word:str,window:int=4)->bool:
    tokens=re.findall(r"[a-z']+",text.lower())
    target=word.lower()

    for i,tok in enumerate(tokens):
        if tok==target:
            start=max(0,i-window)
            if any(t in _NEGATION_WORDS for t in tokens[start:i]):
                continue
            return True

    return False

def _mentions_phrase_unnegated(text:str,phrase:str,window:int=4)->bool:
    tokens=re.findall(r"[a-z']+",text.lower())
    phrase_tokens=phrase.lower().split()
    n=len(phrase_tokens)

    for i in range(len(tokens)-n+1):
        if tokens[i:i+n]==phrase_tokens:
            start=max(0,i-window)
            if any(t in _NEGATION_WORDS for t in tokens[start:i]):
                continue
            return True

    return False

_CARDIAC_PAIN_QUALIFIERS=[
    "pain","pains","painful","pressure","tight","tightness",
    "discomfort","squeezing","heavy","heaviness","ache",
    "aching","hurts","hurting","crushing"
]

_CARDIO_OTHER_KEYWORDS=[
    "chest pressure","chest tightness","angina","precordial",
    "heart","palpitation","arrhythmia","tachycardia",
    "cardiac","stroke","numbness","ticker"
]

def classify_symptom_domain(complaint:str)->dict:
    c=complaint.lower()

    if _mentions_phrase_unnegated(c,"chest pain") or any(
        k in c for k in _CARDIO_OTHER_KEYWORDS
    ):
        return {
            "primary_domain":"cardio",
            "is_ambiguous":False,
            "ambiguous_reason":""
        }

    if _has_word(c,"chest") and any(
        _mentions_word_unnegated(c,q)
        for q in _CARDIAC_PAIN_QUALIFIERS
    ):
        return {
            "primary_domain":"cardio",
            "is_ambiguous":False,
            "ambiguous_reason":""
        }

    pulm_keywords=[
        "cough","wheeze","breath","dyspnea","lung","lungs",
        "asthma","copd","respiratory","bronchitis","sputum",
        "breathless","choking","pneumonia","chest congestion"
    ]

    ent_keywords=[
        "ear","throat","swallow","tonsil","sinus","nose",
        "nasal","voice","hoarse","otalgia","pharyngitis",
        "otitis","rhinitis","nasal congestion"
    ]

    has_pulm=any(k in c for k in pulm_keywords)
    has_ent=any(k in c for k in ent_keywords)

    if "congestion" in c and not has_pulm and not has_ent:
        return {
            "primary_domain":"ambiguous",
            "is_ambiguous":True,
            "ambiguous_reason":
                "Is your congestion primarily in your nasal/sinus passages or deep in your chest/lungs?"
        }

    if has_pulm:
        return {
            "primary_domain":"pulm",
            "is_ambiguous":False,
            "ambiguous_reason":""
        }

    if has_ent:
        return {
            "primary_domain":"ent",
            "is_ambiguous":False,
            "ambiguous_reason":""
        }

    ortho_keywords=[
        "wrist","joint","sprain","strain","carpal","tendon",
        "ligament","elbow","knee","ankle","shoulder",
        "hip joint","fracture","dislocation","muscle pain",
        "muscle ache","back pain","spine","tennis elbow",
        "frozen shoulder","tendonitis","arthritis"
    ]

    if any(k in c for k in ortho_keywords):
        return {
            "primary_domain":"ortho",
            "is_ambiguous":False,
            "ambiguous_reason":""
        }

    return {
        "primary_domain":"general",
        "is_ambiguous":False,
        "ambiguous_reason":""
    }

def detect_symptom_category(complaint:str)->str:
    domain=classify_symptom_domain(complaint)["primary_domain"]
    return "general" if domain=="ambiguous" else domain

_EMERGENCY_OTHER_RED_FLAGS=[
    "crushing chest","difficulty breathing","severe dyspnea",
    "choking","throat swelling","anaphylaxis",
    "loss of consciousness","unresponsive","stroke",
    "slurred speech","facial droop","numbness",
    "suicidal ideation","severe poison","active bleeding",
    "tripod position","epiglottitis","stridor",
    "neck stiffness","stiff neck"
]

def _mentions_flag_unnegated(text:str,flag:str,window:int=4)->bool:
    if " " in flag:
        return _mentions_phrase_unnegated(text,flag,window)
    return _mentions_word_unnegated(text,flag,window)

def deterministic_emergency_screen(complaint:str)->bool:
    c=complaint.lower()

    if _mentions_phrase_unnegated(c,"chest pain") or any(
        _mentions_flag_unnegated(c,f)
        for f in _EMERGENCY_OTHER_RED_FLAGS
    ):
        return True

    if any(_has_word(c,x) for x in ["chest","heart"]) and any(
        _mentions_word_unnegated(c,w)
        for w in _CARDIAC_PAIN_QUALIFIERS
    ):
        return True

    return False

def detect_emergency_subtype(complaint:str)->str:
    c=complaint.lower()

    subtypes=[
        ("neuro_stroke",[
            "stroke","slurred speech","facial droop",
            "loss of consciousness","unresponsive"
        ]),
        ("airway_allergic",[
            "anaphylaxis","throat swelling"
        ]),
        ("psychiatric",[
            "suicidal ideation"
        ]),
        ("toxicology",[
            "severe poison"
        ]),
        ("trauma_bleeding",[
            "active bleeding"
        ]),
        ("meningitis",[
            "neck stiffness","stiff neck"
        ]),
        ("airway_respiratory",[
            "difficulty breathing","severe dyspnea",
            "choking","tripod position",
            "epiglottitis","stridor"
        ])
    ]

    for subtype,phrases in subtypes:
        if any(_mentions_flag_unnegated(c,p) for p in phrases):
            return subtype

    if any(_has_word(c,x) for x in ["chest","heart"]) and any(
        _mentions_word_unnegated(c,w)
        for w in _CARDIAC_PAIN_QUALIFIERS
    ):
        return "cardiac"

    if _mentions_word_unnegated(c,"numbness"):
        return "cardiac"

    return "general"

_RX_DRUGS=[
    r"amoxicillin",r"penicillin",r"lisinopril",r"albuterol",
    r"prednisone",r"dexamethasone",r"ceftriaxone",
    r"atorvastatin",r"levothyroxine",r"metformin",
    r"amlodipine",r"metoprolol",r"gabapentin",
    r"hydrochlorothiazide",r"losartan",r"sertraline",
    r"montelukast",r"fluticasone",r"furosemide",
    r"pantoprazole",r"escitalopram",r"alprazolam",
    r"ciprofloxacin",r"azithromycin",r"doxycycline",
    r"tramadol",r"codeine",r"oxycodone",r"warfarin",
    r"clopidogrel",r"apixaban",r"ibuprofen\s+800mg",
    r"nitroglycerin",r"nitroglycerine",r"sublingual\s+nitro",
    r"morphine",r"digoxin",r"adenosine",r"amiodarone",
    r"heparin",r"enoxaparin",r"atropine",r"epinephrine"
]

_RX_DOSAGE_PATTERN=re.compile(
    r"\b\d+\s*(?:mg|g|mcg|ml|milligrams|grams|micrograms|"
    r"milliliters|iu|units|tablet|tablets|cap|capsules)\b",
    re.I
)

_MD_BOLD_ITALIC=re.compile(r"\*\*\*(.+?)\*\*\*")
_MD_BOLD=re.compile(r"\*\*(.+?)\*\*")
_MD_BOLD_UNDERSCORE=re.compile(r"__(.+?)__")
_MD_ITALIC_STAR=re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_ITALIC_UNDERSCORE=re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_MD_HEADER=re.compile(r"^\s{0,3}#{1,6}\s+",re.M)
_MD_BULLET=re.compile(r"^\s{0,3}[-*+]\s+",re.M)
_MD_INLINE_CODE=re.compile(r"`([^`]+)`")

def strip_markdown_formatting(text:str)->str:
    if not text:
        return text

    text=_MD_BOLD_ITALIC.sub(r"\1",text)
    text=_MD_BOLD.sub(r"\1",text)
    text=_MD_BOLD_UNDERSCORE.sub(r"\1",text)
    text=_MD_ITALIC_STAR.sub(r"\1",text)
    text=_MD_ITALIC_UNDERSCORE.sub(r"\1",text)
    text=_MD_INLINE_CODE.sub(r"\1",text)
    text=_MD_HEADER.sub("",text)
    text=_MD_BULLET.sub("- ",text)

    return text.strip()

def strip_prescription_drugs(text:str)->str:
    for rx in _RX_DRUGS:
        text=re.sub(
            rx,
            "[PRESCRIPTION DRUG STRIPPED]",
            text,
            flags=re.I
        )

    return _RX_DOSAGE_PATTERN.sub(
        "[DOSAGE STRIPPED]",
        text
    )