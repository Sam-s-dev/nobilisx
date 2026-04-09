# app/services/scorer_individual.py
"""
Service de scoring PARTICULIERS — NOBILIS X V2
Calcule un score de compatibilité (0-100) entre une mission freelance et un particulier.

Pondération V2 :
  - Compétences (skills)        : 50%
  - Type de mission             : 25%
  - Niveau / Expérience         : 15%
  - Langue                      : 10%

+ Bonus mots-clés spécifiques (+30% max)
+ Exclusion mots-clés (score forcé à 0)
"""

import logging
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models.individual import Individual
from app.models.tender import Tender
from app.models.analysis import Analysis

logger = logging.getLogger(__name__)


class IndividualScorerService:
    """Calcul du score de compatibilité mission/particulier"""

    # ──────────────────────────────────────────────────
    # Pondérations V2 (Section 4.3 du doc)
    # ──────────────────────────────────────────────────
    WEIGHTS = {
        "skills": 50,           # 50% — Correspondance compétences
        "mission_type": 25,     # 25% — Court/Long terme
        "experience": 15,       # 15% — Niveau + années
        "language": 10,         # 10% — Langue
    }

    # ──────────────────────────────────────────────────
    # Mapping domaine → compétences associées
    # Utilisé pour enrichir le matching même si le
    # particulier n'a pas listé chaque skill exactement.
    # ──────────────────────────────────────────────────
    DOMAIN_SKILLS = {
        "développement web/mobile": [
            "javascript", "react", "vue", "angular", "node", "python",
            "django", "flask", "fastapi", "php", "laravel", "html", "css",
            "typescript", "nextjs", "frontend", "backend", "fullstack",
            "mobile", "flutter", "swift", "kotlin", "android", "ios",
            "api", "rest", "graphql", "sql", "postgresql", "mongodb",
        ],
        "design": [
            "figma", "photoshop", "illustrator", "ui", "ux", "design",
            "branding", "logo", "wireframe", "prototype", "sketch",
            "adobe xd", "canva", "graphic", "web design", "visual",
        ],
        "journalisme et communication": [
            "rédaction", "copywriting", "seo", "content", "blog",
            "article", "journalisme", "presse", "édition", "relecture",
            "ghostwriting", "storytelling", "newsletter", "rédacteur",
            "communication", "pr", "relations presse", "médias",
        ],
        "marketing digital": [
            "seo", "sem", "google ads", "facebook ads", "social media",
            "marketing", "analytics", "email marketing", "growth",
            "community manager", "campaign", "branding", "ads",
            "content marketing", "influencer", "tiktok", "instagram",
        ],
        "traduction": [
            "traduction", "translation", "interprète", "localisation",
            "français", "anglais", "arabe", "espagnol", "transcription",
        ],
        "comptabilité/finance": [
            "comptabilité", "finance", "audit", "fiscalité", "bilan",
            "trésorerie", "excel", "sage", "quickbooks", "paie",
            "budget", "reporting", "contrôle de gestion", "accounting",
        ],
        "consulting": [
            "consultant", "conseil", "stratégie", "management",
            "business plan", "étude de marché", "analyse", "audit",
            "formation", "coaching", "projet", "pmo",
        ],
    }

    # ──────────────────────────────────────────────────
    # Mots-clés indicateurs du type de mission
    # ──────────────────────────────────────────────────
    SHORT_TERM_KEYWORDS = [
        "quick", "urgent", "asap", "one-time", "small project",
        "court terme", "ponctuel", "simple", "fast", "1 week",
        "2 weeks", "sprint", "mvp", "prototype", "fix", "bug",
        "hotfix", "landing page", "one page",
    ]
    LONG_TERM_KEYWORDS = [
        "long term", "ongoing", "full-time", "part-time",
        "long terme", "contrat", "monthly", "retainer",
        "dedicated", "permanent", "6 months", "1 year",
        "maintenance", "support continu", "saas", "startup",
    ]

    # ──────────────────────────────────────────────────
    # Mots-clés de niveau requis dans les offres
    # ──────────────────────────────────────────────────
    EXPERT_KEYWORDS = [
        "senior", "expert", "lead", "architect", "10+ years",
        "5+ years", "experienced", "avancé", "confirmé", "principal",
    ]
    INTERMEDIATE_KEYWORDS = [
        "intermediate", "mid-level", "mid level", "intermédiaire",
        "2-5 years", "3+ years", "some experience",
    ]
    BEGINNER_KEYWORDS = [
        "junior", "entry-level", "entry level", "débutant",
        "intern", "trainee", "no experience", "beginner", "stagiaire",
    ]

    def __init__(self, db: Session):
        self.db = db

    # ══════════════════════════════════════════════════
    #  CRITÈRE 1 : Compétences (50%)
    # ══════════════════════════════════════════════════
    def _skills_score(self, individual: Individual, mission_text: str) -> float:
        """
        Calcule la correspondance entre les compétences du particulier
        et le texte de la mission (titre + description + analyse IA).
        Retourne un score 0.0 → 1.0
        """
        if not mission_text:
            return 0.3  # Score neutre faible

        text = mission_text.lower()

        # ── 1. Skills explicites du profil ──
        user_skills = []
        if individual.skills:
            user_skills = [s.strip().lower() for s in individual.skills.split(",") if s.strip()]

        if not user_skills:
            return 0.2  # Pas de compétences renseignées

        # Comptage des matchs directs
        direct_matches = 0
        for skill in user_skills:
            if skill in text:
                direct_matches += 1
            else:
                # Tentative de match partiel (ex: "react" dans "reactjs")
                for word in text.split():
                    if SequenceMatcher(None, skill, word).ratio() > 0.8:
                        direct_matches += 0.7
                        break

        skill_ratio = direct_matches / len(user_skills) if user_skills else 0

        # ── 2. Bonus domaine ──
        domain_bonus = 0.0
        if individual.domain:
            domain_key = individual.domain.lower().strip()
            domain_skills = self.DOMAIN_SKILLS.get(domain_key, [])
            if domain_skills:
                domain_matches = sum(1 for ds in domain_skills if ds in text)
                if domain_matches >= 3:
                    domain_bonus = 0.15
                elif domain_matches >= 1:
                    domain_bonus = 0.08

        # Score final compétences : ratio de skills matchés + bonus domaine
        raw_score = min(1.0, skill_ratio + domain_bonus)

        return raw_score

    # ══════════════════════════════════════════════════
    #  CRITÈRE 2 : Type de mission (25%)
    # ══════════════════════════════════════════════════
    def _mission_type_score(self, individual: Individual, mission_text: str) -> float:
        """
        Évalue la compatibilité du type de mission (Court/Long/Les deux).
        Retourne un score 0.0 → 1.0
        """
        if not individual.mission_type or not mission_text:
            return 0.5  # Score neutre

        text = mission_text.lower()
        pref = individual.mission_type.lower().strip()

        # Détecter le type de la mission dans le texte
        short_signals = sum(1 for kw in self.SHORT_TERM_KEYWORDS if kw in text)
        long_signals = sum(1 for kw in self.LONG_TERM_KEYWORDS if kw in text)

        mission_is_short = short_signals > long_signals
        mission_is_long = long_signals > short_signals
        mission_is_unknown = short_signals == long_signals  # Pas clair

        # "Les deux" → toujours compatible
        if pref in ("les deux", "both"):
            return 1.0

        if pref in ("court terme", "court", "short"):
            if mission_is_short:
                return 1.0
            elif mission_is_unknown:
                return 0.6
            else:
                return 0.3  # Long terme mais le user veut du court

        if pref in ("long terme", "long"):
            if mission_is_long:
                return 1.0
            elif mission_is_unknown:
                return 0.6
            else:
                return 0.3  # Court terme mais le user veut du long

        return 0.5  # Valeur par défaut

    # ══════════════════════════════════════════════════
    #  CRITÈRE 3 : Niveau / Expérience (15%)
    # ══════════════════════════════════════════════════
    def _experience_score(self, individual: Individual, mission_text: str) -> float:
        """
        Évalue la compatibilité du niveau d'expérience.
        Un Expert qui postule à un poste Junior → OK (surqualifié mais compatible).
        Un Débutant qui postule à un poste Expert → pénalité.
        Retourne un score 0.0 → 1.0
        """
        text = (mission_text or "").lower()
        user_level = (individual.experience_level or "").lower().strip()
        user_years = individual.experience_years or 0

        # ── Détecter le niveau requis par la mission ──
        expert_signals = sum(1 for kw in self.EXPERT_KEYWORDS if kw in text)
        intermediate_signals = sum(1 for kw in self.INTERMEDIATE_KEYWORDS if kw in text)
        beginner_signals = sum(1 for kw in self.BEGINNER_KEYWORDS if kw in text)

        signals = {
            "expert": expert_signals,
            "intermédiaire": intermediate_signals,
            "débutant": beginner_signals,
        }
        mission_level = max(signals, key=signals.get) if any(signals.values()) else "unknown"

        # ── Mapping niveau utilisateur → rang numérique ──
        level_ranks = {
            "débutant": 1, "beginner": 1, "junior": 1,
            "intermédiaire": 2, "intermediate": 2, "mid": 2,
            "expert": 3, "senior": 3, "advanced": 3,
        }
        user_rank = level_ranks.get(user_level, 2)  # Par défaut intermédiaire

        mission_rank_map = {"débutant": 1, "intermédiaire": 2, "expert": 3, "unknown": 0}
        mission_rank = mission_rank_map.get(mission_level, 0)

        # ── Calcul du score ──
        if mission_rank == 0:
            # Niveau non détecté → score basé sur les années d'expérience
            if user_years >= 5:
                return 1.0
            elif user_years >= 3:
                return 0.8
            elif user_years >= 1:
                return 0.6
            return 0.4

        # Niveau détecté → comparaison
        diff = user_rank - mission_rank

        if diff == 0:
            return 1.0       # Niveau exactement aligné
        elif diff > 0:
            return 0.85      # Surqualifié (OK mais pas idéal)
        elif diff == -1:
            return 0.5       # Un niveau en dessous
        else:
            return 0.25      # Très sous-qualifié

    # ══════════════════════════════════════════════════
    #  CRITÈRE 4 : Langue (10%)
    # ══════════════════════════════════════════════════
    def _language_score(self, individual: Individual, mission_text: str) -> float:
        """
        Évalue la compatibilité linguistique.
        Retourne un score 0.0 → 1.0
        """
        text = (mission_text or "").lower()
        user_lang = (individual.languages or "").lower().strip()

        # Détecter la langue de la mission
        fr_signals = sum(1 for w in ["français", "french", "francophone", "fr "] if w in text)
        en_signals = sum(1 for w in ["english", "anglais", "anglophone", "en "] if w in text)

        # Heuristique supplémentaire : détecter la langue du texte lui-même
        # Les missions Upwork/Freelancer sont majoritairement en anglais
        common_en_words = ["the", "and", "for", "with", "this", "that", "project", "looking"]
        common_fr_words = ["le", "la", "les", "pour", "avec", "nous", "projet", "cherchons"]

        en_text_signals = sum(1 for w in common_en_words if f" {w} " in f" {text} ")
        fr_text_signals = sum(1 for w in common_fr_words if f" {w} " in f" {text} ")

        mission_is_en = (en_signals + en_text_signals) > (fr_signals + fr_text_signals)
        mission_is_fr = (fr_signals + fr_text_signals) > (en_signals + en_text_signals)

        # "FR+EN" ou "Les deux" → toujours compatible
        if any(x in user_lang for x in ["fr+en", "en+fr", "les deux", "both", "bilingue"]):
            return 1.0

        if any(x in user_lang for x in ["fr", "français", "french"]):
            if mission_is_fr:
                return 1.0
            elif not mission_is_en:
                return 0.6  # Langue incertaine
            else:
                return 0.3  # Mission anglophone, user francophone

        if any(x in user_lang for x in ["en", "anglais", "english"]):
            if mission_is_en:
                return 1.0
            elif not mission_is_fr:
                return 0.6  # Langue incertaine
            else:
                return 0.3  # Mission francophone, user anglophone

        return 0.5  # Pas de préférence → neutre

    # ══════════════════════════════════════════════════
    #  EXCLUSION & BONUS MOTS-CLÉS
    # ══════════════════════════════════════════════════
    def _keyword_adjustment(self, individual: Individual, mission_text: str) -> float:
        """
        Mots-clés à exclure → retourne 0.0 (score tué)
        Pas d'exclusion → retourne 1.0 (pas de changement)
        Le modèle Individual n'a pas de specific_keywords, seulement exclude_keywords.
        """
        text = mission_text.lower()

        if individual.exclude_keywords:
            excluded = [k.strip().lower() for k in individual.exclude_keywords.split(",") if k.strip()]
            for kw in excluded:
                if kw in text:
                    logger.info(f"🚫 Exclusion trouvée ({kw}) pour {individual.full_name}")
                    return 0.0

        return 1.0

    # ══════════════════════════════════════════════════
    #  TARIF (filtre souple, non pondéré)
    # ══════════════════════════════════════════════════
    def _rate_filter(self, individual: Individual, mission_text: str) -> float:
        """
        Si le particulier a un tarif souhaité, on pénalise légèrement
        les missions dont le budget est trop éloigné.
        Ce n'est pas un critère pondéré mais un ajustement multiplicatif (0.5-1.0).
        """
        if not individual.desired_rate or individual.desired_rate <= 0:
            return 1.0  # Pas de tarif → pas de pénalité

        text = (mission_text or "").lower()

        # Essayer d'extraire un budget du texte (patterns courants)
        import re
        # Pattern : $500, $1000-$5000, $50/hr, etc.
        budget_matches = re.findall(r'\$(\d[\d,]*)', text)
        if not budget_matches:
            return 1.0  # Budget non détecté → pas de pénalité

        try:
            # Prendre le budget le plus élevé trouvé
            budgets = [float(b.replace(",", "")) for b in budget_matches]
            max_budget = max(budgets)

            rate = individual.desired_rate

            if max_budget >= rate * 0.8:
                return 1.0   # Budget OK
            elif max_budget >= rate * 0.5:
                return 0.85  # Budget un peu bas
            else:
                return 0.7   # Budget très bas par rapport au tarif souhaité
        except (ValueError, TypeError):
            return 1.0

    # ══════════════════════════════════════════════════
    #  CALCUL DU SCORE GLOBAL
    # ══════════════════════════════════════════════════
    def calculate_score(
        self,
        individual: Individual,
        tender: Tender,
        analysis: Analysis | None = None,
    ) -> dict:
        """
        Calcule le score global de compatibilité (0-100) pour un particulier.

        Retourne un dict avec :
          - score: float (0-100)
          - details: dict avec les sous-scores
          - explanation: str lisible
        """
        # Construire le texte complet de la mission pour l'analyse
        parts = [
            tender.title or "",
            tender.description or "",
            tender.raw_text or "",
        ]
        if analysis:
            parts.append(analysis.summary or "")
            if analysis.extracted_sector:
                parts.append(analysis.extracted_sector)

        mission_text = " ".join(parts).strip()

        if not mission_text:
            return {
                "score": 0.0,
                "details": {"skills": 0, "mission_type": 0, "experience": 0, "language": 0, "keyword_adj": 1.0},
                "explanation": "Aucun texte disponible pour la mission.",
            }

        # ── Vérification exclusion en premier ──
        kw_adj = self._keyword_adjustment(individual, mission_text)
        if kw_adj == 0.0:
            return {
                "score": 0.0,
                "details": {"skills": 0, "mission_type": 0, "experience": 0, "language": 0, "keyword_adj": 0.0},
                "explanation": "Exclusion : Mot-clé interdit détecté",
            }

        # ── Calcul des 4 critères ──
        skills_s = self._skills_score(individual, mission_text)
        mission_s = self._mission_type_score(individual, mission_text)
        experience_s = self._experience_score(individual, mission_text)
        language_s = self._language_score(individual, mission_text)

        # ── Score pondéré de base ──
        base_weighted_score = (
            skills_s * self.WEIGHTS["skills"]
            + mission_s * self.WEIGHTS["mission_type"]
            + experience_s * self.WEIGHTS["experience"]
            + language_s * self.WEIGHTS["language"]
        )

        # ── Ajustement tarif (multiplicatif) ──
        rate_adj = self._rate_filter(individual, mission_text)
        final_score = base_weighted_score * rate_adj

        # Cap à 100
        final_score = min(100.0, round(final_score, 1))

        # ── Explication lisible ──
        explanation_parts = [
            f"Compétences: {skills_s:.0%}",
            f"Type mission: {mission_s:.0%}",
            f"Expérience: {experience_s:.0%}",
            f"Langue: {language_s:.0%}",
        ]
        if rate_adj < 1.0:
            explanation_parts.append(f"Ajust. tarif: {rate_adj:.0%}")

        explanation = " | ".join(explanation_parts)

        return {
            "score": final_score,
            "details": {
                "skills": round(skills_s * 100, 1),
                "mission_type": round(mission_s * 100, 1),
                "experience": round(experience_s * 100, 1),
                "language": round(language_s * 100, 1),
                "rate_adj": rate_adj,
                "keyword_adj": kw_adj,
            },
            "explanation": explanation,
        }

    # ══════════════════════════════════════════════════
    #  SCORING EN MASSE POUR UN PARTICULIER
    # ══════════════════════════════════════════════════
    def score_all_for_individual(self, individual: Individual) -> list[dict]:
        """
        Calcule les scores pour toutes les missions freelance analysées
        vs un particulier donné.

        Filtre : source_country == 'freelance' (missions Upwork/Freelancer).

        Retourne une liste triée par score décroissant.
        """
        # Récupérer les analyses de missions freelance uniquement
        analyses = (
            self.db.query(Analysis)
            .join(Tender)
            .filter(
                Tender.source_country == "freelance",
                Tender.is_analyzed == True,  # noqa: E712
            )
            .all()
        )

        results = []

        for analysis in analyses:
            tender = analysis.tender
            score_result = self.calculate_score(individual, tender, analysis)

            results.append({
                "tender_id": tender.id,
                "mission_title": tender.title,
                "score": score_result["score"],
                "details": score_result["details"],
                "explanation": score_result["explanation"],
                "source_url": tender.source_url or "",
            })

        # Trier par score décroissant
        results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(
            f"📊 {len(results)} scores calculés pour {individual.full_name} "
            f"(top: {results[0]['score'] if results else 'N/A'})"
        )

        return results
