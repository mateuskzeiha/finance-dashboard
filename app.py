import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from pathlib import Path
import hashlib

# ==========================
# CONFIG BÁSICA
# ==========================

st.set_page_config(
    page_title="Dashboard Financeiro Pessoal",
    page_icon="💰",
    layout="wide"
)

DATA_ROOT = Path("financas_data")  # raiz, depois criamos subpastas por usuário

COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"
BRAPI_URL = "https://brapi.dev/api/quote"


# ==========================
# LOGIN / USUÁRIOS
# ==========================

# Usuários "hardcoded" só pra perfil. NÃO use senha real aqui.
# Você pode adicionar outros depois.
# Exemplo: "empresa": "sha256(5678)"
USERS = {
    "mateus": hashlib.sha256("1234".encode()).hexdigest(),
}

def check_credentials(username: str, password: str) -> bool:
    if username not in USERS:
        return False
    hash_pass = hashlib.sha256(password.encode()).hexdigest()
    return hash_pass == USERS[username]


def login_page():
    st.title("🔐 Login – Dashboard Financeiro")

    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if check_credentials(username, password):
            st.session_state["auth"] = True
            st.session_state["user"] = username
            st.success("Login realizado com sucesso.")
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha inválidos.")


def require_login():
    if "auth" not in st.session_state or not st.session_state["auth"]:
        login_page()
        st.stop()


def get_user_dir() -> Path:
    """Pasta de dados do usuário logado."""
    user = st.session_state.get("user", "anon")
    user_dir = DATA_ROOT / user
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_tx_file() -> Path:
    return get_user_dir() / "transactions.csv"


def get_assets_file() -> Path:
    return get_user_dir() / "assets.csv"


# ==========================
# FUNÇÕES DE DADOS
# ==========================

def load_transactions():
    tx_file = get_tx_file()
    if tx_file.exists():
        df = pd.read_csv(tx_file)
        df["date"] = pd.to_datetime(df["date"])
        return df
    else:
        return pd.DataFrame(columns=["date", "type", "category", "description", "amount"])


def save_transactions(df: pd.DataFrame):
    tx_file = get_tx_file()
    df.to_csv(tx_file, index=False)


def load_assets():
    assets_file = get_assets_file()
    if assets_file.exists():
        return pd.read_csv(assets_file)
    else:
        return pd.DataFrame(columns=[
            "asset_type",        # Cripto, Ação, FII, Imóvel, Carro, Colecionável, Outro
            "category",          # opcional
            "name",              # nome descritivo
            "symbol",            # BTC, PETR4, HGLG11...
            "api_source",        # COINGECKO, BRAPI, MANUAL
            "api_id",            # id no CoinGecko ou ticker
            "quantity",          # quantidade
            "manual_price_brl"   # preço unitário manual, se não tiver API
        ])


def save_assets(df: pd.DataFrame):
    assets_file = get_assets_file()
    df.to_csv(assets_file, index=False)


def fetch_crypto_prices_br(api_ids):
    if not api_ids:
        return {}
    params = {
        "ids": ",".join(api_ids),
        "vs_currencies": "brl",
    }
    try:
        resp = requests.get(COINGECKO_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {k: v.get("brl", 0.0) for k, v in data.items()}
    except Exception as e:
        st.warning(f"Erro ao buscar preços na CoinGecko: {e}")
        return {}


def fetch_brapi_prices(symbols):
    prices = {}
    for sym in symbols:
        try:
            url = f"{BRAPI_URL}/{sym}"
            params = {
                "range": "1d",
                "interval": "1d",
                "fundamental": "false",
                "dividends": "false"
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                prices[sym] = results[0].get("regularMarketPrice", 0.0)
        except Exception as e:
            st.warning(f"Erro ao buscar {sym} na Brapi: {e}")
    return prices


def compute_assets_values(df_assets: pd.DataFrame) -> pd.DataFrame:
    if df_assets.empty:
        df = df_assets.copy()
        df["current_price_brl"] = 0.0
        df["value_brl"] = 0.0
        return df

    df = df_assets.copy()
    df["quantity"] = df["quantity"].fillna(0.0)
    df["manual_price_brl"] = df["manual_price_brl"].fillna(0.0)
    df["current_price_brl"] = 0.0

    # Cripto – CoinGecko
    mask_crypto = df["api_source"] == "COINGECKO"
    crypto_ids = df.loc[mask_crypto, "api_id"].dropna().unique().tolist()
    crypto_prices = fetch_crypto_prices_br(crypto_ids)
    if crypto_prices:
        df.loc[mask_crypto, "current_price_brl"] = df.loc[mask_crypto, "api_id"].map(crypto_prices).fillna(0.0)

    # Ações/FIIs – Brapi
    mask_brapi = df["api_source"] == "BRAPI"
    symbols = df.loc[mask_brapi, "api_id"].dropna().unique().tolist()
    stock_prices = fetch_brapi_prices(symbols)
    if stock_prices:
        df.loc[mask_brapi, "current_price_brl"] = df.loc[mask_brapi, "api_id"].map(stock_prices).fillna(0.0)

    # MANUAL
    mask_manual = df["api_source"] == "MANUAL"
    df.loc[mask_manual, "current_price_brl"] = df.loc[mask_manual, "manual_price_brl"]

    df["value_brl"] = df["current_price_brl"] * df["quantity"].clip(lower=0)

    return df


def compute_monthly_summary(df_tx: pd.DataFrame):
    if df_tx.empty:
        return pd.DataFrame()

    df = df_tx.copy()
    df["year_month"] = df["date"].dt.to_period("M").astype(str)

    summary = df.groupby("year_month")["amount"].agg(total="sum").reset_index()

    income = df[df["amount"] > 0].groupby("year_month")["amount"].sum()
    expense = df[df["amount"] < 0].groupby("year_month")["amount"].sum()

    summary["income"] = summary["year_month"].map(income).fillna(0.0)
    summary["expense"] = summary["year_month"].map(expense).fillna(0.0).abs()
    summary = summary.sort_values("year_month")
    summary["cumulative_balance"] = summary["total"].cumsum()

    return summary


# ==========================
# PÁGINAS
# ==========================

def page_dashboard():
    st.header(f"📊 Dashboard financeiro – {st.session_state.get('user', '')}")

    df_tx = load_transactions()
    df_assets = load_assets()
    df_assets_val = compute_assets_values(df_assets)

    summary = compute_monthly_summary(df_tx)

    cash_balance = summary["cumulative_balance"].iloc[-1] if not summary.empty else 0.0
    total_assets = df_assets_val["value_brl"].sum() if not df_assets_val.empty else 0.0
    net_worth = cash_balance + total_assets

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Saldo em caixa (receitas – despesas)",
        f"R$ {cash_balance:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    col2.metric(
        "Patrimônio (investimentos + bens)",
        f"R$ {total_assets:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    col3.metric(
        "Patrimônio líquido (caixa + patrimônio)",
        f"R$ {net_worth:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Lançar receita / despesa", use_container_width=True):
            st.session_state["current_page"] = "Lançamentos"
            st.experimental_rerun()
    with c2:
        if st.button("🏦 Atualizar patrimônio / investimentos", use_container_width=True):
            st.session_state["current_page"] = "Patrimônio / Investimentos"
            st.experimental_rerun()

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Evolução financeira (caixa x patrimônio líquido)")
        if summary.empty:
            st.info("Sem lançamentos ainda. Use a aba de lançamentos para começar.")
        else:
            networth_series = summary["cumulative_balance"] + total_assets
            chart_df = pd.DataFrame({
                "Saldo em caixa": summary["cumulative_balance"].values,
                "Patrimônio líquido (caixa + patrimônio atual)": networth_series.values
            }, index=summary["year_month"])
            st.line_chart(chart_df)

    with col_right:
        st.subheader("Alocação do patrimônio por tipo")
        if df_assets_val.empty or total_assets == 0:
            st.info("Nenhum patrimônio cadastrado ainda.")
        else:
            alloc = df_assets_val.groupby("asset_type")["value_brl"].sum()
            st.bar_chart(alloc)


def page_lancamentos():
    st.header("📒 Lançar receitas e despesas")

    df = load_transactions()

    with st.form("form_lancamento"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Data", value=datetime.today())
            tx_type = st.selectbox("Tipo", ["Receita", "Despesa"])
            category = st.text_input("Categoria", placeholder="Salário, Mercado, Aluguel...")
        with col2:
            description = st.text_input("Descrição", placeholder="Texto livre...")
            amount = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")

        submitted = st.form_submit_button("Registrar lançamento")

    if submitted:
        if amount <= 0:
            st.warning("Valor deve ser maior que zero.")
        else:
            amount_signed = amount if tx_type == "Receita" else -amount
            new_row = {
                "date": pd.to_datetime(date),
                "type": "income" if tx_type == "Receita" else "expense",
                "category": category,
                "description": description,
                "amount": amount_signed,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_transactions(df)
            st.success("Lançamento registrado.")

    st.subheader("Lançamentos recentes")
    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
        df_sorted = df.sort_values("date", ascending=False)
        df_sorted["date_br"] = df_sorted["date"].dt.strftime("%d/%m/%Y")
        st.dataframe(
            df_sorted[["date_br", "type", "category", "description", "amount"]].rename(columns={
                "date_br": "Data",
                "type": "Tipo",
                "category": "Categoria",
                "description": "Descrição",
                "amount": "Valor (R$)",
            }),
            use_container_width=True
        )


def page_patrimonio():
    st.header("🏦 Patrimônio e investimentos")

    df_assets = load_assets()

    st.subheader("Cadastrar / atualizar patrimônio")

    asset_types = ["Cripto", "Ação", "FII", "Imóvel", "Carro", "Colecionável", "Outro"]

    with st.form("form_asset"):
        col1, col2, col3 = st.columns(3)
        with col1:
            asset_type = st.selectbox("Tipo de ativo", asset_types)
            category = st.text_input("Categoria (opcional)", placeholder="Ex.: Bolsa BR, Exterior, Patrimônio pessoal...")
        with col2:
            name = st.text_input("Nome do ativo", placeholder="Ex.: Bitcoin, PETR4, Casa Praia")
            symbol = st.text_input("Símbolo / Ticker", placeholder="BTC, PETR4, HGLG11...")
        with col3:
            quantity = st.number_input("Quantidade", min_value=0.0, step=1.0, format="%.4f")

        manual_price = st.number_input(
            "Preço unitário manual (R$) – use para bens sem cotação automática",
            min_value=0.0,
            step=100.0,
            format="%.2f"
        )

        submitted = st.form_submit_button("Salvar patrimônio / investimento")

    if submitted:
        if not name:
            st.warning("Informe ao menos o nome do ativo.")
        else:
            if asset_type == "Cripto":
                api_source = "COINGECKO"
                api_id_val = symbol.lower()
            elif asset_type in ["Ação", "FII"]:
                api_source = "BRAPI"
                api_id_val = symbol.upper()
            else:
                api_source = "MANUAL"
                api_id_val = ""

            if asset_type in ["Imóvel", "Carro", "Colecionável", "Outro"] and manual_price <= 0:
                st.warning("Para bens sem cotação automática, informe um preço manual.")
            else:
                new_row = {
                    "asset_type": asset_type,
                    "category": category,
                    "name": name,
                    "symbol": symbol,
                    "api_source": api_source,
                    "api_id": api_id_val,
                    "quantity": quantity if quantity > 0 else 1.0,
                    "manual_price_brl": manual_price,
                }

                if df_assets.empty:
                    df_assets = pd.DataFrame([new_row])
                else:
                    mask = (
                        (df_assets["asset_type"] == asset_type) &
                        (df_assets["name"] == name) &
                        (df_assets["symbol"] == symbol)
                    )
                    if mask.any():
                        df_assets.loc[mask, :] = new_row
                    else:
                        df_assets = pd.concat([df_assets, pd.DataFrame([new_row])], ignore_index=True)

                save_assets(df_assets)
                st.success("Patrimônio/investimento salvo/atualizado.")
                df_assets = load_assets()

    st.subheader("Visão do patrimônio")

    df_assets = load_assets()
    df_assets_val = compute_assets_values(df_assets)

    if df_assets_val.empty:
        st.info("Nenhum patrimônio cadastrado ainda.")
        return

    total_assets = df_assets_val["value_brl"].sum()

    col1, col2 = st.columns([2, 1])
    with col1:
        df_show = df_assets_val.copy()
        df_show["value_brl_fmt"] = df_show["value_brl"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        df_show["current_price_brl_fmt"] = df_show["current_price_brl"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        st.dataframe(
            df_show[[
                "asset_type", "category", "name", "symbol",
                "quantity", "current_price_brl_fmt", "value_brl_fmt"
            ]].rename(columns={
                "asset_type": "Tipo",
                "category": "Categoria",
                "name": "Nome",
                "symbol": "Símbolo",
                "quantity": "Qtd",
                "current_price_brl_fmt": "Preço atual (R$)",
                "value_brl_fmt": "Valor total (R$)",
            }),
            use_container_width=True
        )

    with col2:
        st.metric(
            "Valor total do patrimônio",
            f"R$ {total_assets:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

    st.subheader("Patrimônio por tipo de ativo (R$)")
    alloc = df_assets_val.groupby("asset_type")["value_brl"].sum()
    st.bar_chart(alloc)


# ==========================
# LAYOUT PRINCIPAL
# ==========================

def main():
    require_login()  # força login antes de qualquer coisa

    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Dashboard"

    pages = ["Dashboard", "Lançamentos", "Patrimônio / Investimentos"]

    with st.sidebar:
        st.title("💰 Finanças Pessoais")
        st.caption(f"Usuário: {st.session_state.get('user', '')}")

        selected = st.radio(
            "Navegação",
            pages,
            index=pages.index(st.session_state["current_page"])
        )

        st.markdown("---")
        if st.button("Sair (logout)"):
            st.session_state.clear()
            st.experimental_rerun()

    st.session_state["current_page"] = selected

    if selected == "Dashboard":
        page_dashboard()
    elif selected == "Lançamentos":
        page_lancamentos()
    elif selected == "Patrimônio / Investimentos":
        page_patrimonio()


if __name__ == "__main__":
    main()

