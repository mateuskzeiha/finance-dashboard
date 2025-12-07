import os
import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import pandas as pd
import streamlit as st
import yfinance as yf

# ==============================
# CONFIGURAÇÕES GERAIS
# ==============================

st.set_page_config(page_title="Dashboard Financeiro", layout="wide")

DATA_FILE = "user_data.json"


# ==============================
# FUNÇÕES DE PERSISTÊNCIA
# ==============================

def load_all_data():
    """Carrega o JSON completo com os dados de todos os usuários."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_all_data(data: dict):
    """Salva o dicionário completo de usuários no JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_empty_user_frames():
    """Cria dataframes vazios padrão para receitas, despesas e patrimônio."""
    if "df_receitas" not in st.session_state:
        st.session_state["df_receitas"] = pd.DataFrame(
            columns=["Data", "Categoria", "Descrição", "Valor"]
        )

    if "df_despesas" not in st.session_state:
        st.session_state["df_despesas"] = pd.DataFrame(
            columns=["Data", "Categoria", "Descrição", "Valor"]
        )

    if "df_patrimonio" not in st.session_state:
        st.session_state["df_patrimonio"] = pd.DataFrame(
            columns=[
                "Data",
                "Tipo",
                "Ativo",
                "Quantidade",
                "Preço_R$",
                "Valor_Total_R$",
            ]
        )


def normalize_df_receitas_despesas(df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas padrão para receitas/despesas, especialmente 'Valor'."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Data", "Categoria", "Descrição", "Valor"])

    df = df.copy()

    # Garante colunas mínimas
    for col in ["Data", "Categoria", "Descrição"]:
        if col not in df.columns:
            df[col] = ""

    # Garante coluna Valor
    if "Valor" not in df.columns:
        possiveis = [c for c in df.columns if "valor" in c.lower()]
        if possiveis:
            df["Valor"] = df[possiveis[0]]
        else:
            df["Valor"] = 0.0

    # Reordena colunas
    df = df[["Data", "Categoria", "Descrição", "Valor"]]
    return df


def normalize_df_patrimonio(df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas padrão para patrimônio, incluindo 'Valor_Total_R$'."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "Data",
                "Tipo",
                "Ativo",
                "Quantidade",
                "Preço_R$",
                "Valor_Total_R$",
            ]
        )

    df = df.copy()

    for col in ["Data", "Tipo", "Ativo", "Quantidade"]:
        if col not in df.columns:
            df[col] = "" if col != "Quantidade" else 0.0

    if "Preço_R$" not in df.columns:
        possiveis_preco = [c for c in df.columns if "preço" in c.lower() or "preco" in c.lower()]
        if possiveis_preco:
            df["Preço_R$"] = df[possiveis_preco[0]]
        else:
            df["Preço_R$"] = 0.0

    if "Valor_Total_R$" not in df.columns:
        possiveis_valor = [c for c in df.columns if "valor" in c.lower()]
        if possiveis_valor:
            df["Valor_Total_R$"] = df[possiveis_valor[0]]
        else:
            # se não tiver, calcula aproximado
            try:
                df["Valor_Total_R$"] = df["Quantidade"].astype(float) * df["Preço_R$"].astype(float)
            except Exception:
                df["Valor_Total_R$"] = 0.0

    df = df[
        [
            "Data",
            "Tipo",
            "Ativo",
            "Quantidade",
            "Preço_R$",
            "Valor_Total_R$",
        ]
    ]
    return df


def load_user_data(email: str):
    """Carrega os dados do usuário pelo e-mail e joga no session_state (já normalizado)."""
    data_all = load_all_data()
    user_data = data_all.get(email, {})

    df_r = pd.DataFrame(user_data.get("receitas", []))
    df_d = pd.DataFrame(user_data.get("despesas", []))
    df_p = pd.DataFrame(user_data.get("patrimonio", []))

    st.session_state["df_receitas"] = normalize_df_receitas_despesas(df_r)
    st.session_state["df_despesas"] = normalize_df_receitas_despesas(df_d)
    st.session_state["df_patrimonio"] = normalize_df_patrimonio(df_p)


def save_user_data(email: str):
    """Salva os dataframes atuais no JSON, usando o e-mail como chave."""
    init_empty_user_frames()

    df_r = normalize_df_receitas_despesas(st.session_state["df_receitas"])
    df_d = normalize_df_receitas_despesas(st.session_state["df_despesas"])
    df_p = normalize_df_patrimonio(st.session_state["df_patrimonio"])

    data_all = load_all_data()
    data_all[email] = {
        "receitas": df_r.to_dict(orient="records"),
        "despesas": df_d.to_dict(orient="records"),
        "patrimonio": df_p.to_dict(orient="records"),
    }

    save_all_data(data_all)


# ==============================
# FUNÇÃO PARA ENVIAR CÓDIGO POR E-MAIL (ICLOUD)
# ==============================

def send_email_code(email_to: str, code: str):
    """
    Envia o código de login usando SMTP do iCloud.
    Use e-mail @icloud.com/@me.com + senha de app (não a senha normal).
    """

    # ===== AJUSTE AQUI COM SEUS DADOS =====
    smtp_server = "smtp.mail.me.com"
    smtp_port = 587  # TLS
    smtp_user = "SEU_EMAIL@icloud.com"         # seu e-mail iCloud
    smtp_password = "SENHA_DE_APP_ICLOUD"      # senha de app gerada na Apple
    # ======================================

    subject = "Seu código de login - Dashboard Financeiro"
    body = f"Seu código de acesso é: {code}"

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


# ==============================
# FUNÇÕES DE COTAÇÃO / DATA
# ==============================

def get_asset_price_brl(asset_type: str, ticker: str):
    """
    Busca o preço em R$ usando yfinance.
    - Ação / FII: ticker B3 -> usa .SA se não tiver
    - Criptomoeda: TICKER-USD e converte com USDBRL=X
    Retorna float ou None.
    """
    ticker = ticker.strip().upper()
    try:
        if asset_type in ["Ação", "FII"]:
            yf_ticker = ticker
            if not yf_ticker.endswith(".SA"):
                yf_ticker += ".SA"

            data = yf.Ticker(yf_ticker).history(period="1d")
            if data.empty:
                return None
            price = float(data["Close"].iloc[-1])
            return price

        elif asset_type == "Criptomoeda":
            # Ex: BTC-USD, ETH-USD
            yf_ticker = f"{ticker}-USD"
            data = yf.Ticker(yf_ticker).history(period="1d")
            if data.empty:
                return None
            price_usd = float(data["Close"].iloc[-1])

            usdbrl_data = yf.Ticker("USDBRL=X").history(period="1d")
            if usdbrl_data.empty:
                return None
            usd_brl = float(usdbrl_data["Close"].iloc[-1])

            return price_usd * usd_brl

        else:
            return None
    except Exception:
        return None


def parse_date_column(df: pd.DataFrame, col: str = "Data") -> pd.DataFrame:
    if df is None or df.empty or col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# ==============================
# TELA DE LOGIN
# ==============================

def login_page():
    st.title("Login - Dashboard Financeiro")

    if "login_step" not in st.session_state:
        st.session_state["login_step"] = "email"  # email ou code

    if st.session_state["login_step"] == "email":
        email = st.text_input("Digite seu e-mail:")

        if st.button("Enviar código de acesso"):
            if not email:
                st.error("Informe um e-mail.")
            else:
                code = str(random.randint(100000, 999999))
                st.session_state["login_code"] = code
                st.session_state["temp_email"] = email

                ok, err = send_email_code(email, code)

                if ok:
                    st.success("Código enviado para seu e-mail.")
                    st.session_state["login_step"] = "code"
                    st.rerun()
                else:
                    st.error("Não foi possível enviar o código por e-mail.")
                    st.info(f"Erro técnico: {err}")
                    # Modo teste
                    st.info(f"(Modo teste) Código gerado: {code}")

    elif st.session_state["login_step"] == "code":
        st.write(f"E-mail: **{st.session_state.get('temp_email', '')}**")
        code_input = st.text_input("Digite o código recebido:", type="password")
        if st.button("Entrar"):
            code_real = st.session_state.get("login_code")

            if code_input == code_real and code_real is not None:
                email = st.session_state.get("temp_email")
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email

                # Limpa dados temporários do login
                st.session_state["login_code"] = None
                st.session_state["login_step"] = "email"
                st.session_state["temp_email"] = None

                # Carrega dados do usuário
                load_user_data(email)

                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Código incorreto. Tente novamente.")

        if st.button("Voltar"):
            st.session_state["login_step"] = "email"
            st.session_state["login_code"] = None
            st.session_state["temp_email"] = None
            st.rerun()


# ==============================
# PÁGINA DE LANÇAMENTOS
# ==============================

def lancamentos_page():
    st.title("Lançamentos")

    init_empty_user_frames()

    tab_receita, tab_despesa, tab_patrimonio = st.tabs(
        ["Receita", "Despesa", "Patrimônio"]
    )

    # ========== RECEITA ==========
    with tab_receita:
        st.subheader("Lançar Receita")
        with st.form("form_receitas"):
            data_rec = st.date_input("Data da receita", value=datetime.today())
            cat_rec = st.text_input("Categoria", value="Salário")
            desc_rec = st.text_input("Descrição")
            valor_rec = st.number_input(
                "Valor (R$)", min_value=0.0, step=0.01, format="%.2f"
            )

            submitted_rec = st.form_submit_button("Adicionar receita")

            if submitted_rec:
                nova_linha = {
                    "Data": str(data_rec),
                    "Categoria": cat_rec,
                    "Descrição": desc_rec,
                    "Valor": float(valor_rec),
                }

                df_r = st.session_state.get("df_receitas", pd.DataFrame())
                df_r = normalize_df_receitas_despesas(df_r)
                df_r = pd.concat([df_r, pd.DataFrame([nova_linha])], ignore_index=True)

                st.session_state["df_receitas"] = df_r

                if "user_email" in st.session_state:
                    save_user_data(st.session_state["user_email"])

                st.success("Receita adicionada.")
                st.rerun()

        st.markdown("### Receitas lançadas")
        df_r_view = normalize_df_receitas_despesas(st.session_state.get("df_receitas"))
        if not df_r_view.empty:
            st.dataframe(df_r_view, use_container_width=True)
        else:
            st.info("Nenhuma receita lançada ainda.")

    # ========== DESPESA ==========
    with tab_despesa:
        st.subheader("Lançar Despesa")
        with st.form("form_despesas"):
            data_desp = st.date_input("Data da despesa", value=datetime.today())
            cat_desp = st.text_input("Categoria", value="Alimentação")
            desc_desp = st.text_input("Descrição")
            valor_desp = st.number_input(
                "Valor (R$)", min_value=0.0, step=0.01, format="%.2f"
            )

            submitted_desp = st.form_submit_button("Adicionar despesa")

            if submitted_desp:
                nova_linha = {
                    "Data": str(data_desp),
                    "Categoria": cat_desp,
                    "Descrição": desc_desp,
                    "Valor": float(valor_desp),
                }

                df_d = st.session_state.get("df_despesas", pd.DataFrame())
                df_d = normalize_df_receitas_despesas(df_d)
                df_d = pd.concat([df_d, pd.DataFrame([nova_linha])], ignore_index=True)

                st.session_state["df_despesas"] = df_d

                if "user_email" in st.session_state:
                    save_user_data(st.session_state["user_email"])

                st.success("Despesa adicionada.")
                st.rerun()

        st.markdown("### Despesas lançadas")
        df_d_view = normalize_df_receitas_despesas(st.session_state.get("df_despesas"))
        if not df_d_view.empty:
            st.dataframe(df_d_view, use_container_width=True)
        else:
            st.info("Nenhuma despesa lançada ainda.")

    # ========== PATRIMÔNIO ==========
    with tab_patrimonio:
        st.subheader("Lançar Patrimônio")

        with st.form("form_patrimonio"):
            data_pat = st.date_input("Data do lançamento", value=datetime.today())
            tipo = st.selectbox(
                "Tipo de ativo",
                ["Criptomoeda", "Ação", "FII", "Outro"],
            )
            ativo = st.text_input(
                "Ticker / Nome do ativo",
                help="Ex: BTC, PETR4, MXRF11. Para 'Outro', pode ser descrição livre.",
            )
            qtd = st.number_input(
                "Quantidade",
                min_value=0.0,
                step=0.0001,
                format="%.4f",
                help="Para 'Outro', pode usar 1 e informar o valor total.",
            )

            usa_cotacao = tipo in ["Criptomoeda", "Ação", "FII"]

            valor_manual = None
            if not usa_cotacao:
                valor_manual = st.number_input(
                    "Valor total (R$)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    help="Para 'Outro', informe diretamente o valor em reais.",
                )

            submitted_pat = st.form_submit_button("Adicionar patrimônio")

            if submitted_pat:
                if not ativo:
                    st.error("Informe o ativo.")
                elif qtd <= 0:
                    st.error("Quantidade deve ser maior que zero.")
                else:
                    preco = 0.0
                    valor_total = 0.0

                    if usa_cotacao:
                        preco = get_asset_price_brl(tipo, ativo)
                        if preco is None:
                            st.error(
                                "Não foi possível obter a cotação. "
                                "Confirme o ticker ou tente novamente."
                            )
                        else:
                            valor_total = preco * qtd
                    else:
                        if valor_manual is None or valor_manual <= 0:
                            st.error("Informe o valor total em R$.")
                        else:
                            valor_total = float(valor_manual)
                            preco = valor_total / qtd if qtd > 0 else 0.0

                    if (usa_cotacao and preco is not None) or (
                        not usa_cotacao and valor_manual is not None and valor_manual > 0
                    ):
                        nova_linha = {
                            "Data": str(data_pat),
                            "Tipo": tipo,
                            "Ativo": ativo.upper(),
                            "Quantidade": float(qtd),
                            "Preço_R$": float(preco),
                            "Valor_Total_R$": float(valor_total),
                        }

                        df_p = st.session_state.get("df_patrimonio", pd.DataFrame())
                        df_p = normalize_df_patrimonio(df_p)
                        df_p = pd.concat([df_p, pd.DataFrame([nova_linha])], ignore_index=True)

                        st.session_state["df_patrimonio"] = df_p

                        if "user_email" in st.session_state:
                            save_user_data(st.session_state["user_email"])

                        st.success("Patrimônio adicionado.")
                        st.rerun()

        st.markdown("### Patrimônio lançado")
        df_p_view = normalize_df_patrimonio(st.session_state.get("df_patrimonio"))
        if not df_p_view.empty:
            st.dataframe(df_p_view, use_container_width=True)
        else:
            st.info("Nenhum lançamento de patrimônio ainda.")


# ==============================
# PÁGINA DE DASHBOARD
# ==============================

def dashboard_page():
    st.title("Dashboard")

    init_empty_user_frames()

    df_r = normalize_df_receitas_despesas(st.session_state.get("df_receitas"))
    df_d = normalize_df_receitas_despesas(st.session_state.get("df_despesas"))
    df_p = normalize_df_patrimonio(st.session_state.get("df_patrimonio"))

    df_r = parse_date_column(df_r)
    df_d = parse_date_column(df_d)
    df_p = parse_date_column(df_p)

    # ------------------------------
    # FILTRO DE MÊS / ANO
    # ------------------------------
    st.sidebar.subheader("Filtro de período (Receita/Despesa)")

    datas = []
    if not df_r.empty:
        datas.extend(df_r["Data"].dropna().tolist())
    if not df_d.empty:
        datas.extend(df_d["Data"].dropna().tolist())

    if datas:
        min_data = min(datas)
        max_data = max(datas)
    else:
        hoje = datetime.today()
        min_data = max_data = hoje

    anos = list(range(min_data.year, max_data.year + 1))
    anos = sorted(list(set(anos)))

    ano_sel = st.sidebar.selectbox("Ano", options=anos, index=len(anos) - 1)
    mes_sel = st.sidebar.selectbox(
        "Mês",
        options=list(range(1, 13)),
        index=datetime.today().month - 1,
        format_func=lambda m: f"{m:02d}",
    )

    # ------------------------------
    # DASHBOARD RECEITA x DESPESA
    # ------------------------------

    st.subheader("Receitas x Despesas do mês")

    def filtra_mes(df):
        if df.empty:
            return df
        df = df.copy()
        df["Ano"] = df["Data"].dt.year
        df["Mes"] = df["Data"].dt.month
        return df[(df["Ano"] == ano_sel) & (df["Mes"] == mes_sel)]

    df_r_mes = filtra_mes(df_r)
    df_d_mes = filtra_mes(df_d)

    total_rec_mes = df_r_mes["Valor"].sum() if not df_r_mes.empty else 0.0
    total_desp_mes = df_d_mes["Valor"].sum() if not df_d_mes.empty else 0.0
    saldo_mes = total_rec_mes - total_desp_mes

    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas no mês", f"R$ {total_rec_mes:,.2f}")
    c2.metric("Despesas no mês", f"R$ {total_desp_mes:,.2f}")
    c3.metric("Saldo do mês", f"R$ {saldo_mes:,.2f}")

    # Lançamentos do mês (linha a linha)
    st.markdown("#### Lançamentos do mês (linha a linha)")

    if not df_r_mes.empty:
        df_r_mes_view = df_r_mes[["Data", "Categoria", "Descrição", "Valor"]].copy()
        df_r_mes_view["Tipo"] = "Receita"
    else:
        df_r_mes_view = pd.DataFrame(columns=["Data", "Categoria", "Descrição", "Valor", "Tipo"])

    if not df_d_mes.empty:
        df_d_mes_view = df_d_mes[["Data", "Categoria", "Descrição", "Valor"]].copy()
        df_d_mes_view["Tipo"] = "Despesa"
    else:
        df_d_mes_view = pd.DataFrame(columns=["Data", "Categoria", "Descrição", "Valor", "Tipo"])

    df_ld = pd.concat([df_r_mes_view, df_d_mes_view], ignore_index=True) if not (
        df_r_mes_view.empty and df_d_mes_view.empty
    ) else pd.DataFrame(columns=["Data", "Categoria", "Descrição", "Valor", "Tipo"])

    if not df_ld.empty:
        df_ld = df_ld.sort_values("Data")
        st.dataframe(df_ld, use_container_width=True)

        df_ld_plot = df_ld.copy()
        df_ld_plot["Data"] = df_ld_plot["Data"].dt.strftime("%Y-%m-%d")
        df_ld_plot["Valor_signed"] = df_ld_plot.apply(
            lambda row: row["Valor"] if row["Tipo"] == "Receita" else -row["Valor"],
            axis=1,
        )
        df_ld_plot["Saldo_acumulado"] = df_ld_plot["Valor_signed"].cumsum()

        st.markdown("#### Saldo acumulado no mês (por lançamento)")
        st.line_chart(
            df_ld_plot.set_index("Data")["Saldo_acumulado"],
            use_container_width=True,
        )
    else:
        st.info("Nenhum lançamento para o mês selecionado.")

    st.markdown("---")

    # ------------------------------
    # EVOLUÇÃO DO PATRIMÔNIO
    # ------------------------------
    st.subheader("Evolução do Patrimônio Total")

    if not df_p.empty:
        df_p_evol = df_p.copy()
        df_p_evol = df_p_evol.sort_values("Data")
        df_p_evol["Valor_Total_R$"] = df_p_evol["Valor_Total_R$"].astype(float)
        df_p_evol["Patrimonio_Acumulado"] = df_p_evol["Valor_Total_R$"].cumsum()
        df_p_evol["Data_str"] = df_p_evol["Data"].dt.strftime("%Y-%m-%d")

        st.line_chart(
            df_p_evol.set_index("Data_str")["Patrimonio_Acumulado"],
            use_container_width=True,
        )

        st.markdown("#### Lançamentos de patrimônio")
        st.dataframe(df_p_evol, use_container_width=True)
    else:
        st.info("Nenhum patrimônio lançado ainda.")


# ==============================
# MAIN
# ==============================

def main():
    authenticated = st.session_state.get("authenticated", False)

    if not authenticated:
        login_page()
    else:
        email = st.session_state.get("user_email", "Desconhecido")
        st.sidebar.markdown(f"**Usuário:** {email}")

        if st.sidebar.button("Logout"):
            if "user_email" in st.session_state:
                save_user_data(st.session_state["user_email"])

            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        pagina = st.sidebar.radio("Menu", ["Lançamentos", "Dashboard"])

        if pagina == "Lançamentos":
            lancamentos_page()
        else:
            dashboard_page()


if __name__ == "__main__":
    main()
