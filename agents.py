from langchain_ollama import ChatOllama

class Agent:
    def __init__(self, role, medical_report):
        self.role = role
        self.medical_report = medical_report
        self.model = ChatOllama(model="phi", temperature=0)

    def get_prompt(self):
        if self.role == "General":
            return f"""
You are a general physician.

STRICT RULES:
- Give EXACTLY 3 conditions
- Format: Condition - Reason
- One line per condition
- No extra text

Report:
{self.medical_report}
"""

        elif self.role == "ENT":
            return f"""
You are an ENT specialist.

STRICT RULES:
- Give EXACTLY 3 ENT-related conditions
- Format: Condition - Reason
- No extra explanation

Report:
{self.medical_report}
"""

        elif self.role == "Emergency":
            return f"""
You are an emergency specialist.

STRICT RULES:
- Give EXACTLY 3 urgent risks
- Format: Condition - Reason
- Focus on severity only

Report:
{self.medical_report}
"""

    def run(self):
        try:
            response = self.model.invoke(self.get_prompt())

            output = response.content.strip()

            # Clean + limit output
            lines = [l for l in output.split("\n") if l.strip()]
            return "\n".join(lines[:3])

        except Exception as e:
            print(f"Error in {self.role}:", e)
            return ""


class TeamAgent:
    def __init__(self, gp_output, ent_output, emergency_output):
        self.gp = gp_output
        self.ent = ent_output
        self.emergency = emergency_output
        self.model = ChatOllama(model="phi", temperature=0)

    def run(self):
        prompt = f"""
You are a medical expert team.

STRICT RULES:
- Give EXACTLY 3 final conditions
- Format: Condition - Reason
- No repetition
- No extra text

General Physician:
{self.gp}

ENT Specialist:
{self.ent}

Emergency Specialist:
{self.emergency}
"""

        try:
            response = self.model.invoke(prompt)

            output = response.content.strip()

            # Limit output
            lines = [l for l in output.split("\n") if l.strip()]
            return "\n".join(lines[:3])

        except Exception as e:
            print("Error in Team Agent:", e)
            return ""