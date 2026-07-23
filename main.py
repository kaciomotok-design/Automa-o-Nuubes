from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
from datetime import datetime
import re
import base64

app = FastAPI()

class TarefaRequest(BaseModel):
    event_title: Optional[str] = "Evento sem título"
    event_description: Optional[str] = "Sem descrição"
    organizer_email: Optional[str] = "kacio.mota@grupofokus.com.br"
    event_start_date: Optional[str] = ""
    file_name: Optional[str] = None
    file_base64: Optional[str] = None

@app.post("/criar-tarefa")
async def criar_tarefa(payload: TarefaRequest):
    print(f"DEBUG - Título recebido: {payload.event_title}")
    
    # Limpeza de HTML do e-mail
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
    
    descricao_final = f"E-mail recebido de {payload.organizer_email}.\n\n{texto_final_desc}"

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

    files_to_send = None
    
    # Se veio um arquivo em Base64, decodifica e envia para o Nuubes
    if payload.file_base64 and payload.file_name:
        try:
            file_bytes = base64.b64decode(payload.file_base64)
            files_to_send = {
                'fileInfo': (payload.file_name, file_bytes, 'application/octet-stream')
            }
        except Exception as e:
            print(f"DEBUG - Erro ao decodificar anexo: {e}")

    headers = {
        'User-Agent': 'Nuubes-API-Client',
        'Accept': 'text/plain, */*'
    }

    try:
        response = requests.post(url, data=data, files=files_to_send, headers=headers, timeout=60)
        return {
            "status": "success",
            "nuubes_response": response.text.strip(),
            "title": payload.event_title,
            "has_attachment": bool(payload.file_base64)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
