"""
Database setup for PostgreSQL with SQLAlchemy
Manages per-consultation payments ($6 each)
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/offeri")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PaymentStatus(str, enum.Enum):
    """Payment delivery status"""
    PAID = "paid"                    # User paid, pending report generation
    DELIVERED = "delivered"          # Report successfully generated and delivered
    PENDING_RETRY = "pending_retry"  # Generation failed, allow free retry
    REFUNDED = "refunded"            # Manual refund issued


class Payment(Base):
    """Payment table - one row per $6 consultation"""
    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True)  # Stripe payment intent ID
    user_id = Column(String, index=True, nullable=False)  # Clerk user ID
    amount = Column(Float, default=6.00, nullable=False)  # Fixed $6 per consultation
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PAID, nullable=False)
    job_id = Column(String, nullable=True, index=True)  # Job ID when report generation starts
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
