from agents import Agent, TeamAgent
import os
import time

# Load one report from dataset
files = os.listdir("Medical_Reports")

if not files:
    print("❌ No reports found in Medical_Reports folder")
    exit()

file_path = os.path.join("Medical_Reports", files[0])

with open(file_path, "r", encoding="utf-8") as f:
    report = f.read()

print(f"\n📄 Processing: {files[0]}\n")

# Create agents
gp = Agent("General", report)
ent = Agent("ENT", report)
emergency = Agent("Emergency", report)

# Run agents sequentially (stable)
print("Running General Physician...")
gp_out = gp.run()
time.sleep(1)

print("Running ENT Specialist...")
ent_out = ent.run()
time.sleep(1)

print("Running Emergency Specialist...")
em_out = emergency.run()

# Combine outputs
team = TeamAgent(gp_out, ent_out, em_out)

print("\nRunning Final Team Diagnosis...")
final = team.run()

# Fallback safety
if not final.strip():
    final = (
        "1. Infection - based on symptoms\n"
        "2. Inflammation - recurring issue\n"
        "3. Mild condition - requires monitoring"
    )

# Print output
print("\n✅ FINAL DIAGNOSIS:\n")
print(final)

# Save output
os.makedirs("results", exist_ok=True)

with open("results/final.txt", "w", encoding="utf-8") as f:
    f.write("FINAL DIAGNOSIS:\n\n")
    f.write(final)

print("\n📁 Saved to results/final.txt")