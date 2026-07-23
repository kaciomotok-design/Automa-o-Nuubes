from fastapi import FastAPI, Form, HTTPException
import requests
from datetime import datetime
import json
import re
from html import unescape

app = FastAPI()

@app.post("/criar-tarefa")
async def criar_tarefa(
    event_title: str = Form("Evento sem título"),
    event_description: str = Form("Sem descrição"),
    organizer_email: str = Form("kacio.mota@grupofokus.com.br"),
    event_start_date: str = Form("")
):
    print(f"DEBUG - Título recebido: {event_title}")
    
    # Limpeza cirúrgica do corpo da mensagem
    texto_limpo = event_description
    
    # Se por acaso vier em formato JSON ou objeto
    if texto_limpo.strip().startswith("{"):
        try:
            dados_json = json.loads(texto_limpo)
            texto_limpo = dados_json.get("body", "Reunião do Outlook")
        except:
            pass

    # Decodifica entidades HTML e remove tags de formatação do Word/Outlook
    texto_limpo = unescape(texto_limpo)
    texto_limpo = re.sub(r'<[^>]+>', '\n', texto_limpo)
    
    # Limpa linhas vazias e espaços excessivos
    linhas = [linha.strip() for linha in texto_limpo.splitlines() if linha.strip() and linha.strip() != '&nbsp;']
    
    if linhas:
        texto_final_desc = "\n".join(linhas)
    else:
        texto_final_desc = "Sem descrição informada."

    # Trata a data para o formato do Nuubes (mm/dd/aaaa)
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
    
    descricao_final = f"Evento criado no calendário por {organizer_email}.\n\n{texto_final_desc}"

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

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        'User-Agent': 'Nuubes-API-Client',
        'Accept': 'text/plain, */*'
    }

    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        return {
            "status": "success",
            "nuubes_response": response.text.strip(),
            "title": event_title,
            "deadline": event_deadline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
