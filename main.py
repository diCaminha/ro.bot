import json
import os.path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

import pandas as pd
import os

# Defina sua chave de API
load_dotenv()
api_key = os.getenv('API_KEY')
client = OpenAI(api_key=api_key)

if __name__ == '__main__':

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
        input_field.send_keys('roubo qualificado')

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
                                     informações adicionais, resumo do caso. No formato:

                                    {"teses": [
                                        {
                                        "tese": "TESE_AQUI",
                                        "acolhida": true/false,
                                        "justificativa": "JUSTIFICATIVA",
                                        "infoadd": "INFO_ADICIONAL_AQUI",
                                        "resumo": "RESUMO_AQUI"
                                        },
                                        {
                                        "tese": "TESE_AQUI",
                                        "acolhida": true/false,
                                        "justificativa": "JUSTIFICATIVA",
                                        "infoadd": "INFO_ADICIONAL_AQUI",
                                        "resumo": "RESUMO_AQUI"
                                        }
                                    ]
                                     """},
                        {"role": "user", "content": texto}
                    ]
                )

                resposta = completion.choices[0].message.content.replace("```", "").replace("json", "")
                resposta_json = json.loads(resposta)

                teses = resposta_json["teses"]

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
