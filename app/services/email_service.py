"""
Stub email service. Wire to a real provider (Resend / Postmark / SES) in Phase 3.

The point of this module: session, auth, and notification code should never
import a specific provider — they call these functions.
"""

import logging

logger = logging.getLogger(__name__)


async def send_verification_email(to_email: str, token: str) -> None:
    # TODO Phase 3: enqueue via background worker
    logger.info("Would send verification email to %s with token=%s", to_email, token)


async def send_password_reset_email(to_email: str, token: str) -> None:
    logger.info("Would send password reset email to %s with token=%s", to_email, token)


async def send_subscription_activated(to_email: str) -> None:
    logger.info("Would notify %s: subscription activated", to_email)


async def send_renewal_reminder(to_email: str, days_before: int) -> None:
    logger.info("Would remind %s: subscription expires in %s days", to_email, days_before)