from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import requests
from datetime import datetime
import re
import base64

app = FastAPI()


class AnexoRequest(BaseModel):
    nome: str
    content_type: Optional[str] = "application/octet-stream"
    conteudo_base64: str


class TarefaRequest(BaseModel):
    event_title: Optional[str] = "Evento sem título"
    event_description: Optional[str] = "Sem descrição"
    organizer_email: Optional[str] = "kacio.mota@grupofokus.com.br"
    event_start_date: Optional[str] = ""
    origem: Optional[str] = "calendario"
    anexos: Optional[List[AnexoRequest]] = []


@app.get("/")
async def healthcheck():
    return {
        "status": "online",
        "service": "Nuubes Fokus API"
    }


@app.post("/criar-tarefa")
async def criar_tarefa(payload: TarefaRequest):
    print(f"DEBUG - Título recebido: {payload.event_title}")
    print(f"DEBUG - Origem recebida: {payload.origem}")

    texto_bruto = payload.event_description or ""
    texto_limpo = re.sub(r"<[^>]+>", "\n", texto_bruto)

    linhas_filtradas = []

    for linha in texto_limpo.splitlines():
        linha_limpa = linha.strip()

        if "@font-face" in linha_limpa or "MsoNormal" in linha_limpa or "!--" in linha_limpa:
            continue

        if linha_limpa and linha_limpa != "&nbsp;":
            linhas_filtradas.append(linha_limpa)

    texto_final_desc = "\n".join(linhas_filtradas) if linhas_filtradas else "Sem descrição informada."

    event_deadline = ""

    if payload.event_start_date:
        try:
            event_date = datetime.fromisoformat(payload.event_start_date.replace("Z", "+00:00"))
            event_deadline = event_date.strftime("%m/%d/%Y")
        except Exception as e:
            print(f"DEBUG - Erro ao formatar data: {e}")
            event_deadline = ""

    origem = (payload.origem or "").strip().lower()

    if origem == "email":
        tipo_ocorrencia = "OS. SOLICITAÇÕES INTERNAS"
        descricao_final = f"E-mail recebido de {payload.organizer_email}.\n\n{texto_final_desc}"
    else:
        tipo_ocorrencia = "OS. REUNIÃO INTERNA"
        descricao_final = f"Evento criado no calendário por {payload.organizer_email}.\n\n{texto_final_desc}"

    admin_email = "nuubes@grupofokus.com.br"
    url = "https://api.nuubes.com/api.occurrence.logic"

    data = {
        "company.key": "n1w8wHXbAuE=",
        "occurrence.summary": payload.event_title,
        "occurrence.description": descricao_final,
        "occurrence.requestor.email": admin_email,
        "occurrence.project.name": "ANÁLISE DE PROCESSOS",
        "occurrence.occurrenceType.name": tipo_ocorrencia,
        "occurrence.customer.name": "GRUPO FOKUS",
        "occurrence.customer.externalCode": "FOKUS001"
    }

    if event_deadline:
        data["occurrence.deadLine"] = event_deadline

    files_payload = []

    for anexo in payload.anexos or []:
        if not anexo.conteudo_base64:
            print(f"DEBUG - Anexo ignorado sem conteúdo: {anexo.nome}")
            continue

        try:
            arquivo_bytes = base64.b64decode(anexo.conteudo_base64)

            if not arquivo_bytes:
                print(f"DEBUG - Anexo ignorado vazio após decode: {anexo.nome}")
                continue

            files_payload.append(
                (
                    "file",
                    (
                        anexo.nome,
                        arquivo_bytes,
                        anexo.content_type or "application/octet-stream"
                    )
                )
            )

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao processar anexo {anexo.nome}: {str(e)}"
            )

    headers_sem_anexo = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Nuubes-API-Client",
        "Accept": "text/plain, */*"
    }

    headers_com_anexo = {
        "User-Agent": "Nuubes-API-Client",
        "Accept": "text/plain, */*"
    }

    try:
        if files_payload:
            response = requests.post(
                url,
                data=data,
                files=files_payload,
                headers=headers_com_anexo,
                timeout=30
            )
        else:
            response = requests.post(
                url,
                data=data,
                headers=headers_sem_anexo,
                timeout=30
            )

        resposta = response.text.strip()

        print(f"DEBUG - Tipo enviado: {tipo_ocorrencia}")
        print(f"DEBUG - Anexos válidos enviados: {len(files_payload)}")
        print(f"DEBUG - Resposta Nuubes: {resposta}")

        return {
            "status": "success",
            "nuubes_status_code": response.status_code,
            "nuubes_response": resposta,
            "title": payload.event_title,
            "origem_recebida": origem,
            "tipo_utilizado": tipo_ocorrencia,
            "tem_anexo": bool(files_payload),
            "quantidade_anexos": len(files_payload),
            "deadline": event_deadline
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
