import json
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import base64
import numpy as np
import argparse

from elasticsearch import Elasticsearch, helpers

# 3. Elasticsearch setup
es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])
index_name = 'teses'

mapping = {
    'mappings': {
        'properties': {
            'tese': {'type': 'text'},
            'numero_processo': {'type': 'text'},
            'nome_relator': {'type': 'text'},
            'data_julgamento': {'type': 'text'},
            'acolhida': {'type': 'boolean'},
            'justificativa': {'type': 'text'},
            'resumo': {'type': 'text'},
            'palavras_chave': {
                'type': 'text',
                'fields': {
                    'keyword': {'type': 'keyword'}
                }
            }
        }
    }
}

if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body=mapping)

# Defina sua chave de API
load_dotenv()
api_key = os.getenv('API_KEY')
client = OpenAI(api_key=api_key)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--texto', type=str, help='texto processado')

    args = parser.parse_args()

    texto = args.texto
    print(f"texto enviado foi: {texto}")
    col_teses = []

    service = Service('/opt/homebrew/bin/chromedriver')
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')

    driver = webdriver.Chrome(service=service, options=options)

    try:
        # Abrir a página desejada
        driver.get('https://webapp.tjro.jus.br/juris/consulta/consultaJuris.jsf')

        # Esperar até que o campo de input esteja presente
        wait = WebDriverWait(driver, 10)
        input_field = wait.until(EC.presence_of_element_located((By.ID, 'frmJuris:formConsultaJuris:iPesquisa')))

        # Limpar o campo de input e adicionar o texto desejado
        input_field.clear()
        input_field.send_keys(texto)

        # Encontrar o botão pelo ID
        submit_button = driver.find_element(By.ID, 'frmJuris:formConsultaJuris:btPesquisar')
        print(submit_button)
        # Clicar no botão
        submit_button.click()

        # Esperar por até 10 segundos para a nova página carregar
        wait.until(EC.presence_of_element_located((By.ID, 'frmJuris:formDetalhesJuris:painelResultadosPesquisa_data')))
        tbody = driver.find_element(By.ID, 'frmJuris:formDetalhesJuris:painelResultadosPesquisa_data')

        links = driver.find_elements(By.CLASS_NAME, 'botaoLink')

        # Encontrar o input dentro da linha
        links[0].click()
        # Esperar até que o novo conteúdo esteja presente (ajuste conforme necessário)
        wait.until(EC.presence_of_element_located((By.ID, 'frmJuris:formDetalhesJuris:painelProcessosAcordaos_data')))
        tbody_interno = driver.find_element(By.ID, 'frmJuris:formDetalhesJuris:painelProcessosAcordaos_data')
        trs_links = tbody_interno.find_elements(By.TAG_NAME, 'tr')
        print(f"it found {len(trs_links)} links")

        for index, tr in enumerate(trs_links):
            try:
                # Click on the link using Ctrl+click to force it to open in a new tab
                link = tr.find_element(By.NAME, f"frmJuris:formDetalhesJuris:painelProcessosAcordaos:{index}:j_idt62")
                link.click()
                # Wait for the new tab to open
                WebDriverWait(driver, 30).until(lambda d: len(d.window_handles) > 1)

                # Switch to the new tab
                new_tab = driver.window_handles[1]
                driver.switch_to.window(new_tab)

                # Now you can interact with the new tab
                # print(driver.find_element(By.CLASS_NAME, "colDocTxt").text)

                # driver.find_element(By.ID, "frmJuris:tvTabs:otDadosDocumento")
                new_tab_page_source = driver.page_source

                # Parse the page source with BeautifulSoup
                soup = BeautifulSoup(new_tab_page_source, 'html.parser')
                texto = soup.find(id="divDtDocumento").text

                completion = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system",
                         "content": """
                                     você é defensor público do estado de rondonia. especalista em análise de dados. especialista em 
                                     direito e teses jurídicas. Analise todas as nuances do julgado a seguir e traga de forma detalhada 
                                     as teses da defesa, se foi acolhida ou não e a justificativa com base na decisão analisada. 
                                     faça um objeto json com assunto do caso, teses da defesa, se foi acolhida ou não, justificativa, 
                                     numero do processo, nome do relator, data do julgamento, resumo do caso. Tambem quero que voce
                                     gere um campo chamado palavras_chave, onde voce vai sintetizar todo o conteudo da tese em questão em 5 keywords
                                     que mais resumam essa tese, para que no futuro eu possa pesquisar por essas keywords e trazer essa tese.
                                     
                                     Eu quero que o retorno seja EXATAMENTE do Formato do json abaixo. Eu não quero nenhum outro texto além do formato json abaixo:
                                     
                                    Exemplo de resposta que espero: 
                                    {"teses": [
                                        {
                                        "tese": "TESE_AQUI",
                                        "numero_processo": "NUMERO DO PROCESSO AQUI",
                                        "nome_relator": "COLOCAR NOME DO RELATOR AQUI",
                                        "data_julgamento": "COLOCAR DATA DO JULGAMENTO DA TESE",
                                        "acolhida": true/false,
                                        "justificativa": "JUSTIFICATIVA",
                                        "resumo": "RESUMO_AQUI",
                                        "palavras_chave": ["UMA KEYWORD", "DUAS KEYWORDS", "TRES KEYWORDS", "QUATRO KEYWORD", "CINCO KEYWORD"]
                                        }
                                    ]
                                    
                                     """},
                        {"role": "user", "content": texto}
                    ]
                )

                resposta = completion.choices[0].message.content.replace("```", "").replace("json", "")
                resposta_json = json.loads(resposta)

                teses = resposta_json["teses"]

                actions = []
                doc_ids = []
                doc_embeddings = []

                for tese in teses:

                    # Create document for indexing`
                    doc = {
                        'tese': tese['tese'],
                        'acolhida': tese['acolhida'],
                        'justificativa': tese['justificativa'],
                        'resumo': tese['resumo'],
                        'numero_processo': tese['numero_processo'],
                        'nome_relator': tese['nome_relator'],
                        'data_julgamento': tese['data_julgamento'],
                        'palavras_chave': tese['palavras_chave']
                    }
                    actions.append({
                        '_index': index_name,
                        '_source': doc
                    })

                    doc_ids.append(index)

                # Index in Elasticsearch
                helpers.bulk(es, actions)



                col_teses.extend(teses)

                driver.close()
                # Switch back to the original tab
                driver.switch_to.window(driver.window_handles[0])
            except Exception as e:
                print(f"Error {e}")

        df = pd.DataFrame(col_teses)

        df.to_csv('teses.csv', index=False)

    finally:
        driver.quit()
