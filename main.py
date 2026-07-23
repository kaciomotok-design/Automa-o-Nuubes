from fastapi import FastAPI, File, UploadFile, Form, HTTPException
import requests
import json
import re

app = FastAPI()

@app.post("/criar-tarefa")
async def criar_tarefa(
    event_title: str = Form("Evento sem título"),
    event_description: str = Form("Sem descrição"),
    organizer_email: str = Form("kacio.mota@grupofokus.com.br"),
    event_start_date: str = Form(""),
    file: UploadFile = File(None)
):
    print(f"DEBUG - Título recebido: {event_title}")
    
    # Limpeza de HTML do e-mail
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
            event_deadline = ''

    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    
    # 1. Cria a tarefa principal
    url_occurrence = 'https://api.nuubes.com/api.occurrence.logic'
    descricao_final = f"E-mail recebido de {organizer_email}.\n\n{texto_final_desc}"

    data_occurrence = {
        'company.key': company_key,
        'occurrence.summary': event_title,
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

        # Tenta extrair o número da ocorrência criada da resposta do Nuubes
        # O Nuubes costuma retornar o número ou texto indicando sucesso
        numero_ocorrencia = None
        match = re.search(r'\d+', resposta_texto)
        if match:
            numero_ocorrencia = match.group(0)

        # 2. Se houver anexo e conseguirmos o número da ocorrência, envia o arquivo pela API de arquivos
        if file and file.filename and numero_ocorrencia:
            url_files = 'https://api.nuubes.com/api.files.logic'
            file_content = await file.read()
            
            data_file = {
                'company.key': company_key,
                'occurrence.numberOccurrence': numero_ocorrencia
            }
            
            files_data = {
                'fileInfo': (file.filename, file_content, file.content_type or 'application/octet-stream')
            }
            
            response_file = requests.post(url_files, data=data_file, files=files_data, headers=headers, timeout=60)
            print(f"DEBUG - Resposta Nuubes Anexo: {response_file.text}")

        return {
            "status": "success",
            "nuubes_response": resposta_texto,
            "title": event_title,
            "attachment_sent": bool(file and file.filename)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
