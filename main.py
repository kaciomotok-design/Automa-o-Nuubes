from fastapi import FastAPI, Form, HTTPException
import requests
from datetime import datetime
import re

app = FastAPI()

@app.post("/criar-tarefa")
async def criar_tarefa(
    event_title: str = Form("Evento sem título"),
    event_description: str = Form("Sem descrição"),
    organizer_email: str = Form("kacio.mota@grupofokus.com.br"),
    event_start_date: str = Form("")
):
    print(f"DEBUG - Título recebido: {event_title}")
    
    # 1. Limpeza inteligente da descrição (Remove HTML, JSON e metadados indesejados)
    descricao_limpa = event_description
    
    # Se a descrição veio em formato de dicionário ou contiver tags HTML do Outlook
    if "{" in descricao_limpa and "}" in descricao_limpa:
        # Tenta extrair um texto mais amigável ou define um padrão se for o objeto bruto do Outlook
        descricao_limpa = "Reunião agendada via Calendário do Outlook."
    else:
        # Remove tags HTML comuns caso venham no texto
        descricao_limpa = re.sub('<.*?>', '', descricao_limpa).strip()
        if not descricao_limpa:
            descricao_limpa = "Sem descrição informada."

    # 2. Processar a data do evento para o formato do Nuubes (mm/dd/aaaa)
    event_deadline = ''
    if event_start_date:
        try:
            event_date = datetime.fromisoformat(event_start_date.replace('Z', '+00:00'))
            event_deadline = event_date.strftime('%m/%d/%Y')
        except Exception as e:
            print(f"DEBUG - Erro ao formatar data: {e}")
            event_deadline = ''

    # 3. Configurações para envio ao Nuubes
    admin_email = 'nuubes@grupofokus.com.br'
    url = 'https://api.nuubes.com/api.occurrence.logic'
    
    # Montagem da descrição final organizada
    descricao_final = f"Evento criado no calendário por {organizer_email}.\n\nDetalhes:\n{descricao_limpa}"

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
        response_text = response.text.strip()
        
        print(f"DEBUG - Status Nuubes: {response.status_code} - Resposta: {response_text}")
        
        return {
            "status": "success",
            "nuubes_response": response_text,
            "title": event_title,
            "deadline": event_deadline
        }
    except Exception as e:
        print(f"DEBUG - Erro na requisição: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
