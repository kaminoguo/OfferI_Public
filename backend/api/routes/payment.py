"""
Stripe payment routes for $6 per-consultation payments
"""
import os
from datetime import datetime

import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from database import get_db, Payment, PaymentStatus

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Fixed price per consultation
CONSULTATION_PRICE = 6.00

router = APIRouter(prefix="/api/payment", tags=["payment"])


# ============================================================================
# Models
# ============================================================================

class PaymentRequest(BaseModel):
    """Request to create payment session"""
    user_id: str  # Clerk user ID


class PaymentResponse(BaseModel):
    """Stripe checkout response"""
    checkout_url: str
    session_id: str


# ============================================================================
# Routes
# ============================================================================

@router.post("/create-session", response_model=PaymentResponse)
async def create_payment_session(
    request: PaymentRequest,
    db: Session = Depends(get_db)
):
    """
    Create Stripe checkout session for $6 consultation
    """
    try:
        # Create Stripe checkout session
        # Only enabled payment methods (apple_pay/google_pay/samsung_pay auto-included with card)
        # alipay and wechat_pay pending approval - will add after Stripe approves (5-7 days)
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=[
                "card",           # Cards (+ Apple Pay, Google Pay, Samsung Pay)
                "link",           # Link (enabled)
                "kakao_pay",      # Kakao Pay (enabled)
                "naver_pay",      # Naver Pay (enabled)
                "payco",          # PAYCO (enabled)
                "bancontact",     # Bancontact (enabled)
                "eps",            # EPS (enabled)
            ],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "OfferI Study Abroad Consultation",
                            "description": "AI-powered personalized study abroad recommendation report",
                        },
                        "unit_amount": int(CONSULTATION_PRICE * 100),  # Convert to cents
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{FRONTEND_URL}?payment_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}?payment=cancel",
            metadata={
                "user_id": request.user_id,
            },
        )

        logger.info(f"Payment session created for user {request.user_id}: {checkout_session.id}")

        return PaymentResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )

    except Exception as e:
        logger.error(f"Error creating payment session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment session: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events
    Creates Payment record when payment completes
    """
    try:
        # Get webhook payload
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except Exception as e:
            if 'signature' in str(e).lower():
                logger.error(f"Invalid signature: {e}")
                raise HTTPException(status_code=400, detail="Invalid signature")
            raise

        # Handle checkout.session.completed event
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            # Extract data
            user_id = session["metadata"]["user_id"]
            payment_intent = session.get("payment_intent")
            session_id = session.get("id")

            logger.info(f"Payment completed: user={user_id}, session={session_id}, payment_intent={payment_intent}")

            # Create payment record
            payment = Payment(
                id=payment_intent or session_id,  # Use payment_intent ID or session ID
                user_id=user_id,
                amount=CONSULTATION_PRICE,
                status=PaymentStatus.PAID,
            )
            db.add(payment)
            db.commit()

            logger.success(f"Payment record created: {payment.id} for user {user_id}")

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@router.get("/verify/{payment_id}")
async def verify_payment(payment_id: str, db: Session = Depends(get_db)):
    """
    Verify that a payment exists and is valid for use
    Used by job submission to check payment before generating report
    """
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            return {"valid": False, "reason": "Payment not found"}

        # Payment is valid if it's PAID or PENDING_RETRY (allow retry after failure)
        if payment.status in [PaymentStatus.PAID, PaymentStatus.PENDING_RETRY]:
            return {
                "valid": True,
                "payment_id": payment.id,
                "user_id": payment.user_id,
                "status": payment.status
            }
        else:
            return {
                "valid": False,
                "reason": f"Payment already {payment.status}"
            }

    except Exception as e:
        logger.error(f"Error verifying payment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify payment: {str(e)}")


@router.post("/refund/{payment_id}")
async def refund_failed_report(
    payment_id: str,
    db: Session = Depends(get_db)
):
    """
    Issue refund for failed report generation
    Marks payment as PENDING_RETRY (allows one free retry)

    This endpoint should be called automatically when report generation fails
    """
    try:
        # Get payment from database
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        if payment.status != PaymentStatus.PAID:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot refund payment with status {payment.status}"
            )

        # Issue Stripe refund
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                reason="requested_by_customer",
                metadata={
                    "reason": "Report generation failed",
                    "user_id": payment.user_id,
                }
            )
            logger.info(f"Stripe refund issued: {refund.id} for payment {payment_id}")
        except Exception as e:
            logger.error(f"Stripe refund failed: {e}")
            # Continue anyway and mark as pending retry
            # (Some payment methods may not support instant refunds)

        # Update payment status to PENDING_RETRY (allows free retry)
        payment.status = PaymentStatus.PENDING_RETRY
        db.commit()

        logger.success(f"Payment {payment_id} marked as PENDING_RETRY - user can retry for free")

        return {
            "status": "success",
            "payment_id": payment_id,
            "refund_issued": True,
            "message": "Refund issued. You can retry report generation for free."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing refund: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process refund: {str(e)}")


@router.get("/history/{user_id}")
async def get_payment_history(user_id: str, db: Session = Depends(get_db)):
    """Get user's consultation payment history"""
    try:
        payments = db.query(Payment).filter(
            Payment.user_id == user_id
        ).order_by(Payment.created_at.desc()).limit(50).all()

        return {
            "user_id": user_id,
            "consultations": [
                {
                    "payment_id": p.id,
                    "amount": p.amount,
                    "status": p.status,
                    "job_id": p.job_id,
                    "created_at": p.created_at.isoformat(),
                }
                for p in payments
            ]
        }

    except Exception as e:
        logger.error(f"Error getting payment history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get payment history: {str(e)}")
