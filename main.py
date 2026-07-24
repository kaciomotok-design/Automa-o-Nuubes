Main:
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
from datetime import datetime
import re

app = FastAPI()

class TarefaRequest(BaseModel):
    event_title: Optional[str] = "Evento sem título"
    event_description: Optional[str] = "Sem descrição"
    organizer_email: Optional[str] = "kacio.mota@grupofokus.com.br"
    event_start_date: Optional[str] = ""

@app.post("/criar-tarefa")
async def criar_tarefa(payload: TarefaRequest):
    print(f"DEBUG - Título recebido: {payload.event_title}")
    
    # Limpeza radical de qualquer HTML ou tag do Outlook
    texto_bruto = payload.event_description or ""
    
    # Remove tudo o que estiver entre tags <> (HTML completo)
    texto_limpo = re.sub(r'<[^>]+>', '\n', texto_bruto)
    
    # Limpa linhas vazias, espaços excessivos e restos de estilos CSS
    linhas_filtradas = []
    ignorar = False
    for linha in texto_limpo.splitlines():
        linha_limpa = linha.strip()
        # Ignora blocos de estilo do Word/Outlook que possam sobrar
        if "@font-face" in linha_limpa or "MsoNormal" in linha_limpa or "!--" in linha_limpa:
            continue
        if linha_limpa and linha_limpa != "&nbsp;":
            linhas_filtradas.append(linha_limpa)

    texto_final_desc = "\n".join(linhas_filtradas) if linhas_filtradas else "Sem descrição informada."

    # Tratar a data para o formato do Nuubes (mm/dd/aaaa)
    event_deadline = ''
    if payload.event_start_date:
        try:
            event_date = datetime.fromisoformat(payload.event_start_date.replace('Z', '+00:00'))
            event_deadline = event_date.strftime('%m/%d/%Y')
        except Exception as e:
            print(f"DEBUG - Erro ao formatar data: {e}")
            event_deadline = ''

    admin_email = 'nuubes@grupofokus.com.br'
    url = 'https://api.nuubes.com/api.occurrence.logic'
    
    # Descrição final estruturada limpa
    descricao_final = f"Evento criado no calendário por {payload.organizer_email}.\n\n{texto_final_desc}"

    data = {
        'company.key': 'n1w8wHXbAuE=',
        'occurrence.summary': payload.event_title,
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': 'OS. REUNIÃO INTERNA',
        'occurrence.customer.name': 'GRUPO FOKUS',
        'occurrence.customer.externalCode': 'FOKUS001'
    }

    if event_deadline:
        data['occurrence.deadLine'] = event_deadline

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        'User-Agent': 'Nuubes-API-Client',
        'Accept': 'text/plain, */*'
    }

    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        return {
            "status": "success",
            "nuubes_response": response.text.strip(),
            "title": payload.event_title,
            "deadline": event_deadline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
