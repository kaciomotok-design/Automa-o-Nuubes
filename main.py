from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
from datetime import datetime
import re

app = FastAPI()

# Modelo para o Calendário
class CalendarioRequest(BaseModel):
    event_title: Optional[str] = "Evento sem título"
    event_description: Optional[str] = "Sem descrição"
    organizer_email: Optional[str] = "kacio.mota@grupofokus.com.br"
    event_start_date: Optional[str] = ""

# Modelo para a Caixa de Entrada (E-mail)
class EmailRequest(BaseModel):
    event_title: Optional[str] = "E-mail sem título"
    event_description: Optional[str] = "Sem descrição"
    organizer_email: Optional[str] = "kacio.mota@grupofokus.com.br"
    event_start_date: Optional[str] = ""

def limpar_html(texto_bruto):
    if not texto_bruto:
        return "Sem descrição informada."
    texto_limpo = re.sub(r'<[^>]+>', '\n', texto_bruto)
    linhas_filtradas = []
    for linha in texto_limpo.splitlines():
        linha_limpa = linha.strip()
        if "@font-face" in linha_limpa or "MsoNormal" in linha_limpa or "!--" in linha_limpa:
            continue
        if linha_limpa and linha_limpa != "&nbsp;":
            linhas_filtradas.append(linha_limpa)
    return "\n".join(linhas_filtradas) if linhas_filtradas else "Sem descrição informada."

def formatar_data(data_str):
    if not data_str:
        return ''
    try:
        data_limpa_str = data_str[:19]
        event_date = datetime.strptime(data_limpa_str, '%Y-%m-%dT%H:%M:%S')
        return event_date.strftime('%m/%d/%Y')
    except Exception:
        return ''

# Rota 1: Exclusiva para o Calendário
@app.post("/criar-tarefa-calendario")
async def criar_tarefa_calendario(payload: CalendarioRequest):
    texto_final_desc = limpar_html(payload.event_description)
    event_deadline = formatar_data(payload.event_start_date)
    
    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    url_occurrence = 'https://api.nuubes.com/api.occurrence.logic'
    
    descricao_final = f"Evento de Calendário de {payload.organizer_email}.\n\n{texto_final_desc}"

    data_occurrence = {
        'company.key': company_key,
        'occurrence.summary': payload.event_title,
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': 'OS. REUNIÃO INTERNA',
        'occurrence.customer.name': 'GRUPO FOKUS',
        'occurrence.customer.externalCode': 'FOKUS001'
    }

    if event_deadline:
        data_occurrence['occurrence.deadLine'] = event_deadline

    headers = {'User-Agent': 'Nuubes-API-Client', 'Accept': 'text/plain, */*'}
    response = requests.post(url_occurrence, data=data_occurrence, headers=headers, timeout=30)
    return {"status": "success", "nuubes_response": response.text.strip()}

# Rota 2: Exclusiva para a Caixa de Entrada (E-mails)
@app.post("/criar-tarefa-email")
async def criar_tarefa_email(payload: EmailRequest):
    texto_final_desc = limpar_html(payload.event_description)
    event_deadline = formatar_data(payload.event_start_date)
    
    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    url_occurrence = 'https://api.nuubes.com/api.occurrence.logic'
    
    descricao_final = f"E-mail recebido de {payload.organizer_email}.\n\n{texto_final_desc}"

    data_occurrence = {
        'company.key': company_key,
        'occurrence.summary': payload.event_title,
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': 'OS. REUNIÃO INTERNA',
        'occurrence.customer.name': 'GRUPO FOKUS',
        'occurrence.customer.externalCode': 'FOKUS001'
    }

    if event_deadline:
        data_occurrence['occurrence.deadLine'] = event_deadline

    headers = {'User-Agent': 'Nuubes-API-Client', 'Accept': 'text/plain, */*'}
    response = requests.post(url_occurrence, data=data_occurrence, headers=headers, timeout=30)
    return {"status": "success", "nuubes_response": response.text.strip()}
