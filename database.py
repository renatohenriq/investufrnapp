import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///investufrnapp.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

    participants = relationship("Participant", back_populates="competition")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    is_admin = Column(Boolean, default=False)

    participations = relationship("Participant", back_populates="user")

class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cash_balance = Column(Float, nullable=False)

    competition = relationship("Competition", back_populates="participants")
    user = relationship("User", back_populates="participations")
    orders = relationship("Order", back_populates="participant")
    positions = relationship("Position", back_populates="participant")

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
    side = Column(String(4), nullable=False) # 'BUY' ou 'SELL'
    order_type = Column(String(10), nullable=False) # 'MARKET', 'LIMIT', 'STOP'
    quantity = Column(Integer, nullable=False)
    target_price = Column(Float, nullable=True)
    execution_price = Column(Float, nullable=True)
    status = Column(String(15), default="EXECUTED")
    created_at = Column(DateTime, default=datetime.utcnow)

    participant = relationship("Participant", back_populates="orders")

def init_db():
    Base.metadata.create_all(bind=engine)