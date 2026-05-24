import streamlit as st
import json
import random
import re
import math
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# --- Configuração ---
st.set_page_config(page_title="Cardápio Semanal", layout="wide")

@st.cache_data
def carregar_dados():
    with open('dieta.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def aplicar_substituicoes(texto, lista_frutas, lista_saladas):
    if "Frutas" in texto and lista_frutas:
        texto = texto.replace("Frutas", random.choice(lista_frutas))
    if "Fruta" in texto and lista_frutas:
        texto = texto.replace("Fruta", random.choice(lista_frutas))
    if "Salada" in texto and lista_saladas:
        texto = texto.replace("Salada", random.choice(lista_saladas))
    return texto

# --- Adicionar categoria aos alimentos ---
def obter_categoria(item):
    if any(x in item for x in ["Filé", "Patinho", "Salmão", "Ovos", "Carne", "Tilápia"]): return "Proteínas"
    if any(x in item for x in ["Arroz", "Feijão", "Tapioca", "Aveia", "Cuscuz", "Macarrão", "Pão", "Rap10", "Grão"]): return "Mercearia"
    if any(x in item for x in ["Maçã", "Banana", "Mamão", "Morango", "Alface", "Tomate", "Cenoura", "Mandioca", "Batata"]): return "Hortifruti"
    if any(x in item for x in ["Queijo", "Requeijão", "Ricota"]): return "Laticínios"
    return "Outros"

# --- Lógica da Lista de Compras ---
def gerar_lista_compras(cronograma, dados):
    compras = {}
    for row in cronograma:
        prato = row['Item']
        if ":" in prato:
            prato = prato.split(":", 1)[1]
            
        ingredientes = [i.strip() for i in prato.split("+")]
        
        for ing in ingredientes:
            ing_lower = ing.lower()
            
            if "arroz" in ing_lower:
                compras["Arroz branco (Pacote 5kg)"] = 1
            elif "feijão" in ing_lower or "feijao" in ing_lower:
                compras["Feijão (Pacote 1kg)"] = 1
            elif "ovo" in ing_lower:
                match_ovo = re.search(r'\((\d+)\s*un', ing_lower)
                qtd_ovo = int(match_ovo.group(1)) if match_ovo else 2
                compras["Ovos (Unidades)"] = compras.get("Ovos (Unidades)", 0) + qtd_ovo
            elif "frango" in ing_lower and not "hamburger" in ing_lower:
                compras["Filé de Frango (Kg)"] = compras.get("Filé de Frango (Kg)", 0.0) + 0.15
            elif "patinho" in ing_lower or "carne" in ing_lower:
                compras["Patinho/Carne Magra (Kg)"] = compras.get("Patinho/Carne Magra (Kg)", 0.0) + 0.15
            elif "tilápia" in ing_lower or "tilapia" in ing_lower:
                compras["Filé de tilápia (Kg)"] = compras.get("Filé de tilápia (Kg)", 0.0) + 0.20
            elif "salmão" in ing_lower or "salmao" in ing_lower:
                compras["Salmão (Kg)"] = compras.get("Salmão (Kg)", 0.0) + 0.20
            elif "mignon" in ing_lower:
                compras["Filé-mignon (Kg)"] = compras.get("Filé-mignon (Kg)", 0.0) + 0.15
            elif "tapioca" in ing_lower:
                compras["Goma de Tapioca (Pacote 500g)"] = compras.get("Goma de Tapioca (Pacote 500g)", 0) + 1
            else:
                nome_limpo = re.sub(r'\(.*?\)', '', ing).strip()
                match = re.search(r'^(\d+)\s*(.*)', nome_limpo)
                if match:
                    qtd = int(match.group(1))
                    nome_base = match.group(2).strip()
                else:
                    qtd = 1
                    nome_base = nome_limpo
                    
                encontrou_fruta = False
                for f in dados.get('frutas_disponiveis', []):
                    if f.lower() in nome_base.lower():
                        nome_base = f  
                        encontrou_fruta = True
                        break
                        
                if not encontrou_fruta and nome_base.endswith('s') and len(nome_base) > 3:
                    if not nome_base.lower() in ["flocos", "minas"]: 
                        nome_base = nome_base[:-1]

                nome_final = nome_base.capitalize()
                compras[nome_final] = compras.get(nome_final, 0) + qtd

    lista_final = {}
    for item, qtd in compras.items():
        if item == "Ovos (Unidades)":
            lista_final["Ovos (Dúzia)"] = math.ceil(qtd / 12)
        elif "(Kg)" in item:
            lista_final[item] = round(qtd, 1)
        elif "Goma de Tapioca" in item:
            lista_final[item] = math.ceil(qtd / 7)
        else:
            lista_final[item] = qtd
            
    return lista_final

# --- Funções de Geração de PDF ---
def gerar_pdf_cronograma(cronograma_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Cardapio Semanal", ln=True, align='C')
    df = pd.DataFrame(cronograma_data)
    if not df.empty:
        for data in df['Data'].unique():
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(200, 200, 200)
            pdf.cell(0, 10, data, ln=True, fill=True)
            pdf.set_font("Arial", '', 10)
            for _, row in df[df['Data'] == data].iterrows():
                pdf.multi_cell(0, 7, f"{row['Refeição']}: {row['Item']}".encode('latin-1', 'replace').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

def gerar_pdf_compras(cronograma_data, dados_json):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, "LISTA DE COMPRAS", ln=True, align='C')
    pdf.ln(5)
    
    lista_compras = gerar_lista_compras(cronograma_data, dados_json)
    
    # Organiza os itens por categoria
    categorias_map = {}
    for item, qtd in lista_compras.items():
        cat = obter_categoria(item)
        if cat not in categorias_map:
            categorias_map[cat] = []
        categorias_map[cat].append((item, qtd))
    
    # Escreve no PDF separando por blocos de categorias
    for cat in sorted(categorias_map.keys()):
        pdf.ln(4)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(230, 240, 255) # Cor de fundo azul bem clara
        pdf.cell(0, 8, f" {cat.upper()}", ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", '', 11)
        for item, qtd in sorted(categorias_map[cat]):
            if "(Kg)" in item or "(Pacote" in item or "(Dúzia)" in item:
                linha = f"   [  ] {qtd} - {item}"
            else:
                linha = f"   [  ] {qtd} un. - {item}"
            pdf.cell(0, 7, linha.encode('latin-1', 'replace').decode('latin-1'), ln=True)
        
    return pdf.output(dest='S').encode('latin-1')

# --- Conexão Inteligente com o Google Sheets ---
@st.cache_data(ttl=10)
def buscar_precos_nuvem():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_planilha = conn.read(spreadsheet=st.secrets["spreadsheet_url"], worksheet="Precos", usecols=[0, 1])
        df_planilha = df_planilha.dropna(subset=['Item'])
        return dict(zip(df_planilha['Item'], df_planilha['Preco']))
    except Exception as e:
        st.warning("⚠️ Não foi possível conectar ao Google Sheets. Usando preços do JSON.")
        return carregar_dados().get('precos_estimados', {})


# --- Interface Principal ---
st.title("🥗 Cardápio Semanal")
dados = carregar_dados()

# --- Configuração de Memória (Session State) ---
if 'escolhas_cardapio' not in st.session_state:
    st.session_state['escolhas_cardapio'] = {}

def salvar_escolha(chave):
    st.session_state['escolhas_cardapio'][chave] = st.session_state[chave]

# --- SIDEBAR: Menu e Configurações ---
st.sidebar.title("🧭 Menu Principal")
menu_selecionado = st.sidebar.radio(
    "",
    ["🗓️ Planejamento Semanal", "🛒 Lista & Custos", "📖 Descrição das Refeições"]
)
st.sidebar.divider()

st.sidebar.subheader("⚙️ Configurações")
num_dias = st.sidebar.slider("Quantos dias deseja planejar?", 7, 31, 7)

st.sidebar.subheader("🍎 Preferências da Semana")
todas_frutas = dados.get('frutas_disponiveis', [])
frutas_selecionadas = st.sidebar.multiselect(
    "Escolha até 3 frutas:",
    options=todas_frutas,
    default=todas_frutas[:3] if len(todas_frutas) >= 3 else todas_frutas,
    max_selections=3
)

if not frutas_selecionadas:
    frutas_selecionadas = todas_frutas

data_hoje = datetime.now()
dias_info = [{"label": (data_hoje + timedelta(days=i)).strftime('%d/%m\n%A').capitalize(), 
              "data_str": (data_hoje + timedelta(days=i)).strftime("%d/%m/%Y")} for i in range(num_dias)]

# ---
