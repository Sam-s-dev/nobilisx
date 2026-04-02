# app/services/email_service_individual.py
"""
Service d'envoi d'emails pour les PARTICULIERS — NOBILIS X V2

Différences avec le service Entreprises :
- Ton plus direct, plus jeune, orienté action ("Postule maintenant")
- Pas de PDF joint (email HTML uniquement)
- Top 10 missions avec score de compatibilité
- 2 conseils IA personnalisés (vs 2-5 pour les entreprises)
- Template visuel distinct (gradient violet/indigo vs bleu marine/or)
"""

import base64
import html
import logging
import os
import re
import unicodedata
import urllib.parse
from datetime import datetime, timedelta

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.individual import Individual
from app.models.tender import Tender
from app.models.analysis import Analysis
from app.models.email_log import EmailLog

logger = logging.getLogger(__name__)
settings = get_settings()


class IndividualEmailService:
    """Service d'envoi d'emails pour les particuliers via API HTTP Mailjet"""

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

        for item in scored_missions[:10]:
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
    <p style="margin:0 0 4px 0;font-size:12px;color:#a78bfa;font-weight:600;font-family:-apple-system,sans-serif;letter-spacing:1.5px;text-transform:uppercase;">Missions Freelance</p>
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
    #  Envoi via API HTTP Mailjet (Port 443)
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
    )
    def _send_mailjet_http(self, to_email: str, subject: str, html_body: str) -> bool:
        """Envoie un email via l'API REST Mailjet v3.1 (Port 443)."""
        logger.info(f"📨 Envoi Mailjet (Individual) -> {to_email}")

        api_url = "https://api.mailjet.com/v3.1/send"
        auth = (settings.SMTP_USER, settings.SMTP_PASSWORD)

        plain_text = self._clean_plain_text(getattr(self, '_text_summary', '') or subject)

        payload = {
            "Messages": [
                {
                    "From": {
                        "Email": settings.SMTP_FROM,
                        "Name": "NOBILIS X"
                    },
                    "To": [
                        {
                            "Email": to_email
                        }
                    ],
                    "Subject": self._clean_subject(subject),
                    "TextPart": f"Salut,\n\nVoici tes missions de la semaine sur NOBILIS X.\n\n{plain_text}",
                    "HTMLPart": html_body,
                    "CustomID": f"indiv_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
                }
            ]
        }

        try:
            response = requests.post(api_url, json=payload, auth=auth, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ Email envoyé (Individual) à {to_email}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Echec HTTP Mailjet (Individual): {e}")
            if e.response is not None:
                logger.error(f"Response Mailjet: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Echec envoi Mailjet (Individual): {e}")
            raise

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
            amount = "À définir"  # Tarifs particuliers à définir (Section 8)
            message_body = f"""
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;">Ta pre-inscription pour le plan <strong style="color:#a78bfa;">NOBILIS {plan_base}</strong> est enregistree.</p>
    <div style="background:rgba(124,58,237,0.1);border:1px solid #7c3aed;padding:18px;border-radius:12px;margin:20px 0;">
        <h3 style="color:#a78bfa;margin-top:0;font-size:16px;">Action requise : Paiement Orange Money</h3>
        <p style="color:#fff;line-height:1.6;margin-bottom:0;font-size:14px;">Pour activer ton abonnement et recevoir tes missions chaque lundi, fais un depot au :</p>
        <p style="color:#a78bfa;font-size:22px;font-weight:bold;text-align:center;margin:12px 0;">+224 627 27 13 97</p>
        <p style="color:#94a3b8;font-size:12px;margin:0;text-align:center;">Envoie la capture du paiement sur WhatsApp a ce numero.</p>
    </div>
            """
        else:
            message_body = f"""
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;">C'est bon, tu es inscrit ! Chaque <strong style="color:#a78bfa;">lundi a 7h</strong>, tu recevras tes meilleures missions en <strong style="color:#fff;">{clean_domain}</strong>.</p>
    <p style="color:#e2e8f0;line-height:1.7;font-size:14px;">NOBILIS X analyse <strong style="color:#fff;">Upwork</strong> et <strong style="color:#fff;">Freelancer.com</strong> pour toi et calcule un <strong style="color:#a78bfa;">Score de Compatibilite</strong> personnalise.</p>
    <div style="background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.3);padding:14px 18px;border-radius:10px;margin:16px 0;">
        <p style="color:#c4b5fd;font-size:13px;margin:0;line-height:1.5;">💡 <strong>Astuce :</strong> Plus tes competences sont detaillees, meilleur sera le matching. N'hesite pas a mettre a jour ton profil !</p>
    </div>
            """

        html_body = f"""<!DOCTYPE html>
<html lang="fr"><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:20px;background:#0f0b2e;color:#fff;">
    <div style="max-width:500px;margin:0 auto;background:#1e1b4b;padding:40px;border-radius:20px;border:1px solid #312e81;">
    <h1 style="color:#a78bfa;font-size:26px;margin:0 0 4px 0;font-weight:900;">NOBILIS X</h1>
    <p style="color:#6366f1;font-size:11px;margin:0 0 24px 0;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">Missions Freelance</p>
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
            self._send_mailjet_http(individual.email, subject, html_body)
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
    #  Rapport hebdomadaire — Particulier
    # ------------------------------------------------------------------

    def send_weekly_report(
        self,
        individual: Individual,
        scored_missions: list[dict],
        recommendations: list[str] | None = None,
    ) -> bool:
        """Envoie le rapport hebdomadaire au particulier."""
        if not individual.email:
            return False

        subject = f"NOBILIS X - {len(scored_missions[:10])} missions pour toi cette semaine"
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
            self._send_mailjet_http(individual.email, subject, html_body)
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

    def send_all_individual_reports(self) -> dict:
        """
        Envoie le rapport hebdomadaire à tous les particuliers éligibles.
        Utilise IndividualScorerService pour le scoring.
        """
        from app.services.scorer_individual import IndividualScorerService
        from app.services.ai_analyzer import AIAnalyzerService

        individuals = self.db.query(Individual).filter(
            Individual.email.isnot(None)
        ).all()

        scorer = IndividualScorerService(self.db)
        ai_service = AIAnalyzerService(self.db)

        results = {"sent": 0, "failed": 0, "skipped": 0}

        for individual in individuals:
            try:
                # ── Bloquer les comptes en attente de paiement ──
                plan = (individual.subscription_plan or "PASS").upper()

                if plan.startswith("PENDING_"):
                    logger.info(
                        f"⏸️ Paiement en attente pour {individual.full_name} ({plan}) — rapport ignoré"
                    )
                    results["skipped"] += 1
                    continue

                # ── Bloquer les PASS expirés (essai 2 jours) ──
                if plan == "PASS":
                    if datetime.utcnow() > individual.created_at + timedelta(days=2):
                        logger.info(f"⏸️ PASS expiré pour {individual.full_name} — rapport ignoré")
                        results["skipped"] += 1
                        continue

                # ── Scoring des missions freelance ──
                scored = scorer.score_all_for_individual(individual)
                if not scored:
                    logger.info(f"📭 Aucune mission pour {individual.full_name}")
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
