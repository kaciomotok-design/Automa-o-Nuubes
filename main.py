from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import requests
from datetime import datetime
import re
import base64
import json

app = FastAPI()

COMPANY_KEY = "n1w8wHXbAuE="
ADMIN_EMAIL = "tarefas.nuubes@grupofokus.com.br"

URL_CRIAR_OCORRENCIA = "https://api.nuubes.com/api.occurrence.logic"
URL_ANEXAR_ARQUIVO = "https://api.nuubes.com/api.files.logic"
URL_HISTORICO = "https://api.nuubes.com/api.occurrenceHistory.logic"
URL_WORKFLOW = "https://api.nuubes.com/api.workflowPath.logic"

EMAILS_NUUBES_NOTIFICACAO = [
    "tarefas.nuubes@grupofokus.com.br",
    "tarefas@grupofokus.com.br"
]


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


# ============================================================
# ANEXOS
# ============================================================

def preparar_arquivo_base64(anexo: AnexoRequest):
    """
    Recebe o conteúdo Base64 enviado pelo Power Automate,
    converte para os bytes reais do arquivo e registra informações
    de diagnóstico no log do Render.
    """

    if not anexo.conteudo_base64:
        return None

    conteudo = anexo.conteudo_base64.strip()

    # Caso o conteúdo venha no formato:
    # data:image/jpeg;base64,/9j/4AAQ...
    if conteudo.startswith("data:") and "," in conteudo:
        conteudo = conteudo.split(",", 1)[1]

    try:
        arquivo_bytes = base64.b64decode(
            conteudo,
            validate=True
        )

    except Exception as e:
        raise ValueError(
            f"Anexo '{anexo.nome}' não contém Base64 válido: {str(e)}"
        )

    if not arquivo_bytes:
        return None

    # --------------------------------------------------------
    # DIAGNÓSTICO
    # --------------------------------------------------------

    assinatura = arquivo_bytes[:16]

    print(
        f"DEBUG ANEXO - "
        f"Nome: {anexo.nome} | "
        f"Content-Type: {anexo.content_type} | "
        f"Tamanho Base64: {len(conteudo)} | "
        f"Tamanho bytes: {len(arquivo_bytes)} | "
        f"Assinatura: {assinatura!r}"
    )

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

            print(
                f"DEBUG ANEXO - Enviando '{anexo.nome}' "
                f"para OS {numero_ocorrencia}"
            )

            response = requests.post(
                URL_ANEXAR_ARQUIVO,
                data=data_anexo,
                files=files,
                timeout=30
            )

            print(
                f"DEBUG ANEXO - Resposta Nuubes | "
                f"Arquivo: {anexo.nome} | "
                f"HTTP: {response.status_code} | "
                f"Resposta: {response.text[:500]}"
            )

            resultados.append({
                "arquivo": anexo.nome,
                "status_code": response.status_code,
                "resposta": response.text.strip()
            })

        except Exception as e:

            print(
                f"DEBUG ANEXO - ERRO | "
                f"Arquivo: {anexo.nome} | "
                f"Erro: {str(e)}"
            )

            resultados.append({
                "arquivo": anexo.nome,
                "status": "erro",
                "resposta": str(e)
            })

    return resultados


# ============================================================
# CONSULTAS AO NUUBES
# ============================================================

TIMEOUT_NUUBES = (5, 12)


def _resumo_resposta(response, limite=500):
    texto = (response.text or "").strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto[:limite]


def _json_seguro(response, nome_endpoint):
    """
    Converte a resposta do Nuubes em JSON sem deixar um JSON inválido
    derrubar toda a integração.
    """

    content_type = (response.headers.get("content-type") or "").lower()
    texto = (response.text or "").strip()

    if not texto:
        raise ValueError(
            f"{nome_endpoint} retornou resposta vazia "
            f"(HTTP {response.status_code}, "
            f"content-type={content_type or 'não informado'})"
        )

    try:
        return response.json()

    except ValueError as exc:
        trecho = _resumo_resposta(response)

        raise ValueError(
            f"{nome_endpoint} retornou conteúdo que não é JSON válido "
            f"(HTTP {response.status_code}, "
            f"content-type={content_type or 'não informado'}). "
            f"Trecho recebido: {trecho!r}"
        ) from exc


def _get_nuubes(url, params, nome_endpoint):

    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Nuubes-Fokus-Integration/1.0"
            },
            timeout=TIMEOUT_NUUBES
        )

        response.raise_for_status()

        return _json_seguro(response, nome_endpoint)

    except requests.Timeout as exc:

        raise requests.RequestException(
            f"{nome_endpoint} excedeu o tempo limite de consulta ao Nuubes"
        ) from exc

    except requests.RequestException:
        raise


def _extrair_dados_historico(historico):

    resultado = {
        "responsavel": "",
        "comentario": "",
        "data": "",
        "status": "",
        "tipo": ""
    }

    if not isinstance(historico, list) or not historico:
        return resultado

    for item in historico:

        descricao = (item.get("description") or "").strip()
        audit = (item.get("auditInfo") or "").strip()
        usuario = (item.get("user") or "").strip()

        m_resp = re.search(
            r"Responsável da atividade definido para\s+(.+?)(?:\.|$)",
            descricao,
            flags=re.IGNORECASE
        )

        if m_resp:
            resultado["responsavel"] = m_resp.group(1).strip()

        m_tipo = re.search(
            r"Tipo de atividade alterado de .+? para\s+(.+?)(?:\.|$)",
            descricao,
            flags=re.IGNORECASE
        )

        if m_tipo:
            resultado["tipo"] = m_tipo.group(1).strip()

        texto_status = f"{audit} {descricao}"

        m_status = re.search(
            r"Status (?:foi )?alterado de .+? para\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ ]+)",
            texto_status,
            flags=re.IGNORECASE
        )

        if m_status:
            resultado["status"] = m_status.group(1).strip(" .,;")

        if not resultado["responsavel"] and usuario:
            resultado["responsavel"] = usuario

    for item in reversed(historico):

        descricao = (item.get("description") or "").strip()
        audit = (item.get("auditInfo") or "").strip()

        if (
            descricao
            and not descricao.lower().startswith("responsável da atividade")
            and not descricao.lower().startswith("tipo de atividade")
            and not descricao.lower().startswith("status alterado")
            and not audit
        ):

            resultado["comentario"] = descricao
            resultado["data"] = (item.get("dateAdd") or "").strip()

            if item.get("user"):
                resultado["responsavel"] = (
                    item.get("user") or ""
                ).strip()

            break

    if not resultado["comentario"]:

        ultimo = historico[-1]

        resultado["comentario"] = (
            ultimo.get("description") or ""
        ).strip()

        resultado["data"] = (
            ultimo.get("dateAdd") or ""
        ).strip()

        if not resultado["responsavel"]:
            resultado["responsavel"] = (
                ultimo.get("user") or ""
            ).strip()

    return resultado


def obter_historico_completo(numero_ocorrencia):

    params = {
        "company.key": COMPANY_KEY,
        "occurrence.numberOccurrence": numero_ocorrencia
    }

    dados = _get_nuubes(
        URL_HISTORICO,
        params,
        "api.occurrenceHistory.logic"
    )

    if not dados:
        return []

    if isinstance(dados, list):
        return dados

    if isinstance(dados, dict):
        return [dados]

    raise ValueError(
        "api.occurrenceHistory.logic retornou um formato inesperado"
    )


def obter_historico_ocorrencia(numero_ocorrencia):

    historico = obter_historico_completo(numero_ocorrencia)

    if not historico:
        return None

    return _extrair_dados_historico(historico)


def consultar_ocorrencia(numero_ocorrencia):

    params = {
        "company.key": COMPANY_KEY,
        "occurrence.numberOccurrence": numero_ocorrencia
    }

    dados = _get_nuubes(
        URL_CRIAR_OCORRENCIA,
        params,
        "api.occurrence.logic"
    )

    if isinstance(dados, list):
        return dados[0] if dados else None

    return dados if isinstance(dados, dict) else None


def consultar_workflow(numero_ocorrencia):

    params = {
        "company.key": COMPANY_KEY,
        "occurrence.numberOccurrence": numero_ocorrencia
    }

    dados = _get_nuubes(
        URL_WORKFLOW,
        params,
        "api.workflowPath.logic"
    )

    if not dados:
        return []

    return dados if isinstance(dados, list) else [dados]


def selecionar_etapa_workflow(workflow):

    if not workflow:
        return None

    return workflow[-1]


def montar_dados_os(numero_ocorrencia):

    avisos = []

    ocorrencia = None
    historico = None
    workflow = []

    try:
        ocorrencia = consultar_ocorrencia(numero_ocorrencia)

    except Exception as e:
        mensagem = f"occurrence: {str(e)}"
        print(f"DEBUG - {mensagem}")
        avisos.append(mensagem)

    try:
        historico = obter_historico_ocorrencia(numero_ocorrencia)

    except Exception as e:
        mensagem = f"historico: {str(e)}"
        print(f"DEBUG - {mensagem}")
        avisos.append(mensagem)

    try:
        workflow = consultar_workflow(numero_ocorrencia)

    except Exception as e:
        mensagem = f"workflow: {str(e)}"
        print(f"DEBUG - {mensagem}")
        avisos.append(mensagem)
        workflow = []

    etapa = selecionar_etapa_workflow(workflow)

    if not ocorrencia and not historico and not etapa:

        if avisos:
            raise RuntimeError(
                "Não foi possível obter dados da OS no Nuubes. "
                + " | ".join(avisos)
            )

        return None

    ocorrencia = ocorrencia or {}
    historico = historico or {}
    etapa = etapa or {}

    numero = (
        ocorrencia.get("numero")
        or ocorrencia.get("numberOccurrence")
        or etapa.get("numero")
        or numero_ocorrencia
    )

    assunto = (
        ocorrencia.get("assunto")
        or ocorrencia.get("summary")
        or etapa.get("assunto")
        or etapa.get("summary")
        or ""
    )

    status = (
        ocorrencia.get("status")
        or etapa.get("status")
        or historico.get("status")
        or ""
    )

    responsavel = (
        ocorrencia.get("responsavel")
        or etapa.get("responsavel")
        or historico.get("responsavel")
        or ""
    )

    area = (
        ocorrencia.get("area")
        or etapa.get("area")
        or ocorrencia.get("project")
        or etapa.get("project")
        or ""
    )

    if isinstance(area, dict):
        area = area.get("name") or area.get("nome") or ""

    departamento = (
        ocorrencia.get("departamento")
        or etapa.get("departamento")
        or area
        or ""
    )

    tipo = (
        ocorrencia.get("tipo")
        or etapa.get("tipo")
        or historico.get("tipo")
        or ""
    )

    solicitante = (
        ocorrencia.get("solicitante")
        or etapa.get("solicitante")
        or ""
    )

    return {
        "status_integracao":
            "success" if not avisos else "partial_success",

        "numero_ocorrencia": str(numero),
        "assunto": assunto,
        "status_os": status,
        "responsavel": responsavel,
        "departamento": departamento,
        "area": area,
        "tipo": tipo,
        "solicitante": solicitante,
        "comentario": historico.get("comentario", ""),
        "usuario_resposta": historico.get("responsavel", ""),
        "data_resposta": historico.get("data", ""),
        "workflow": workflow,
        "avisos_integracao": avisos
    }


# ============================================================
# ENDPOINTS
# ============================================================

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
    print(f"DEBUG - Remetente recebido: {payload.organizer_email}")

    origem = (payload.origem or "").strip().lower()
    area_origem = (payload.area_origem or "").strip().lower()
    email_remetente = (
        payload.organizer_email or ""
    ).strip().lower()

    if any(
        email in email_remetente
        for email in EMAILS_NUUBES_NOTIFICACAO
    ):

        print(
            "DEBUG - E-mail automático do Nuubes ignorado. "
            "Nenhuma tarefa será criada."
        )

        return {
            "status": "ignored",
            "reason": "E-mail automático do Nuubes ignorado",
            "organizer_email": payload.organizer_email,
            "title": payload.event_title,
            "origem_recebida": origem,
            "area_origem_recebida": area_origem,
            "numero_ocorrencia": "",
            "tem_anexo": False,
            "quantidade_anexos": 0
        }

    texto_final_desc = limpar_html(
        payload.event_description or ""
    )

    event_deadline = formatar_data(
        payload.event_start_date or ""
    )

    if origem == "email" and area_origem == "tecnologia":

        projeto_ocorrencia = "TECNOLOGIA"
        tipo_ocorrencia = "OS. SUPORTE T.I"

        descricao_final = (
            f"E-mail recebido de "
            f"{payload.organizer_email}.\n\n"
            f"{texto_final_desc}"
        )

    elif origem == "email":

        projeto_ocorrencia = "ANÁLISE DE PROCESSOS"
        tipo_ocorrencia = "OS. SOLICITAÇÕES INTERNAS"

        descricao_final = (
            f"E-mail recebido de "
            f"{payload.organizer_email}.\n\n"
            f"{texto_final_desc}"
        )

    else:

        projeto_ocorrencia = "ANÁLISE DE PROCESSOS"
        tipo_ocorrencia = "OS. REUNIÃO INTERNA"

        descricao_final = (
            f"Evento criado no calendário por "
            f"{payload.organizer_email}.\n\n"
            f"{texto_final_desc}"
        )

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
        "Content-Type":
            "application/x-www-form-urlencoded; charset=utf-8",
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
        print(
            f"DEBUG - Solicitante técnico enviado: "
            f"{ADMIN_EMAIL}"
        )
        print(
            f"DEBUG - Resposta criação Nuubes: "
            f"{resposta_nuubes}"
        )

        numero_ocorrencia = (
            resposta_nuubes
            if resposta_nuubes.isdigit()
            else ""
        )

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
            "email_admin_utilizado": ADMIN_EMAIL,
            "tem_anexo": bool(payload.anexos),
            "quantidade_anexos":
                len(payload.anexos or []),
            "resultado_anexos":
                resultados_anexos,
            "deadline": event_deadline
        }

    except Exception as e:

        print(f"DEBUG - Erro crítico: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/obter-historico/{numero_ocorrencia}")
async def obter_historico(numero_ocorrencia: str):

    try:

        resultado = obter_historico_ocorrencia(
            numero_ocorrencia
        )

        if not resultado:

            return {
                "status": "not_found",
                "numero_ocorrencia":
                    numero_ocorrencia
            }

        return {
            "status": "success",
            "numero_ocorrencia":
                numero_ocorrencia,
            "responsavel":
                resultado["responsavel"],
            "comentario":
                resultado["comentario"],
            "data":
                resultado["data"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/obter-dados-os/{numero_ocorrencia}")
async def obter_dados_os(numero_ocorrencia: str):

    try:

        resultado = montar_dados_os(
            numero_ocorrencia
        )

        if not resultado:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"OS {numero_ocorrencia} "
                    f"não encontrada no Nuubes"
                )
            )

        return resultado

    except HTTPException:
        raise

    except requests.RequestException as e:

        print(
            f"DEBUG - Erro de comunicação ao consultar "
            f"OS {numero_ocorrencia}: {str(e)}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Erro de comunicação com a API "
                f"do Nuubes: {str(e)}"
            )
        )

    except Exception as e:

        print(
            f"DEBUG - Erro ao obter dados da OS "
            f"{numero_ocorrencia}: {str(e)}"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Falha ao consultar dados da OS "
                f"{numero_ocorrencia}: {str(e)}"
            )
        )
