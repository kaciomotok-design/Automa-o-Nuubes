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

@app.post("/criar-tarefa-calendario")
async def criar_tarefa_calendario(payload: CalendarioRequest):
    print(f"DEBUG - Título recebido: {payload.event_title}")
    
    texto_final_desc = limpar_html(payload.event_description)
    event_deadline = formatar_data(payload.event_start_date)

    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    url_occurrence = 'https://api.nuubes.com/api.occurrence.logic'
    
    descricao_final = f"Evento de Calendário de {payload.organizer_email}.\n\n{texto_final_desc}"

    data_occurrence = {
        'company.key': company_key,
        'occurrence.summary': payload.event_title or "Sem título",
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': 'OS. REUNIÃO INTERNA',
        'occurrence.customer.name': 'GRUPO FOKUS',
        'occurrence.customer.externalCode': 'FOKUS001'
    }

    if event_deadline:
        data_occurrence['occurrence.deadLine'] = event_deadline

    headers = {
        'User-Agent': 'Nuubes-API-Client',
        'Accept': 'text/plain, */*'
    }

    try:
        response_occ = requests.post(url_occurrence, data=data_occurrence, headers=headers, timeout=30)
        resposta_texto = response_occ.text.strip()
        print(f"DEBUG - Resposta Nuubes: {resposta_texto}")

        return {
            "status": "success",
            "nuubes_response": resposta_texto,
            "title": payload.event_title,
            "deadline_used": event_deadline
        }
    except Exception as e:
        print(f"DEBUG - Erro crítico na requisição: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        # Atualizado em 2026 ás 14:03
