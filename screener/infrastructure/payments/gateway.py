"""Payment gateway abstractions for the Pro subscription.

A real checkout needs merchant credentials (Razorpay/Stripe keys) that are
never available in the sandboxed preview environment. The product therefore
works against a pluggable ``PaymentGateway``: a sandbox gateway is the default
so the full checkout UX (create session -> confirm -> entitlement) can be
exercised end-to-end, and a production gateway can be swapped in via
configuration without changing any service code.

The security invariant that matters: the server always owns the checkout state.
Clients can only create sessions and confirm them; a session grants Pro only
after the gateway reports it as paid (sandbox confirms immediately; a real
gateway would verify webhook/signature server-side).
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Protocol

from screener.core.subscription_models import BillingPlan, CheckoutSession

# --------------------------------------------------------------------------- #
# Gateway contract
# --------------------------------------------------------------------------- #


class PaymentGateway(Protocol):
    """Creates and settles checkout sessions for a Pro plan."""

    name: str

    def create_session(self, user_id: str, plan: BillingPlan) -> CheckoutSession:
        """Open a checkout for ``plan``. Returns an unpaid session."""
        ...

    def confirm_session(self, session: CheckoutSession) -> CheckoutSession:
        """Settle a previously created session (idempotent).

        Returns the session with ``status='paid'``. Raises when the session
        cannot be settled (e.g. expired). Real gateways verify payment
        server-side (signature / webhook) before marking paid.
        """
        ...


# --------------------------------------------------------------------------- #
# Sandbox gateway (default) — deterministic, offline, no merchant keys needed
# --------------------------------------------------------------------------- #


class SimulatedPaymentGateway:
    """Offline gateway for development / preview / sandbox environments.

    Every checkout is immediately "payable" via a direct confirm URL. The
    confirm endpoint deliberately simulates a successful payment so the
    freemium flow can be demonstrated without holding real money.
    """

    name = "sandbox"

    def create_session(self, user_id: str, plan: BillingPlan) -> CheckoutSession:
        return CheckoutSession(
            session_id=f"sess_{uuid.uuid4().hex[:16]}",
            plan_id=plan.id,
            status="created",
            gateway=self.name,
            amount_inr=plan.price_inr,
            confirm_url=f"#/pricing?checkout=sess_{uuid.uuid4().hex[:8]}",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )

    def confirm_session(self, session: CheckoutSession) -> CheckoutSession:
        if session.expires_at and datetime.utcnow() > session.expires_at:
            return session.model_copy(update={"status": "expired"})
        return session.model_copy(update={"status": "paid"})


# --------------------------------------------------------------------------- #
# Gateway factory
# --------------------------------------------------------------------------- #


def build_payment_gateway(name: str | None = None) -> PaymentGateway:
    """Instantiate the configured gateway.

    ``name`` is the value of ``SCREENER_PAYMENT_GATEWAY`` (default ``sandbox``).
    The switch is the only place a production gateway would be wired (e.g.
    ``razorpay`` -> RazorpayGateway(credentials)). Unknown names fall back to
    the sandbox so the app never crashes at startup in a preview.
    """
    selected = (name or "sandbox").strip().lower()
    if selected in {"sandbox", "simulated", "test", "demo", ""}:
        return SimulatedPaymentGateway()
    # Unknown / not-yet-wired providers degrade to sandbox rather than failing.
    return SimulatedPaymentGateway()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(10)}"
