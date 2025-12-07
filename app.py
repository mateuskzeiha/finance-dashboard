import os
import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
import streamlit as st

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
    """Cria dataframes vazios padrão para receitas e despesas."""
    if "df_receitas" not in st.session_state:
        st.session_state["df_receitas"] = pd.DataFrame(
            columns=["Data", "Categoria", "Descrição", "Valor"]
        )
    if "df_despesas" not in st.session_state:
        st.session_state["df_despesas"] = pd.DataFrame(
            columns=["Data", "Categoria", "Descrição", "Valor"]
        )


def load_user_data(email: str):
    """Carrega os dados do usuário pelo e-mail e joga no session_state."""
    data_all = load_all_data()
    user_data = data_all.get(email)

    if user_data:
        st.session_state["df_receitas"] = pd.DataFrame(user_data.get("receitas", []))
        st.session_state["df_despesas"] = pd.DataFrame(user_data.get("despesas", []))
    else:
        init_empty_user_frames()


def save_user_data(email: str):
    """Salva os dataframes atuais no JSON, usando o e-mail como chave."""
    data_all = load_all_data()

    data_all[email] = {
        "receitas": st.session_state["df_receitas"].to_dict(orient="records"),
        "despesas": st.session_state["df_despesas"].to_dict(orient="records"),
    }

    save_all_data(data_all)


# ==============================
# FUNÇÃO PARA ENVIAR CÓDIGO POR E-MAIL (ICLOUD)
# ==============================

def send_email_code(email_to: str, code: str):
    """
    Envia o código de login usando SMTP do iCloud.
    Atenção: use e-mail @icloud.com / @me.com + senha de app.
    """

    # ===== AJUSTE AQUI COM SEUS DADOS =====
    smtp_server = "smtp.mail.me.com"
    smtp_port = 587  # TLS
    smtp_user = "mateuskr@icloud.com"  # seu e-mail iCloud
    smtp_password = "dklx-aojq-fond-tjfn"  # senha de app gerada na Apple
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
                    st.error(f"Não foi possível enviar o código. Tente novamente mais tarde.")
                    # Se quiser debugar local, pode exibir o erro:
                    # st.info(f"Erro técnico: {err}")
                    # E até o código (modo teste):
                    # st.info(f"(Teste) Código gerado: {code}")

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
# DASHBOARD LOGADO
# ==============================

def dashboard_page():
    st.title("Dashboard Financeiro")

    email = st.session_state.get("user_email", "Desconhecido")
    st.sidebar.markdown(f"**Usuário:** {email}")

    # Botão de logout
    if st.sidebar.button("Logout"):
        # Garante que tudo esteja salvo
        if "user_email" in st.session_state:
            save_user_data(st.session_state["user_email"])

        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.rerun()

    # Garante que dataframes existam
    init_empty_user_frames()

    col1, col2 = st.columns(2)

    # FORM RECEITAS
    with col1:
        st.subheader("Cadastrar Receita")
        with st.form("form_receitas"):
            data_rec = st.date_input("Data da receita")
            cat_rec = st.text_input("Categoria da receita", value="Salário")
            desc_rec = st.text_input("Descrição da receita")
            valor_rec = st.number_input("Valor da receita", min_value=0.0, step=0.01)

            submitted_rec = st.form_submit_button("Adicionar receita")

            if submitted_rec:
                nova_linha = {
                    "Data": str(data_rec),
                    "Categoria": cat_rec,
                    "Descrição": desc_rec,
                    "Valor": float(valor_rec),
                }
                st.session_state["df_receitas"] = pd.concat(
                    [
                        st.session_state["df_receitas"],
                        pd.DataFrame([nova_linha]),
                    ],
                    ignore_index=True,
                )

                if "user_email" in st.session_state:
                    save_user_data(st.session_state["user_email"])

                st.success("Receita adicionada com sucesso!")
                st.rerun()

    # FORM DESPESAS
    with col2:
        st.subheader("Cadastrar Despesa")
        with st.form("form_despesas"):
            data_desp = st.date_input("Data da despesa")
            cat_desp = st.text_input("Categoria da despesa", value="Alimentação")
            desc_desp = st.text_input("Descrição da despesa")
            valor_desp = st.number_input("Valor da despesa", min_value=0.0, step=0.01)

            submitted_desp = st.form_submit_button("Adicionar despesa")

            if submitted_desp:
                nova_linha = {
                    "Data": str(data_desp),
                    "Categoria": cat_desp,
                    "Descrição": desc_desp,
                    "Valor": float(valor_desp),
                }
                st.session_state["df_despesas"] = pd.concat(
                    [
                        st.session_state["df_despesas"],
                        pd.DataFrame([nova_linha]),
                    ],
                    ignore_index=True,
                )

                if "user_email" in st.session_state:
                    save_user_data(st.session_state["user_email"])

                st.success("Despesa adicionada com sucesso!")
                st.rerun()

    st.markdown("---")

    # Tabelas
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Receitas")
        if not st.session_state["df_receitas"].empty:
            st.dataframe(st.session_state["df_receitas"], use_container_width=True)
        else:
            st.info("Nenhuma receita cadastrada ainda.")

    with col4:
        st.subheader("Despesas")
        if not st.session_state["df_despesas"].empty:
            st.dataframe(st.session_state["df_despesas"], use_container_width=True)
        else:
            st.info("Nenhuma despesa cadastrada ainda.")

    # Resumo simples
    total_receitas = st.session_state["df_receitas"]["Valor"].sum()
    total_despesas = st.session_state["df_despesas"]["Valor"].sum()
    saldo = total_receitas - total_despesas

    st.markdown("---")
    st.subheader("Resumo")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Receitas", f"R$ {total_receitas:,.2f}")
    c2.metric("Total de Despesas", f"R$ {total_despesas:,.2f}")
    c3.metric("Saldo", f"R$ {saldo:,.2f}")


# ==============================
# MAIN
# ==============================

def main():
    authenticated = st.session_state.get("authenticated", False)

    if not authenticated:
        login_page()
    else:
        dashboard_page()


if __name__ == "__main__":
    main()
