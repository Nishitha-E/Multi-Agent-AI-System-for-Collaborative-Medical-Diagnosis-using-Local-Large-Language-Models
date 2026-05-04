import streamlit as st
import os
from agents import Agent, TeamAgent

st.set_page_config(page_title="AI Medical Diagnosis", layout="wide")

st.title("🧠 Multi-Agent Medical Diagnosis System")

# Upload option
uploaded_file = st.file_uploader("Upload Medical Report", type=["txt"])

report = ""

# Option 1: Upload
if uploaded_file:
    report = uploaded_file.read().decode("utf-8")

# Option 2: Select existing
files = os.listdir("Medical_Reports")

if files:
    selected = st.selectbox("Or Select Existing Report", files)
    if st.button("Load Selected Report"):
        with open(os.path.join("Medical_Reports", selected), "r", encoding="utf-8") as f:
            report = f.read()

# Show report
if report:

    st.subheader("📄 Medical Report")
    st.write(report)

    run = st.button("Run Diagnosis")

    if run:
        with st.spinner("Analyzing... Please wait..."):

            try:
                gp = Agent("General", report)
                ent = Agent("ENT", report)
                em = Agent("Emergency", report)

                gp_out = gp.run()
                ent_out = ent.run()
                em_out = em.run()

                team = TeamAgent(gp_out, ent_out, em_out)
                final = team.run()

                st.success("Diagnosis Completed ✅")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("### 🩺 General Physician")
                    st.write(gp_out)

                with col2:
                    st.markdown("### 👂 ENT Specialist")
                    st.write(ent_out)

                with col3:
                    st.markdown("### 🚨 Emergency")
                    st.write(em_out)

                st.markdown("---")
                st.markdown("## ✅ Final Diagnosis")
                st.write(final)

            except Exception as e:
                st.error(f"Error occurred: {e}")