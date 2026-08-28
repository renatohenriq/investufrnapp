import streamlit as st
import pandas as pd
import io
import unicodedata
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
from database import init_db, SessionLocal, User, Classroom, Competition, Participant, Position, Order, DividendPayment, hash_password, verify_password
from market_data import get_stock_price, get_historical_data, get_recent_dividends

st.set_page_config(page_title="InvestUFRN App", layout="wide", page_icon="📈")
init_db()

SUPER_ADMIN_EMAIL = "renato.mota@ufrn.br"

def normalize_text(text: str) -> str:
    """Normaliza texto para ordenação alfabética insensível a acentos e maiúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()

if "user" not in st.session_state:
    st.session_state.user = None
if "active_comp_id" not in st.session_state:
    st.session_state.active_comp_id = None

db = SessionLocal()

# Garante turma padrão inicial
if db.query(Classroom).count() == 0:
    default_turma = Classroom(name="Mercado Financeiro - Geral", semester="2026.2")
    db.add(default_turma)
    db.commit()

# --- BARRA LATERAL: AUTENTICAÇÃO ---
def sidebar_auth():
    with st.sidebar:
        st.title("📈 InvestUFRN")
        st.markdown("**Liga Universitária de Investimentos**")
        st.markdown("---")

        if not st.session_state.user:
            auth_mode = st.radio("Acesso ao Sistema", ["🔑 Entrar (Login)", "📝 Criar Conta (Cadastro)"], horizontal=True)

            if auth_mode == "🔑 Entrar (Login)":
                st.subheader("Login")
                with st.form("form_login"):
                    login_email = st.text_input("E-mail ou Matrícula").strip().lower()
                    login_pass = st.text_input("Senha de Acesso", type="password")
                    btn_login = st.form_submit_button("Entrar", use_container_width=True)

                    if btn_login:
                        if not login_email or not login_pass:
                            st.error("Informe usuário/e-mail e senha.")
                        else:
                            user = db.query(User).filter(
                                (User.email == login_email) | (User.registration_id == login_email)
                            ).first()

                            if not user and login_email == SUPER_ADMIN_EMAIL.lower():
                                user = User(
                                    email=SUPER_ADMIN_EMAIL.lower(),
                                    password_hash=hash_password(login_pass),
                                    registration_id="ORGANIZADOR",
                                    name="Prof. Renato Gurgel",
                                    is_admin=True
                                )
                                db.add(user)
                                db.commit()
                                db.refresh(user)

                            if user and verify_password(login_pass, user.password_hash):
                                is_admin = user.is_admin or (user.email.lower() == SUPER_ADMIN_EMAIL.lower())
                                st.session_state.user = {
                                    "id": user.id,
                                    "email": user.email,
                                    "name": user.name,
                                    "registration_id": user.registration_id,
                                    "is_admin": is_admin
                                }
                                st.success("Login realizado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Credenciais incorretas ou usuário não cadastrado.")

            elif auth_mode == "📝 Criar Conta (Cadastro)":
                st.subheader("Novo Cadastro")
                with st.form("form_cadastro"):
                    cad_name = st.text_input("Nome Completo").strip()
                    cad_matricula = st.text_input("Matrícula").strip()
                    cad_email = st.text_input("E-mail (Qualquer provedor)").strip().lower()
                    cad_pass = st.text_input("Crie uma Senha", type="password")
                    cad_pass_conf = st.text_input("Confirme a Senha", type="password")

                    classrooms = db.query(Classroom).all()
                    sorted_classrooms = sorted(classrooms, key=lambda c: normalize_text(c.name))
                    turma_dict = {f"{c.name} ({c.semester or 'S/S'})": c.id for c in sorted_classrooms}
                    cad_turma = st.selectbox("Selecione sua Turma", list(turma_dict.keys()) if turma_dict else ["Geral"])

                    btn_cadastrar = st.form_submit_button("Cadastrar", use_container_width=True)

                    if btn_cadastrar:
                        if not cad_name or not cad_email or not cad_pass:
                            st.error("Preencha todos os campos obrigatórios.")
                        elif cad_pass != cad_pass_conf:
                            st.error("As senhas digitadas não conferem.")
                        elif len(cad_pass) < 4:
                            st.error("A senha deve ter no mínimo 4 caracteres.")
                        else:
                            exists = db.query(User).filter(User.email == cad_email).first()
                            if exists:
                                st.error("Este e-mail já está cadastrado. Vá até a aba Entrar.")
                            else:
                                is_admin = (cad_email == SUPER_ADMIN_EMAIL.lower())
                                new_user = User(
                                    name=cad_name,
                                    registration_id=cad_matricula,
                                    email=cad_email,
                                    password_hash=hash_password(cad_pass),
                                    classroom_id=turma_dict.get(cad_turma),
                                    is_admin=is_admin
                                )
                                db.add(new_user)
                                db.commit()
                                db.refresh(new_user)

                                st.session_state.user = {
                                    "id": new_user.id,
                                    "email": new_user.email,
                                    "name": new_user.name,
                                    "registration_id": new_user.registration_id,
                                    "is_admin": is_admin
                                }
                                st.success("Cadastro efetuado com sucesso!")
                                st.rerun()
        else:
            st.write(f"Conectado: **{st.session_state.user['name']}**")
            st.caption(f"Matrícula: `{st.session_state.user['registration_id'] or 'Docente'}`")
            st.caption(f"Perfil: **{'👑 Organizador' if st.session_state.user['is_admin'] else '🎓 Participante'}**")
            
            if st.session_state.active_comp_id:
                active_comp_obj = db.query(Competition).filter(Competition.id == st.session_state.active_comp_id).first()
                if active_comp_obj:
                    st.success(f"🏆 Liga Ativa:\n**{active_comp_obj.name}**")
                    if st.button("⬅️ Trocar / Voltar ao Hub", use_container_width=True):
                        st.session_state.active_comp_id = None
                        st.rerun()

            st.markdown("---")
            if st.button("🚪 Sair da Conta", use_container_width=True):
                st.session_state.user = None
                st.session_state.active_comp_id = None
                st.rerun()

sidebar_auth()

if not st.session_state.user:
    st.info("👋 Faça login ou crie sua conta na barra lateral para acessar o InvestUFRN.")
    db.close()
    st.stop()

user_data = st.session_state.user

# Atualiza permissão de admin
db_user = db.query(User).filter(User.id == user_data["id"]).first()
if db_user:
    user_data["is_admin"] = db_user.is_admin or (user_data["email"].lower() == SUPER_ADMIN_EMAIL.lower())

# ==============================================================================
# FLUXO 1: HUB INICIAL DE COMPETIÇÕES
# ==============================================================================
if st.session_state.active_comp_id is None:
    
    if user_data["is_admin"]:
        hub_tab_titles = ["🌐 Hub de Competições", "⚙️ Gestão do Organizador"]
        hub_tabs = st.tabs(hub_tab_titles)
        hub_container = hub_tabs[0]
        admin_container = hub_tabs[1]
    else:
        hub_container = st.container()
        admin_container = None

    with hub_container:
        st.header("🌐 Hub Central de Competições")
        st.caption("Acesse uma liga em que você já está inscrito ou ingresse em uma nova competição disponível.")

        user_participations = db.query(Participant).filter(Participant.user_id == user_data["id"]).all()
        user_comp_ids = [p.competition_id for p in user_participations]
        all_active_competitions = db.query(Competition).filter(Competition.is_active == True).all()

        # 1. MINHAS COMPETIÇÕES
        st.subheader("📌 Minhas Competições Ativas")
        if user_participations:
            for part in user_participations:
                comp = part.competition
                with st.container(border=True):
                    col_info, col_action = st.columns([3, 1])
                    with col_info:
                        st.markdown(f"### 🏆 {comp.name}")
                        st.write(f"📅 **Vigência:** {comp.start_date.strftime('%d/%m/%Y')} a {comp.end_date.strftime('%d/%m/%Y')} | **Status:** {'🟢 Aberta' if comp.is_active else '🔴 Encerrada'}")
                        st.write(f"💰 **Saldo em Caixa Atual:** R$ {part.cash_balance:,.2f}")
                    with col_action:
                        st.write("")
                        if st.button("🎯 Acessar Competição", key=f"hub_enter_{comp.id}", use_container_width=True, type="primary"):
                            st.session_state.active_comp_id = comp.id
                            st.rerun()
        else:
            st.info("Você ainda não está participando de nenhuma competição. Escolha uma das ligas abertas abaixo para ingressar.")

        st.markdown("---")

        # 2. COMPETIÇÕES ABERTAS DISPONÍVEIS
        st.subheader("🚀 Competições Disponíveis para Ingressar")
        available_to_join = [c for c in all_active_competitions if c.id not in user_comp_ids]

        if available_to_join:
            for comp in available_to_join:
                with st.container(border=True):
                    st.markdown(f"### 🏅 {comp.name}")
                    st.write(f"📅 **Período:** {comp.start_date.strftime('%d/%m/%Y')} até {comp.end_date.strftime('%d/%m/%Y')} | 💵 **Capital Inicial:** R$ {comp.initial_cash:,.2f}")
                    
                    with st.expander("ℹ️ Detalhes e inscrição"):
                        st.markdown(comp.description or "Sem regras específicas cadastradas.")
                        st.write(f"**Capital Inicial:** R$ {comp.initial_cash:,.2f}")
                        st.write(f"**Data de Término:** {comp.end_date.strftime('%d/%m/%Y')}")
                        
                        if st.button("🚀 Confirmar Inscrição e Iniciar Carteira", key=f"btn_join_comp_{comp.id}", type="primary", use_container_width=True):
                            new_part = Participant(
                                competition_id=comp.id,
                                user_id=user_data["id"],
                                cash_balance=comp.initial_cash
                            )
                            db.add(new_part)
                            db.commit()
                            st.session_state.active_comp_id = comp.id
                            st.success(f"Inscrição confirmada na liga '{comp.name}'!")
                            st.rerun()
        else:
            st.write("🎉 Você já está cadastrado em todas as ligas disponíveis no momento.")

    # PAINEL DO ORGANIZADOR NO HUB
    if admin_container is not None:
        with admin_container:
            st.header("⚙️ Painel de Gestão do Organizador")
            admin_sub_tabs = st.tabs([
                "📊 Estatísticas por Competição",
                "🏆 Gerenciar Competições",
                "🏫 Turmas",
                "👥 Participantes da Liga",
                "👤 Gestão de Usuários",
                "💰 Dividendos & Excel",
                "📜 Log de Auditoria"
            ])

            # 1. ESTATÍSTICAS
            with admin_sub_tabs[0]:
                st.subheader("📊 Painel Estatístico da Liga")
                all_registered_comps = db.query(Competition).all()
                if all_registered_comps:
                    comp_stat_dict = {f"ID {c.id} - {c.name} ({'Ativa' if c.is_active else 'Encerrada'})": c.id for c in all_registered_comps}
                    sel_stat_comp_str = st.selectbox("Selecione a Competição para Inspecionar", list(comp_stat_dict.keys()))
                    stat_comp = db.query(Competition).filter(Competition.id == comp_stat_dict[sel_stat_comp_str]).first()

                    if stat_comp:
                        stat_parts = db.query(Participant).filter(Participant.competition_id == stat_comp.id).all()
                        
                        tot_participantes = len(stat_parts)
                        tot_patrimonio = 0.0
                        tot_caixa = sum(p.cash_balance for p in stat_parts)
                        tot_investido = 0.0

                        ranking_stat_list = []
                        for p in stat_parts:
                            eq_val = sum((get_stock_price(pos.ticker) or pos.avg_price) * pos.quantity for pos in p.positions)
                            p_wealth = p.cash_balance + eq_val
                            tot_investido += eq_val
                            tot_patrimonio += p_wealth
                            p_ret = ((p_wealth / stat_comp.initial_cash) - 1) * 100
                            
                            ranking_stat_list.append({
                                "Aluno": p.user.name,
                                "Matrícula": p.user.registration_id,
                                "Turma": p.user.classroom.name if p.user.classroom else "Geral",
                                "Patrimônio Total": p_wealth,
                                "Saldo em Caixa": p.cash_balance,
                                "Investido em Ações": eq_val,
                                "Rentabilidade (%)": p_ret,
                                "Qtd Ordens": len(p.orders)
                            })

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Alunos Inscritos", tot_participantes)
                        m2.metric("Patrimônio Total em Jogo", f"R$ {tot_patrimonio:,.2f}")
                        m3.metric("Total em Caixa", f"R$ {tot_caixa:,.2f}")
                        m4.metric("Total Alocado em Ações", f"R$ {tot_investido:,.2f}")

                        st.markdown("---")
                        st.subheader(f"Classificação Completa — {stat_comp.name}")
                        if ranking_stat_list:
                            df_stat_rank = pd.DataFrame(ranking_stat_list).sort_values(by="Patrimônio Total", ascending=False).reset_index(drop=True)
                            df_stat_rank.index += 1
                            st.dataframe(
                                df_stat_rank.style.format({
                                    "Patrimônio Total": "R$ {:,.2f}",
                                    "Saldo em Caixa": "R$ {:,.2f}",
                                    "Investido em Ações": "R$ {:,.2f}",
                                    "Rentabilidade (%)": "{:+.2f}%"
                                }),
                                use_container_width=True
                            )
                        else:
                            st.info("Nenhum participante inscrito nesta competição.")
                else:
                    st.info("Nenhuma competição criada ainda.")

            # 2. GERENCIAR COMPETIÇÕES
            with admin_sub_tabs[1]:
                st.subheader("1. Lançar Nova Competição")
                with st.form("form_create_comp_hub"):
                    c_name = st.text_input("Nome da Competição (Ex.: Liga de Finanças 2026.2)")
                    c_cash = st.number_input("Capital Inicial por Aluno (R$)", value=100000.0, step=10000.0)
                    c_start = st.date_input("Data de Início", value=date.today())
                    c_end = st.date_input("Data de Término", value=date.today())
                    c_desc = st.text_area("Regulamento e Diretrizes da Liga")
                    
                    if st.form_submit_button("🚀 Publicar Competição"):
                        if not c_name:
                            st.error("Informe o nome da competição.")
                        else:
                            new_comp = Competition(
                                name=c_name,
                                initial_cash=c_cash,
                                start_date=datetime.combine(c_start, datetime.min.time()),
                                end_date=datetime.combine(c_end, datetime.max.time()),
                                description=c_desc,
                                is_active=True
                            )
                            db.add(new_comp)
                            db.commit()
                            st.success(f"Competição '{c_name}' criada com sucesso!")
                            st.rerun()

                st.markdown("---")
                st.subheader("2. Editar ou Excluir Competições")
                all_comps_manage = db.query(Competition).all()
                if all_comps_manage:
                    comp_options = {f"ID {c.id} - {c.name}": c.id for c in all_comps_manage}
                    selected_edit_comp_str = st.selectbox("Selecione a Competição", list(comp_options.keys()))
                    target_comp = db.query(Competition).filter(Competition.id == comp_options[selected_edit_comp_str]).first()

                    if target_comp:
                        with st.form("form_edit_competition_hub"):
                            edit_name = st.text_input("Nome da Competição", value=target_comp.name)
                            edit_cash = st.number_input("Capital Inicial (R$)", value=float(target_comp.initial_cash), step=10000.0)
                            edit_start = st.date_input("Data de Início", value=target_comp.start_date.date())
                            edit_end = st.date_input("Data de Fim", value=target_comp.end_date.date())
                            edit_active = st.checkbox("Competição Ativa", value=target_comp.is_active)
                            edit_desc = st.text_area("Regulamento", value=target_comp.description or "")

                            col_save, col_del = st.columns([1, 1])
                            save_btn = col_save.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                            delete_btn = col_del.form_submit_button("🗑️ Excluir Competição", use_container_width=True)

                            if save_btn:
                                target_comp.name = edit_name
                                target_comp.initial_cash = edit_cash
                                target_comp.start_date = datetime.combine(edit_start, datetime.min.time())
                                target_comp.end_date = datetime.combine(edit_end, datetime.max.time())
                                target_comp.is_active = edit_active
                                target_comp.description = edit_desc
                                db.commit()
                                st.success("Competição atualizada!")
                                st.rerun()

                            if delete_btn:
                                db.delete(target_comp)
                                db.commit()
                                st.warning(f"Competição '{target_comp.name}' excluída.")
                                st.rerun()

            # 3. TURMAS
            with admin_sub_tabs[2]:
                st.subheader("1. Cadastrar Nova Turma")
                with st.form("form_add_turma_hub"):
                    t_name = st.text_input("Nome da Turma (Ex.: Mercado Financeiro - Turma 01)").strip()
                    t_sem = st.text_input("Semestre (Ex.: 2026.2)").strip()
                    if st.form_submit_button("Cadastrar Turma"):
                        if t_name:
                            new_t = Classroom(name=t_name, semester=t_sem)
                            db.add(new_t)
                            db.commit()
                            st.success(f"Turma '{t_name}' cadastrada com sucesso!")
                            st.rerun()

                st.markdown("---")
                st.subheader("2. Editar ou Excluir Turmas")
                all_turmas_manage = db.query(Classroom).all()
                if all_turmas_manage:
                    sorted_turmas = sorted(all_turmas_manage, key=lambda t: normalize_text(t.name))
                    t_dict = {f"ID {t.id} - {t.name} ({t.semester or 'S/S'})": t.id for t in sorted_turmas}
                    sel_turma_str = st.selectbox("Selecione a Turma", list(t_dict.keys()))
                    target_turma = db.query(Classroom).filter(Classroom.id == t_dict[sel_turma_str]).first()

                    if target_turma:
                        with st.form("form_edit_turma_hub"):
                            t_edit_name = st.text_input("Nome da Turma", value=target_turma.name)
                            t_edit_sem = st.text_input("Semestre", value=target_turma.semester or "")
                            c_t_save, c_t_del = st.columns([1, 1])
                            btn_t_save = c_t_save.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                            btn_t_del = c_t_del.form_submit_button("🗑️ Excluir Turma", use_container_width=True)

                            if btn_t_save:
                                target_turma.name = t_edit_name
                                target_turma.semester = t_edit_sem
                                db.commit()
                                st.success("Turma atualizada!")
                                st.rerun()

                            if btn_t_del:
                                db.delete(target_turma)
                                db.commit()
                                st.warning(f"Turma '{target_turma.name}' removida.")
                                st.rerun()

            # 4. PARTICIPANTES DA LIGA
            with admin_sub_tabs[3]:
                st.subheader("Remover Participante de uma Competição")
                if all_registered_comps:
                    comp_parts_dict = {f"ID {c.id} - {c.name}": c.id for c in all_registered_comps}
                    sel_c_part_str = st.selectbox("Selecione a Competição", list(comp_parts_dict.keys()), key="sel_c_part")
                    
                    target_c_parts = db.query(Participant).filter(Participant.competition_id == comp_parts_dict[sel_c_part_str]).all()
                    sorted_target_c_parts = sorted(target_c_parts, key=lambda p: normalize_text(p.user.name))

                    if sorted_target_c_parts:
                        p_remove_dict = {
                            f"{p.user.name} (Matrícula: {p.user.registration_id or 'S/M'} | ID Inscrição: {p.id})": p.id 
                            for p in sorted_target_c_parts
                        }
                        sel_p_rem_str = st.selectbox("Selecione o Participante para Remover", list(p_remove_dict.keys()))
                        
                        if st.button("🗑️ Excluir Participante desta Liga", type="secondary"):
                            target_p_to_remove = db.query(Participant).filter(Participant.id == p_remove_dict[sel_p_rem_str]).first()
                            if target_p_to_remove:
                                db.delete(target_p_to_remove)
                                db.commit()
                                st.warning("Participante removido da competição.")
                                st.rerun()
                    else:
                        st.info("Nenhum participante inscrito nesta competição.")

            # 5. GESTÃO DE USUÁRIOS
            with admin_sub_tabs[4]:
                st.subheader("1. Promover / Revogar Perfil de Organizador")
                all_users_global = db.query(User).all()
                sorted_users_global = sorted(all_users_global, key=lambda u: normalize_text(u.name))
                
                user_list_promo = [
                    f"{u.name} (Matrícula: {u.registration_id or 'S/M'} | E-mail: {u.email})" 
                    for u in sorted_users_global
                ]
                
                c_u1, c_u2 = st.columns([3, 1])
                sel_u_str = c_u1.selectbox("Selecione o Usuário (Ordem Alfabética)", user_list_promo if user_list_promo else ["Nenhum"])
                if sel_u_str != "Nenhum":
                    target_email = sel_u_str.split("E-mail: ")[-1].replace(")", "").strip()
                    target_u = db.query(User).filter(User.email == target_email).first()
                    if target_u:
                        btn_lbl = "Revogar Perfil de Organizador" if target_u.is_admin else "Promover a Organizador"
                        if c_u2.button(btn_lbl, use_container_width=True):
                            if target_u.email.lower() == SUPER_ADMIN_EMAIL.lower():
                                st.error("Não é permitido alterar as permissões do Organizador Principal.")
                            else:
                                target_u.is_admin = not target_u.is_admin
                                db.commit()
                                st.success("Permissão atualizada com sucesso!")
                                st.rerun()

                st.markdown("---")
                st.subheader("2. Editar ou Excluir Cadastro Global de Usuário")
                if sorted_users_global:
                    user_edit_dict = {
                        f"{u.name} (Matrícula: {u.registration_id or 'S/M'} | E-mail: {u.email})": u.id 
                        for u in sorted_users_global
                    }
                    sel_user_edit_str = st.selectbox("Selecione o Usuário para Editar/Excluir (Ordem Alfabética)", list(user_edit_dict.keys()))
                    target_edit_user = db.query(User).filter(User.id == user_edit_dict[sel_user_edit_str]).first()

                    if target_edit_user:
                        with st.form("form_edit_user_global_hub"):
                            u_name_edit = st.text_input("Nome Completo", value=target_edit_user.name)
                            u_mat_edit = st.text_input("Matrícula", value=target_edit_user.registration_id or "")
                            u_email_edit = st.text_input("E-mail", value=target_edit_user.email)
                            
                            all_turmas_u = db.query(Classroom).all()
                            sorted_turmas_edit = sorted(all_turmas_u, key=lambda t: normalize_text(t.name))
                            turma_opts = {f"{c.name} ({c.semester or 'S/S'})": c.id for c in sorted_turmas_edit}
                            
                            curr_t_idx = 0
                            if target_edit_user.classroom_id:
                                for idx, t_id in enumerate(turma_opts.values()):
                                    if t_id == target_edit_user.classroom_id:
                                        curr_t_idx = idx
                                        break
                                        
                            u_turma_edit = st.selectbox("Turma do Usuário", list(turma_opts.keys()) if turma_opts else ["Geral"], index=curr_t_idx)

                            c_u_save, c_u_del = st.columns([1, 1])
                            btn_u_save = c_u_save.form_submit_button("💾 Salvar Dados do Usuário", use_container_width=True)
                            btn_u_del = c_u_del.form_submit_button("🗑️ Excluir Usuário do Sistema", use_container_width=True)

                            if btn_u_save:
                                target_edit_user.name = u_name_edit.strip()
                                target_edit_user.registration_id = u_mat_edit.strip()
                                target_edit_user.email = u_email_edit.lower().strip()
                                target_edit_user.classroom_id = turma_opts.get(u_turma_edit)
                                db.commit()
                                st.success("Dados do usuário atualizados!")
                                st.rerun()

                            if btn_u_del:
                                if target_edit_user.email.lower() == SUPER_ADMIN_EMAIL.lower():
                                    st.error("Não é permitido excluir o Organizador Principal.")
                                else:
                                    db.delete(target_edit_user)
                                    db.commit()
                                    st.warning("Usuário excluído permanentemente.")
                                    st.rerun()

            # 6. DIVIDENDOS E EXCEL
            with admin_sub_tabs[5]:
                c_div_l, c_div_r = st.columns(2)
                with c_div_l:
                    st.subheader("💰 Processamento de Dividendos")
                    st.caption("Credita proventos pagos na B3 no saldo dos alunos com trava anti-duplicidade.")
                    if st.button("Executar Crédito de Dividendos da B3", use_container_width=True):
                        all_active_positions = db.query(Position).filter(Position.quantity > 0).all()
                        credited_count = 0
                        total_div_amount = 0.0

                        for pos in all_active_positions:
                            divs = get_recent_dividends(pos.ticker, days=30)
                            for div in divs:
                                div_date = div["date"]
                                already_paid = db.query(DividendPayment).filter(
                                    DividendPayment.participant_id == pos.participant_id,
                                    DividendPayment.ticker == pos.ticker,
                                    DividendPayment.payment_date == div_date
                                ).first()

                                if not already_paid:
                                    payout = pos.quantity * div["amount"]
                                    pos.participant.cash_balance += payout
                                    
                                    new_payment = DividendPayment(
                                        participant_id=pos.participant_id,
                                        ticker=pos.ticker,
                                        payment_date=div_date,
                                        amount_per_share=div["amount"],
                                        total_credited=payout
                                    )
                                    db.add(new_payment)
                                    credited_count += 1
                                    total_div_amount += payout
                        
                        db.commit()
                        if credited_count > 0:
                            st.success(f"Sucesso! {credited_count} provento(s) creditados somando R$ {total_div_amount:,.2f}.")
                        else:
                            st.info("Nenhum dividendo pendente para creditar.")
                        st.rerun()

                with c_div_r:
                    st.subheader("📥 Exportação de Relatórios Gerais")
                    st.caption("Baixe uma planilha Excel consolidada de todas as competições e ordens.")
                    
                    all_exp_parts = db.query(Participant).all()
                    export_ranking = []
                    for p in all_exp_parts:
                        eq_inv = sum((get_stock_price(pos.ticker) or pos.avg_price) * pos.quantity for pos in p.positions)
                        tot = p.cash_balance + eq_inv
                        export_ranking.append({
                            "Competição": p.competition.name,
                            "Aluno": p.user.name,
                            "Matrícula": p.user.registration_id,
                            "Turma": p.user.classroom.name if p.user.classroom else "Geral",
                            "E-mail": p.user.email,
                            "Patrimônio Final (R$)": tot,
                            "Saldo Caixa (R$)": p.cash_balance,
                            "Total Investido (R$)": eq_inv,
                            "Rentabilidade (%)": ((tot / p.competition.initial_cash) - 1) * 100
                        })
                    
                    df_exp_rank = pd.DataFrame(export_ranking)
                    
                    all_ords = db.query(Order).all()
                    df_exp_ords = pd.DataFrame([{
                        "Data/Hora": o.created_at.strftime("%d/%m/%Y %H:%M"),
                        "Competição": o.participant.competition.name,
                        "Aluno": o.participant.user.name,
                        "Matrícula": o.participant.user.registration_id,
                        "E-mail": o.participant.user.email,
                        "Operação": o.side,
                        "Ticker": o.ticker,
                        "Qtd": o.quantity,
                        "Preço": o.execution_price,
                        "Volume Total (R$)": o.quantity * (o.execution_price or 0.0)
                    } for o in all_ords])

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_exp_rank.to_excel(writer, sheet_name='Ranking_Consolidado', index=False)
                        df_exp_ords.to_excel(writer, sheet_name='Historico_Ordens', index=False)
                    
                    st.download_button(
                        label="📊 Baixar Relatório Completo (.xlsx)",
                        data=buffer.getvalue(),
                        file_name=f"investufrn_relatorio_geral_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

            # 7. LOG DE AUDITORIA
            with admin_sub_tabs[6]:
                st.subheader("Auditoria Geral de Ordens Transmitidas")
                orders_audit = db.query(Order).order_by(Order.created_at.desc()).all()
                if orders_audit:
                    audit_data = [{
                        "Data/Hora": o.created_at.strftime("%d/%m/%Y %H:%M"),
                        "Competição": o.participant.competition.name,
                        "Discente": o.participant.user.name,
                        "Matrícula": o.participant.user.registration_id,
                        "Turma": o.participant.user.classroom.name if o.participant.user.classroom else "Geral",
                        "Operação": o.side,
                        "Ticker": o.ticker,
                        "Qtd": o.quantity,
                        "Preço": f"R$ {o.execution_price:.2f}"
                    } for o in orders_audit]
                    st.dataframe(pd.DataFrame(audit_data), use_container_width=True)
                else:
                    st.info("Nenhuma ordem transmitida até o momento.")

# ==============================================================================
# FLUXO 2: TELA DA COMPETIÇÃO ATIVA (RANKING, CARTEIRA E MESA DE OPERAÇÕES)
# ==============================================================================
else:
    active_comp = db.query(Competition).filter(Competition.id == st.session_state.active_comp_id).first()
    active_part = db.query(Participant).filter(
        Participant.competition_id == st.session_state.active_comp_id,
        Participant.user_id == user_data["id"]
    ).first()

    if not active_comp:
        st.session_state.active_comp_id = None
        st.rerun()

    col_hdr_title, col_hdr_btn = st.columns([4, 1])
    with col_hdr_title:
        st.title(f"🏆 {active_comp.name}")
        st.caption(f"📅 Vigência: {active_comp.start_date.strftime('%d/%m/%Y')} a {active_comp.end_date.strftime('%d/%m/%Y')} | Status: {'🟢 Ativa' if active_comp.is_active else '🔴 Encerrada'}")
    with col_hdr_btn:
        st.write("")
        if st.button("⬅️ Trocar / Voltar ao Hub", type="secondary", use_container_width=True):
            st.session_state.active_comp_id = None
            st.rerun()

    with st.expander("📜 Regulamento e Diretrizes da Competição"):
        st.markdown(active_comp.description or "Sem regras cadastradas.")
        st.write(f"**Capital Inicial:** R$ {active_comp.initial_cash:,.2f}")

    st.markdown("---")

    comp_tabs = st.tabs(["📊 Ranking da Liga", "💼 Minha Carteira", "⚡ Mesa de Operações"])

    # --- ABA 1: RANKING DA LIGA ---
    with comp_tabs[0]:
        st.subheader("Classificação Geral da Liga")
        all_participants = db.query(Participant).filter(Participant.competition_id == active_comp.id).all()
        ranking_data = []

        for part in all_participants:
            equity_invested = 0.0
            for pos in part.positions:
                curr_price = get_stock_price(pos.ticker) or pos.avg_price
                equity_invested += pos.quantity * curr_price
            
            total_wealth = part.cash_balance + equity_invested
            ret_pct = ((total_wealth / active_comp.initial_cash) - 1) * 100
            
            is_self_or_admin = (part.user_id == user_data["id"] or user_data["is_admin"])
            turma_name = part.user.classroom.name if part.user.classroom else "Geral"
            
            ranking_data.append({
                "Participante": part.user.name if is_self_or_admin else f"Participante #{part.id}",
                "Turma": turma_name,
                "Patrimônio Total": total_wealth,
                "Rentabilidade (%)": ret_pct,
                "Saldo em Caixa": part.cash_balance,
                "Total Investido": equity_invested
            })

        if ranking_data:
            df_ranking = pd.DataFrame(ranking_data).sort_values(by="Patrimônio Total", ascending=False).reset_index(drop=True)
            df_ranking.index += 1
            st.dataframe(
                df_ranking.style.format({
                    "Patrimônio Total": "R$ {:,.2f}",
                    "Saldo em Caixa": "R$ {:,.2f}",
                    "Total Investido": "R$ {:,.2f}",
                    "Rentabilidade (%)": "{:+.2f}%"
                }),
                use_container_width=True
            )
        else:
            st.info("Nenhum participante inscrito nesta competição ainda.")

    # --- ABA 2: MINHA CARTEIRA ---
    with comp_tabs[1]:
        if not active_part:
            st.warning("Você não está formalmente inscrito nesta liga.")
        else:
            st.subheader("Minha Custódia e Patrimônio")
            positions = db.query(Position).filter(Position.participant_id == active_part.id, Position.quantity > 0).all()
            
            total_invested = 0.0
            pos_data = []
            
            for pos in positions:
                curr_price = get_stock_price(pos.ticker) or pos.avg_price
                pos_total = pos.quantity * curr_price
                total_invested += pos_total
                pl_pct = ((curr_price / pos.avg_price) - 1) * 100 if pos.avg_price > 0 else 0.0
                
                pos_data.append({
                    "Ticker": pos.ticker,
                    "Quantidade": pos.quantity,
                    "Preço Médio": pos.avg_price,
                    "Cotação Atual": curr_price,
                    "Total na Posição": pos_total,
                    "Resultado (%)": pl_pct
                })

            total_wealth = active_part.cash_balance + total_invested
            total_return = ((total_wealth / active_comp.initial_cash) - 1) * 100

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Patrimônio Total", f"R$ {total_wealth:,.2f}", delta=f"{total_return:+.2f}%")
            c2.metric("Saldo em Caixa", f"R$ {active_part.cash_balance:,.2f}")
            c3.metric("Total em Ações", f"R$ {total_invested:,.2f}")
            c4.metric("Capital Inicial", f"R$ {active_comp.initial_cash:,.2f}")

            st.markdown("---")
            col_c1, col_c2 = st.columns([3, 2])
            
            with col_c1:
                st.subheader("Ações em Carteira")
                if pos_data:
                    df_pos = pd.DataFrame(pos_data)
                    st.dataframe(
                        df_pos.style.format({
                            "Preço Médio": "R$ {:,.2f}",
                            "Cotação Atual": "R$ {:,.2f}",
                            "Total na Posição": "R$ {:,.2f}",
                            "Resultado (%)": "{:+.2f}%"
                        }),
                        use_container_width=True
                    )
                else:
                    st.info("Nenhuma ação em custódia. Envie ordens de compra na **Mesa de Operações**.")

            with col_c2:
                st.subheader("Alocação Patrimonial")
                if pos_data:
                    alloc_df = pd.DataFrame(pos_data)[["Ticker", "Total na Posição"]]
                    alloc_df.loc[len(alloc_df)] = ["Caixa Disponível", active_part.cash_balance]
                    fig = px.pie(alloc_df, names="Ticker", values="Total na Posição", hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.write("100% em Caixa Disponível.")

    # --- ABA 3: MESA DE OPERAÇÕES (BOTÕES NATIVOS COM BOLINHAS VERDE E VERMELHA) ---
    with comp_tabs[2]:
        st.subheader("Mesa de Negociação (B3)")
        if not active_part:
            st.warning("Inscreva-se na competição para emitir ordens.")
        else:
            ticker = st.text_input("Código do Ativo (Ex.: PETR4, VALE3, ITUB4, WEGE3)").strip().upper()
            
            if ticker:
                curr_price = get_stock_price(ticker)
                if not curr_price:
                    st.error(f"Não foi possível localizar cotação para '{ticker}'. Verifique se o código está correto.")
                else:
                    c_chart, c_boleta = st.columns([2, 1])
                    
                    with c_chart:
                        st.subheader(f"{ticker} — Cotação Atual: R$ {curr_price:.2f}")
                        hist = get_historical_data(ticker)
                        if not hist.empty:
                            fig = go.Figure(data=[go.Candlestick(
                                x=hist.index, open=hist['Open'], high=hist['High'],
                                low=hist['Low'], close=hist['Close'], name=ticker
                            )])
                            fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0))
                            st.plotly_chart(fig, use_container_width=True)

                    with c_boleta:
                        st.subheader("⚡ Boleta de Negociação")
                        st.caption(f"Cotação a Mercado: **R$ {curr_price:.2f}**")
                        
                        # Seletor de Quantidade com step=100
                        qty = st.number_input(
                            "Quantidade de Ações", 
                            min_value=1, 
                            step=100, 
                            value=100
                        )

                        total_order = qty * curr_price
                        
                        st.markdown(f"#### Total: **R$ {total_order:,.2f}**")
                        st.caption(f"Saldo em Caixa: R$ {active_part.cash_balance:,.2f}")
                        
                        # Botões com Bolinhas 🟢 COMPRAR e 🔴 VENDER
                        col_buy, col_sell = st.columns(2)
                        
                        btn_buy = col_buy.button("🟢 COMPRAR", use_container_width=True, key="btn_buy_stock")
                        btn_sell = col_sell.button("🔴 VENDER", use_container_width=True, key="btn_sell_stock")

                        # Execução de Compra
                        if btn_buy:
                            if not active_comp.is_active:
                                st.error("Esta competição está inativa ou encerrada para novas ordens.")
                            elif active_part.cash_balance < total_order:
                                st.error("Saldo em caixa insuficiente para efetuar esta compra.")
                            else:
                                active_part.cash_balance -= total_order
                                pos = db.query(Position).filter(Position.participant_id == active_part.id, Position.ticker == ticker).first()
                                if not pos:
                                    pos = Position(participant_id=active_part.id, ticker=ticker, quantity=qty, avg_price=curr_price)
                                    db.add(pos)
                                else:
                                    new_qty = pos.quantity + qty
                                    pos.avg_price = ((pos.quantity * pos.avg_price) + total_order) / new_qty
                                    pos.quantity = new_qty
                                
                                db.add(Order(
                                    participant_id=active_part.id, ticker=ticker, side="BUY",
                                    order_type="MARKET", quantity=qty,
                                    target_price=curr_price, execution_price=curr_price
                                ))
                                db.commit()
                                st.toast(f"✅ Ordem enviada: Compra de {qty}x {ticker} a R$ {curr_price:.2f}!")
                                st.success("Ordem enviada com sucesso!")
                                st.rerun()

                        # Execução de Venda
                        if btn_sell:
                            if not active_comp.is_active:
                                st.error("Esta competição está inativa ou encerrada para novas ordens.")
                            else:
                                pos = db.query(Position).filter(Position.participant_id == active_part.id, Position.ticker == ticker).first()
                                if not pos or pos.quantity < qty:
                                    st.error("Quantidade de ativos insuficiente em custódia para realizar a venda.")
                                else:
                                    active_part.cash_balance += total_order
                                    pos.quantity -= qty
                                    db.add(Order(
                                        participant_id=active_part.id, ticker=ticker, side="SELL",
                                        order_type="MARKET", quantity=qty,
                                        target_price=curr_price, execution_price=curr_price
                                    ))
                                    db.commit()
                                    st.toast(f"✅ Ordem enviada: Venda de {qty}x {ticker} a R$ {curr_price:.2f}!")
                                    st.success("Ordem enviada com sucesso!")
                                    st.rerun()

            st.markdown("---")
            # --- HISTÓRICO DAS 10 ÚLTIMAS ORDENS ---
            st.subheader("📜 Minhas Últimas 10 Ordens na Competição")
            recent_orders = db.query(Order).filter(
                Order.participant_id == active_part.id
            ).order_by(Order.created_at.desc()).limit(10).all()

            if recent_orders:
                orders_table_data = [{
                    "Data e Hora": o.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                    "Operação": "COMPRA" if o.side == "BUY" else "VENDA",
                    "Ativo": o.ticker,
                    "Quantidade": o.quantity,
                    "Preço Executado": f"R$ {o.execution_price:.2f}",
                    "Volume Total": f"R$ {(o.quantity * o.execution_price):,.2f}",
                    "Status": "Executada"
                } for o in recent_orders]
                st.dataframe(pd.DataFrame(orders_table_data), use_container_width=True, hide_index=True)
            else:
                st.info("Você ainda não transmitiu nenhuma ordem nesta competição.")

db.close()