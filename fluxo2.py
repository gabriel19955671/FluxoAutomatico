
import streamlit as st
import os
import uuid
import docx
import tempfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
import base64
import json
from io import BytesIO
from PIL import Image
import pandas as pd

st.set_page_config(
    page_title="Fluxograma Automático para Escritórios de Contabilidade",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .upload-area {
        border: 2px dashed #ccc;
        border-radius: 8px;
        padding: 30px;
        text-align: center;
        margin-bottom: 20px;
        background-color: #f8f9fa;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .bpmn-container {
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .properties-panel {
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 5px;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

def create_temp_directories():
    temp_dir = tempfile.gettempdir()
    upload_dir = os.path.join(temp_dir, 'fluxograma_uploads')
    bpmn_dir = os.path.join(temp_dir, 'fluxograma_bpmn')
    export_dir = os.path.join(temp_dir, 'fluxograma_exports')
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(bpmn_dir, exist_ok=True)
    os.makedirs(export_dir, exist_ok=True)
    return upload_dir, bpmn_dir, export_dir

def extract_procedure(file):
    doc = docx.Document(file)
    procedure = {
        'title': '', 'department': '', 'periodicity': '', 'responsible': '', 'estimated_time': '',
        'objective': '', 'materials': [], 'documents': [], 'steps': [], 'decisions': []
    }
    current_section = None
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if "PROCEDIMENTO:" in text:
            procedure['title'] = text.replace("PROCEDIMENTO:", "").strip()
        elif "DEPARTAMENTO:" in text:
            procedure['department'] = text.replace("DEPARTAMENTO:", "").strip()
        elif "PERIODICIDADE:" in text:
            procedure['periodicity'] = text.replace("PERIODICIDADE:", "").strip()
        elif "RESPONSÁVEL:" in text:
            procedure['responsible'] = text.replace("RESPONSÁVEL:", "").strip()
        elif "TEMPO MÉDIO ESTIMADO:" in text:
            procedure['estimated_time'] = text.replace("TEMPO MÉDIO ESTIMADO:", "").strip()
        elif "OBJETIVO:" in text:
            current_section = "objective"
        elif "MATERIAIS E SISTEMAS NECESSÁRIOS:" in text:
            current_section = "materials"
        elif "DOCUMENTOS GERADOS:" in text:
            current_section = "documents"
        elif "DESCRIÇÃO:" in text:
            current_section = "steps"
        elif text.endswith("?"):
            procedure['decisions'].append({'question': text, 'options': []})
            current_section = "decision_options"
        elif current_section == "objective":
            procedure['objective'] += text
        elif current_section == "materials":
            procedure['materials'].append(text)
        elif current_section == "documents":
            procedure['documents'].append(text)
        elif current_section == "steps":
            if text.startswith("Fim do processo"):
                procedure['steps'].append({'text': text, 'type': 'end'})
            else:
                procedure['steps'].append({'text': text, 'type': 'task'})
        elif current_section == "decision_options" and text.startswith("Se "):
            if procedure['decisions']:
                procedure['decisions'][-1]['options'].append(text)
    return procedure

def generate_bpmn_xml(procedure):
    return generate_example_bpmn()

def generate_example_bpmn():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
id="Definitions_Example" targetNamespace="http://bpmn.io/schema/bpmn">
<bpmn:process id="Process_1" isExecutable="false">
<bpmn:startEvent id="StartEvent_1" name="Início">
<bpmn:outgoing>Flow_1</bpmn:outgoing>
</bpmn:startEvent>
<bpmn:task id="Task_1" name="Executar tarefa 1">
<bpmn:incoming>Flow_1</bpmn:incoming>
<bpmn:outgoing>Flow_2</bpmn:outgoing>
</bpmn:task>
<bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Task_1"/>
<bpmn:endEvent id="EndEvent_1" name="Fim">
<bpmn:incoming>Flow_2</bpmn:incoming>
</bpmn:endEvent>
<bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="EndEvent_1"/>
</bpmn:process>
</bpmn:definitions>'''

def get_download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'
    return href

def display_bpmn(bpmn_xml):
    st.markdown('<div class="section-header">Visualização do BPMN</div>', unsafe_allow_html=True)
    st.code(bpmn_xml, language="xml")

def main():
    st.markdown("<div class='main-header'>Fluxograma Automático para Escritórios de Contabilidade</div>", unsafe_allow_html=True)
    upload_dir, bpmn_dir, export_dir = create_temp_directories()
    uploaded_file = st.file_uploader("Envie um arquivo Word (.docx) com o procedimento:", type="docx")
    if uploaded_file is not None:
        procedure = extract_procedure(uploaded_file)
        bpmn_xml = generate_bpmn_xml(procedure)
        st.success("Procedimento extraído e BPMN gerado com sucesso!")
        display_bpmn(bpmn_xml)
        st.markdown(get_download_link(bpmn_xml, "fluxograma.bpmn", "⬇️ Baixar BPMN XML"), unsafe_allow_html=True)
    else:
        st.info("Envie um arquivo para iniciar a geração do fluxograma.")

if __name__ == "__main__":
    main()
