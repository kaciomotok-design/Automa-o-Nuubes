from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
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
        except Exception:
            event_deadline = ''

    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    
    # 1. Cria a tarefa principal no Nuubes
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

    headers = {
        'User-Agent': 'Nuubes-API-Client',
        'Accept': 'text/plain, */*'
    }

    try:
        response_occ = requests.post(url_occurrence, data=data_occurrence, headers=headers, timeout=30)
        resposta_texto = response_occ.text.strip()
        print(f"DEBUG - Resposta Nuubes Tarefa: {resposta_texto}")

        # Extrai o número da ocorrência criada
        numero_ocorrencia = None
        match = re.search(r'\d+', resposta_texto)
        if match:
            numero_ocorrencia = match.group(0)

        # 2. Se houver anexo em Base64 e o número da ocorrência, envia usando a API de arquivos do Nuubes
        if payload.file_base64 and numero_ocorrencia:
            url_files = 'https://api.nuubes.com/api.files.logic'
            try:
                file_bytes = base64.b64decode(payload.file_base64)
                # Nome padrão caso venha vazio
                nome_arq = payload.file_name if payload.file_name else "anexo_email.dat"
                
                data_file = {
                    'company.key': company_key,
                    'occurrence.numberOccurrence': numero_ocorrencia
                }
                
                files_data = {
                    'fileInfo': (nome_arq, file_bytes, 'application/octet-stream')
                }
                
                response_file = requests.post(url_files, data=data_file, files=files_data, headers=headers, timeout=60)
                print(f"DEBUG - Resposta Nuubes Anexo: {response_file.text}")
            except Exception as e:
                print(f"DEBUG - Erro ao processar anexo Base64: {e}")

        return {
            "status": "success",
            "nuubes_response": resposta_texto,
            "title": payload.event_title,
            "attachment_sent": bool(payload.file_base64)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
