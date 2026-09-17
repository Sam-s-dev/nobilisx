# app/services/email_service_individual.py
"""
Service d'envoi d'emails pour les PARTICULIERS — NOBILIS X V2

Différences avec le service Entreprises :
- Ton plus direct, plus jeune, orienté action ("Postule maintenant")
- Pas de PDF joint (email HTML uniquement)
- Top 10 missions avec score de compatibilité
- 2 conseils IA personnalisés (vs 2-5 pour les entreprises)
- Template visuel distinct (gradient violet/indigo vs bleu marine/or)

L'envoi lui-même est délégué à app/services/email_sender.py (Brevo, SMTP2GO,
Resend, Mailjet puis SMTP — tous en HTTPS, seule méthode qui passe sur un
hébergeur cloud où les ports SMTP sont bloqués).
"""

import html
import logging
import re
import unicodedata
import urllib.parse
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.individual import Individual
from app.models.tender import Tender
from app.models.analysis import Analysis
from app.models.email_log import EmailLog
from app.services import email_templates as tpl
from app.services.email_sender import send_email
from app.services.subscription import (
    PASS_TRIAL_DAYS,
    blocked_reason,
    is_active,
    is_elite,
    plan_base,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class IndividualEmailService:
    """Service d'envoi d'emails pour les particuliers"""

    def __init__(self, db: Session):
        self.db = db
        self._text_summary = ""

    # ------------------------------------------------------------------
    #  Nettoyage de texte (réutilise la même logique que EmailService)
    # ------------------------------------------------------------------

    def _strip_emojis(self, text: str) -> str:
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001f900-\U0001f9FF"
            "\U00002600-\U000026FF"
            "\U0000FE00-\U0000FE0F"
            "\U0000200D"
            "\U0000200B"
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text)

    def _fix_encoding(self, text: str) -> str:
        if not text:
            return ""
        try:
            fixed = text.encode('latin-1').decode('utf-8')
            if fixed != text:
                return fixed
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        replacements = {
            'Ã©': 'é', 'Ã¨': 'è', 'Ãª': 'ê', 'Ã«': 'ë',
            'Ã ': 'à', 'Ã¢': 'â', 'Ã§': 'ç', 'Ã´': 'ô',
            'Ã¹': 'ù', 'Ã»': 'û', 'Ã®': 'î', 'Ã¯': 'ï',
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)
        return text

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = self._fix_encoding(text)
        text = unicodedata.normalize('NFC', text)
        text = self._strip_emojis(text)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        text = html.escape(text)
        return text.strip()

    def _clean_subject(self, subject: str) -> str:
        if not subject:
            return "NOBILIS X - Vos missions"
        subject = self._fix_encoding(subject)
        subject = self._strip_emojis(subject)
        subject = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', subject)
        return subject.strip() or "NOBILIS X - Vos missions"

    def _clean_plain_text(self, text: str) -> str:
        if not text:
            return ""
        text = self._fix_encoding(text)
        text = self._strip_emojis(text)
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return text.strip()

    # ------------------------------------------------------------------
    #  Construction du corps HTML — Template PARTICULIERS
    # ------------------------------------------------------------------

    def _build_individual_html(
        self,
        individual: Individual,
        scored_missions: list[dict],
        recommendations: list[str] | None = None,
    ) -> str:
        """
        Construit le corps HTML de l'email pour les particuliers.
        Design : gradient violet/indigo, ton direct, boutons "Postule maintenant".
        """
        mission_rows = ""
        text_lines = []

        # Détermination du nombre de missions selon le plan
        # Les ELITE voient 10 missions, les autres 5.
        max_missions = 10 if is_elite(individual) else 5
        
        for item in scored_missions[:max_missions]:
            score = item["score"]
            score_color = "#22c55e" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
            source_url = item.get("source_url", "")
            clean_title = self._clean_text(item.get("mission_title", item.get("tender_title", ""))[:80])
            clean_summary = self._clean_text(item.get("summary", item.get("explanation", ""))[:200])

            if source_url and source_url.startswith("http"):
                btn_url = source_url
            else:
                search_query = urllib.parse.quote_plus(
                    self._clean_plain_text(item.get("mission_title", item.get("tender_title", ""))[:100])
                )
                btn_url = f"https://www.google.com/search?q={search_query}+freelance+mission"

            level_label = "Excellent match" if score >= 70 else "Bon potentiel" if score >= 40 else "A explorer"
            level_bg = "#dcfce7" if score >= 70 else "#fef3c7" if score >= 40 else "#fee2e2"
            level_txt = "#166534" if score >= 70 else "#92400e" if score >= 40 else "#991b1b"

            mission_rows += f"""
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;background:#ffffff;border-radius:16px;border:1px solid #e5e7eb;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.04);">
              <tr>
                <td width="80" style="padding:22px 0 22px 14px;vertical-align:top;text-align:center;">
                  <table cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr><td style="width:58px;height:58px;border-radius:14px;background:{score_color}15;border:2px solid {score_color}40;text-align:center;vertical-align:middle;">
                    <span style="font-size:20px;font-weight:900;color:{score_color};font-family:-apple-system,BlinkMacSystemFont,sans-serif;">{score:.0f}</span><br>
                    <span style="font-size:8px;font-weight:700;color:{score_color}88;text-transform:uppercase;font-family:-apple-system,sans-serif;">/100</span>
                  </td></tr></table>
                </td>
                <td style="padding:18px 18px 18px 10px;vertical-align:top;">
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;background:{level_bg};font-size:10px;font-weight:700;color:{level_txt};font-family:-apple-system,sans-serif;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:8px;">{level_label}</span>
                  <p style="margin:0 0 6px 0;font-size:14px;font-weight:700;color:#111827;line-height:1.4;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">{clean_title}</p>
                  <p style="margin:0 0 14px 0;font-size:12px;color:#6b7280;line-height:1.5;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">{clean_summary}</p>
                  <a href="{btn_url}" target="_blank" style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#6366f1);color:#ffffff;padding:9px 22px;border-radius:100px;text-decoration:none;font-size:12px;font-weight:700;font-family:-apple-system,BlinkMacSystemFont,sans-serif;letter-spacing:0.2px;">Postule maintenant &rarr;</a>
                </td>
              </tr>
            </table>"""
            text_lines.append(f"- {self._clean_plain_text(item.get('mission_title', '')[:80])} (Score: {score:.0f}/100)")

        self._text_summary = "\n".join(text_lines) if text_lines else "Aucune mission correspondante cette semaine."

        # ── Section recommandations IA (2 conseils) ──
        reco_section = ""
        if recommendations:
            reco_items = ""
            for i, reco in enumerate(recommendations[:2], 1):
                clean_reco = self._clean_text(reco)
                reco_items += f"""
                <tr><td style="padding:10px 0;border-bottom:1px solid #f3f0ff;">
                  <table cellpadding="0" cellspacing="0" width="100%"><tr>
                    <td width="28" style="vertical-align:top;padding-top:1px;">
                      <div style="width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#a855f7);text-align:center;line-height:22px;display:inline-block;">
                        <span style="font-size:11px;font-weight:800;color:#fff;font-family:-apple-system,sans-serif;">{i}</span>
                      </div>
                    </td>
                    <td style="padding-left:8px;font-size:13px;color:#374151;line-height:1.6;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">{clean_reco}</td>
                  </tr></table>
                </td></tr>"""
            reco_section = f"""<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;background:#faf5ff;border-radius:14px;border:1px solid #e9d5ff;overflow:hidden;">
              <tr><td style="padding:20px 22px 4px 22px;">
                <p style="margin:0 0 2px 0;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#7c3aed;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">Conseils IA</p>
                <p style="margin:0 0 12px 0;font-size:16px;font-weight:800;color:#111827;font-family:-apple-system,BlinkMacSystemFont,sans-serif;letter-spacing:-0.2px;">Boostez votre profil</p>
                <table width="100%" cellpadding="0" cellspacing="0"><tbody>{reco_items}</tbody></table>
              </td></tr>
            </table>"""

        date_str = datetime.utcnow().strftime("%d %B %Y")
        clean_name = self._clean_text(individual.full_name.split()[0])  # Prénom seulement
        clean_domain = self._clean_text(individual.domain)
        nb_missions = len(scored_missions[:10])

        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NOBILIS X - Missions {date_str}</title>
</head>
<body style="margin:0;padding:0;background-color:#f8f7ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8f7ff;padding:30px 14px;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">
  <!-- HEADER -->
  <tr><td style="background:linear-gradient(160deg,#1e1b4b 0%,#312e81 55%,#3730a3 100%);border-radius:20px 20px 0 0;padding:36px 30px 32px 30px;text-align:center;">
    <h1 style="margin:0 0 6px 0;font-size:30px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">NOBILIS X</h1>
    <p style="margin:0 0 4px 0;font-size:12px;color:#a78bfa;font-weight:600;font-family:-apple-system,sans-serif;letter-spacing:1.5px;text-transform:uppercase;">Missions 100% en Ligne (Télétravail)</p>
    <p style="margin:0;font-size:13px;color:#94a3b8;font-weight:400;font-family:-apple-system,sans-serif;">Rapport Hebdomadaire &bull; {date_str}</p>

  </td></tr>

  <!-- BODY -->
  <tr><td style="background:#fefefe;padding:26px 20px;border-radius:0 0 20px 20px;border:1px solid #e5e7eb;border-top:none;">

    <!-- Greeting -->
    <p style="margin:0 0 4px 0;font-size:20px;font-weight:800;color:#111827;letter-spacing:-0.3px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">Salut {clean_name} &#x1F44B;</p>
    <p style="margin:0 0 22px 0;font-size:14px;color:#6b7280;line-height:1.6;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
      On a trouve <strong style="color:#7c3aed;">{nb_missions} mission{"s" if nb_missions > 1 else ""}</strong> qui matchent ton profil <strong style="color:#111827;">{clean_domain}</strong> cette semaine.
    </p>

    <!-- Missions -->
    {mission_rows}

    <!-- Recommandations IA -->
    {reco_section}

    <!-- CTA Footer -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
      <tr><td style="text-align:center;padding:20px 18px;background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:14px;">
        <p style="margin:0 0 6px 0;font-size:14px;font-weight:700;color:#ffffff;font-family:-apple-system,sans-serif;">Tu veux plus de missions ?</p>
        <p style="margin:0 0 14px 0;font-size:12px;color:#a5b4fc;font-family:-apple-system,sans-serif;">Mets a jour tes competences pour un meilleur matching.</p>
        <a href="https://wa.me/224627271397" style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#a855f7);color:#ffffff;padding:11px 24px;border-radius:100px;text-decoration:none;font-size:13px;font-weight:700;letter-spacing:-0.1px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">Contacte-nous &#x2192;</a>
      </td></tr>
    </table>

    <!-- Footer -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:20px;">
      <tr><td style="text-align:center;padding:8px;">
        <p style="margin:0 0 4px 0;font-size:11px;color:#9ca3af;font-family:-apple-system,sans-serif;">NOBILIS X &mdash; L'intelligence des marches</p>
        <p style="margin:0;font-size:10px;color:#d1d5db;font-family:-apple-system,sans-serif;">Fait en Guinee. Concu pour que les meilleurs gagnent.</p>
      </td></tr>
    </table>

  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""
        return html_content

    # ------------------------------------------------------------------
    #  Envoi (cascade de fournisseurs HTTPS - voir email_sender.py)
    # ------------------------------------------------------------------

    def _send_email_intelligent(self, to_email: str, subject: str, html_body: str) -> bool:
        """Envoie le mail en passant par la cascade de fournisseurs HTTPS.

        Voir app/services/email_sender.py : Brevo -> SMTP2GO -> Resend -> Mailjet -> SMTP.
        Leve EmailProviderError si aucun fournisseur n'a abouti (le detail de la
        reponse de l'API est conserve dans le message, pour les logs Render).
        """
        plain_text = self._clean_plain_text(getattr(self, '_text_summary', '') or subject)
        send_email(
            to_email=to_email,
            subject=self._clean_subject(subject),
            html_body=html_body,
            text_body=(
                "Salut,\n\nVoici tes missions de la semaine sur NOBILIS X.\n\n"
                f"{plain_text}"
            ),
        )
        return True

    # ------------------------------------------------------------------
    #  Email de bienvenue — Particulier
    # ------------------------------------------------------------------

    def send_welcome_email(self, individual: Individual) -> bool:
        """Envoie un email de bienvenue au particulier."""
        if not individual.email:
            return False

        plan = (individual.subscription_plan or "PASS").upper()
        plan_base = plan.replace("PENDING_", "")
        is_pending = plan.startswith("PENDING_")

        subject = f"Bienvenue sur NOBILIS X, {individual.full_name.split()[0]} !"
        clean_name = self._clean_text(individual.full_name.split()[0])
        clean_domain = self._clean_text(individual.domain)

        if is_pending:
            amount = "1 500 000" if plan_base == "ELITE" else "1 000 000"
            message_body = f"""
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;">Ta pre-inscription pour le plan <strong style="color:#a78bfa;">NOBILIS {plan_base}</strong> est enregistree.</p>
    <div style="background:rgba(124,58,237,0.1);border:1px solid #7c3aed;padding:18px;border-radius:12px;margin:20px 0;">
        <h3 style="color:#a78bfa;margin-top:0;font-size:16px;">Action requise : Paiement Orange Money</h3>
        <p style="color:#fff;line-height:1.6;margin-bottom:0;font-size:14px;">Pour activer ton abonnement et recevoir tes missions chaque lundi, fais un depot de <strong>{amount} GNF</strong> au :</p>
        <p style="color:#a78bfa;font-size:22px;font-weight:bold;text-align:center;margin:12px 0;">+224 627 27 13 97</p>
        <p style="color:#94a3b8;font-size:12px;margin:0;text-align:center;">Precise "NOBILIS" ou envoie la capture du paiement sur WhatsApp a ce numero.</p>
    </div>
            """
        else:
            message_body = f"""
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;"><strong>C'est bon, ton paiement a été validé ! Ton compte NOBILIS {plan_base} est maintenant 100% actif.</strong></p>
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;">Chaque <strong>lundi à 7h</strong>, tu recevras par mail tes meilleures missions 100% en ligne (télétravail) en <strong style="color:#fff;">{clean_domain}</strong> avec un score de compatibilité personnalisé.</p>
    <div style="background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.3);padding:14px 18px;border-radius:10px;margin:16px 0;">
        <p style="color:#c4b5fd;font-size:13px;margin:0;line-height:1.5;">💡 <strong>Astuce :</strong> Surveille bien ta boîte mail lundi matin à 7h00 précise !</p>
    </div>
            """

        html_body = f"""<!DOCTYPE html>
<html lang="fr"><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:20px;background:#0f0b2e;color:#fff;">
    <div style="max-width:500px;margin:0 auto;background:#1e1b4b;padding:40px;border-radius:20px;border:1px solid #312e81;">
    <h1 style="color:#a78bfa;font-size:26px;margin:0 0 4px 0;font-weight:900;">NOBILIS X</h1>
    <p style="color:#6366f1;font-size:11px;margin:0 0 24px 0;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">Missions 100% en Ligne</p>
    <h2 style="color:#fff;font-size:20px;font-weight:800;">Salut {clean_name} !</h2>
    {message_body}
    <hr style="border:1px solid #312e81;margin:24px 0;">
    <p style="color:#6366f1;font-size:12px;">trillionnx@gmail.com | +224 627 27 13 97</p>
    <p style="color:#4338ca;font-size:11px;">Fait en Guinee. Concu pour que les meilleurs gagnent.</p>
    </div>
</body></html>"""

        email_log = EmailLog(
            individual_id=individual.id,
            recipient_email=individual.email,
            subject=self._clean_subject(subject),
            status="pending",
        )
        self.db.add(email_log)
        self.db.flush()

        try:
            self._send_email_intelligent(individual.email, subject, html_body)
            email_log.status = "sent"
            email_log.sent_at = datetime.utcnow()
            self.db.commit()
            return True
        except Exception as e:
            email_log.status = "failed"
            email_log.error_message = str(e)[:500]
            self.db.commit()
            return False

    def send_expiration_reminder(self, individual: Individual, days_left: int) -> bool:
        """Envoie un rappel d'expiration au particulier."""
        if not individual.email:
            return False

        subject = f"⚠️ NOBILIS X - Ton abonnement expire dans {days_left} jours"
        clean_name = self._clean_text(individual.full_name.split()[0])

        message_body = f"""
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;"><strong>Attention {clean_name},</strong> ton abonnement <strong style="color:#a78bfa;">NOBILIS X</strong> expire dans <strong>{days_left} jours</strong>.</p>
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;">Renouvelle-le dès maintenant pour continuer à recevoir tes offres de missions freelance exclusives chaque lundi !</p>
    <div style="background:rgba(124,58,237,0.1);border:1px solid #7c3aed;padding:18px;border-radius:12px;margin:20px 0;">
        <h3 style="color:#a78bfa;margin-top:0;font-size:16px;">Comment renouveler ?</h3>
        <p style="color:#fff;line-height:1.6;margin-bottom:0;font-size:14px;">Fais un dépôt Orange Money au :</p>
        <p style="color:#a78bfa;font-size:22px;font-weight:bold;text-align:center;margin:12px 0;">+224 627 27 13 97</p>
        <p style="color:#94a3b8;font-size:12px;margin:0;text-align:center;">Envoie ensuite la capture sur WhatsApp pour prolonger automatiquement ton compte.</p>
    </div>
        """

        html_body = f"""<!DOCTYPE html>
<html lang="fr"><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:20px;background:#0f0b2e;color:#fff;">
    <div style="max-width:500px;margin:0 auto;background:#1e1b4b;padding:40px;border-radius:20px;border:1px solid #312e81;">
    <h1 style="color:#a78bfa;font-size:26px;margin:0 0 4px 0;font-weight:900;">NOBILIS X</h1>
    <p style="color:#6366f1;font-size:11px;margin:0 0 24px 0;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">Missions Freelance</p>
    {message_body}
    <hr style="border:1px solid #312e81;margin:24px 0;">
    <p style="color:#6366f1;font-size:12px;">trillionnx@gmail.com | +224 627 27 13 97</p>
    <p style="color:#4338ca;font-size:11px;">Fait en Guinee. Concu pour que les meilleurs gagnent.</p>
    </div>
</body></html>"""

        email_log = EmailLog(
            individual_id=individual.id,
            recipient_email=individual.email,
            subject=self._clean_subject(subject),
            status="pending",
        )
        self.db.add(email_log)
        self.db.flush()

        try:
            self._send_email_intelligent(individual.email, subject, html_body)
            email_log.status = "sent"
            email_log.sent_at = datetime.utcnow()
            self.db.commit()
            return True
        except Exception as e:
            email_log.status = "failed"
            email_log.error_message = str(e)[:500]
            self.db.commit()
            return False

    # ------------------------------------------------------------------
    #  Envoi + journalisation
    # ------------------------------------------------------------------

    def _dispatch(self, individual: Individual, subject: str, html_body: str) -> bool:
        """Journalise puis envoie. Toute erreur est tracee dans email_logs."""
        if not individual.email:
            return False

        email_log = EmailLog(
            individual_id=individual.id,
            recipient_email=individual.email,
            subject=self._clean_subject(subject),
            status="pending",
        )
        self.db.add(email_log)
        self.db.flush()

        try:
            self._send_email_intelligent(individual.email, subject, html_body)
            email_log.status = "sent"
            email_log.sent_at = datetime.utcnow()
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Échec envoi '{subject}' à {individual.email} : {e}")
            email_log.status = "failed"
            email_log.error_message = str(e)[:500]
            self.db.commit()
            return False

    # ------------------------------------------------------------------
    #  Alerte ELITE temps reel — Particulier
    # ------------------------------------------------------------------

    def send_elite_alert(self, individual: Individual, scored_missions: list[dict]) -> bool:
        """Alerte immediate sur des missions a fort score (ELITE uniquement)."""
        if not individual.email or not scored_missions:
            return False

        count = len(scored_missions)
        first_name = individual.full_name.split()[0]
        subject = f"ALERTE NOBILIS X - {count} mission{'s' if count > 1 else ''} qui te correspond{'ent' if count > 1 else ''}"

        cards = ""
        text_lines = []
        for item in scored_missions[:5]:
            score = item["score"]
            title = self._clean_text(item.get("mission_title", item.get("tender_title", ""))[:90])
            summary = self._clean_text(item.get("summary", item.get("explanation", ""))[:180])
            url = item.get("source_url", "") or "#"
            cards += f"""
            <div style="background:#1e1b4b;border:1px solid #312e81;border-left:4px solid #22c55e;border-radius:10px;padding:16px 18px;margin-bottom:12px;">
              <p style="margin:0 0 6px 0;font-size:11px;font-weight:800;color:#22c55e;letter-spacing:1px;">MATCH {score:.0f}/100</p>
              <p style="margin:0 0 6px 0;font-size:15px;font-weight:700;color:#ffffff;line-height:1.4;">{title}</p>
              <p style="margin:0 0 12px 0;font-size:13px;color:#94a3b8;line-height:1.55;">{summary}</p>
              <a href="{url}" style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#a855f7);color:#ffffff;padding:9px 20px;border-radius:100px;text-decoration:none;font-size:12px;font-weight:700;">Postule maintenant &#x2192;</a>
            </div>"""
            text_lines.append(f"- {self._clean_plain_text(item.get('mission_title', '')[:90])} ({score:.0f}/100)")

        self._text_summary = "\n".join(text_lines)

        body = (
            tpl.paragraph(
                tpl.INDIVIDUAL,
                f"<strong>{self._clean_text(first_name)}</strong>, on vient de repérer "
                f"{count} mission{'s' if count > 1 else ''} qui colle{'nt' if count > 1 else ''} vraiment à ton profil.",
            )
            + tpl.paragraph(
                tpl.INDIVIDUAL,
                "Tu la reçois tout de suite, sans attendre ton rapport : "
                "c'est l'avantage de ton abonnement <strong>NOBILIS ELITE</strong>.",
            )
            + cards
            + tpl.info_box(
                tpl.INDIVIDUAL,
                "Sur les missions en ligne, les premiers candidats sont souvent retenus. Postule vite.",
            )
        )

        html_body = tpl.render(
            tpl.INDIVIDUAL,
            heading=f"Alerte : {count} mission{'s' if count > 1 else ''} pour toi",
            body_html=body,
            preheader=f"{count} mission(s) à fort match viennent d'être détectées.",
        )
        return self._dispatch(individual, subject, html_body)

    # ------------------------------------------------------------------
    #  Expiration et renouvellement — Particulier
    # ------------------------------------------------------------------

    def send_expiration_notice(self, individual: Individual) -> bool:
        """Previent que l'abonnement vient d'expirer."""
        if not individual.email:
            return False

        plan = plan_base(individual)
        first_name = self._clean_text(individual.full_name.split()[0])
        subject = f"NOBILIS X - Tes missions sont en pause, {individual.full_name.split()[0]}"

        if plan == "PASS":
            body = (
                tpl.paragraph(tpl.INDIVIDUAL, f"<strong>{first_name}</strong>, ton essai gratuit de {PASS_TRIAL_DAYS} jours vient de se terminer.")
                + tpl.paragraph(tpl.INDIVIDUAL, "Tu ne recevras plus de missions tant que ton compte n'est pas activé.")
                + tpl.action_box(
                    tpl.INDIVIDUAL,
                    heading="Activer ton abonnement",
                    intro="Fais un dépôt Orange Money de <strong>1 000 000 GNF</strong> (ENTRY) ou <strong>1 500 000 GNF</strong> (ELITE) au :",
                    footnote="Précise « NOBILIS » lors du dépôt, puis envoie la capture sur WhatsApp pour une activation immédiate.",
                )
            )
        else:
            amount = "1 500 000" if plan == "ELITE" else "1 000 000"
            body = (
                tpl.paragraph(tpl.INDIVIDUAL, f"<strong>{first_name}</strong>, ton abonnement <strong>NOBILIS {plan}</strong> a expiré.")
                + tpl.paragraph(tpl.INDIVIDUAL, "Tes missions sont en pause : tu ne recevras plus rien tant que le renouvellement n'est pas fait.")
                + tpl.action_box(
                    tpl.INDIVIDUAL,
                    heading="Renouveler pour 1 an",
                    intro="Fais un dépôt Orange Money de",
                    amount=amount,
                    footnote="Envoie ensuite la capture sur WhatsApp : ton compte est réactivé dans la foulée.",
                )
                + tpl.info_box(tpl.INDIVIDUAL, "Ton profil et tes compétences sont conservés. Le renouvellement les réactive à l'identique.")
            )

        html_body = tpl.render(
            tpl.INDIVIDUAL,
            heading="Ton accès est en pause",
            body_html=body,
            preheader="Tes missions NOBILIS X sont en pause. Voici comment les relancer.",
        )
        return self._dispatch(individual, subject, html_body)

    def send_renewal_confirmation(self, individual: Individual) -> bool:
        """Confirme un renouvellement ou un retablissement."""
        if not individual.email:
            return False

        plan = plan_base(individual)
        first_name = self._clean_text(individual.full_name.split()[0])
        expires = getattr(individual, "subscription_expires_at", None)
        expires_str = expires.strftime("%d/%m/%Y") if expires else "dans 1 an"
        cadence = "chaque matin à 7h" if plan == "ELITE" else "chaque lundi à 8h"
        nb = 10 if plan == "ELITE" else 5

        subject = f"NOBILIS X - Abonnement renouvelé, {individual.full_name.split()[0]}"

        body = (
            tpl.paragraph(tpl.INDIVIDUAL, f"<strong>Merci {first_name} !</strong> Ton paiement est confirmé et ton compte <strong>NOBILIS {plan}</strong> est de nouveau actif.")
            + tpl.paragraph(tpl.INDIVIDUAL, f"Tu recevras tes <strong>{nb} meilleures missions</strong> {cadence}, avec ton score de compatibilité.")
            + tpl.info_box(tpl.INDIVIDUAL, f"Ton abonnement court jusqu'au <strong>{expires_str}</strong>. On te préviendra 7 jours puis 3 jours avant l'échéance.")
        )

        if plan == "ELITE":
            body += tpl.paragraph(
                tpl.INDIVIDUAL,
                "En ELITE, tu reçois aussi les <strong>alertes immédiates</strong> à 8h45 et 18h45 "
                "dès qu'une mission à fort match apparaît.",
            )

        html_body = tpl.render(
            tpl.INDIVIDUAL,
            heading="Compte réactivé",
            body_html=body,
            preheader=f"Ton compte NOBILIS {plan} est actif jusqu'au {expires_str}.",
        )
        return self._dispatch(individual, subject, html_body)

    # ------------------------------------------------------------------
    #  Rapport hebdomadaire — Particulier
    # ------------------------------------------------------------------

    def send_weekly_report(
        self,
        individual: Individual,
        scored_missions: list[dict],
        recommendations: list[str] | None = None,
    ) -> bool:
        """Envoie le rapport periodique au particulier."""
        if not individual.email:
            return False

        nb = len(scored_missions[:10 if is_elite(individual) else 5])
        periode = "aujourd'hui" if is_elite(individual) else "cette semaine"
        subject = f"NOBILIS X - {nb} missions pour toi {periode}"
        html_body = self._build_individual_html(individual, scored_missions, recommendations)

        email_log = EmailLog(
            individual_id=individual.id,
            recipient_email=individual.email,
            subject=self._clean_subject(subject),
            status="pending",
        )
        self.db.add(email_log)
        self.db.flush()

        try:
            self._send_email_intelligent(individual.email, subject, html_body)
            email_log.status = "sent"
            email_log.sent_at = datetime.utcnow()
            self.db.commit()
            return True
        except Exception as e:
            email_log.status = "failed"
            email_log.error_message = str(e)[:500]
            self.db.commit()
            return False

    # ------------------------------------------------------------------
    #  Envoi en masse — Tous les particuliers
    # ------------------------------------------------------------------

    def send_all_individual_reports(self, elite_only: bool | None = None, only_if_new: bool = False) -> dict:
        """Envoie le rapport aux particuliers eligibles.

        elite_only=None  : tous les particuliers actifs (cycle hebdomadaire du lundi)
        elite_only=True  : uniquement les ELITE (rapport quotidien de 7h)
        elite_only=False : uniquement les non-ELITE (PASS et ENTRY)

        only_if_new=True : n'envoie qu'aux particuliers dont le classement contient
        au moins une mission parue dans les dernieres 24h.
        """
        from app.services.scorer_individual import IndividualScorerService
        from app.services.ai_analyzer import AIAnalyzerService

        recent_ids: set[int] = set()
        if only_if_new:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_ids = {
                row[0]
                for row in self.db.query(Tender.id).filter(Tender.created_at >= cutoff).all()
            }
            if not recent_ids:
                logger.info("Aucune nouvelle mission depuis 24h — rapport quotidien ELITE ignoré")
                return {"sent": 0, "failed": 0, "skipped": 0}

        individuals = self.db.query(Individual).filter(
            Individual.email.isnot(None)
        ).all()

        scorer = IndividualScorerService(self.db)
        ai_service = AIAnalyzerService(self.db)

        results = {"sent": 0, "failed": 0, "skipped": 0}

        for individual in individuals:
            try:
                # Comptes en attente de paiement, suspendus ou expirés : pas de rapport
                if not is_active(individual):
                    logger.info(
                        f"⏸️ Rapport ignoré pour {individual.full_name} : "
                        f"{blocked_reason(individual)}"
                    )
                    results["skipped"] += 1
                    continue

                # Les ELITE ont leur rapport quotidien : pas de doublon le lundi.
                if elite_only is not None and is_elite(individual) != elite_only:
                    results["skipped"] += 1
                    continue

                # ── Scoring des missions freelance ──
                scored = scorer.score_all_for_individual(individual)
                if not scored:
                    logger.info(f"📭 Aucune mission pour {individual.full_name}")
                    results["skipped"] += 1
                    continue

                if only_if_new and not any(item["tender_id"] in recent_ids for item in scored[:10]):
                    logger.info(f"Aucune nouveauté pour {individual.full_name} — rapport quotidien ignoré")
                    results["skipped"] += 1
                    continue

                # ── Enrichir avec les résumés IA ──
                for item in scored:
                    analysis = self.db.query(Analysis).filter(
                        Analysis.tender_id == item["tender_id"]
                    ).first()
                    if analysis:
                        item["summary"] = analysis.summary or ""

                # ── Recommandations IA (2 conseils personnalisés) ──
                reco = None
                try:
                    reco = ai_service.generate_individual_recommendations(
                        individual, scored[:5]
                    )
                except AttributeError:
                    # Méthode pas encore implémentée dans ai_analyzer
                    logger.debug("generate_individual_recommendations non disponible")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur génération recommandations IA : {e}")

                # ── Envoi ──
                success = self.send_weekly_report(individual, scored, recommendations=reco)
                results["sent" if success else "failed"] += 1

            except Exception as e:
                logger.error(f"❌ Erreur rapport pour {individual.full_name}: {e}")
                results["failed"] += 1

        logger.info(
            f"📊 Rapports individuels envoyés: {results['sent']} | "
            f"échoués: {results['failed']} | ignorés: {results['skipped']}"
        )
        return results
