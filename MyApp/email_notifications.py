import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send(subject, message, recipient_list):
    if not recipient_list:
        return
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send email: %s", subject)


def send_company_welcome_email(company):
    if not company.business_email:
        return
    _send(
        f"Welcome to the platform – {company.name}",
        (
            f"Hello {company.first_name},\n\n"
            f"Your company '{company.name}' is registered.\n"
            f"Login ID: {company.code}\n"
            f"Your 7-day free trial has started.\n\n"
            f"Log in at your site URL to manage clients and work."
        ),
        [company.business_email],
    )


def send_payment_review_email(payment, approved):
    company = payment.company
    if not company or not company.business_email:
        return
    status = "approved" if approved else "rejected"
    _send(
        f"Payment {status} – {company.name}",
        (
            f"Hello,\n\n"
            f"Your payment request ({payment.transaction_reference}) was {status}.\n"
            f"Amount: {payment.currency} {payment.amount}\n\n"
            f"Log in to your billing page for details."
        ),
        [company.business_email],
    )
