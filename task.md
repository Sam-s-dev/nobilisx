# JOURNAL DE BORD - NOBILIS X V2

Ce fichier sert de mémoire permanente pour le projet. État d'avancement des étapes (1 à 10).

## Étape 1 : Cycle Hebdomadaire (Monday 7h) ✅
- [x] Migration de la planification vers le lundi matin.

## Étape 2 : Modèles & Migration Individual ✅
- [x] Création du modèle `Individual`.
- [x] Refactorisation de `EmailLog`.
- [x] Script de migration Alembic corrigé et validé.

## Étape 3 : Anti-blocage & Stealth Scraper ✅
- [x] Rotation de 10 User-Agents.
- [x] Délais aléatoires (3-8s).
- [x] Fenêtre de scraping (Samedi 22h30).
- [x] Séparation Collecte (Samedi) / Analyse (Lundi).

## Étape 4 : InternationalTenderScraper (UNGM + UNDP) ✅
- [x] Ajout de la colonne `source_country` dans le modèle `Tender`.
- [x] Script de migration Alembic (`7a2e4b3c1d5f`) créé.
- [x] Création de `app/services/scraper_international.py`.
- [x] Intégration dans `app/scheduler/jobs.py`.

## Étape 5 : FreelanceScraper (Upwork + Freelancer) ✅
- [x] Recherche technique (RSS vs Scraping) effectuée.
- [x] Création de `app/services/scraper_freelance.py`.
- [x] Intégration dans `app/scheduler/jobs.py`.

## Étape 6 : IndividualScorerService ✅
- [x] Création de `app/services/scorer_individual.py`.
- [x] Pondération V2 : Compétences 50% / Type mission 25% / Expérience 15% / Langue 10%.
- [x] Matching compétences (skills explicites + bonus domaine + match partiel SequenceMatcher).
- [x] Détection type de mission (Court/Long terme via mots-clés).
- [x] Détection niveau requis (Expert/Intermédiaire/Débutant).
- [x] Détection langue de la mission (FR/EN heuristique).
- [x] Exclusion mots-clés (score forcé à 0).
- [x] Filtre tarif souhaité (ajustement multiplicatif).
- [x] Méthode `score_all_for_individual()` filtre `source_country="freelance"`.
- [x] Syntaxe Python validée.

## Étape 7 : Email Templates Particuliers + Router ✅
- [x] Création de `app/services/email_service_individual.py`.
- [x] Template HTML premium violet/indigo (distinct du bleu marine entreprises).
- [x] Ton direct orienté action ("Salut", "Postule maintenant", tutoiement).
- [x] Email de bienvenue avec flow paiement Orange Money.
- [x] Rapport hebdomadaire top 10 missions + score compatibilité.
- [x] Section recommandations IA (2 conseils "Boostez votre profil").
- [x] Envoi en masse `send_all_individual_reports()` avec filtre PASS expiré / PENDING.
- [x] Création de `app/routers/individuals.py` (CRUD complet).
- [x] POST /individuals (inscription + email bienvenue auto).
- [x] GET /individuals (liste filtrée domaine/pays).
- [x] GET/PUT/DELETE /individuals/{id}.
- [x] Enregistrement du router dans `app/main.py`.
- [x] Syntaxe Python validée (3 fichiers).

## Étape 8 : Scheduler complet (Bi-segment) ✅
- [x] Ajout de `generate_individual_recommendations` dans `AIAnalyzerService`.
- [x] Orchestration du scraping (Samedi 22h30) pour toutes les sources (Local, Intl, Freelance).
- [x] Orchestration du cycle complet (Lundi 07h00) : Analyse IA + Envois aux deux segments.
- [x] Respect de la stratégie anti-blocage (fenêtres horaires séparées).
- [x] Syntaxe Python validée (2 fichiers).

## Étapes suivantes
- [ ] Étape 9 : Frontend V2 (Vue bi-segment).
- [ ] Étape 10 : Tests finaux et déploiement.
