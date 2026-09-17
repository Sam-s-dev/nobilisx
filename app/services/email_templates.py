# app/services/email_templates.py
"""
Gabarits HTML partages pour les emails transactionnels (hors rapports).

Les rapports hebdomadaires ont chacun leur mise en page dans leur service
respectif. Ici on couvre les messages courts — bienvenue, expiration,
renouvellement, alerte — dont la structure est identique pour les deux
segments : un bandeau, un titre, un corps, un encadre d'action, un pied.

Seule la palette change entre entreprises (noir / or) et particuliers
(indigo / violet).
"""

from dataclasses import dataclass

ORANGE_MONEY_NUMBER = "+224 627 27 13 97"
WHATSAPP_URL = "https://wa.me/224627271397"
SUPPORT_EMAIL = "trillionnx@gmail.com"

# Les clients mail ne chargent que des images distantes : une image jointe ou
# en data: URI est bloquee par Gmail et Outlook. Le logo doit donc etre servi
# par le site en HTTPS. PUBLIC_BASE_URL permet de pointer ailleurs (test local).
DEFAULT_SITE_URL = "https://nobilisx.onrender.com"


def site_url() -> str:
    from app.config import get_settings
    return (getattr(get_settings(), "PUBLIC_BASE_URL", "") or DEFAULT_SITE_URL).rstrip("/")


def logo_url() -> str:
    return f"{site_url()}/static/icons/icon-192.png"


@dataclass(frozen=True)
class Palette:
    """Couleurs d'un segment."""
    page_bg: str
    card_bg: str
    border: str
    accent: str
    accent_soft: str
    title: str
    text: str
    muted: str
    tagline: str


ENTERPRISE = Palette(
    page_bg="#0d1117",
    card_bg="#161b22",
    border="#30363d",
    accent="#c9a84c",
    accent_soft="rgba(201,168,76,0.1)",
    title="#ffffff",
    text="#c9d1d9",
    muted="#8b949e",
    tagline="L'INTELLIGENCE DES MARCHÉS",
)

INDIVIDUAL = Palette(
    page_bg="#0f0b2e",
    card_bg="#1e1b4b",
    border="#312e81",
    accent="#a78bfa",
    accent_soft="rgba(124,58,237,0.1)",
    title="#ffffff",
    text="#e2e8f0",
    muted="#94a3b8",
    tagline="MISSIONS 100% EN LIGNE",
)


def action_box(palette: Palette, heading: str, intro: str, footnote: str,
               amount: str | None = None) -> str:
    """Encadre d'appel a l'action : paiement Orange Money + WhatsApp."""
    amount_line = (
        f'<p style="color:#fff;line-height:1.6;margin:0 0 8px 0;font-size:14px;">'
        f'{intro} <strong>{amount} GNF</strong> au numéro suivant :</p>'
        if amount else
        f'<p style="color:#fff;line-height:1.6;margin:0 0 8px 0;font-size:14px;">{intro}</p>'
    )
    return f"""
    <div style="background:{palette.accent_soft};border:1px solid {palette.accent};padding:18px;border-radius:12px;margin:22px 0;">
        <h3 style="color:{palette.accent};margin:0 0 10px 0;font-size:16px;">{heading}</h3>
        {amount_line}
        <p style="color:{palette.accent};font-size:23px;font-weight:bold;text-align:center;margin:12px 0;">{ORANGE_MONEY_NUMBER}</p>
        <p style="color:{palette.muted};font-size:12px;margin:0;text-align:center;">{footnote}</p>
        <p style="text-align:center;margin:16px 0 0 0;">
          <a href="{WHATSAPP_URL}" style="display:inline-block;background:{palette.accent};color:{palette.page_bg};padding:11px 26px;border-radius:100px;text-decoration:none;font-size:13px;font-weight:700;">Envoyer ma preuve sur WhatsApp &#x2192;</a>
        </p>
    </div>"""


def info_box(palette: Palette, text: str) -> str:
    """Encadre discret pour une information secondaire."""
    return f"""
    <div style="background:{palette.accent_soft};border:1px solid {palette.border};padding:14px 18px;border-radius:10px;margin:18px 0;">
        <p style="color:{palette.accent};font-size:13px;margin:0;line-height:1.55;">{text}</p>
    </div>"""


def render(palette: Palette, heading: str, body_html: str,
           preheader: str = "") -> str:
    """Assemble un email transactionnel complet.

    heading   : titre principal (ex. « Bienvenue Ahmed ! »)
    body_html : corps deja mis en forme (paragraphes, encadres)
    preheader : texte d'apercu affiche par les clients mail avant ouverture
    """
    preheader_block = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>'
        if preheader else ""
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:20px;background:{palette.page_bg};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
{preheader_block}
<div style="max-width:520px;margin:0 auto;background:{palette.card_bg};padding:40px 32px;border-radius:18px;border:1px solid {palette.border};">
    <table cellpadding="0" cellspacing="0" style="margin:0 0 22px 0;"><tr>
      <td style="vertical-align:middle;padding-right:12px;">
        <img src="{logo_url()}" width="48" height="48" alt="NobilisX"
             style="display:block;width:48px;height:48px;border-radius:12px;background:#ffffff;">
      </td>
      <td style="vertical-align:middle;">
        <div style="color:{palette.accent};font-size:24px;font-weight:900;letter-spacing:-0.5px;line-height:1.1;">NOBILIS X</div>
        <div style="color:{palette.muted};font-size:10px;letter-spacing:1.5px;font-weight:600;margin-top:3px;">{palette.tagline}</div>
      </td>
    </tr></table>
    <h2 style="color:{palette.title};font-size:20px;font-weight:800;margin:0 0 14px 0;">{heading}</h2>
    {body_html}
    <hr style="border:none;border-top:1px solid {palette.border};margin:26px 0 18px 0;">
    <p style="color:{palette.muted};font-size:12px;margin:0 0 4px 0;">{SUPPORT_EMAIL} &nbsp;|&nbsp; {ORANGE_MONEY_NUMBER}</p>
    <p style="color:{palette.border};font-size:11px;margin:0;">Fait en Guinée. Conçu pour que les meilleurs gagnent.</p>
</div>
</body></html>"""


def paragraph(palette: Palette, text: str) -> str:
    return (
        f'<p style="color:{palette.text};line-height:1.7;font-size:14px;margin:0 0 14px 0;">{text}</p>'
    )
