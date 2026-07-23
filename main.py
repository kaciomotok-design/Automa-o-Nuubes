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
    
    # Limpeza avançada da descrição do Outlook
    descricao_limpa = event_description
    
    # Tenta encontrar o texto real do corpo se houver tags HTML do Outlook
    if "<body" in descricao_limpa or "<html>" in descricao_limpa:
        # Procura o que está dentro das tags <p class="MsoNormal"> ou similares
        match_p = re.findall(r'<p[^>]*>(.*?)</p>', descricao_limpa, re.DOTALL)
        if match_p:
            # Junta os parágrafos encontrados limpando as tags HTML internas
            textos_paragrafos = [re.sub('<.*?>', '', p).strip() for p in match_p]
            textos_validos = [t for t in textos_paragrafos if t and t != '&nbsp;']
            if textos_validos:
                descricao_limpa = "\n".join(textos_validos)
            else:
                descricao_limpa = "Sem descrição informada."
        else:
            # Remove qualquer HTML restante se não achar parágrafos específicos
            descricao_limpa = re.sub('<.*?>', '', descricao_limpa).strip()
    
    # Se ainda sobrar o blocão JSON de metadados, limpa de forma genérica
    if '"subject":' in descricao_limpa or '"id":' in descricao_limpa:
        descricao_limpa = "Reunião agendada via Calendário do Outlook (Sem descrição adicional)."

    # Processar a data do evento para o formato do Nuubes (mm/dd/aaaa)
    event_deadline = ''
    if event_start_date:
        try:
            event_date = datetime.fromisoformat(event_start_date.replace('Z', '+00:00'))
            event_deadline = event_date.strftime('%m/%d/%Y')
        except Exception as e:
            print(f"DEBUG - Erro ao formatar data: {e}")
            event_deadline = ''

    # Configurações para envio ao Nuubes
    admin_email = 'nuubes@grupofokus.com.br'
    url = 'https://api.nuubes.com/api.occurrence.logic'
    
    # Montagem da descrição final limpa e organizada
    descricao_final = f"Evento criado no calendário por {organizer_email}.\n\n{descricao_limpa}"

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
