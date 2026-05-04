import pandas as pd
import os

# Path to dataset
file_path = "Medical_Report/mtsamples.csv"

# Load dataset
df = pd.read_csv(file_path)

# Create output folder
os.makedirs("Medical_Reports", exist_ok=True)

# Convert first 10 reports
for i in range(4900):
    text = str(df.iloc[i]["transcription"])

    with open(f"Medical_Reports/report_{i}.txt", "w", encoding="utf-8") as f:
        f.write(text)

print("✅ Reports created successfully!")