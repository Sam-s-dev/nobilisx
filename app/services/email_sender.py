# app/services/email_sender.py
"""
Couche d'envoi bas-niveau, partagee par EmailService (entreprises) et
IndividualEmailService (particuliers).

POURQUOI CE MODULE
------------------
En local, l'envoi SMTP (Gmail port 587) fonctionne. Une fois deploye sur
Render / Railway / Fly.io, les ports SMTP sortants (25, 465, 587) sont bloques :
plus aucun mail ne part. La seule methode fiable en production est une API REST
HTTPS (port 443), jamais bloquee.

Tous les fournisseurs ci-dessous passent par HTTPS. Ordre par defaut :

    brevo  ->  smtp2go  ->  resend  ->  mailjet  ->  smtp

Brevo et SMTP2GO sont en tete car ils fonctionnent SANS nom de domaine
(indispensable ici : l'expediteur est une adresse Gmail). Resend, lui, exige
un domaine verifie par DNS pour ecrire a des destinataires quelconques.

Forcer un fournisseur :   EMAIL_PROVIDER=brevo
Changer l'ordre       :   EMAIL_PROVIDER_ORDER=resend,brevo,smtp
"""

import base64
import logging
import os
import smtplib
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Domaines grand public : impossible de les authentifier (SPF/DKIM) chez un
# fournisseur d'emailing. Utilises pour detecter une config incomplete.
PUBLIC_DOMAINS = (
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.fr", "hotmail.com",
    "hotmail.fr", "outlook.com", "outlook.fr", "live.com", "live.fr",
    "aol.com", "icloud.com", "msn.com", "orange.fr", "free.fr", "proton.me",
    "protonmail.com",
)

DEFAULT_ORDER = ("brevo", "smtp2go", "resend", "mailjet", "smtp")

# Codes HTTP qui justifient une nouvelle tentative (panne passagere).
# Tout le reste (401, 403, 422...) est une erreur de configuration : reessayer
# ne sert a rien et fait perdre 30 s par destinataire lors de l'envoi en masse.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class EmailProviderError(Exception):
    """Echec d'un fournisseur, avec le detail renvoye par son API.

    `requests.raise_for_status()` ne conserve que « 403 Client Error » et perd
    le corps de la reponse, la ou se trouve toujours la vraie cause. On le
    conserve ici pour que les logs Render soient exploitables.
    """

    def __init__(self, provider: str, message: str, status_code: int | None = None,
                 body: str | None = None, retryable: bool = False):
        self.provider = provider
        self.status_code = status_code
        self.body = (body or "")[:800]
        self.retryable = retryable
        detail = f"[{provider}] {message}"
        if status_code:
            detail += f" (HTTP {status_code})"
        if self.body:
            detail += f" | reponse: {self.body}"
        super().__init__(detail)


class EmailConfigError(EmailProviderError):
    """Fournisseur inutilisable en l'etat (cle absente, expediteur invalide)."""


# ----------------------------------------------------------------------
#  Helpers
# ----------------------------------------------------------------------

def _domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip() if email and "@" in email else ""


def is_public_domain(email: str) -> bool:
    """True si l'adresse est chez un fournisseur grand public (Gmail & co)."""
    return _domain_of(email) in PUBLIC_DOMAINS


def _from_address() -> str:
    """Adresse expediteur globale (EMAIL_FROM, sinon SMTP_FROM, sinon CONTACT_EMAIL)."""
    return (
        getattr(settings, "EMAIL_FROM", "")
        or settings.SMTP_FROM
        or settings.CONTACT_EMAIL
    ).strip()


def _from_name() -> str:
    return (getattr(settings, "EMAIL_FROM_NAME", "") or settings.APP_NAME or "NOBILIS X").strip()


def _read_pdf_b64(pdf_path: str | None) -> tuple[str, str] | None:
    """Retourne (nom_fichier, contenu_base64) ou None si pas de piece jointe."""
    if not pdf_path or not os.path.exists(pdf_path):
        return None
    try:
        with open(pdf_path, "rb") as f:
            return os.path.basename(pdf_path), base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Piece jointe PDF illisible ({pdf_path}) : {e}")
        return None


def _post(provider: str, url: str, *, json: dict, headers: dict | None = None,
          auth: tuple | None = None, timeout: int = 30) -> requests.Response:
    """POST avec remontee complete de l'erreur (statut + corps)."""
    try:
        response = requests.post(url, json=json, headers=headers, auth=auth, timeout=timeout)
    except requests.RequestException as e:
        # Panne reseau / DNS / timeout : transitoire, on peut reessayer.
        raise EmailProviderError(provider, f"erreur reseau : {e}", retryable=True) from e

    if response.status_code >= 400:
        raise EmailProviderError(
            provider,
            "l'API a refuse l'envoi",
            status_code=response.status_code,
            body=response.text,
            retryable=response.status_code in RETRYABLE_STATUS,
        )
    return response


# ----------------------------------------------------------------------
#  Fournisseurs
# ----------------------------------------------------------------------

def _send_brevo(to_email: str, subject: str, html_body: str, text_body: str,
                pdf_path: str | None = None) -> str:
    """Brevo (ex-Sendinblue) - 300 mails/jour gratuits, aucun domaine requis.

    Si le domaine de l'expediteur n'est pas authentifie (cas d'une adresse
    Gmail), Brevo reecrit automatiquement l'expediteur en @brevosend.com et
    l'envoi passe quand meme. C'est ce qui permet de fonctionner sans domaine.
    L'adresse utilisee doit etre validee dans Brevo (Senders > Add a sender,
    confirmation par code recu sur cette boite).
    """
    if not settings.BREVO_API_KEY:
        raise EmailConfigError("brevo", "BREVO_API_KEY absente")

    sender = _from_address()
    if not sender:
        raise EmailConfigError("brevo", "aucun expediteur configure (EMAIL_FROM / SMTP_FROM)")

    payload = {
        "sender": {"name": _from_name(), "email": sender},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }

    attachment = _read_pdf_b64(pdf_path)
    if attachment:
        payload["attachment"] = [{"name": attachment[0], "content": attachment[1]}]

    response = _post(
        "brevo",
        "https://api.brevo.com/v3/smtp/email",
        json=payload,
        headers={
            "api-key": settings.BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        return response.json().get("messageId", "") or "envoye"
    except ValueError:
        return "envoye"


def _send_smtp2go(to_email: str, subject: str, html_body: str, text_body: str,
                  pdf_path: str | None = None) -> str:
    """SMTP2GO - 1 000 mails/mois gratuits, aucun domaine requis.

    Verifier l'adresse expeditrice dans Sending > Verified Senders > Single
    Sender Emails (confirmation par mail). Sans domaine verifie, le compte est
    limite a 25 envois/heure : suffisant ici, et c'est un excellent secours
    quand le quota Brevo du jour est atteint.
    """
    if not settings.SMTP2GO_API_KEY:
        raise EmailConfigError("smtp2go", "SMTP2GO_API_KEY absente")

    sender = (settings.SMTP2GO_FROM or _from_address()).strip()
    if not sender:
        raise EmailConfigError("smtp2go", "aucun expediteur configure (SMTP2GO_FROM / EMAIL_FROM)")

    payload = {
        "sender": f"{_from_name()} <{sender}>",
        "to": [to_email],
        "subject": subject,
        "html_body": html_body,
        "text_body": text_body,
    }

    attachment = _read_pdf_b64(pdf_path)
    if attachment:
        payload["attachments"] = [{
            "filename": attachment[0],
            "fileblob": attachment[1],
            "mimetype": "application/pdf",
        }]

    response = _post(
        "smtp2go",
        "https://api.smtp2go.com/v3/email/send",
        json=payload,
        headers={
            "X-Smtp2go-Api-Key": settings.SMTP2GO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    # SMTP2GO repond 200 meme lorsqu'il rejette le message : le verdict reel
    # est dans le corps (data.succeeded / data.failures).
    try:
        data = response.json().get("data", {})
    except ValueError:
        return "envoye"

    if data.get("error") or data.get("failures"):
        raise EmailProviderError(
            "smtp2go",
            "message rejete",
            status_code=response.status_code,
            body=response.text,
        )
    if not data.get("succeeded"):
        raise EmailProviderError(
            "smtp2go",
            "aucun destinataire accepte",
            status_code=response.status_code,
            body=response.text,
        )
    return data.get("email_id", "") or "envoye"


def _send_resend(to_email: str, subject: str, html_body: str, text_body: str,
                 pdf_path: str | None = None) -> str:
    """Resend - 3 000 mails/mois gratuits, MAIS un domaine verifie est obligatoire.

    Sans domaine verifie, le seul expediteur autorise est onboarding@resend.dev,
    qui n'accepte QUE l'adresse du proprietaire du compte comme destinataire
    (HTTP 403 pour tous les autres). Un envoi client ne peut donc pas passer.

    Pour l'activer : acheter un domaine, l'ajouter sur resend.com/domains,
    poser les enregistrements DNS proposes, puis renseigner
    RESEND_FROM=contact@votre-domaine.com
    """
    if not settings.RESEND_API_KEY:
        raise EmailConfigError("resend", "RESEND_API_KEY absente")

    sender = (settings.RESEND_FROM or _from_address()).strip()
    if not sender:
        raise EmailConfigError("resend", "aucun expediteur configure (RESEND_FROM)")

    if is_public_domain(sender) or sender.endswith("@resend.dev"):
        raise EmailConfigError(
            "resend",
            f"l'expediteur '{sender}' n'est pas un domaine verifie Resend. "
            "Resend refuse d'ecrire a des tiers depuis une adresse Gmail ou depuis "
            "onboarding@resend.dev. Verifiez un domaine sur resend.com/domains puis "
            "renseignez RESEND_FROM=contact@votre-domaine.com (ou utilisez Brevo/SMTP2GO, "
            "qui ne demandent aucun domaine)",
        )

    payload = {
        "from": f"{_from_name()} <{sender}>",
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }

    attachment = _read_pdf_b64(pdf_path)
    if attachment:
        payload["attachments"] = [{"filename": attachment[0], "content": attachment[1]}]

    response = _post(
        "resend",
        "https://api.resend.com/emails",
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        return response.json().get("id", "") or "envoye"
    except ValueError:
        return "envoye"


def _send_mailjet(to_email: str, subject: str, html_body: str, text_body: str,
                  pdf_path: str | None = None) -> str:
    """Mailjet - API REST v3.1 (expediteur a valider dans le compte Mailjet)."""
    if not (settings.MAILJET_API_KEY and settings.MAILJET_SECRET_KEY):
        raise EmailConfigError("mailjet", "MAILJET_API_KEY / MAILJET_SECRET_KEY absentes")

    sender = _from_address()
    if not sender:
        raise EmailConfigError("mailjet", "aucun expediteur configure (EMAIL_FROM / SMTP_FROM)")

    message = {
        "From": {"Email": sender, "Name": _from_name()},
        "To": [{"Email": to_email}],
        "Subject": subject,
        "TextPart": text_body,
        "HTMLPart": html_body,
    }

    attachment = _read_pdf_b64(pdf_path)
    if attachment:
        message["Attachments"] = [{
            "ContentType": "application/pdf",
            "Filename": attachment[0],
            "Base64Content": attachment[1],
        }]

    response = _post(
        "mailjet",
        "https://api.mailjet.com/v3.1/send",
        json={"Messages": [message]},
        auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
    )

    try:
        result = response.json().get("Messages", [{}])[0]
    except (ValueError, IndexError):
        return "envoye"

    if result.get("Status") != "success":
        raise EmailProviderError(
            "mailjet", "message rejete",
            status_code=response.status_code, body=response.text,
        )
    return "envoye"


def _send_smtp(to_email: str, subject: str, html_body: str, text_body: str,
               pdf_path: str | None = None) -> str:
    """SMTP classique - fonctionne en local, bloque sur la plupart des hebergeurs cloud."""
    if not settings.SMTP_HOST:
        raise EmailConfigError("smtp", "SMTP_HOST absent")

    sender = _from_address()
    msg = MIMEMultipart("mixed") if pdf_path else MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{_from_name()} <{sender}>"
    msg["To"] = to_email

    text_part = MIMEText(text_body, "plain", "utf-8")
    html_part = MIMEText(html_body, "html", "utf-8")

    if pdf_path:
        alternative = MIMEMultipart("alternative")
        alternative.attach(text_part)
        alternative.attach(html_part)
        msg.attach(alternative)

        attachment = _read_pdf_b64(pdf_path)
        if attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(base64.b64decode(attachment[1]))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={attachment[0]}")
            msg.attach(part)
    else:
        msg.attach(text_part)
        msg.attach(html_part)

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
            if settings.SMTP_TLS:
                server.starttls()
        try:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(sender, to_email, msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                pass
    except OSError as e:
        # Port SMTP filtre : signature typique d'un hebergement cloud.
        raise EmailProviderError(
            "smtp",
            f"connexion a {settings.SMTP_HOST}:{settings.SMTP_PORT} impossible ({e}). "
            "Les hebergeurs cloud (Render, Railway, Fly.io) bloquent les ports SMTP : "
            "configurez BREVO_API_KEY ou SMTP2GO_API_KEY",
        ) from e
    except smtplib.SMTPException as e:
        raise EmailProviderError("smtp", f"erreur SMTP : {e}") from e

    return "envoye"


PROVIDERS = {
    "brevo": _send_brevo,
    "smtp2go": _send_smtp2go,
    "resend": _send_resend,
    "mailjet": _send_mailjet,
    "smtp": _send_smtp,
}


# ----------------------------------------------------------------------
#  Orchestration
# ----------------------------------------------------------------------

def provider_order() -> list[str]:
    """Ordre d'essai des fournisseurs, selon EMAIL_PROVIDER / EMAIL_PROVIDER_ORDER."""
    forced = (getattr(settings, "EMAIL_PROVIDER", "") or "").strip().lower()
    if forced and forced != "auto":
        names = [forced]
    else:
        raw = (getattr(settings, "EMAIL_PROVIDER_ORDER", "") or "").strip().lower()
        names = [n.strip() for n in raw.split(",") if n.strip()] if raw else list(DEFAULT_ORDER)

    valid = [n for n in names if n in PROVIDERS]
    if not valid:
        logger.warning(f"Ordre de fournisseurs invalide ({names}), retour a l'ordre par defaut")
        return list(DEFAULT_ORDER)
    return valid


def configured_providers() -> list[str]:
    """Fournisseurs reellement utilisables (cle presente)."""
    available = []
    for name in provider_order():
        if name == "brevo" and settings.BREVO_API_KEY:
            available.append(name)
        elif name == "smtp2go" and settings.SMTP2GO_API_KEY:
            available.append(name)
        elif name == "resend" and settings.RESEND_API_KEY:
            available.append(name)
        elif name == "mailjet" and settings.MAILJET_API_KEY and settings.MAILJET_SECRET_KEY:
            available.append(name)
        elif name == "smtp" and settings.SMTP_HOST:
            available.append(name)
    return available


def send_email(to_email: str, subject: str, html_body: str, text_body: str,
               pdf_path: str | None = None, max_attempts: int = 2) -> dict:
    """Envoie un mail en essayant chaque fournisseur configure, dans l'ordre.

    Retourne {"provider": nom, "message_id": id, "attempts": [...]}.
    Leve le dernier EmailProviderError si aucun fournisseur n'a abouti.

    Seules les pannes passageres (reseau, 429, 5xx) sont reessayees : une cle
    invalide ou un expediteur refuse echoue immediatement et on passe au
    fournisseur suivant.
    """
    attempts: list[dict] = []
    last_error: Exception | None = None

    for name in provider_order():
        send = PROVIDERS[name]

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Envoi via {name} -> {to_email} (tentative {attempt}/{max_attempts})")
                message_id = send(to_email, subject, html_body, text_body, pdf_path)
                logger.info(f"Email envoye via {name} a {to_email} | id={message_id}")
                attempts.append({"provider": name, "ok": True, "message_id": message_id})
                return {"provider": name, "message_id": message_id, "attempts": attempts}

            except EmailConfigError as e:
                # Fournisseur non configure : ce n'est pas une panne, on n'en
                # fait pas un bruit d'erreur et on passe au suivant.
                logger.debug(f"{name} ignore : {e}")
                attempts.append({"provider": name, "ok": False, "skipped": True, "error": str(e)})
                last_error = e
                break

            except EmailProviderError as e:
                last_error = e
                attempts.append({"provider": name, "ok": False, "error": str(e)})
                if e.retryable and attempt < max_attempts:
                    delay = 3 * attempt
                    logger.warning(f"{name} : panne passagere, nouvelle tentative dans {delay}s ({e})")
                    time.sleep(delay)
                    continue
                logger.warning(f"Echec {name} : {e}")
                break

            except Exception as e:  # pragma: no cover - garde-fou
                last_error = e
                attempts.append({"provider": name, "ok": False, "error": str(e)})
                logger.exception(f"Erreur inattendue avec {name}")
                break

    tried = ", ".join(a["provider"] for a in attempts) or "aucun"
    logger.error(f"Aucun fournisseur n'a pu envoyer a {to_email} (essayes : {tried})")
    if last_error:
        raise last_error
    raise EmailConfigError(
        "aucun",
        "aucun fournisseur d'email configure. Renseignez BREVO_API_KEY "
        "(300 mails/jour gratuits, aucun domaine requis) dans les variables "
        "d'environnement de votre hebergeur",
    )


def describe_config() -> dict:
    """Etat de la configuration email, sans rien envoyer (pour /admin/email_config)."""
    sender = _from_address()
    available = configured_providers()
    resend_from = (settings.RESEND_FROM or sender).strip()

    warnings: list[str] = []
    if not available:
        warnings.append(
            "Aucun fournisseur configure : les envois echoueront. "
            "Renseignez BREVO_API_KEY."
        )
    if available == ["smtp"]:
        warnings.append(
            "Seul le SMTP est configure. Il fonctionne en local mais les hebergeurs "
            "cloud (Render, Railway) bloquent les ports SMTP : configurez BREVO_API_KEY "
            "ou SMTP2GO_API_KEY."
        )
    if settings.RESEND_API_KEY and (is_public_domain(resend_from) or resend_from.endswith("@resend.dev")):
        warnings.append(
            f"Resend est configure mais l'expediteur '{resend_from}' n'est pas un domaine "
            "verifie : Resend ne pourra ecrire qu'au proprietaire du compte. "
            "Verifiez un domaine sur resend.com/domains puis renseignez RESEND_FROM."
        )
    if not sender:
        warnings.append("Aucun expediteur configure (EMAIL_FROM ou SMTP_FROM).")

    return {
        "from_email": sender,
        "from_name": _from_name(),
        "from_is_public_domain": is_public_domain(sender),
        "order": provider_order(),
        "available": available,
        "active_provider": available[0] if available else None,
        "keys": {
            "brevo": bool(settings.BREVO_API_KEY),
            "smtp2go": bool(settings.SMTP2GO_API_KEY),
            "resend": bool(settings.RESEND_API_KEY),
            "mailjet": bool(settings.MAILJET_API_KEY and settings.MAILJET_SECRET_KEY),
            "smtp": bool(settings.SMTP_HOST and settings.SMTP_USER),
        },
        "resend_from": resend_from,
        "smtp_host": f"{settings.SMTP_HOST}:{settings.SMTP_PORT}" if settings.SMTP_HOST else "",
        "warnings": warnings,
    }
