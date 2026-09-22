import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.agents import detect_symptom_category, AegisTriagePipeline

TEST_CASES = [
    ("Ear pain and fullness in right ear for 2 days, no fever", "ent", False),
    ("Sore throat and difficulty swallowing for 3 days", "ent", False),
    ("Nasal congestion and facial pressure for a week", "ent", False),
    ("Hoarse voice and throat tickling after a cold", "ent", False),
    ("Ringing in ears and dizziness for two days", "ent", False),
    ("Chest pain and pressure radiating to left arm", "cardio", True),
    ("Occasional heart palpitations after coffee", "cardio", False),
    ("Chest tightness during light exercise", "cardio", False),
    ("Irregular heartbeat noticed for the past hour", "cardio", False),
    ("Numbness in left arm with mild chest discomfort", "cardio", True),
    ("Persistent cough and wheezing for a week", "pulm", False),
    ("Shortness of breath after climbing stairs", "pulm", False),
    ("Chest congestion with productive cough", "pulm", False),
    ("Asthma flare-up with mild wheezing", "pulm", False),
    ("Difficulty breathing and choking sensation", "pulm", True),
    ("Mild fatigue and general body ache for two days", "general", False),
    ("Feeling tired with no other symptoms", "general", False),
    ("Mild headache after a long day", "general", False),
    ("Slight stomach discomfort after eating", "general", False),
    ("Sudden slurred speech and facial droop", "general", True),
    ("Loss of consciousness for a few seconds", "general", True),
    ("Severe throat swelling, difficulty breathing", "pulm", True),
    ("Stiff neck with high fever", "general", True),
]

def run_evaluation():
    pipeline = AegisTriagePipeline()
    cat_correct, em_correct, total = 0, 0, len(TEST_CASES)
    cat_fails, em_fails = [], []

    for complaint, exp_cat, exp_em in TEST_CASES:
        act_cat = detect_symptom_category(complaint)
        act_em = pipeline._deterministic_emergency_screen(complaint)
        if act_cat == exp_cat: cat_correct += 1
        else: cat_fails.append((complaint, exp_cat, act_cat))
        if act_em == exp_em: em_correct += 1
        else: em_fails.append((complaint, exp_em, act_em))

    cat_acc, em_acc = cat_correct / total * 100, em_correct / total * 100
    print("=" * 70 + "\nAGENTIC-MED ROUTING EVALUATION\n" + "=" * 70)
    print(f"Test cases: {total}\nCategory routing accuracy: {cat_correct}/{total} ({cat_acc:.1f}%)\nEmergency screen accuracy: {em_correct}/{total} ({em_acc:.1f}%)\n")
    if not cat_fails and not em_fails:
        print("All cases passed both checks.")
    print("=" * 70)
    return {"category_accuracy": cat_acc, "emergency_accuracy": em_acc, "category_failures": cat_fails, "emergency_failures": em_fails}

if __name__ == "__main__":
    run_evaluation()
