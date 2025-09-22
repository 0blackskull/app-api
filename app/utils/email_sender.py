from abc import ABC, abstractmethod
from typing import Any, Dict
from app.utils.logger import get_logger
import requests
from app.config import settings

logger = get_logger(__name__)

class EmailSender(ABC):
    @abstractmethod
    def send_email(self, to_email: str, subject: str, html_content: str, **kwargs) -> Any:
        pass

# Mailgun email sender
class MailgunEmailSender(EmailSender):
    def __init__(self, api_key: str, domain: str, sender_email: str, sender_name: str = None, base_url: str = "https://api.mailgun.net"):
        self.api_key = api_key
        self.domain = domain
        self.sender_email = sender_email
        self.sender_name = sender_name or sender_email
        self.base_url = base_url.rstrip('/')

    def send_email(self, to_email: str, subject: str, html_content: str, **kwargs) -> Any:
        url = f"{self.base_url}/v3/{self.domain}/messages"
        data: Dict[str, str] = {
            "from": f"{self.sender_name} <{self.sender_email}>",
            "to": to_email,
            "subject": subject,
            "html": html_content,
        }
        reply_to = kwargs.get("reply_to")
        if reply_to:
            data["h:Reply-To"] = reply_to
        bcc = kwargs.get("bcc")
        if bcc:
            data["bcc"] = bcc
        resp = requests.post(url, auth=("api", self.api_key), data=data, timeout=10)
        if resp.status_code >= 200 and resp.status_code < 300:
            logger.info("Email sent via Mailgun: %s", resp.json())
            return resp.json()
        logger.error("Mailgun send failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Mailgun send email failed: {resp.status_code} {resp.text}")

# Fallback email sender that logs instead of sending
class LoggingEmailSender(EmailSender):
    def __init__(self, sender_email: str, sender_name: str = None):
        self.sender_email = sender_email
        self.sender_name = sender_name or sender_email

    def send_email(self, to_email: str, subject: str, html_content: str, **kwargs) -> Any:
        logger.info(f"EMAIL WOULD BE SENT (logging sender):")
        logger.info(f"  To: {to_email}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  Content: {html_content}")
        if kwargs:
            logger.info(f"  Extra: {kwargs}")
        return {"message": "Email logged (no provider configured)"}

# Factory function to create email sender based on settings
def create_email_sender() -> EmailSender:
    provider = (settings.EMAIL_PROVIDER or "logging").lower()
    if provider == "mailgun" and settings.MAILGUN_API_KEY and settings.MAILGUN_DOMAIN:
        return MailgunEmailSender(
            api_key=settings.MAILGUN_API_KEY,
            domain=settings.MAILGUN_DOMAIN,
            sender_email=settings.EMAIL_FROM,
            sender_name=settings.EMAIL_FROM_NAME,
            base_url=settings.MAILGUN_BASE_URL,
        )
    logger.warning("Falling back to LoggingEmailSender (provider=%s)", provider)
    return LoggingEmailSender(settings.EMAIL_FROM, settings.EMAIL_FROM_NAME) 