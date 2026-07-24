from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from typing import Optional
import requests
from datetime import datetime
import re

app = FastAPI()

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
        event_date = datetime.fromisoformat(data_str.replace('Z', '+00:00'))
        return event_date.strftime('%m/%d/%Y')
    except Exception:
        return ''

@app.post("/criar-tarefa")
async def criar_tarefa(
    event_title: Optional[str] = Form("Evento sem título"),
    event_description: Optional[str] = Form("Sem descrição"),
    organizer_email: Optional[str] = Form("kacio.mota@grupofokus.com.br"),
    event_start_date: Optional[str] = Form(""),
    origem: Optional[str] = Form("calendario"),
    file: Optional[UploadFile] = File(None)
):
    print(f"DEBUG - Título recebido: {event_title} | Origem: {origem}")
    
    texto_final_desc = limpar_html(event_description)
    event_deadline = formatar_data(event_start_date)

    admin_email = 'nuubes@grupofokus.com.br'
    url = 'https://api.nuubes.com/api.occurrence.logic'
    
    # Define o tipo de ocorrência baseado na origem enviada pelo Power Automate
    if origem and origem.lower() == "email":
        tipo_ocorrencia = 'OS. SOLICITAÇÕES INTERNAS'
        prefixo_desc = f"E-mail recebido de {organizer_email}."
    else:
        tipo_ocorrencia = 'OS. REUNIÃO INTERNA'
        prefixo_desc = f"Evento criado no calendário por {organizer_email}."

    descricao_final = f"{prefixo_desc}\n\n{texto_final_desc}"

    # Dados base que vão para o Nuubes
    data = {
        'company.key': 'n1w8wHXbAuE=',
        'occurrence.summary': event_title,
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': tipo_ocorrencia,
        'occurrence.customer.name': 'GRUPO FOKUS',
        'occurrence.customer.externalCode': 'FOKUS001'
    }

    if event_deadline:
        data['occurrence.deadLine'] = event_deadline

    try:
        # Prepara os arquivos caso existam
        files_payload = None
        if file and file.filename:
            file_bytes = await file.read()
            # O Nuubes geralmente espera o campo do arquivo nomeado corretamente
            files_payload = {'file': (file.filename, file_bytes, file.content_type or 'application/octet-stream')}

        # O requests gerencia automaticamente o Content-Type como multipart/form-data quando 'files' é passado
        response = requests.post(url, data=data, files=files_payload, timeout=30)
        
        resposta_nuubes = response.text.strip()
        print(f"DEBUG - Resposta Nuubes: {resposta_nuubes}")

        return {
            "status": "success",
            "nuubes_response": resposta_nuubes,
            "title": event_title,
            "tipo_utilizado": tipo_ocorrencia,
            "tem_anexo": bool(files_payload),
            "deadline": event_deadline
        }
    except Exception as e:
        print(f"DEBUG - Erro crítico: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        # Atualizado as 24/07
