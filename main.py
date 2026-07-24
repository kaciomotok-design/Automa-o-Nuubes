from fastapi import FastAPI, HTTPException, Request
import requests
from datetime import datetime
import re
import html
import base64
import json

app = FastAPI()


def limpar_html(texto_bruto):
    if not texto_bruto:
        return "Sem descrição informada."

    texto_bruto = html.unescape(str(texto_bruto))
    texto_limpo = re.sub(r"<[^>]+>", "\n", texto_bruto)

    linhas_filtradas = []

    for linha in texto_limpo.splitlines():
        linha_limpa = linha.strip()

        if not linha_limpa or linha_limpa == "&nbsp;":
            continue

        if (
            "@font-face" in linha_limpa
            or "MsoNormal" in linha_limpa
            or "!--" in linha_limpa
            or "font-family" in linha_limpa
            or "mso-" in linha_limpa.lower()
        ):
            continue

        linhas_filtradas.append(linha_limpa)

    return "\n".join(linhas_filtradas) if linhas_filtradas else "Sem descrição informada."


def formatar_data(data_str):
    if not data_str:
        return ""

    try:
        event_date = datetime.fromisoformat(str(data_str).replace("Z", "+00:00"))
        return event_date.strftime("%m/%d/%Y")
    except Exception:
        return ""


def obter_campo(payload, nome, padrao=""):
    valor = payload.get(nome, padrao)

    if valor is None:
        return padrao

    return str(valor)


async def extrair_dados_request(request: Request):
    content_type = request.headers.get("content-type", "").lower()

    payload = {}
    arquivos = []

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="JSON inválido no corpo da requisição."
            )

        anexos_json = payload.get("anexos") or []

        if isinstance(anexos_json, str):
            try:
                anexos_json = json.loads(anexos_json)
            except Exception:
                anexos_json = []

        for anexo in anexos_json:
            nome = anexo.get("nome") or anexo.get("name") or "anexo"
            content_type_anexo = (
                anexo.get("content_type")
                or anexo.get("contentType")
                or "application/octet-stream"
            )
            conteudo_base64 = (
                anexo.get("conteudo_base64")
                or anexo.get("contentBytes")
                or anexo.get("base64")
            )

            if not conteudo_base64:
                continue

            try:
                arquivo_bytes = base64.b64decode(conteudo_base64)
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=f"Anexo inválido em Base64: {nome}"
                )

            arquivos.append(
                ("file", (nome, arquivo_bytes, content_type_anexo))
            )

    elif (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        form = await request.form()

        for chave, valor in form.multi_items():
            if hasattr(valor, "filename"):
                if valor.filename:
                    arquivo_bytes = await valor.read()
                    arquivos.append(
                        (
                            "file",
                            (
                                valor.filename,
                                arquivo_bytes,
                                valor.content_type or "application/octet-stream",
                            ),
                        )
                    )
            else:
                payload[chave] = valor

    else:
        raise HTTPException(
            status_code=415,
            detail=f"Content-Type não suportado: {content_type}"
        )

    return payload, arquivos, content_type


@app.get("/")
async def healthcheck():
    return {
        "status": "online",
        "service": "Nuubes Fokus API"
    }


@app.post("/criar-tarefa")
async def criar_tarefa(request: Request):
    payload, arquivos, content_type_recebido = await extrair_dados_request(request)

    event_title = obter_campo(payload, "event_title", "Evento sem título")
    event_description = obter_campo(payload, "event_description", "Sem descrição")
    organizer_email = obter_campo(
        payload,
        "organizer_email",
        "kacio.mota@grupofokus.com.br"
    )
    event_start_date = obter_campo(payload, "event_start_date", "")
    origem = obter_campo(payload, "origem", "calendario").strip().lower()

    print(
        f"DEBUG - Título recebido: {event_title} | "
        f"Origem: {origem} | "
        f"Content-Type: {content_type_recebido} | "
        f"Anexos: {len(arquivos)}"
    )

    texto_final_desc = limpar_html(event_description)
    event_deadline = formatar_data(event_start_date)

    admin_email = "nuubes@grupofokus.com.br"
    url = "https://api.nuubes.com/api.occurrence.logic"

    if origem == "email":
        tipo_ocorrencia = "OS. SOLICITAÇÕES INTERNAS"
        prefixo_desc = f"E-mail recebido de {organizer_email}."
    else:
        tipo_ocorrencia = "OS. REUNIÃO INTERNA"
        prefixo_desc = f"Evento criado no calendário por {organizer_email}."

    descricao_final = f"{prefixo_desc}\n\n{texto_final_desc}"

    data = {
        "company.key": "n1w8wHXbAuE=",
        "occurrence.summary": event_title,
        "occurrence.description": descricao_final,
        "occurrence.requestor.email": admin_email,
        "occurrence.area.name": "ANÁLISE DE PROCESSOS",
        "occurrence.project.name": "ANÁLISE DE PROCESSOS",
        "occurrence.occurrenceType.name": tipo_ocorrencia,
        "occurrence.customer.name": "GRUPO FOKUS",
        "occurrence.customer.externalCode": "FOKUS001",
    }

    if event_deadline:
        data["occurrence.deadLine"] = event_deadline

    try:
        response = requests.post(
            url,
            data=data,
            files=arquivos if arquivos else None,
            timeout=30
        )

        resposta_nuubes = response.text.strip()

        print(f"DEBUG - Status Nuubes: {response.status_code}")
        print(f"DEBUG - Resposta Nuubes: {resposta_nuubes}")

        return {
            "status": "success",
            "nuubes_status_code": response.status_code,
            "nuubes_response": resposta_nuubes,
            "title": event_title,
            "origem_recebida": origem,
            "tipo_utilizado": tipo_ocorrencia,
            "tem_anexo": bool(arquivos),
            "quantidade_anexos": len(arquivos),
            "deadline": event_deadline
        }

    except Exception as e:
        print(f"DEBUG - Erro crítico: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
