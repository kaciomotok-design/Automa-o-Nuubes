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
    
    # Limpeza de HTML ou tags do Outlook
    texto_bruto = payload.event_description or ""
    texto_limpo = re.sub(r'<[^>]+>', '\n', texto_bruto)
    
    linhas_filtradas = []
    for linha in texto_limpo.splitlines():
        linha_limpa = linha.strip()
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
    
    # Identifica automaticamente se é e-mail ou calendário pelo contexto/título ou origem
    # Se vier da caixa de entrada, podemos direcionar para a OS de solicitações internas:
    # (Caso queira separar por palavra no título ou se o fluxo de e-mail mandar algo específico)
    if "E-mail" in (payload.event_title or "") or "Solicitação" in (payload.event_title or ""):
        tipo_ocorrencia = 'OS. SOLICITAÇÕES INTERNAS'
        prefixo_desc = "E-mail recebido de"
    else:
        tipo_ocorrencia = 'OS. REUNIÃO INTERNA'
        prefixo_desc = "Evento criado no calendário por"

    descricao_final = f"{prefixo_desc} {payload.organizer_email}.\n\n{texto_final_desc}"

    data = {
        'company.key': 'n1w8wHXbAuE=',
        'occurrence.summary': payload.event_title,
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': tipo_ocorrencia,
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
            "tipo_utilizado": tipo_ocorrencia,
            "deadline": event_deadline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
