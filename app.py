import streamlit as st
import pandas as pd
from datetime import date, timedelta
from src.db import init_db, get_connection, list_collaborators, list_supervisors, get_stores_for_collaborator, save_submission, list_submissions_for_supervisor, review_submission, list_submissions, get_submission_visits, authenticate_user, count_app_users
from src.import_export import import_base, export_visits

st.set_page_config(page_title="Agendador de Visitas", page_icon="📅", layout="wide")
init_db()

def week_start(d):
    return d - timedelta(days=d.weekday())

def read_bytes(uploaded, header_row):
    return pd.read_excel(uploaded, header=header_row)

def tela_login():
    st.title("📅 Agendador de Visitas")
    st.caption("Entre com as credenciais cadastradas para acessar o sistema.")
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if submitted:
            user = authenticate_user(username, password)
            if user:
                st.session_state["auth_user"] = user
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos, ou conta inativa.")
    if count_app_users() == 0:
        st.warning("Ainda não existem usuários cadastrados. Crie as contas no banco antes de entrar.")

if "auth_user" not in st.session_state:
    tela_login()
    st.stop()

auth_user = st.session_state["auth_user"]
mode = auth_user["role"]

with st.sidebar:
    st.success(f"Conectado: {auth_user['username']}")
    st.caption(f"Perfil: {mode}")
    if st.button("Sair", use_container_width=True):
        for key in ("auth_user", "draft", "export_data"):
            st.session_state.pop(key, None)
        st.rerun()
    if mode == "Colaborador":
        people = list_collaborators()
        actor = st.selectbox("Selecione seu nome", people) if people else None
    elif mode == "Supervisor":
        people = list_supervisors()
        actor = st.selectbox("Selecione seu nome", people) if people else None
    else:
        actor = "Administrador"

st.title("📅 Agendador de Visitas")
st.caption("MVP operacional • Cadastros via Excel • Agendas com aprovação do supervisor")

if mode == "Administrador":
    st.subheader("Administração de cadastros")
    st.markdown("""
Importe uma planilha Excel (`.xlsx`) com uma linha por vínculo **colaborador × loja**.
Colunas obrigatórias: `Colaborador`, `Supervisor`, `Código PDV`, `Loja`.
Colunas opcionais: `Cidade`, `UF`, `Ativo`.
A importação sincroniza os vínculos existentes com os vínculos presentes no arquivo.
""")
    up = st.file_uploader("Arquivo Excel da base", type=["xlsx"])
    header_row = st.number_input("Número da linha do cabeçalho no Excel (1 = primeira linha)", min_value=1, max_value=100, value=1) - 1
    if up and st.button("Importar / atualizar base", type="primary"):
        try:
            df = read_bytes(up, int(header_row))
            result = import_base(df)
            st.success(f"Importação concluída: {result['employees']} colaboradores, {result['stores']} lojas e {result['assignments']} vínculos.")
            if result["warnings"]:
                st.warning("Avisos: " + " | ".join(result["warnings"]))
        except Exception as e:
            st.error(f"Não foi possível importar: {e}")

    st.divider()
    st.subheader("Exportação")
    status = st.selectbox("Registros a exportar", ["Aprovadas", "Todas as agendas", "Pendentes de aprovação", "Reprovadas"])
    if st.button("Preparar Excel"):
        status_map = {"Aprovadas":"APROVADA", "Pendentes de aprovação":"PENDENTE_APROVACAO", "Reprovadas":"REPROVADA", "Todas as agendas":None}
        data = export_visits(status_map[status])
        st.session_state["export_data"] = data
    if "export_data" in st.session_state:
        st.download_button("Baixar agendamentos.xlsx", data=st.session_state["export_data"], file_name="agendamentos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.divider()
    st.subheader("Visão geral")
    df_sub = list_submissions()
    if not df_sub.empty:
        st.dataframe(df_sub, use_container_width=True, hide_index=True)
    else:
        st.info("Ainda não há agendas enviadas.")

elif mode == "Colaborador":
    if not actor:
        st.info("Nenhum colaborador cadastrado. Importe a base na área Administrador.")
    else:
        st.subheader(f"Olá, {actor}")
        today = date.today()
        default_monday = week_start(today)
        chosen_week = st.date_input("Escolha a semana (selecione qualquer dia da semana)", value=default_monday)
        monday = week_start(chosen_week)
        sunday = monday + timedelta(days=6)
        st.caption(f"Semana selecionada: {monday.strftime('%d/%m/%Y')} a {sunday.strftime('%d/%m/%Y')}")

        stores = get_stores_for_collaborator(actor)
        if stores.empty:
            st.warning("Não há lojas vinculadas a este colaborador. Solicite a atualização do cadastro.")
        else:
            store_labels = {
                f"{r['store_code']} — {r['store_name']} ({r.get('city') or ''}/{r.get('uf') or ''})": r['store_code']
                for _, r in stores.iterrows()
            }
            with st.form("add_visit_form", clear_on_submit=True):
                c1, c2 = st.columns([2,1])
                with c1:
                    selected_label = st.selectbox("Loja vinculada", list(store_labels.keys()))
                with c2:
                    visit_date = st.date_input("Data da visita", value=monday, min_value=monday, max_value=sunday)
                add = st.form_submit_button("Adicionar ao rascunho")
            if "draft" not in st.session_state:
                st.session_state["draft"] = []
            if add:
                code = store_labels[selected_label]
                if any(v["store_code"] == code and v["visit_date"] == visit_date.isoformat() for v in st.session_state["draft"]):
                    st.error("Esta loja já está no rascunho para essa data.")
                else:
                    st.session_state["draft"].append({"store_code": code, "store_label": selected_label, "visit_date": visit_date.isoformat()})
                    st.success("Visita adicionada ao rascunho.")

            draft = st.session_state.get("draft", [])
            st.subheader("Rascunho da semana")
            if draft:
                view = pd.DataFrame([{"Loja":v["store_label"], "Data":v["visit_date"]} for v in draft])
                st.dataframe(view, use_container_width=True, hide_index=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Limpar rascunho"):
                        st.session_state["draft"] = []
                        st.rerun()
                with c2:
                    if st.button("Enviar para aprovação", type="primary"):
                        try:
                            result = save_submission(actor, monday.isoformat(), draft)
                            st.session_state["draft"] = []
                            st.success(f"Agenda enviada ao supervisor. Protocolo: {result}")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            else:
                st.info("Adicione as visitas da semana antes de enviar.")

elif mode == "Supervisor":
    if not actor:
        st.info("Nenhum supervisor cadastrado. Importe a base na área Administrador.")
    else:
        st.subheader(f"Agendas aguardando análise — {actor}")
        pending = list_submissions_for_supervisor(actor)
        if pending.empty:
            st.success("Não há agendas pendentes para aprovação.")
        else:
            for _, row in pending.iterrows():
                with st.expander(f"Protocolo #{row['submission_id']} • {row['collaborator']} • semana de {row['week_start']} • {row['visit_count']} visita(s)"):
                    visits = get_submission_visits(int(row["submission_id"]))
                    st.dataframe(visits, use_container_width=True, hide_index=True)
                    comment = st.text_input("Comentário (obrigatório ao reprovar)", key=f"comment_{row['submission_id']}")
                    a, b = st.columns(2)
                    with a:
                        if st.button("Aprovar agenda", key=f"approve_{row['submission_id']}", type="primary"):
                            try:
                                review_submission(int(row["submission_id"]), actor, "APROVADA", comment)
                                st.success("Agenda aprovada.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    with b:
                        if st.button("Reprovar agenda", key=f"reject_{row['submission_id']}"):
                            try:
                                review_submission(int(row["submission_id"]), actor, "REPROVADA", comment)
                                st.warning("Agenda reprovada.")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

st.divider()
st.caption("MVP de referência. Antes de uso real: implementar autenticação corporativa, autorização no servidor, backups, logs e hospedagem compartilhada.")
