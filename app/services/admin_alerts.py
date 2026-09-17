# app/services/admin_alerts.py
"""
Notifications internes destinees a l'administrateur (pas aux clients).

Sans ce module, aucune alerte ne prevenait d'une nouvelle inscription : le seul
signal etait le message WhatsApp du client au moment du paiement. Un client qui
payait sans ecrire restait invisible jusqu'a la prochaine ouverture de l'espace
admin.

L'adresse de destination est ADMIN_ALERT_EMAIL, sinon EMAIL_FROM, sinon
CONTACT_EMAIL.
"""

import logging
from datetime import datetime

from app.config import get_settings
from app.services import email_templates as tpl
from app.services.email_sender import send_email
from app.services.subscription import is_pending, plan_base

logger = logging.getLogger(__name__)
settings = get_settings()

# Tarifs affiches dans l'alerte, pour savoir quel montant attendre.
PRICES = {
    ("enterprise", "ENTRY"): "2 000 000 GNF",
    ("enterprise", "ELITE"): "3 000 000 GNF",
    ("individual", "ENTRY"): "1 000 000 GNF",
    ("individual", "ELITE"): "1 500 000 GNF",
}


def admin_recipient() -> str:
    """Adresse qui recoit les alertes internes."""
    return (
        getattr(settings, "ADMIN_ALERT_EMAIL", "")
        or getattr(settings, "EMAIL_FROM", "")
        or settings.SMTP_FROM
        or settings.CONTACT_EMAIL
    ).strip()


def send_registration_alert(user, user_type: str) -> bool:
    """Previent l'admin qu'un compte vient d'etre cree.

    user_type : 'enterprise' ou 'individual'.
    Ne leve jamais : une alerte interne ne doit pas faire echouer une inscription.
    """
    recipient = admin_recipient()
    if not recipient:
        logger.warning("Alerte admin non envoyée : aucune adresse de destination configurée")
        return False

    plan = plan_base(user)
    pending = is_pending(user)
    is_enterprise = user_type == "enterprise"

    name = user.name if is_enterprise else user.full_name
    segment = "Entreprise" if is_enterprise else "Particulier"
    detail_label = "Secteur" if is_enterprise else "Domaine"
    detail_value = (user.sector if is_enterprise else user.domain) or "non précisé"
    amount = PRICES.get((user_type, plan))

    subject = (
        f"[NOBILIS ADMIN] {'PAIEMENT ATTENDU' if pending else 'Essai gratuit'} - "
        f"{name} ({segment} / {plan})"
    )

    rows = [
        ("Nom", name),
        ("Segment", segment),
        ("Plan choisi", plan),
        (detail_label, detail_value),
        ("Email", user.email or "non renseigné"),
        ("Téléphone", getattr(user, "phone", None) or "non renseigné"),
        ("Inscrit le", datetime.utcnow().strftime("%d/%m/%Y à %H:%M UTC")),
    ]
    table = "".join(
        f'<tr>'
        f'<td style="padding:7px 12px 7px 0;color:#8b949e;font-size:13px;white-space:nowrap;">{label}</td>'
        f'<td style="padding:7px 0;color:#ffffff;font-size:13px;font-weight:600;">{value}</td>'
        f'</tr>'
        for label, value in rows
    )

    if pending:
        action = tpl.info_box(
            tpl.ENTERPRISE,
            f"<strong>Action requise :</strong> ce compte attend un paiement de "
            f"<strong>{amount or 'montant à vérifier'}</strong>. "
            "Dès réception de la preuve Orange Money, validez-le dans l'espace admin "
            "— le client recevra automatiquement sa confirmation.",
        )
    else:
        action = tpl.info_box(
            tpl.ENTERPRISE,
            "Compte en <strong>essai gratuit</strong>. Aucune action nécessaire pour l'instant : "
            "il recevra ses rapports puis un message d'expiration à la fin de l'essai.",
        )

    body = (
        tpl.paragraph(tpl.ENTERPRISE, "Une nouvelle inscription vient d'être enregistrée.")
        + f'<table style="width:100%;border-collapse:collapse;margin:18px 0;">{table}</table>'
        + action
    )

    html_body = tpl.render(
        tpl.ENTERPRISE,
        heading="Nouvelle inscription",
        body_html=body,
        preheader=f"{name} — {segment} — plan {plan}",
    )

    text_body = "Nouvelle inscription NOBILIS X\n\n" + "\n".join(
        f"{label} : {value}" for label, value in rows
    )

    try:
        send_email(
            to_email=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
        logger.info(f"Alerte admin envoyée à {recipient} pour {name} ({plan})")
        return True
    except Exception as e:
        # Une alerte interne ne doit jamais casser le parcours d'inscription.
        logger.error(f"Échec de l'alerte admin pour {name} : {e}")
        return False
