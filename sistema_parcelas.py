
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import os

# --- Config ---
SALES_FILE = "sales.csv"
PARCELS_FILE = "parcels.csv"
DAILY_FINE = 3.90  # valor fixo por dia de atraso (moeda local)

st.set_page_config(page_title="Sistema de Parcelamento - Bestcell", layout="wide")

# --- Helpers ---
def ensure_files():
    if not os.path.exists(SALES_FILE):
        df = pd.DataFrame(columns=[
            "sale_id","cliente","aparelho_modelo","aparelho_marca",
            "valor_entrada","num_parcelas","valor_parcela","data_venda","created_at"
        ])
        df.to_csv(SALES_FILE, index=False)
    if not os.path.exists(PARCELS_FILE):
        df = pd.DataFrame(columns=[
            "sale_id","cliente","aparelho_modelo","aparelho_marca",
            "parcela_num","valor_parcela","vencimento","status","dias_atraso","juros","data_pagamento"
        ])
        df.to_csv(PARCELS_FILE, index=False)

def load_sales():
    return pd.read_csv(SALES_FILE, parse_dates=["data_venda","created_at"])

def load_parcels():
    return pd.read_csv(PARCELS_FILE, parse_dates=["vencimento","data_pagamento"])

def save_sales(df):
    df.to_csv(SALES_FILE, index=False)

def save_parcels(df):
    df.to_csv(PARCELS_FILE, index=False)

def add_months_safe(orig_date, months):
    # preserva o dia quando possível; ajusta para o último dia do mês quando necessário
    return (orig_date + relativedelta(months=months))

def generate_parcels_from_sale(sale_row):
    parcels = []
    sale_id = sale_row["sale_id"]
    cliente = sale_row["cliente"]
    modelo = sale_row["aparelho_modelo"]
    marca = sale_row["aparelho_marca"]
    valor_parcela = float(sale_row["valor_parcela"])
    num = int(sale_row["num_parcelas"])
    data_venda = pd.to_datetime(sale_row["data_venda"]).date()
    for i in range(1, num+1):
        venc = add_months_safe(data_venda, i)
        parcels.append({
            "sale_id": sale_id,
            "cliente": cliente,
            "aparelho_modelo": modelo,
            "aparelho_marca": marca,
            "parcela_num": i,
            "valor_parcela": round(valor_parcela, 2),
            "vencimento": pd.to_datetime(venc),
            "status": "Pendente",
            "dias_atraso": 0,
            "juros": 0.0,
            "data_pagamento": pd.NaT
        })
    return parcels

def recalc_overdue_and_juros(parcels_df):
    today = pd.to_datetime(date.today())
    if parcels_df.empty:
        return parcels_df
    parcels_df["vencimento"] = pd.to_datetime(parcels_df["vencimento"]).dt.normalize()
    parcels_df["data_pagamento"] = pd.to_datetime(parcels_df["data_pagamento"])
    # calcular dias em atraso apenas para parcelas pendentes
    def calc_row(r):
        if r["status"] == "Pago" or pd.notna(r["data_pagamento"]):
            r["dias_atraso"] = 0
            r["juros"] = 0.0
        else:
            delta = (today - r["vencimento"]).days
            dias = delta if delta > 0 else 0
            r["dias_atraso"] = int(dias)
            r["juros"] = round(dias * DAILY_FINE, 2)
            # Atualiza status se vencida
            if dias > 0:
                r["status"] = "Atrasada"
            else:
                r["status"] = "Pendente"
        return r
    parcels_df = parcels_df.apply(calc_row, axis=1)
    return parcels_df

def currency(v):
    try:
        return f"R$ {float(v):,.2f}"
    except:
        return v

# --- Inicialização ---
ensure_files()
sales_df = load_sales()
parcels_df = load_parcels()
parcels_df = recalc_overdue_and_juros(parcels_df)
save_parcels(parcels_df)

# --- Layout ---
st.title("Sistema de Parcelamento de Vendas — Bestcell")
tabs = st.tabs(["🧾 Vendas", "💰 Parcelas", "📊 Relatórios"])

# -------- VENDAS TAB --------
with tabs[0]:
    st.header("Cadastro de Venda")
    with st.form("cadastro_venda", clear_on_submit=True):
        col1, col2 = st.columns(2)
        cliente = col1.text_input("Cliente", max_chars=100)
        aparelho_modelo = col1.text_input("Aparelho - Modelo", max_chars=100)
        aparelho_marca = col2.text_input("Aparelho - Marca", max_chars=100)
        valor_entrada = col1.number_input("Valor Entrada (R$)", min_value=0.0, format="%.2f")
        num_parcelas = col2.number_input("Número de parcelas", min_value=1, step=1, value=1)
        valor_parcela = col1.number_input("Valor da parcela (R$)", min_value=0.0, format="%.2f")
        data_venda = col2.date_input("Data da venda", value=date.today())
        submit = st.form_submit_button("Salvar venda")
        if submit:
            # gerar sale_id simples
            sale_id = int(pd.Timestamp.utcnow().timestamp() * 1000)
            new_sale = {
                "sale_id": sale_id,
                "cliente": cliente,
                "aparelho_modelo": aparelho_modelo,
                "aparelho_marca": aparelho_marca,
                "valor_entrada": float(valor_entrada),
                "num_parcelas": int(num_parcelas),
                "valor_parcela": float(valor_parcela),
                "data_venda": pd.to_datetime(data_venda),
                "created_at": pd.to_datetime(datetime.utcnow())
            }
            sales_df = sales_df.append(new_sale, ignore_index=True)
            save_sales(sales_df)
            # gerar parcelas
            new_parcels = generate_parcels_from_sale(new_sale)
            parcels_df = parcels_df.append(new_parcels, ignore_index=True)
            parcels_df = recalc_overdue_and_juros(parcels_df)
            save_parcels(parcels_df)
            st.success("Venda e parcelas geradas com sucesso!")
            st.experimental_rerun()

    st.markdown("---")
    st.subheader("Vendas cadastradas")
    if sales_df.empty:
        st.info("Ainda não há vendas registradas.")
    else:
        display_sales = sales_df.copy()
        display_sales["valor_entrada"] = display_sales["valor_entrada"].map(currency)
        display_sales["valor_parcela"] = display_sales["valor_parcela"].map(currency)
        display_sales["data_venda"] = pd.to_datetime(display_sales["data_venda"]).dt.date
        st.dataframe(display_sales.sort_values("created_at", ascending=False))

# -------- PARCELAS TAB --------
with tabs[1]:
    st.header("Controle de Parcelas")
    # filtros rápidos
    colf1, colf2, colf3 = st.columns([2,2,1])
    cliente_filter = colf1.text_input("Filtrar por cliente")
    status_filter = colf2.selectbox("Filtrar por status", options=["Todos","Pendente","Pago","Atrasada"], index=0)
    show_only_overdue = colf3.checkbox("Mostrar apenas atrasadas", value=False)

    dfp = parcels_df.copy()
    if cliente_filter:
        dfp = dfp[dfp["cliente"].str.contains(cliente_filter, case=False, na=False)]
    if status_filter != "Todos":
        dfp = dfp[dfp["status"] == status_filter]
    if show_only_overdue:
        dfp = dfp[dfp["status"] == "Atrasada"]

    # exibir tabela principal
    if dfp.empty:
        st.info("Nenhuma parcela encontrada com os filtros selecionados.")
    else:
        dfp_display = dfp.copy()
        dfp_display["vencimento"] = pd.to_datetime(dfp_display["vencimento"]).dt.date
        dfp_display["valor_parcela"] = dfp_display["valor_parcela"].map(currency)
        dfp_display["juros"] = dfp_display["juros"].map(currency)
        dfp_display["data_pagamento"] = pd.to_datetime(dfp_display["data_pagamento"]).dt.date
        st.dataframe(dfp_display.sort_values(["vencimento","cliente"]))

        st.markdown("### Ações rápidas")
        # permitir marcar parcelas como pagas com seleção de linhas (usa sale_id + parcela_num como chave)
        select_sale = st.selectbox("Selecione sale_id", options=sorted(dfp["sale_id"].unique()))
        select_parc = st.selectbox("Parcela número", options=sorted(dfp[dfp["sale_id"]==select_sale]["parcela_num"].unique()))
        if st.button("Marcar como Paga"):
            mask = (parcels_df["sale_id"]==select_sale) & (parcels_df["parcela_num"]==select_parc)
            parcels_df.loc[mask, "status"] = "Pago"
            parcels_df.loc[mask, "data_pagamento"] = pd.to_datetime(date.today())
            parcels_df.loc[mask, "dias_atraso"] = 0
            parcels_df.loc[mask, "juros"] = 0.0
            save_parcels(parcels_df)
            st.success("Parcela marcada como Paga.")
            st.experimental_rerun()

# -------- RELATÓRIOS TAB (placeholder) --------
with tabs[2]:
    st.header("Relatórios (em breve)")
    st.info("A aba de relatórios já está reservada na interface. Implementaremos gráficos e métricas na próxima etapa.")

# Footer / resumo rápido
st.sidebar.header("Resumo rápido")
total_vendido = sales_df["valor_entrada"].sum() + (sales_df["valor_parcela"] * sales_df["num_parcelas"]).sum() if not sales_df.empty else 0.0
total_recebido = parcels_df[parcels_df["status"]=="Pago"]["valor_parcela"].sum() if not parcels_df.empty else 0.0
total_pendente = parcels_df[parcels_df["status"]!="Pago"]["valor_parcela"].sum() if not parcels_df.empty else 0.0
total_juros = parcels_df["juros"].sum() if not parcels_df.empty else 0.0

st.sidebar.metric("Total vendido (estimado)", currency(total_vendido))
st.sidebar.metric("Total recebido", currency(total_recebido))
st.sidebar.metric("Total pendente", currency(total_pendente))
st.sidebar.metric("Total juros (acumulado)", currency(total_juros))

st.sidebar.markdown("---")
st.sidebar.caption("Observações:\n- Juros fixos = R$ 3,90 por dia de atraso (valor separado do valor da parcela).\n- Vencimentos calculados como o mesmo dia da venda nos meses subsequentes.\n- Marque manualmente parcelas como Paga na aba 'Parcelas'.")
