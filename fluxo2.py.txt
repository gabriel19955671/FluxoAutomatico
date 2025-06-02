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

# Configuração da página Streamlit
st.set_page_config(
    page_title="Fluxograma Automático para Escritórios de Contabilidade",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
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

# Função para criar diretórios temporários
def create_temp_directories():
    temp_dir = tempfile.gettempdir()
    upload_dir = os.path.join(temp_dir, 'fluxograma_uploads')
    bpmn_dir = os.path.join(temp_dir, 'fluxograma_bpmn')
    export_dir = os.path.join(temp_dir, 'fluxograma_exports')
    
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(bpmn_dir, exist_ok=True)
    os.makedirs(export_dir, exist_ok=True)
    
    return upload_dir, bpmn_dir, export_dir

# Função para extrair procedimento de um arquivo Word
def extract_procedure(file):
    doc = docx.Document(file)
    
    # Inicializar estrutura do procedimento
    procedure = {
        'title': '',
        'department': '',
        'periodicity': '',
        'responsible': '',
        'estimated_time': '',
        'objective': '',
        'materials': [],
        'documents': [],
        'steps': [],
        'decisions': []
    }
    
    # Extrair informações do documento
    current_section = None
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        # Identificar seções do documento
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
            # Identificar perguntas como decisões
            procedure['decisions'].append({
                'question': text,
                'options': []
            })
            current_section = "decision_options"
        elif current_section == "objective" and "OBJETIVO:" not in text:
            procedure['objective'] += text
        elif current_section == "materials" and "MATERIAIS E SISTEMAS NECESSÁRIOS:" not in text:
            procedure['materials'].append(text)
        elif current_section == "documents" and "DOCUMENTOS GERADOS:" not in text:
            procedure['documents'].append(text)
        elif current_section == "steps" and "DESCRIÇÃO:" not in text:
            # Verificar se é um passo numerado
            if text.startswith("Fim do processo"):
                procedure['steps'].append({
                    'text': text,
                    'type': 'end'
                })
            else:
                procedure['steps'].append({
                    'text': text,
                    'type': 'task'
                })
        elif current_section == "decision_options" and text.startswith("Se "):
            # Adicionar opção à última decisão
            if procedure['decisions']:
                procedure['decisions'][-1]['options'].append(text)
    
    return procedure

# Função para gerar BPMN XML a partir de um procedimento
def generate_bpmn_xml(procedure):
    """Gera um XML BPMN a partir da estrutura do procedimento."""
    
    # Criar elemento raiz
    root = ET.Element('bpmn:definitions')
    root.set('xmlns:bpmn', 'http://www.omg.org/spec/BPMN/20100524/MODEL')
    root.set('xmlns:bpmndi', 'http://www.omg.org/spec/BPMN/20100524/DI')
    root.set('xmlns:dc', 'http://www.omg.org/spec/DD/20100524/DC')
    root.set('xmlns:di', 'http://www.omg.org/spec/DD/20100524/DI')
    root.set('id', f"Definitions_{uuid.uuid4().hex}")
    root.set('targetNamespace', 'http://bpmn.io/schema/bpmn')
    
    # Criar processo
    process = ET.SubElement(root, 'bpmn:process')
    process_id = f"Process_{uuid.uuid4().hex}"
    process.set('id', process_id)
    process.set('isExecutable', 'false')
    
    # Adicionar evento de início
    start_event = ET.SubElement(process, 'bpmn:startEvent')
    start_event_id = f"StartEvent_{uuid.uuid4().hex}"
    start_event.set('id', start_event_id)
    start_event.set('name', 'Início')
    
    # Variáveis para controle de fluxo
    last_element_id = start_event_id
    last_element_type = 'startEvent'
    
    # Adicionar tarefas
    for i, step in enumerate(procedure['steps']):
        if step['type'] == 'end':
            # Adicionar evento de fim
            end_event = ET.SubElement(process, 'bpmn:endEvent')
            end_event_id = f"EndEvent_{uuid.uuid4().hex}"
            end_event.set('id', end_event_id)
            end_event.set('name', 'Fim')
            
            # Conectar último elemento ao evento de fim
            sequence_flow = ET.SubElement(process, 'bpmn:sequenceFlow')
            sequence_flow.set('id', f"Flow_{uuid.uuid4().hex}")
            sequence_flow.set('sourceRef', last_element_id)
            sequence_flow.set('targetRef', end_event_id)
            
            last_element_id = end_event_id
            last_element_type = 'endEvent'
        else:
            # Adicionar tarefa
            task = ET.SubElement(process, 'bpmn:task')
            task_id = f"Task_{uuid.uuid4().hex}"
            task.set('id', task_id)
            task.set('name', step['text'])
            
            # Conectar último elemento à tarefa
            sequence_flow = ET.SubElement(process, 'bpmn:sequenceFlow')
            sequence_flow.set('id', f"Flow_{uuid.uuid4().hex}")
            sequence_flow.set('sourceRef', last_element_id)
            sequence_flow.set('targetRef', task_id)
            
            last_element_id = task_id
            last_element_type = 'task'
    
    # Adicionar decisões
    for decision in procedure['decisions']:
        # Adicionar gateway
        gateway = ET.SubElement(process, 'bpmn:exclusiveGateway')
        gateway_id = f"Gateway_{uuid.uuid4().hex}"
        gateway.set('id', gateway_id)
        gateway.set('name', decision['question'])
        
        # Conectar último elemento ao gateway
        sequence_flow = ET.SubElement(process, 'bpmn:sequenceFlow')
        sequence_flow.set('id', f"Flow_{uuid.uuid4().hex}")
        sequence_flow.set('sourceRef', last_element_id)
        sequence_flow.set('targetRef', gateway_id)
        
        # Adicionar opções como tarefas
        for option in decision['options']:
            # Adicionar tarefa para a opção
            task = ET.SubElement(process, 'bpmn:task')
            task_id = f"Task_{uuid.uuid4().hex}"
            task.set('id', task_id)
            task.set('name', option)
            
            # Conectar gateway à tarefa
            sequence_flow = ET.SubElement(process, 'bpmn:sequenceFlow')
            sequence_flow.set('id', f"Flow_{uuid.uuid4().hex}")
            sequence_flow.set('sourceRef', gateway_id)
            sequence_flow.set('targetRef', task_id)
        
        last_element_id = gateway_id
        last_element_type = 'exclusiveGateway'
    
    # Adicionar evento de fim se não foi adicionado
    if last_element_type != 'endEvent':
        end_event = ET.SubElement(process, 'bpmn:endEvent')
        end_event_id = f"EndEvent_{uuid.uuid4().hex}"
        end_event.set('id', end_event_id)
        end_event.set('name', 'Fim')
        
        # Conectar último elemento ao evento de fim
        sequence_flow = ET.SubElement(process, 'bpmn:sequenceFlow')
        sequence_flow.set('id', f"Flow_{uuid.uuid4().hex}")
        sequence_flow.set('sourceRef', last_element_id)
        sequence_flow.set('targetRef', end_event_id)
    
    # Adicionar diagrama BPMN (BPMNDiagram)
    bpmndi = ET.SubElement(root, 'bpmndi:BPMNDiagram')
    bpmndi.set('id', f"BPMNDiagram_{uuid.uuid4().hex}")
    
    bpmnplane = ET.SubElement(bpmndi, 'bpmndi:BPMNPlane')
    bpmnplane.set('id', f"BPMNPlane_{uuid.uuid4().hex}")
    bpmnplane.set('bpmnElement', process_id)
    
    # Converter para string formatada
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

# Função para gerar BPMN XML de exemplo
def generate_example_bpmn():
    bpmn_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="Definitions_0y1uj6c" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1" name="Início">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:task id="Activity_1" name="Receber Nota Fiscal">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:task>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Activity_1" />
    <bpmn:exclusiveGateway id="Gateway_1" name="Nota válida?">
      <bpmn:incoming>Flow_2</bpmn:incoming>
      <bpmn:outgoing>Flow_3</bpmn:outgoing>
      <bpmn:outgoing>Flow_4</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Activity_1" targetRef="Gateway_1" />
    <bpmn:task id="Activity_2" name="Registrar no sistema">
      <bpmn:incoming>Flow_3</bpmn:incoming>
      <bpmn:outgoing>Flow_5</bpmn:outgoing>
    </bpmn:task>
    <bpmn:sequenceFlow id="Flow_3" name="Sim" sourceRef="Gateway_1" targetRef="Activity_2" />
    <bpmn:task id="Activity_3" name="Devolver nota">
      <bpmn:incoming>Flow_4</bpmn:incoming>
      <bpmn:outgoing>Flow_6</bpmn:outgoing>
    </bpmn:task>
    <bpmn:sequenceFlow id="Flow_4" name="Não" sourceRef="Gateway_1" targetRef="Activity_3" />
    <bpmn:endEvent id="EndEvent_1" name="Fim">
      <bpmn:incoming>Flow_5</bpmn:incoming>
      <bpmn:incoming>Flow_6</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_5" sourceRef="Activity_2" targetRef="EndEvent_1" />
    <bpmn:sequenceFlow id="Flow_6" sourceRef="Activity_3" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
        <di:waypoint x="192" y="120" />
        <di:waypoint x="250" y="120" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2">
        <di:waypoint x="350" y="120" />
        <di:waypoint x="405" y="120" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_3_di" bpmnElement="Flow_3">
        <di:waypoint x="455" y="120" />
        <di:waypoint x="510" y="120" />
        <bpmndi:BPMNLabel>
          <dc:Bounds x="474" y="102" width="18" height="14" />
        </bpmndi:BPMNLabel>
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_4_di" bpmnElement="Flow_4">
        <di:waypoint x="430" y="145" />
        <di:waypoint x="430" y="230" />
        <di:waypoint x="510" y="230" />
        <bpmndi:BPMNLabel>
          <dc:Bounds x="435" y="185" width="21" height="14" />
        </bpmndi:BPMNLabel>
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_5_di" bpmnElement="Flow_5">
        <di:waypoint x="610" y="120" />
        <di:waypoint x="672" y="120" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_6_di" bpmnElement="Flow_6">
        <di:waypoint x="610" y="230" />
        <di:waypoint x="690" y="230" />
        <di:waypoint x="690" y="138" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="156" y="102" width="36" height="36" />
        <bpmndi:BPMNLabel>
          <dc:Bounds x="159" y="145" width="30" height="14" />
        </bpmndi:BPMNLabel>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Activity_1_di" bpmnElement="Activity_1">
        <dc:Bounds x="250" y="80" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Gateway_1_di" bpmnElement="Gateway_1" isMarkerVisible="true">
        <dc:Bounds x="405" y="95" width="50" height="50" />
        <bpmndi:BPMNLabel>
          <dc:Bounds x="401" y="65" width="58" height="14" />
        </bpmndi:BPMNLabel>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Activity_2_di" bpmnElement="Activity_2">
        <dc:Bounds x="510" y="80" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Activity_3_di" bpmnElement="Activity_3">
        <dc:Bounds x="510" y="190" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
        <dc:Bounds x="672" y="102" width="36" height="36" />
        <bpmndi:BPMNLabel>
          <dc:Bounds x="680" y="78" width="20" height="14" />
        </bpmndi:BPMNLabel>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>'''
    return bpmn_xml

# Função para criar download link para arquivos
def get_download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'
    return href

# Função para criar download link para arquivos binários
def get_binary_download_link(content, filename, text):
    b64 = base64.b64encode(content).decode()
    mime_type = 'application/octet-stream'
    if filename.endswith('.png'):
        mime_type = 'image/png'
    elif filename.endswith('.svg'):
        mime_type = 'image/svg+xml'
    elif filename.endswith('.pdf'):
        mime_type = 'application/pdf'
    href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">{text}</a>'
    return href

# Função para exibir BPMN XML como diagrama
def display_bpmn(bpmn_xml):
    # Aqui seria ideal usar uma biblioteca para renderizar BPMN,
    # mas como isso é complexo no Streamlit, vamos usar uma abordagem simplificada
    # exibindo o XML e oferecendo opções de download
    
    st.markdown('<div class="section-header">Visua
(Content truncated due to size limit. Use line ranges to read in chunks)