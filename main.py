from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
from datetime import datetime
import re

app = FastAPI()

class CalendarioRequest(BaseModel):
    event_title: Optional[str] = "Evento sem título"
    event_description: Optional[str] = "Sem descrição"
    organizer_email: Optional[str] = "kacio.mota@grupofokus.com.br"
    event_start_date: Optional[str] = ""

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

def processar_envio_nuubes(titulo, descricao, email, data_str, tipo_origem):
    texto_final_desc = limpar_html(descricao)
    event_deadline = formatar_data(data_str)
    
    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    url_occurrence = 'https://api.nuubes.com/api.occurrence.logic'
    
    descricao_final = f"{tipo_origem} de {email}.\n\n{texto_final_desc}"

    data_occurrence = {
        'company.key': company_key,
        'occurrence.summary': titulo or "Sem título",
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
    print(f"DEBUG - Resposta Nuubes Status: {response.status_code}, Body: {response.text}")
    
    return response.text.strip(), response.status_code

@app.post("/criar-tarefa-calendario")
async def criar_tarefa_calendario(payload: CalendarioRequest):
    resp_texto, status = processar_envio_nuubes(
        payload.event_title, payload.event_description, 
        payload.organizer_email, payload.event_start_date, "Evento de Calendário"
    )
    return {"status": "success", "nuubes_code": status, "nuubes_response": resp_texto}

@app.post("/criar-tarefa-email")
async def criar_tarefa_email(payload: EmailRequest):
    resp_texto, status = processar_envio_nuubes(
        payload.event_title, payload.event_description, 
        payload.organizer_email, payload.event_start_date, "E-mail recebido"
    )
    return {"status": "success", "nuubes_code": status, "nuubes_response": resp_texto}
