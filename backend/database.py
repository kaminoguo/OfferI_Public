"""
Database setup for PostgreSQL with SQLAlchemy
Manages:
- Web consultations: $6 payment per report (via Stripe)
- MCP API access: 10 free consultations/month + super keys for unlimited
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, Enum, Integer, Boolean, ARRAY
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
    """API keys for MCP API access with tier-based access control

    Three key types:
    - Basic: Tools 1-5 (basic consultation workflow)
    - Advanced: Tools 1-7 (full workflow with deep research)
    - Upgrade: Tool upgrade_to_advanced only (internal use)

    Global shared keys for website users:
    - sk_live_basic_shared (all basic tier web users)
    - sk_live_advanced_shared (all advanced tier web users)
    - sk_live_upgrade_shared (all upgrade tier web users)

    Individual keys for institutional buyers (custom generation)
    """
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, index=True)  # API key (e.g., "sk_live_...")
    user_id = Column(String, index=True, nullable=True)  # Clerk user ID (NULL for shared keys)
    name = Column(String, nullable=True)  # Key description (e.g., "Production Key", "Basic Shared")
    tier = Column(String, nullable=False)  # 'basic', 'advanced', 'upgrade'
    allowed_tools = Column(ARRAY(String), nullable=False)  # List of tool names this key can call
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


def create_shared_api_keys(db):
    """Create three global shared API keys for website users

    Only creates keys if they don't exist (idempotent operation)
    """
    shared_keys = [
        {
            'id': 'sk_live_basic_shared',
            'name': 'Basic Tier Shared Key (Website Users) - v1.2.0',
            'tier': 'basic',
            'allowed_tools': [
                # Workflow tools v1.2.0 (6 tools)
                'start_and_select_universities',
                'select_classifications',
                'process_university_programs',
                'analyze_and_shortlist',
                'select_final_programs',
                'generate_final_report',
                # Utility tools (2 tools)
                'get_available_countries',
                'get_database_statistics'
            ]
        },
        {
            'id': 'sk_live_advanced_shared',
            'name': 'Advanced Tier Shared Key (Website Users) - v1.2.0',
            'tier': 'advanced',
            'allowed_tools': [
                # All basic tools (8 tools)
                'start_and_select_universities',
                'select_classifications',
                'process_university_programs',
                'analyze_and_shortlist',
                'select_final_programs',
                'generate_final_report',
                'get_available_countries',
                'get_database_statistics',
                # Advanced-only tool (1 tool)
                'generate_final_report_advanced'
            ]
        },
        {
            'id': 'sk_live_upgrade_shared',
            'name': 'Upgrade Tier Shared Key (Website Users)',
            'tier': 'upgrade',
            'allowed_tools': [
                'upgrade_to_advanced',  # Only upgrade tool
                'get_available_countries',
                'get_database_statistics'
            ]
        }
    ]

    for key_data in shared_keys:
        existing = db.query(APIKey).filter(APIKey.id == key_data['id']).first()
        if not existing:
            key = APIKey(**key_data, user_id=None, is_active=True)
            db.add(key)

    db.commit()
    return shared_keys


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
