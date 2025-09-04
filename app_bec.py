import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
from io import BytesIO

# --- CONFIGURAÇÕES GLOBAIS ---
URL_PESQUISA = 'https://www.bec.sp.gov.br/BEC_Catalogo_ui/CatalogoPesquisa3.aspx'
TEMPO_ESPERA_MAXIMO = 30
PAUSA_MINIMA = 1
PAUSA_MAXIMA = 2

# --- FUNÇÃO CONFIGURAR_DRIVER (VERSÃO OTIMIZADA PARA MEMÓRIA) ---
@st.cache_resource
def configurar_driver():
    """
    Configura o WebDriver para rodar no Streamlit Cloud de forma otimizada,
    com argumentos para economizar memória.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    
    # --- NOVAS OPÇÕES PARA ECONOMIA DE MEMÓRIA ---
    options.add_argument("--disable-extensions") # Desativa extensões
    options.add_argument("--disable-popup-blocking") # Desativa pop-ups
    options.add_argument("--disable-infobars") # Desativa as barras de informação
    options.add_argument("--single-process") # Roda o Chrome em um único processo (grande economia de RAM)
    options.add_argument("--disable-application-cache") # Desativa o cache que pode consumir memória

    # O Streamlit Cloud/Apt-get colocará o chromedriver em um local padrão que o Selenium encontra.
    service = ChromeService()
    
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# A função buscar_dados permanece a mesma
def buscar_dados(driver, codigo):
    """Função de scraping para um único código. Retorna um dicionário."""
    try:
        driver.get(URL_PESQUISA)
        wait = WebDriverWait(driver, TEMPO_ESPERA_MAXIMO)
        input_codigo = wait.until(EC.presence_of_element_located((By.ID, "tbCodigoItem")))
        input_codigo.clear()
        input_codigo.send_keys(codigo)
        driver.find_element(By.ID, "ImageButton1").click()
        link_resultado = wait.until(
            EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_gvResultadoPesquisa_lbTituloItem_0"))
        )
        link_resultado.click()
        elemento_descricao = wait.until(
            EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lbCaracteristicaCompleta"))
        )
        descricao = elemento_descricao.text.strip()
        natureza_despesa = "Não encontrada"
        try:
            elemento_nd = wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_lbNdInfo")))
            natureza_despesa = elemento_nd.get_attribute('innerHTML').replace('<br>', ' ').strip()
        except TimeoutException:
            pass
        return {"status": "sucesso", "descricao": descricao, "natureza_despesa": natureza_despesa}
    except TimeoutException:
        return {"status": "erro", "mensagem": "Item não encontrado ou página demorou a responder (Timeout)."}
    except Exception as e:
        return {"status": "erro", "mensagem": f"Erro inesperado: {e}"}

# --- Interface do Aplicativo Web (sem alterações) ---
st.set_page_config(page_title="Buscador de Itens BEC", layout="centered")
st.title("🤖 Buscador de Itens na BEC")
st.markdown("Faça o upload de um arquivo `.txt` com os códigos dos itens (um por linha) para iniciar a busca.")

uploaded_file = st.file_uploader("Escolha o arquivo de códigos:", type="txt")

if uploaded_file is not None:
    try:
        codigos = [line.decode('utf-8').strip() for line in uploaded_file.readlines() if line.strip()]
        st.success(f"{len(codigos)} códigos carregados com sucesso do arquivo '{uploaded_file.name}'!")
        
        if st.button("🚀 Iniciar Busca Agora"):
            if not codigos:
                st.error("O arquivo está vazio ou não contém códigos válidos.")
            else:
                st.info("Configurando o ambiente... Isso pode levar um minuto.")
                driver = configurar_driver()
                resultados = []
                
                log_area = st.empty()
                progress_bar = st.progress(0)
                
                total_codigos = len(codigos)
                for i, codigo in enumerate(codigos):
                    log_text = f"[{i+1}/{total_codigos}] Processando código: {codigo}"
                    log_area.info(log_text)
                    
                    dados = buscar_dados(driver, codigo)
                    
                    if dados['status'] == 'sucesso':
                        log_area.info(f"  -> Sucesso! {dados['descricao'][:40]}...")
                        resultados.append({'Código': codigo, 'Descrição': dados['descricao'], 'Natureza de Despesa': dados['natureza_despesa']})
                    else:
                        log_area.warning(f"  -> Falha: {dados['mensagem']}")
                        resultados.append({'Código': codigo, 'Descrição': f"ERRO - {dados['mensagem']}", 'Natureza de Despesa': 'Erro'})
                    
                    progress_bar.progress((i + 1) / total_codigos)
                    time.sleep(random.uniform(PAUSA_MINIMA, PAUSA_MAXIMA))

                driver.quit()
                log_area.success("Busca finalizada! O arquivo Excel está pronto para download.")
                
                df_final = pd.DataFrame(resultados)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Resultados')
                
                st.download_button(
                    label="📥 Baixar Resultados em Excel",
                    data=output.getvalue(),
                    file_name=f"resultados_{uploaded_file.name.replace('.txt', '.xlsx')}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")