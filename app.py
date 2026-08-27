import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from database import init_db, SessionLocal, User, Competition, Participant, Position, Order
from market_data import get_stock_price, get_historical_data, generate_synthetic_book

st.set_page_config(page_title="InvestUFRN App", layout="wide", page_icon="📈")
init_db()

# --- CONFIGURAÇÃO DE E-MAILS DE ORGANIZADORES/ADMINISTRADORES ---
# Insira os e-mails institucionais que terão acesso ao painel de criação de ligas e auditoria
ADMIN_EMAILS = ["renato.mota@ufrn.br", "admin@ufrn.br"]

if "user" not in st.session_state:
    st.session_state.user = None

def login_sidebar():
    with st.sidebar:
        st.title("📈 InvestUFRN App")
        st.markdown("**Liga Universitária de Investimentos - UFRN**")
        st.markdown("---")
        if not st.session_state.user:
            st.subheader("Login Institucional")
            email = st.text_input("E-mail (@ufrn.br ou @academico.ufrn.br)")
            name = st.text_input("Nome Completo")
            if st.button("Entrar", use_container_width=True):
                clean_email = email.strip().lower()
                if clean_email and ("@ufrn.br" in clean_email or "@academico.ufrn.br" in clean_email):
                    db = SessionLocal()
                    user = db.query(User).filter(User.email == clean_email).first()
                    is_admin = clean_email in [a.lower() for a in ADMIN_EMAILS]
                    if not user:
                        user = User(email=clean_email, name=name.strip(), is_admin=is_admin)
                        db.add(user)
                        db.commit()
                        db.refresh(user)
                    st.session_state.user = {"id": user.id, "email": user.email, "name": user.name, "is_admin": user.is_admin}
                    db.close()
                    st.rerun()
                else:
                    st.error("Utilize um e-mail institucional válido (@ufrn.br ou @academico.ufrn.br).")
        else:
            st.write(f"Conectado como: **{st.session_state.user['name']}**")
            st.caption(f"Perfil: {'Organizador (Admin)' if st.session_state.user['is_admin'] else 'Discente'}")
            if st.button("Sair", use_container_width=True):
                st.session_state.user = None
                st.rerun()

login_sidebar()

if not st.session_state.user:
    st.info("👋 Faça login com seu e-mail institucional na barra lateral para acessar o InvestUFRN.")
    st.stop()

db = SessionLocal()
user_data = st.session_state.user

# Recupera competições cadastradas
competitions = db.query(Competition).all()
if not competitions and not user_data["is_admin"]:
    st.warning("Nenhuma competição ativa no momento. Aguarde a abertura da liga pelo professor.")
    db.close()
    st.stop()

comp_dict = {c.name: c.id for c in competitions}
selected_comp_name = st.sidebar.selectbox("Competição", list(comp_dict.keys())) if comp_dict else None
current_comp = db.query(Competition).filter(Competition.id == comp_dict[selected_comp_name]).first() if selected_comp_name else None

# Inscrição automática do aluno na competição selecionada
current_participant = None
if current_comp:
    current_participant = db.query(Participant).filter(
        Participant.competition_id == current_comp.id,
        Participant.user_id == user_data["id"]
    ).first()

    if not current_participant:
        current_participant = Participant(
            competition_id=current_comp.id,
            user_id=user_data["id"],
            cash_balance=current_comp.initial_cash
        )
        db.add(current_participant)
        db.commit()
        db.refresh(current_participant)

# Abas de Navegação
tabs = ["📊 Ranking Geral", "💼 Minha Carteira", "⚡ Negociação de Ativos"]
if user_data["is_admin"]:
    tabs.append("⚙️ Painel do Organizador")

active_tab = st.radio("Navegação", tabs, horizontal=True, label_visibility="collapsed")
st.markdown("---")

# ==========================================
# ABA 1: RANKING GERAL (SEM EXPOR CARTEIRAS ALHEIAS)
# ==========================================
if active_tab == "📊 Ranking Geral":
    if not current_comp:
        st.info("Nenhuma competição selecionada.")
        st.stop()

    st.header(f"🏆 Ranking Geral — {current_comp.name}")
    st.caption(f"Vigência: {current_comp.start_date.strftime('%d/%m/%Y')} a {current_comp.end_date.strftime('%d/%m/%Y')} | Critério: Riqueza Total Acumulada")

    with st.expander("📜 Regulamento e Diretrizes da Competição"):
        st.markdown(current_comp.description or "Sem regras cadastradas.")

    all_participants = db.query(Participant).filter(Participant.competition_id == current_comp.id).all()
    ranking_data = []

    for part in all_participants:
        equity_invested = 0.0
        for pos in part.positions:
            curr_price = get_stock_price(pos.ticker) or pos.avg_price
            equity_invested += pos.quantity * curr_price
        
        total_wealth = part.cash_balance + equity_invested
        ret_pct = ((total_wealth / current_comp.initial_cash) - 1) * 100
        
        ranking_data.append({
            "Participante": part.user.name if (part.user_id == user_data["id"] or user_data["is_admin"]) else f"Discente #{part.id}",
            "Patrimônio Total (R$)": total_wealth,
            "Rentabilidade (%)": ret_pct,
            "Saldo em Caixa (R$)": part.cash_balance,
            "Total Investido (R$)": equity_invested
        })

    df_ranking = pd.DataFrame(ranking_data).sort_values(by="Patrimônio Total (R$)", ascending=False).reset_index(drop=True)
    df_ranking.index += 1
    
    st.dataframe(
        df_ranking.style.format({
            "Patrimônio Total (R$)": "R$ {:,.2f}",
            "Saldo em Caixa (R$)": "R$ {:,.2f}",
            "Total Investido (R$)": "R$ {:,.2f}",
            "Rentabilidade (%)": "{:+.2f}%"
        }),
        use_container_width=True
    )

# ==========================================
# ABA 2: MINHA CARTEIRA
# ==========================================
elif active_tab == "💼 Minha Carteira":
    if not current_participant:
        st.stop()

    st.header("💼 Painel da Minha Carteira")
    positions = db.query(Position).filter(Position.participant_id == current_participant.id, Position.quantity > 0).all()
    
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
            "Preço Médio (R$)": pos.avg_price,
            "Cotação Atual (R$)": curr_price,
            "Total na Posição (R$)": pos_total,
            "Lucro/Prejuízo (%)": pl_pct
        })

    total_wealth = current_participant.cash_balance + total_invested
    total_return = ((total_wealth / current_comp.initial_cash) - 1) * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Patrimônio Total", f"R$ {total_wealth:,.2f}", delta=f"{total_return:+.2f}%")
    col2.metric("Saldo em Caixa", f"R$ {current_participant.cash_balance:,.2f}")
    col3.metric("Capital Investido", f"R$ {total_invested:,.2f}")
    col4.metric("Capital Inicial", f"R$ {current_comp.initial_cash:,.2f}")

    st.markdown("---")
    c_left, c_right = st.columns([3, 2])
    
    with c_left:
        st.subheader("Ativos em Custódia")
        if pos_data:
            df_pos = pd.DataFrame(pos_data)
            st.dataframe(
                df_pos.style.format({
                    "Preço Médio (R$)": "R$ {:,.2f}",
                    "Cotação Atual (R$)": "R$ {:,.2f}",
                    "Total na Posição (R$)": "R$ {:,.2f}",
                    "Lucro/Prejuízo (%)": "{:+.2f}%"
                }),
                use_container_width=True
            )
        else:
            st.info("Você ainda não possui ativos comprados. Vá até a aba 'Negociação de Ativos'.")

    with c_right:
        st.subheader("Alocação Patrimonial")
        if pos_data:
            alloc_df = pd.DataFrame(pos_data)[["Ticker", "Total na Posição (R$)"]]
            alloc_df.loc[len(alloc_df)] = ["Caixa", current_participant.cash_balance]
            fig = px.pie(alloc_df, names="Ticker", values="Total na Posição (R$)", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("100% do capital disponível em Caixa.")

# ==========================================
# ABA 3: NEGOCIAÇÃO DE ATIVOS
# ==========================================
elif active_tab == "⚡ Negociação de Ativos":
    st.header("⚡ Mesa de Operações (B3)")
    ticker = st.text_input("Ticker do Ativo (Ex.: PETR4, VALE3, ITUB4, WEGE3)").strip().upper()
    
    if ticker:
        curr_price = get_stock_price(ticker)
        if not curr_price:
            st.error(f"Não foi possível localizar cotações para o ticker '{ticker}'. Verifique se o código está correto.")
        else:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader(f"{ticker} — Cotação de Mercado: R$ {curr_price:.2f}")
                hist = get_historical_data(ticker)
                if not hist.empty:
                    fig = go.Figure(data=[go.Candlestick(
                        x=hist.index, open=hist['Open'], high=hist['High'],
                        low=hist['Low'], close=hist['Close'], name=ticker
                    )])
                    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
                    st.plotly_chart(fig, use_container_width=True)
            
            with c2:
                st.subheader("Book de Ofertas")
                bids_df, asks_df = generate_synthetic_book(ticker, curr_price)
                st.caption("Ofertas de Venda (Asks)")
                st.dataframe(asks_df, use_container_width=True, hide_index=True)
                st.caption("Ofertas de Compra (Bids)")
                st.dataframe(bids_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("Boleta de Negociação")
            b1, b2, b3, b4 = st.columns(4)
            side = b1.selectbox("Operação", ["BUY (Compra)", "SELL (Venda)"])
            order_type = b2.selectbox("Tipo de Ordem", ["MARKET (A Mercado)", "LIMIT (Limitada)", "STOP (Stop Loss)"])
            qty = b3.number_input("Quantidade de Ações", min_value=1, step=100, value=100)
            target_price = b4.number_input("Preço da Ordem (R$)", min_value=0.01, value=float(curr_price), step=0.05) if "MARKET" not in order_type else curr_price

            total_order = qty * target_price
            st.write(f"**Volume Financeiro da Ordem:** R$ {total_order:,.2f}")

            if st.button("Transmitir Ordem", use_container_width=True):
                is_buy = "BUY" in side
                if is_buy:
                    if current_participant.cash_balance < total_order:
                        st.error("Saldo em caixa insuficiente para executar esta compra.")
                    else:
                        current_participant.cash_balance -= total_order
                        pos = db.query(Position).filter(Position.participant_id == current_participant.id, Position.ticker == ticker).first()
                        if not pos:
                            pos = Position(participant_id=current_participant.id, ticker=ticker, quantity=qty, avg_price=target_price)
                            db.add(pos)
                        else:
                            new_qty = pos.quantity + qty
                            pos.avg_price = ((pos.quantity * pos.avg_price) + total_order) / new_qty
                            pos.quantity = new_qty
                        
                        db.add(Order(participant_id=current_participant.id, ticker=ticker, side="BUY", order_type=order_type.split()[0], quantity=qty, target_price=target_price, execution_price=target_price))
                        db.commit()
                        st.success(f"Ordem de COMPRA de {qty}x {ticker} executada com sucesso a R$ {target_price:.2f}!")
                        st.rerun()
                else: # SELL
                    pos = db.query(Position).filter(Position.participant_id == current_participant.id, Position.ticker == ticker).first()
                    if not pos or pos.quantity < qty:
                        st.error("Quantidade em carteira insuficiente para realizar esta venda.")
                    else:
                        current_participant.cash_balance += total_order
                        pos.quantity -= qty
                        db.add(Order(participant_id=current_participant.id, ticker=ticker, side="SELL", order_type=order_type.split()[0], quantity=qty, target_price=target_price, execution_price=target_price))
                        db.commit()
                        st.success(f"Ordem de VENDA de {qty}x {ticker} executada com sucesso!")
                        st.rerun()

# ==========================================
# ABA 4: PAINEL DO ORGANIZADOR (PROFESSOR)
# ==========================================
elif active_tab == "⚙️ Painel do Organizador" and user_data["is_admin"]:
    st.header("⚙️ Painel de Gestão do Organizador")
    with st.form("new_comp"):
        st.subheader("Criar Nova Competição")
        c_name = st.text_input("Nome da Competição (Ex.: Liga de Finanças UFRN 2026.2)")
        c_cash = st.number_input("Capital Inicial por Aluno (R$)", value=100000.0, step=10000.0)
        c_start = st.date_input("Data de Início")
        c_end = st.date_input("Data de Término")
        c_desc = st.text_area("Regulamento / Limites Operacionais (Ex.: Máximo 25% em uma única ação)")
        if st.form_submit_button("Publicar Competição"):
            new_c = Competition(
                name=c_name, initial_cash=c_cash,
                start_date=datetime.combine(c_start, datetime.min.time()),
                end_date=datetime.combine(c_end, datetime.max.time()),
                description=c_desc, is_active=True
            )
            db.add(new_c)
            db.commit()
            st.success("Competição criada com sucesso!")
            st.rerun()

    st.markdown("---")
    st.subheader("Auditoria de Transações de Todos os Alunos")
    orders_audit = db.query(Order).order_by(Order.created_at.desc()).all()
    if orders_audit:
        audit_data = [{
            "Data": o.created_at.strftime("%d/%m/%Y %H:%M"),
            "Discente": o.participant.user.name,
            "E-mail": o.participant.user.email,
            "Operação": o.side,
            "Ticker": o.ticker,
            "Qtd": o.quantity,
            "Preço": f"R$ {o.execution_price:.2f}"
        } for o in orders_audit]
        st.dataframe(pd.DataFrame(audit_data), use_container_width=True)
    else:
        st.write("Nenhuma ordem transmitida até o momento.")

db.close()