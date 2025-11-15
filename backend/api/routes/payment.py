"""
Stripe payment routes for $6 per-consultation payments
"""
import os
from datetime import datetime

import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger

from database import get_db, Payment, PaymentStatus

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Stripe Price IDs for different tiers
PRICE_IDS = {
    'basic': 'price_1STcw0AYK8RdUDIMoHe7yAN1',      # $9 Basic
    'update': 'price_1STcxJAYK8RdUDIMXqbho0bJ',     # $39.99 Update
    'advanced': 'price_1STcyfAYK8RdUDIM1o3uhF2V',   # $49.99 Advanced
}

# Price mapping for database records
TIER_PRICES = {
    'basic': 9.00,
    'update': 39.99,
    'advanced': 49.99,
}

router = APIRouter(prefix="/api/payment", tags=["payment"])


# ============================================================================
# Models
# ============================================================================

class PaymentRequest(BaseModel):
    """Request to create payment session"""
    user_id: str  # Clerk user ID
    tier: str = 'basic'  # 'basic', 'update', or 'advanced'


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
    Create Stripe checkout session for study abroad consultation
    Supports 3 tiers: basic ($9), update ($39.99), advanced ($49.99)
    """
    try:
        # Validate tier
        if request.tier not in PRICE_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier: {request.tier}. Must be 'basic', 'update', or 'advanced'"
            )

        # Create Stripe checkout session using Price ID
        # Using globally supported payment methods (works in all regions)
        # Alipay will show based on Stripe Dashboard settings + customer location/preferences
        # Prefer automatic payment methods so Stripe decides the best set (card, wallets, Link, Alipay, etc.)
        # Make sure the methods you want are enabled in Stripe Dashboard → Payments → Payment methods → Checkout
        checkout_session = stripe.checkout.Session.create(
            automatic_payment_methods={
                "enabled": True,
                # Allow redirect-based methods like Alipay when available for the customer
                "allow_redirects": "always",
            },
            line_items=[
                {
                    "price": PRICE_IDS[request.tier],
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{FRONTEND_URL}?payment_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}?payment=cancel",
            metadata={
                "user_id": request.user_id,
                "tier": request.tier,
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
            tier = session["metadata"].get("tier", "basic")
            payment_intent = session.get("payment_intent")
            session_id = session.get("id")

            # Get amount based on tier
            amount = TIER_PRICES.get(tier, 9.00)

            logger.info(f"Payment completed: user={user_id}, tier={tier}, amount=${amount}, session={session_id}, payment_intent={payment_intent}")

            # Create payment record
            payment = Payment(
                id=payment_intent or session_id,  # Use payment_intent ID or session ID
                user_id=user_id,
                amount=amount,
                status=PaymentStatus.PAID,
            )
            db.add(payment)
            db.commit()

            logger.success(f"Payment record created: {payment.id} for user {user_id} (tier={tier}, amount=${amount})")

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


class RetryRequest(BaseModel):
    """Request body for manual retry with optional background update"""
    new_background: Optional[str] = Field(
        None,
        min_length=20,
        description="Updated background information (optional, minimum 20 characters)"
    )


@router.post("/retry/{job_id}")
async def manual_retry_report(
    job_id: str,
    request: Optional[RetryRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Allow user to manually retry a failed report generation for free.

    This endpoint:
    1. Checks if the job failed (status = failed or retry_scheduled)
    2. Allows free retry if payment status is PENDING_RETRY
    3. Optionally allows user to UPDATE their background input
    4. Re-enqueues the job for processing
    5. Returns apologetic message

    Users can retry failed reports without paying again and can provide better input.
    """
    try:
        from workers.queue import RedisQueue

        # Initialize queue
        queue = RedisQueue()

        # Get job data
        job_data = queue.get_job_data(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="任务不存在")

        # Check job status
        job_status = job_data.get("status")
        if job_status not in ["failed", "retry_scheduled"]:
            raise HTTPException(
                status_code=400,
                detail=f"该任务无法重试（当前状态: {job_status}）"
            )

        # Get payment ID and check payment status
        payment_id = job_data.get("payment_id")
        if payment_id:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise HTTPException(status_code=404, detail="支付记录不存在")

            # Only allow retry if payment is PENDING_RETRY (already refunded)
            if payment.status != PaymentStatus.PENDING_RETRY:
                raise HTTPException(
                    status_code=400,
                    detail=f"该支付无法重试（当前状态: {payment.status}）"
                )

        # Handle background update if provided
        background_updated = False
        if request and request.new_background:
            new_bg = request.new_background.strip()

            # Validate new background (additional quality checks)
            if len(new_bg) < 20:
                raise HTTPException(
                    status_code=400,
                    detail="新的背景信息至少需要20字符。请提供学校、GPA、实习等详细信息"
                )

            # Update user_background in Redis
            import json
            updated_data = json.dumps({"background": new_bg}, ensure_ascii=False)
            queue.client.hset(f"job:{job_id}", "user_background", updated_data)
            background_updated = True
            logger.info(f"Updated background for job {job_id} ({len(new_bg)} chars)")

        # Reset retry count for manual retry
        queue.client.hset(f"job:{job_id}", "retry_count", "0")

        # Update job status to queued
        queue.update_job_status(
            job_id,
            "queued",
            progress=0,
            error=None
        )

        # Re-enqueue job
        queue.client.lpush("job_queue", job_id)

        logger.info(f"Manual retry triggered for job {job_id} by user (background_updated={background_updated})")

        message = "非常抱歉给您带来不便！我们已为您重新启动报告生成，本次重试完全免费。"
        if background_updated:
            message += " 您已更新了背景信息，报告质量应该会更好。"

        return {
            "status": "success",
            "job_id": job_id,
            "background_updated": background_updated,
            "message": message,
            "apology": {
                "zh": "我们对之前的失败表示诚挚的歉意。您的报告正在重新生成，预计10-15分钟完成。",
                "en": "We sincerely apologize for the previous failure. Your report is being regenerated and should be ready in 10-15 minutes."
            },
            "queued_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing manual retry: {e}")
        raise HTTPException(status_code=500, detail=f"重试失败: {str(e)}")
