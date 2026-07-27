from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import requests
from datetime import datetime
import re
import base64

app = FastAPI()

COMPANY_KEY = "n1w8wHXbAuE="
ADMIN_EMAIL = "nuubes@grupofokus.com.br"

URL_CRIAR_OCORRENCIA = "https://api.nuubes.com/api.occurrence.logic"
URL_ANEXAR_ARQUIVO = "https://api.nuubes.com/api.files.logic"


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
    area_origem: Optional[str] = ""
    anexos: Optional[List[AnexoRequest]] = []


def limpar_html(texto_bruto):
    if not texto_bruto:
        return "Sem descrição informada."

    texto_limpo = re.sub(r"<[^>]+>", "\n", texto_bruto)

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
        return ""

    try:
        event_date = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return event_date.strftime("%m/%d/%Y")
    except Exception as e:
        print(f"DEBUG - Erro ao formatar data: {e}")
        return ""


def preparar_arquivo_base64(anexo: AnexoRequest):
    if not anexo.conteudo_base64:
        return None

    conteudo = anexo.conteudo_base64

    if "," in conteudo:
        conteudo = conteudo.split(",", 1)[1]

    arquivo_bytes = base64.b64decode(conteudo)

    if not arquivo_bytes:
        return None

    return (
        anexo.nome,
        arquivo_bytes,
        anexo.content_type or "application/octet-stream"
    )


def anexar_arquivos(numero_ocorrencia, anexos):
    resultados = []

    for anexo in anexos or []:
        try:
            arquivo = preparar_arquivo_base64(anexo)

            if not arquivo:
                resultados.append({
                    "arquivo": anexo.nome,
                    "status": "ignorado",
                    "resposta": "Arquivo sem conteúdo"
                })
                continue

            data_anexo = {
                "company.key": COMPANY_KEY,
                "occurrence.numberOccurrence": numero_ocorrencia
            }

            files = {
                "fileInfo": arquivo
            }

            response = requests.post(
                URL_ANEXAR_ARQUIVO,
                data=data_anexo,
                files=files,
                timeout=30
            )

            resultados.append({
                "arquivo": anexo.nome,
                "status_code": response.status_code,
                "resposta": response.text.strip()
            })

        except Exception as e:
            resultados.append({
                "arquivo": anexo.nome,
                "status": "erro",
                "resposta": str(e)
            })

    return resultados


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
    print(f"DEBUG - Área origem recebida: {payload.area_origem}")

    texto_final_desc = limpar_html(payload.event_description or "")
    event_deadline = formatar_data(payload.event_start_date or "")

    origem = (payload.origem or "").strip().lower()
    area_origem = (payload.area_origem or "").strip().lower()

    if origem == "email" and area_origem == "tecnologia":
        projeto_ocorrencia = "TECNOLOGIA"
        tipo_ocorrencia = "OS. SUPORTE T.I"
        descricao_final = f"E-mail recebido de {payload.organizer_email}.\n\n{texto_final_desc}"
    elif origem == "email":
        projeto_ocorrencia = "ANÁLISE DE PROCESSOS"
        tipo_ocorrencia = "OS. SOLICITAÇÕES INTERNAS"
        descricao_final = f"E-mail recebido de {payload.organizer_email}.\n\n{texto_final_desc}"
    else:
        projeto_ocorrencia = "ANÁLISE DE PROCESSOS"
        tipo_ocorrencia = "OS. REUNIÃO INTERNA"
        descricao_final = f"Evento criado no calendário por {payload.organizer_email}.\n\n{texto_final_desc}"

    data = {
        "company.key": COMPANY_KEY,
        "occurrence.summary": payload.event_title,
        "occurrence.description": descricao_final,
        "occurrence.requestor.email": ADMIN_EMAIL,
        "occurrence.project.name": projeto_ocorrencia,
        "occurrence.occurrenceType.name": tipo_ocorrencia,
        "occurrence.customer.name": "GRUPO FOKUS",
        "occurrence.customer.externalCode": "FOKUS001"
    }

    if event_deadline:
        data["occurrence.deadLine"] = event_deadline

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Nuubes-API-Client",
        "Accept": "text/plain, */*"
    }

    try:
        response = requests.post(
            URL_CRIAR_OCORRENCIA,
            data=data,
            headers=headers,
            timeout=30
        )

        resposta_nuubes = response.text.strip()

        print(f"DEBUG - Projeto enviado: {projeto_ocorrencia}")
        print(f"DEBUG - Tipo enviado: {tipo_ocorrencia}")
        print(f"DEBUG - Resposta criação Nuubes: {resposta_nuubes}")

        numero_ocorrencia = resposta_nuubes if resposta_nuubes.isdigit() else ""

        resultados_anexos = []

        if numero_ocorrencia and payload.anexos:
            resultados_anexos = anexar_arquivos(
                numero_ocorrencia,
                payload.anexos
            )

        return {
            "status": "success",
            "nuubes_status_code": response.status_code,
            "nuubes_response": resposta_nuubes,
            "numero_ocorrencia": numero_ocorrencia,
            "title": payload.event_title,
            "origem_recebida": origem,
            "area_origem_recebida": area_origem,
            "projeto_utilizado": projeto_ocorrencia,
            "tipo_utilizado": tipo_ocorrencia,
            "tem_anexo": bool(payload.anexos),
            "quantidade_anexos": len(payload.anexos or []),
            "resultado_anexos": resultados_anexos,
            "deadline": event_deadline
        }

    except Exception as e:
        print(f"DEBUG - Erro crítico: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        #
