from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from typing import Optional, List
import requests
from datetime import datetime
import re
import json

app = FastAPI()


def limpar_html(texto_bruto):
    if not texto_bruto:
        return "Sem descrição informada."

    texto_limpo = re.sub(r'<[^>]+>', '\n', texto_bruto)

    linhas_filtradas = []

    for linha in texto_limpo.splitlines():
        linha_limpa = linha.strip()

        if "@font-face" in linha_limpa:
            continue

        if "MsoNormal" in linha_limpa:
            continue

        if "!--" in linha_limpa:
            continue

        if linha_limpa and linha_limpa != "&nbsp;":
            linhas_filtradas.append(linha_limpa)

    return "\n".join(linhas_filtradas) if linhas_filtradas else "Sem descrição informada."


def formatar_data(data_str):

    if not data_str:
        return ""

    try:
        event_date = datetime.fromisoformat(
            data_str.replace("Z", "+00:00")
        )

        return event_date.strftime("%m/%d/%Y")

    except Exception:
        return ""


@app.post("/criar-tarefa")
async def criar_tarefa(
    request: Request,
    event_title: Optional[str] = Form(None),
    event_description: Optional[str] = Form(None),
    organizer_email: Optional[str] = Form(None),
    event_start_date: Optional[str] = Form(None),
    origem: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[])
):

    ##################################################
    # Detecta automaticamente JSON ou Form
    ##################################################

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:

        body = await request.json()

        event_title = body.get("event_title")

        event_description = body.get("event_description")

        organizer_email = body.get("organizer_email")

        event_start_date = body.get("event_start_date")

        origem = body.get("origem", "calendario")

    else:

        event_title = event_title or "Evento sem título"

        event_description = event_description or "Sem descrição"

        organizer_email = organizer_email or "kacio.mota@grupofokus.com.br"

        event_start_date = event_start_date or ""

        origem = origem or "calendario"

    print(f"Origem recebida: {origem}")

    ##################################################
    # Define o tipo da ocorrência
    ##################################################

    if origem.lower() == "email":

        tipo_ocorrencia = "OS. SOLICITAÇÕES INTERNAS"

        prefixo_desc = f"E-mail recebido de {organizer_email}."

    else:

        tipo_ocorrencia = "OS. REUNIÃO INTERNA"

        prefixo_desc = f"Evento criado no calendário por {organizer_email}."

    ##################################################
    # Limpeza da descrição
    ##################################################

    texto_final_desc = limpar_html(event_description)

    descricao_final = f"{prefixo_desc}\n\n{texto_final_desc}"

    ##################################################
    # Data
    ##################################################

    deadline = formatar_data(event_start_date)

    ##################################################
    # Dados Nuubes
    ##################################################

    data = {

        "company.key": "n1w8wHXbAuE=",

        "occurrence.summary": event_title,

        "occurrence.description": descricao_final,

        "occurrence.requestor.email": "nuubes@grupofokus.com.br",

        "occurrence.project.name": "ANÁLISE DE PROCESSOS",

        "occurrence.occurrenceType.name": tipo_ocorrencia,

        "occurrence.customer.name": "GRUPO FOKUS",

        "occurrence.customer.externalCode": "FOKUS001"

    }

    if deadline:
        data["occurrence.deadLine"] = deadline

    ##################################################
    # Arquivos
    ##################################################

    files_payload = []

    for arquivo in files:

        conteudo = await arquivo.read()

        files_payload.append(

            (

                "file",

                (

                    arquivo.filename,

                    conteudo,

                    arquivo.content_type or "application/octet-stream"

                )

            )

        )

    if len(files_payload) == 0:

        files_payload = None

    ##################################################
    # Envia ao Nuubes
    ##################################################

    try:

        resposta = requests.post(

            "https://api.nuubes.com/api.occurrence.logic",

            data=data,

            files=files_payload,

            timeout=30

        )

        return {

            "status": "success",

            "tipo_utilizado": tipo_ocorrencia,

            "origem": origem,

            "title": event_title,

            "deadline": deadline,

            "tem_anexo": files_payload is not None,

            "quantidade_anexos": len(files) if files else 0,

            "nuubes_response": resposta.text

        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )
