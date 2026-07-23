def processar_envio_nuubes(titulo, descricao, email, data_str, tipo_origem):
    texto_final_desc = limpar_html(descricao)
    event_deadline = formatar_data(data_str)
    
    admin_email = 'nuubes@grupofokus.com.br'
    company_key = 'n1w8wHXbAuE='
    url_occurrence = 'https://api.nuubes.com/api.occurrence.logic'
    
    descricao_final = f"{tipo_origem} de {email}.\n\n{texto_final_desc}"

    data_occurrence = {
        'company.key': company_key,
        'occurrence.summary': titulo or "Sem título",
        'occurrence.description': descricao_final,
        'occurrence.requestor.email': admin_email,
        'occurrence.project.name': 'ANÁLISE DE PROCESSOS',
        'occurrence.occurrenceType.name': 'OS. REUNIÃO INTERNA',
        'occurrence.customer.name': 'GRUPO FOKUS',
        'occurrence.customer.externalCode': 'FOKUS001'
    }

    if event_deadline:
        data_occurrence['occurrence.deadLine'] = event_deadline

    headers = {'User-Agent': 'Nuubes-API-Client', 'Accept': 'text/plain, */*'}
    
    response = requests.post(url_occurrence, data=data_occurrence, headers=headers, timeout=30)
    print(f"DEBUG - Resposta Nuubes Status: {response.status_code}, Body: {response.text}")
    
    return response.text.strip(), response.status_code
