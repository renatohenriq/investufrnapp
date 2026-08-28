import os
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///investufrnapp.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def hash_password(password: str) -> str:
    """Gera hash seguro em SHA-256 para armazenamento de senhas."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha digitada confere com o hash salvo."""
    return hash_password(plain_password) == hashed_password

class Classroom(Base):
    __tablename__ = "classrooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    semester = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="classroom")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    registration_id = Column(String(30), nullable=True)
    name = Column(String(150), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    classroom = relationship("Classroom", back_populates="users")
    participations = relationship("Participant", back_populates="user", cascade="all, delete-orphan")

class Competition(Base):
    __tablename__ = "competitions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    initial_cash = Column(Float, default=100000.0)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    participants = relationship("Participant", back_populates="competition", cascade="all, delete-orphan")

class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cash_balance = Column(Float, nullable=False)

    competition = relationship("Competition", back_populates="participants")
    user = relationship("User", back_populates="participations")
    orders = relationship("Order", back_populates="participant", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="participant", cascade="all, delete-orphan")
    dividends = relationship("DividendPayment", back_populates="participant", cascade="all, delete-orphan")

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    quantity = Column(Integer, default=0)
    avg_price = Column(Float, default=0.0)

    participant = relationship("Participant", back_populates="positions")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False) # BUY / SELL
    order_type = Column(String(10), nullable=False) # MARKET / LIMIT / STOP
    quantity = Column(Integer, nullable=False)
    target_price = Column(Float, nullable=True)
    execution_price = Column(Float, nullable=True)
    status = Column(String(15), default="EXECUTED")
    created_at = Column(DateTime, default=datetime.utcnow)

    participant = relationship("Participant", back_populates="orders")

class DividendPayment(Base):
    __tablename__ = "dividend_payments"
    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    payment_date = Column(DateTime, nullable=False)
    amount_per_share = Column(Float, nullable=False)
    total_credited = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    participant = relationship("Participant", back_populates="dividends")

def init_db():
    Base.metadata.create_all(bind=engine)