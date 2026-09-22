from fpdf import FPDF
import os

def _sanitize_for_pdf(text):
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    return text.encode("latin-1", errors="replace").decode("latin-1")

class AegisPDF(FPDF):
    def header(self):
        self.set_fill_color(30, 41, 59)
        self.rect(0, 0, 210, 15, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, -5, 'AEGIS CLINICAL DECISION SUPPORT SYSTEM', align='C')
        self.ln(10)
        
    def footer(self):
        self.set_y(-20)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, 'Disclaimer: For decision-support only. Not a medical diagnosis. Always consult a physician.', align='C')
        self.ln(5)
        self.cell(0, 5, f'Page {self.page_no()}', align='C')

def generate_triage_pdf(report_data, output_path):
    pdf = AegisPDF()
    pdf.add_page()
    pdf.set_margins(15, 20, 15)
    
    pdf.set_y(25)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, 'Patient Triage Decision-Support Report', ln=True, align='L')
    
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, 36, 195, 36)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(70, 80, 95)
    pdf.cell(45, 7, 'Case Reference ID:', 0, 0)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(50, 7, report_data.get('case_id', 'N/A'), 0, 0)
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(45, 7, 'Triage Confidence:', 0, 0)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(50, 7, f"{report_data.get('confidence_score', 0.0):.2%}", 0, 1)
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(45, 7, 'Urgency/Risk Level:', 0, 0)
    risk_level = report_data.get('risk_level', 'LOW')
    if risk_level.upper() in ['EMERGENCY', 'HIGH']:
        pdf.set_text_color(220, 38, 38)
    elif risk_level.upper() in ['MEDIUM']:
        pdf.set_text_color(217, 119, 6)
    else:
        pdf.set_text_color(22, 163, 74)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(50, 7, risk_level.upper(), 0, 0)
    
    pdf.set_text_color(70, 80, 95)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(45, 7, 'Source Engine:', 0, 0)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(50, 7, report_data.get('engine', 'Ollama LLM'), 0, 1)
    
    pdf.ln(5)
    
    start_y = pdf.get_y()
    complaint_text = _sanitize_for_pdf(report_data.get('patient_complaint', 'N/A'))
    pdf.set_font('Helvetica', '', 10)
    lines = pdf.multi_cell(174, 5, complaint_text, dry_run=True, output='LINES')
    box_height = 8 + (len(lines) * 5) + 4
    
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(15, start_y, 180, max(box_height, 16), 'F')
    pdf.set_y(start_y + 2)
    pdf.set_x(18)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 5, 'Initial Patient Complaint & Intake:', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_x(18)
    pdf.multi_cell(174, 5, complaint_text)
    pdf.set_y(start_y + max(box_height, 16) + 4)
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, 'Specialist Clinical Assessments')
    pdf.ln(8)
    pdf.set_x(15)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    
    specialists = report_data.get('specialists', {})
    if not specialists:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 6, 'No specialized assessments triggered.')
        pdf.ln(6)
        pdf.set_x(15)
    else:
        for spec_name, assessment in specialists.items():
            pdf.set_x(15)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(0, 6, _sanitize_for_pdf(f'{spec_name}:'))
            pdf.ln(6)
            pdf.set_x(15)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 5, _sanitize_for_pdf(assessment))
            pdf.ln(2)
            
    pdf.set_x(15)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, 'Consensus Coordinator Report')
    pdf.ln(8)
    pdf.set_x(15)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, _sanitize_for_pdf(report_data.get('consensus', 'N/A')))
    pdf.ln(4)

    pdf.set_x(15)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, 'Evidence Verification & Patient Explainability')
    pdf.ln(8)
    pdf.set_x(15)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 5, 'RAG Grounding Evidence Citations:')
    pdf.ln(5)
    pdf.set_x(15)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(80, 80, 80)
    citations = report_data.get('citations', [])
    if not citations:
        pdf.cell(0, 5, 'No relevant clinical documents retrieved.')
        pdf.ln(5)
        pdf.set_x(15)
    else:
        for cit in citations:
            pdf.set_x(15)
            pdf.multi_cell(0, 4.5, _sanitize_for_pdf(f"- [{cit.get('doc_id')}] {cit.get('title')} (Similarity: {cit.get('score', 0.0)})"))
            
    pdf.ln(3)
    pdf.set_x(15)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 5, 'Plain-Language Rationale for Patient:')
    pdf.ln(5)
    pdf.set_x(15)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, _sanitize_for_pdf(report_data.get('explainability', 'N/A')))
    pdf.ln(4)
    
    pdf.set_x(15)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 8, 'Pharmacy Safety & OTC Review')
    pdf.ln(8)
    pdf.set_x(15)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, _sanitize_for_pdf(report_data.get('pharmacist_review', 'N/A')))
    pdf.ln(6)
    
    notice_text = 'This document is generated by an artificial intelligence assistant. It does NOT constitute medical advice, diagnosis, or treatment. It is intended solely to support triage prioritizing. Please consult a qualified doctor immediately.'
    current_y = pdf.get_y()
    if current_y > 245:
        pdf.add_page()
        current_y = pdf.get_y()
        
    pdf.set_font('Helvetica', '', 8.5)
    notice_lines = pdf.multi_cell(174, 4, notice_text, dry_run=True, output='LINES')
    notice_box_height = 8 + (len(notice_lines) * 4) + 4

    pdf.set_fill_color(254, 242, 242)
    pdf.set_draw_color(239, 68, 68)
    pdf.rect(15, current_y, 180, notice_box_height, 'DF')
    pdf.set_y(current_y + 2)
    pdf.set_x(18)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(185, 28, 28)
    pdf.cell(0, 4, 'IMPORTANT DECISION-SUPPORT NOTICE:')
    pdf.ln(4)
    pdf.set_x(18)
    pdf.set_font('Helvetica', '', 8.5)
    pdf.multi_cell(174, 4, notice_text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)
    return output_path
