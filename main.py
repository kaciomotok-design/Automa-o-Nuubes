from fastapi import FastAPI, Form, File, UploadFile, HTTPException
import requests
from datetime import datetime
import re

app = FastAPI()

@app.post("/criar-tarefa")
async def criar_tarefa(
    event_title: str = Form("Evento sem título"),
    event_description: str = Form("Sem descrição"),
    organizer_email: str = Form("kacio.mota@grupofokus.com.br"),
    event_start_date: str = Form(""),
    file: UploadFile = File(None) # Captura opcional de anexo
):
    print(f"DEBUG - Título recebido: {event_title}")
    
    # Limpeza de HTML/sujeira do texto
    texto_bruto = event_description or ""
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
    if event_start_date:
        try:
            event_date = datetime.fromisoformat(event_start_date.replace('Z', '+00:00'))
            event_deadline = event_date.strftime('%m/%d/%Y')
        except Exception as e:
            print(f"DEBUG - Erro ao formatar data: {e}")
            event_deadline = ''

    admin_email = 'nuubes@grupofokus.com.br'
    url = 'https://api.nuubes.com/api.occurrence.logic'
    
    descricao_final = f"E-mail recebido de {organizer_email}.\n\n{texto_final_desc}"

    # Monta os dados básicos do formulário
    data = {
        'company.key': 'n1w8wHXbAuE=',
        'occurrence.summary': event_title,
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
    
    # Se houver um anexo vindo do Power Automate, prepara para enviar ao Nuubes
    if file and file.filename:
        file_content = await file.read()
        files_to_send = {
            'fileInfo': (file.filename, file_content, file.content_type or 'application/octet-stream')
        }

    headers = {
        'User-Agent': 'Nuubes-API-Client',
        'Accept': 'text/plain, */*'
        # Nota: O requests gerencia o Content-Type automaticamente quando enviamos 'files'
    }

    try:
        # Envia para o Nuubes (com ou sem anexo)
        response = requests.post(url, data=data, files=files_to_send, headers=headers, timeout=60)
        return {
            "status": "success",
            "nuubes_response": response.text.strip(),
            "title": event_title,
            "has_attachment": bool(file and file.filename)
        }
    except Exception as e:
        print(f"DEBUG - Erro na requisição: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
