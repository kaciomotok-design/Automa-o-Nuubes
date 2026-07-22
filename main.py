from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()


# Modelo dos dados que vamos receber do Outlook / Power Automate
class EventoCalendario(BaseModel):
  event_title: str
  event_description: str = "Sem descrição"
  organizer_email: str
  event_start_date: str


@app.post("/criar-tarefa")
def receber_evento(evento: EventoCalendario):
  print(f"\nRecebido evento: {evento.event_title} de {evento.organizer_email}")

  # 1. Processar a data do evento para o formato mm/dd/yyyy exigido pelo Nuubes
  event_deadline = ""
  if evento.event_start_date:
    try:
      event_date = datetime.fromisoformat(
          evento.event_start_date.replace("Z", "+00:00")
      )
      event_deadline = event_date.strftime("%m/%d/%Y")
    except Exception as e:
      print(f"Erro ao formatar data: {e}")
      event_deadline = ""

  # 2. Configurações da API do Nuubes
  admin_email = "nuubes@grupofokus.com.br"
  url = "https://api.nuubes.com/api.occurrence.logic"

  # 3. Montar os parâmetros do POST
  data = {
      "company.key": "n1w8wHXbAuE=",
      "occurrence.summary": evento.event_title,
      "occurrence.description": (
          f"Evento criado no calendário por {evento.organizer_email}:"
          f" {evento.event_description}"
      ),
      "occurrence.requestor.email": admin_email,
      "occurrence.project.name": "ANÁLISE DE PROCESSOS",
      "occurrence.occurrenceType.name": "OS. REUNIÃO INTERNA",
      "occurrence.customer.name": "GRUPO FOKUS",
      "occurrence.customer.externalCode": "FOKUS001",
  }

  if event_deadline:
    data["occurrence.deadLine"] = event_deadline

  headers = {
      "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
      "User-Agent": "Nuubes-API-Client",
      "Accept": "text/plain, */*",
  }

  # 4. Enviar a requisição POST para o Nuubes
  try:
    response = requests.post(url, data=data, headers=headers, timeout=30)
    print(f"Status Nuubes: {response.status_code} - Resposta: {response.text}")

    if response.status_code == 200:
      return {
          "status": "sucesso",
          "nuubes_response": response.text.strip(),
      }
    else:
      raise HTTPException(
          status_code=response.status_code,
          detail="Erro ao integrar com o Nuubes",
      )
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))