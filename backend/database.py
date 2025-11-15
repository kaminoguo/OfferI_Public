"""
Database setup for PostgreSQL with SQLAlchemy
Manages:
- Web consultations: $6 payment per report (via Stripe)
- MCP API access: 10 free consultations/month + super keys for unlimited
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, Enum, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
import secrets

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
    """Payment table - supports 3 tiers: basic ($9), advanced ($49.99), update ($39.99)"""
    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True)  # Stripe payment intent ID
    user_id = Column(String, index=True, nullable=False)  # Clerk user ID
    amount = Column(Float, default=9.00, nullable=False)  # Tier-based pricing
    tier = Column(String, default='basic', nullable=False)  # basic/advanced/update
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PAID, nullable=False)
    job_id = Column(String, nullable=True, index=True)  # Job ID when report generation starts
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class APIKey(Base):
    """API keys for MCP API access

    Regular keys: 10 free consultations/month
    Super keys: Unlimited consultations (for testing/B2B)
    """
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, index=True)  # API key (e.g., "sk_live_...")
    user_id = Column(String, index=True, nullable=False)  # Clerk user ID
    name = Column(String, nullable=True)  # User-given name (e.g., "Production Key")
    is_super_key = Column(Boolean, default=False, nullable=False)  # True = unlimited access
    is_active = Column(Boolean, default=True, nullable=False)  # False = revoked
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)  # Last API call timestamp


class MCPUsage(Base):
    """Track monthly MCP API usage (for non-super keys)

    10 free consultations per month per user
    """
    __tablename__ = "mcp_usage"

    id = Column(String, primary_key=True, index=True)  # Format: {user_id}_{year}_{month}
    user_id = Column(String, index=True, nullable=False)  # Clerk user ID
    year = Column(Integer, nullable=False)  # Year (e.g., 2025)
    month = Column(Integer, nullable=False)  # Month (1-12)
    usage_count = Column(Integer, default=0, nullable=False)  # Number of consultations used
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


def generate_api_key(prefix="sk_live"):
    """Generate a secure API key"""
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def get_or_create_mcp_usage(db, user_id: str) -> MCPUsage:
    """Get or create MCP usage record for current month"""
    now = datetime.utcnow()
    year = now.year
    month = now.month
    usage_id = f"{user_id}_{year}_{month}"

    usage = db.query(MCPUsage).filter(MCPUsage.id == usage_id).first()

    if not usage:
        usage = MCPUsage(
            id=usage_id,
            user_id=user_id,
            year=year,
            month=month,
            usage_count=0
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)

    return usage
