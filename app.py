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

# ---> O NOVO CÓDIGO CSS ENTRA AQUI:
st.markdown("""
    <style>
        /* Fundo de toda a página em Azul Marinho */
        .stApp {
            background-color: #002B5B; 
        }
        
        /* Todos os textos, títulos e labels em Branco */
        h1, h2, h3, h4, p, li, label, div {
            color: #FFFFFF !important;
        }
        
        /* Ajuste específico para a Sidebar para manter o contraste */
        [data-testid="stSidebar"] {
            background-color: #001f3f; 
        }
        
        /* Ajuste dos inputs e selectboxes */
        .stSelectbox div[data-baseweb="select"] {
            background-color: #001f3f !important;
            color: white !important;
        }
        
        /* Botões */
        div.stButton > button:first-child {
            background-color: #FFFFFF;
            color: #002B5B;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

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

# --- Categorização de Alimentos ---
def obter_categoria(item):
    item_lower = item.lower()
    if any(x in item_lower for x in ["filé", "patinho", "salmão", "carne", "tilápia", "frango", "atum", "peixe", "mignon"]): return "Açougue e Peixaria"
    if any(x in item_lower for x in ["queijo", "requeijão", "ricota", "ovo", "leite", "iogurte", "manteiga"]): return "Laticínios e Ovos"
    if any(x in item_lower for x in ["maçã", "banana", "mamão", "morango", "melão", "melancia", "abacaxi", "kiwi", "tangerina", "pêssego", "uva", "caju", "ameixa", "pêra", "goiaba", "manga", "açai", "açaí", "limão"]): return "Frutas"
    if any(x in item_lower for x in ["alface", "rúcula", "agrião", "espinafre", "couve", "repolho", "acelga", "brócolis"]): return "Verduras (Folhas)"
    if any(x in item_lower for x in ["tomate", "cenoura", "mandioca", "batata", "abobrinha", "cebola", "pepino", "pimentão", "alho", "berinjela", "chuchu"]): return "Legumes e Tubérculos"
    if any(x in item_lower for x in ["arroz", "feijão", "aveia", "cuscuz", "grão", "ervilha", "lentilha", "soja", "milho"]): return "Grãos e Cereais"
    if any(x in item_lower for x in ["tapioca", "macarrão", "pão", "rap10", "massa", "bolo"]): return "Padaria e Massas"
    if any(x in item_lower for x in ["castanha", "amendoim", "amêndoa", "nozes", "chia", "linhaça"]): return "Castanhas e Sementes"
    if any(x in item_lower for x in ["mel", "doce", "geleia", "chocolate", "cacau", "paçoca", "açúcar"]): return "Doces e Ingredientes"
    if any(x in item_lower for x in ["suco", "café", "chá", "água"]): return "Bebidas"
    if any(x in item_lower for x in ["whey", "creatina", "albumina", "suplemento"]): return "Suplementos"
    return "Outros (Mercearia)"

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
            if "arroz" in ing_lower: compras["Arroz branco (Pacote 5kg)"] = 1
            elif "feijão" in ing_lower or "feijao" in ing_lower: compras["Feijão (Pacote 1kg)"] = 1
            elif "ovo" in ing_lower:
                match_ovo = re.search(r'\((\d+)\s*un', ing_lower)
                qtd_ovo = int(match_ovo.group(1)) if match_ovo else 2
                compras["Ovos (Unidades)"] = compras.get("Ovos (Unidades)", 0) + qtd_ovo
            elif "frango" in ing_lower and not "hamburger" in ing_lower: compras["Filé de Frango (Kg)"] = compras.get("Filé de Frango (Kg)", 0.0) + 0.15
            elif "patinho" in ing_lower or "carne" in ing_lower: compras["Patinho/Carne Magra (Kg)"] = compras.get("Patinho/Carne Magra (Kg)", 0.0) + 0.15
            elif "tilápia" in ing_lower or "tilapia" in ing_lower: compras["Filé de tilápia (Kg)"] = compras.get("Filé de tilápia (Kg)", 0.0) + 0.20
            elif "salmão" in ing_lower or "salmao" in ing_lower: compras["Salmão (Kg)"] = compras.get("Salmão (Kg)", 0.0) + 0.20
            elif "mignon" in ing_lower: compras["Filé-mignon (Kg)"] = compras.get("Filé-mignon (Kg)", 0.0) + 0.15
            elif "tapioca" in ing_lower: compras["Goma de Tapioca (Pacote 500g)"] = compras.get("Goma de Tapioca (Pacote 500g)", 0) + 1
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
        if item == "Ovos (Unidades)": lista_final["Ovos (Dúzia)"] = math.ceil(qtd / 12)
        elif "(Kg)" in item: lista_final[item] = round(qtd, 1)
        elif "Goma de Tapioca" in item: lista_final[item] = math.ceil(qtd / 7)
        else: lista_final[item] = qtd
            
    return lista_final

# --- Funções de Geração de PDF ---
def gerar_pdf_cronograma(cronograma_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, "CRONOGRAMA SEMANAL", ln=True, align='C')
    pdf.ln(5)
    
    df = pd.DataFrame(cronograma_data)
    if not df.empty:
        # Itera sobre os dias únicos já formatados com Data e Dia da Semana
        for label in df['LabelPDF'].unique():
            pdf.ln(4)
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(230, 240, 255) # Azul claro padronizado
            pdf.cell(0, 8, f" {label.upper()}", ln=True, fill=True)
            pdf.ln(2)
            
            pdf.set_font("Arial", '', 11)
            for _, row in df[df['LabelPDF'] == label].iterrows():
                linha = f"   {row['Refeição']}: {row['Item']}"
                pdf.cell(0, 7, linha.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            
    return pdf.output(dest='S').encode('latin-1')

def gerar_pdf_compras(cronograma_data, dados_json):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, "LISTA DE COMPRAS", ln=True, align='C')
    pdf.ln(5)
    
    lista_compras = gerar_lista_compras(cronograma_data, dados_json)
    
    categorias_map = {}
    for item, qtd in lista_compras.items():
        cat = obter_categoria(item)
        if cat not in categorias_map:
            categorias_map[cat] = []
        categorias_map[cat].append((item, qtd))
    
    for cat in sorted(categorias_map.keys()):
        pdf.ln(4)
        pdf.set_font("Arial", 'B', 12)
        pdf.set_fill_color(230, 240, 255) # Azul claro padronizado
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
        return carregar_dados().get('precos_estimados', {})


# --- Interface Principal ---
st.title("Sistema de Gestão Alimentar")
dados = carregar_dados()

if 'escolhas_cardapio' not in st.session_state:
    st.session_state['escolhas_cardapio'] = {}

def salvar_escolha(chave):
    st.session_state['escolhas_cardapio'][chave] = st.session_state[chave]

# --- SIDEBAR: Menu e Configurações ---
st.sidebar.title("Menu Principal")
menu_selecionado = st.sidebar.radio(
    "",
    ["Planejamento Semanal", "Lista de Compras e Custos", "Descrição das Refeições"]
)
st.sidebar.divider()

st.sidebar.subheader("Configurações")
num_dias = st.sidebar.slider("Dias planejados:", 7, 31, 7)

st.sidebar.subheader("Preferências")
todas_frutas = dados.get('frutas_disponiveis', [])
frutas_selecionadas = st.sidebar.multiselect(
    "Seleção de Frutas:",
    options=todas_frutas,
    default=todas_frutas[:3] if len(todas_frutas) >= 3 else todas_frutas,
    max_selections=3
)

if not frutas_selecionadas:
    frutas_selecionadas = todas_frutas

# Construção segura dos dias da semana em Português
dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
data_hoje = datetime.now()

dias_info = []
for i in range(num_dias):
    data_alvo = data_hoje + timedelta(days=i)
    data_str = data_alvo.strftime("%d/%m/%Y")
    nome_dia = dias_semana_pt[data_alvo.weekday()]
    dias_info.append({
        "label_interface": f"{data_alvo.strftime('%d/%m')} - {nome_dia}", 
        "data_str": data_str,
        "label_pdf": f"{data_str} - {nome_dia}"
    })

# --- CONSTRUTOR GLOBAL DO CRONOGRAMA ---
cronograma = []
for dia in dias_info:
    for ref in dados['refeicoes']:
        chave_unica = f"{dia['data_str']}_{ref['nome']}"
        
        random.seed(chave_unica)
        opcoes = [aplicar_substituicoes(o['descricao'], frutas_selecionadas, dados.get('saladas_disponiveis', [])) for o in ref['opcoes']]
        random.seed()

        if chave_unica in st.session_state['escolhas_cardapio']:
            item_atual = st.session_state['escolhas_cardapio'][chave_unica]
        else:
            item_atual = opcoes[0]
            st.session_state['escolhas_cardapio'][chave_unica] = item_atual
            
        cronograma.append({
            "Data": dia['data_str'], 
            "LabelPDF": dia['label_pdf'], # Rótulo rico para o PDF
            "Refeição": ref['nome'], 
            "Item": item_atual, 
            "Opcoes": opcoes, 
            "Chave": chave_unica
        })

# --- CONTEÚDO DINÂMICO DA PÁGINA ---

if menu_selecionado == "Planejamento Semanal":
    cols = st.columns(min(num_dias, 7)) 
    for i, dia in enumerate(dias_info):
        col = cols[i % 7]
        with col:
            st.markdown(f"#### <span style='color: #2C3E50;'>{dia['label_interface']}</span>", unsafe_allow_html=True)
            st.divider()
            
            itens_do_dia = [c for c in cronograma if c["Data"] == dia['data_str']]
            
            for prato in itens_do_dia:
                chave = prato["Chave"]
                opcoes = prato["Opcoes"]
                
                try:
                    idx = opcoes.index(prato["Item"])
                except:
                    idx = 0
                    
                st.selectbox(
                    f"{prato['Refeição']}", 
                    opcoes, 
                    index=idx,
                    key=chave,
                    on_change=salvar_escolha,
                    args=(chave,)
                )

elif menu_selecionado == "Lista de Compras e Custos":
    st.subheader("Controle de Custos e Carrinho")
    st.markdown("Acompanhe os itens no carrinho e ajuste os preços unitários conforme a gôndola.")
    
    if cronograma:
        lista_compras = gerar_lista_compras(cronograma, dados)
        precos_base = buscar_precos_nuvem() 
        
        tabela_custos = []
        for item, qtd in sorted(lista_compras.items()):
            preco_unit = precos_base.get(item, 0.0)
            if preco_unit == 0.0:
                for k, v in precos_base.items():
                    if k.lower() == item.lower():
                        preco_unit = float(v)
                        break

            tabela_custos.append({
                "No Carrinho": False, 
                "Categoria": obter_categoria(item), 
                "Item": item,
                "Qtd": qtd,
                "Preço Unit (R$)": float(preco_unit)
            })
            
        df_custos = pd.DataFrame(tabela_custos).sort_values("Categoria")
        
        if not df_custos.empty:
            df_editado = st.data_editor(
                df_custos,
                disabled=["Item", "Qtd", "Categoria"],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "No Carrinho": st.column_config.CheckboxColumn("No Carrinho", default=False),
                    "Preço Unit (R$)": st.column_config.NumberColumn("Preço Unit (R$)", min_value=0.0, format="R$ %.2f")
                }
            )
            
            df_editado['Subtotal'] = df_editado['Qtd'] * df_editado['Preço Unit (R$)']
            valor_total = df_editado['Subtotal'].sum()
            valor_carrinho = df_editado[df_editado['No Carrinho'] == True]['Subtotal'].sum()
            
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"<h3 style='color: #7F8C8D;'>Previsão Total: R$ {valor_total:.2f}</h3>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<h3 style='text-align: right; color: #27AE60;'>Subtotal Carrinho: R$ {valor_carrinho:.2f}</h3>", unsafe_allow_html=True)
            
            st.markdown("---")
            if st.button("Salvar Novos Preços no Banco de Dados"):
                try:
                    novos_precos = precos_base.copy()
                    for idx, row in df_editado.iterrows():
                        novos_precos[row['Item']] = row['Preço Unit (R$)']
                        
                    df_salvar = pd.DataFrame(list(novos_precos.items()), columns=['Item', 'Preco'])
                    
                    with st.spinner("Atualizando banco de dados..."):
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        conn.update(spreadsheet=st.secrets["spreadsheet_url"], worksheet="Precos", data=df_salvar)
                        st.cache_data.clear() 
                        st.success("Sucesso! O banco de dados foi atualizado.")
                except Exception as e:
                    st.error(f"Erro ao salvar na nuvem: {e}")

elif menu_selecionado == "Descrição das Refeições":
    st.subheader("Detalhamento Nutricional e Substituições")
    for ref in dados['refeicoes']:
        horario_str = f" às {ref['horario']}" if 'horario' in ref else ""
        with st.expander(f"{ref['nome']}{horario_str}", expanded=True):
            for o in ref['opcoes']:
                st.markdown(f" * {o['descricao']}")

# --- Exportação ---
st.sidebar.markdown("---")
st.sidebar.subheader("Exportação (PDF)")
st.sidebar.download_button(label="Baixar Cronograma", data=gerar_pdf_cronograma(cronograma), file_name="cronograma.pdf", mime="application/pdf")
st.sidebar.download_button(label="Baixar Lista de Compras", data=gerar_pdf_compras(cronograma, dados), file_name="compras.pdf", mime="application/pdf")
