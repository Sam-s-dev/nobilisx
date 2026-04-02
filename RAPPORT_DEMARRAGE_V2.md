# NOBILIS X V2 — Rapport de Démarrage

**Date** : 2 avril 2026  
**Auteur** : Développeur Python Senior  
**Document de référence** : `NOBILIS_X_V2_Specification.docx`

---

## 1. Confirmation : Les 10 Sections du Document V2 Comprises

| # | Section | Résumé de compréhension |
|---|---------|------------------------|
| 1 | **Contexte & Pourquoi une V2** | La V1 cible uniquement les entreprises guinéennes (JAO, DGCMP, TELEMO). Deux recommandations terrain : ouvrir aux particuliers (freelancers, étudiants) + aller à l'international. NOBILIS X passe d'un outil de niche B2B local à une plateforme SaaS bi-segment, bi-marché. |
| 2 | **Architecture Globale V2** | Deux portes d'entrée (Entreprise / Particulier), même infrastructure technique. Passage de quotidien à **hebdomadaire (lundi 7h)**. Raisons : économie tokens Groq, moins de blocage scraping, rapport plus dense, meilleure délivrabilité email. |
| 3 | **Stratégie Anti-Blocage** | Point le plus critique. Délais aléatoires 3-8s, User-Agent rotatif (10 profils), respect robots.txt, scraping **uniquement samedi soir 22h-2h**, retry backoff 30min sur erreur 429, cache local URLs, pas de téléchargement massif de PDF. Sources peu nombreuses mais fiables. |
| 4 | **Fonctionnalités Complètes V2** | **Entreprises** : JAO+TELEMO (local) + UNGM+UNDP (international), scoring 35/30/20/15, rapport PDF+email, recommandations IA (2 ENTRY, 5 ELITE), alertes temps réel ELITE. **Particuliers** : Upwork RSS + Freelancer API + LinkedIn optionnel, scoring 50/25/15/10, email HTML orienté action. |
| 5 | **Plan de Développement (10 étapes)** | Ordre strict à respecter : 1) Scheduler lundi → 2) Modèle Individual → 3) Scraper anti-blocage → 4) International scraper → 5) Freelance scraper → 6) IndividualScorer → 7) Email+Router particuliers → 8) Scheduler deux segments → 9) Frontend deux portes → 10) Tests+Prod. Durée totale : 19-27 jours. |
| 6 | **Modèle Individual (17 champs)** | id, full_name, email, country, domain (liste prédéfinie), skills (mots-clés), experience_level (Débutant/Intermédiaire/Expert), experience_years, mission_type (Court/Long/Les deux), desired_rate (optionnel, USD), languages (FR/EN/FR+EN), portfolio_url, bio, exclude_keywords, subscription_plan, created_at, updated_at. |
| 7 | **LinkedIn — Intégration prudente** | 1 requête/semaine max, samedi soir 23h-2h, 20 premières offres seulement, User-Agent rotatif, délai 5-10s. Désactivation automatique si blocage (erreur 429) pendant 2 semaines. Si 3 échecs → désactivation définitive, le système tourne sur Upwork+Freelancer seulement. |
| 8 | **Tarification (principes)** | Facturation annuelle pour les deux segments, PASS 2 jours conservé, tarif particulier < tarif entreprise. Paiement exclusif Orange Money +224 627 27 13 97. Plans PENDING_ENTRY et PENDING_ELITE bloqués jusqu'au paiement. |
| 9 | **Ce qui ne change PAS** | Stack inchangée (FastAPI, PostgreSQL, SQLAlchemy, Docker, Railway, Groq, Mailjet). Modèles existants (Enterprise, Tender, Analysis, EmailLog, Subscription) **intacts**. Services existants conservés. Endpoints API compatibles. Coût : 0 GNF. |
| 10 | **Conclusion** | Livraison progressive en 10 étapes indépendantes. Chaque étape testable isolément. Cible adressable multipliée par 5-10x. Coût opérationnel maintenu à zéro. |

---

## 2. État Exact du Code V1

### 2.1 Inventaire complet des fichiers

#### Core (3 fichiers)
| Fichier | Lignes | Rôle |
|---------|--------|------|
| `app/main.py` | 181 | Application FastAPI, lifespan (startup/shutdown), CORS, montage static, routers, health check, scheduler status |
| `app/config.py` | 109 | Pydantic Settings : DATABASE_URL, Groq API, SMTP/Mailjet, URLs scraping, retry config |
| `app/database.py` | 116 | SQLAlchemy engine avec pool, SessionLocal, get_db (FastAPI), get_db_context (scheduler), init_db avec retry |

#### Modèles SQLAlchemy (5 modèles, 6 fichiers)
| Fichier | Lignes | Champs | Relations |
|---------|--------|--------|-----------|
| `app/models/enterprise.py` | 50 | 12 champs (name, sector, min/max_budget, zones, experience_years, technical_capacity, email, specific_keywords, exclude_keywords, logo_url, subscription_plan, created_at, updated_at) | → email_logs, subscriptions |
| `app/models/tender.py` | 41 | 10 champs (title, description, raw_text, sector, estimated_budget, location, deadline, source_url, pdf_path, is_analyzed, created_at) | → analysis |
| `app/models/analysis.py` | 44 | 10 champs (tender_id FK, enterprise_id FK, summary, score, explanation, extracted_sector/budget/location/deadline, created_at) | → tender |
| `app/models/email_log.py` | 45 | 8 champs (enterprise_id FK, tender_id FK, recipient_email, subject, status, error_message, sent_at, created_at) | → enterprise |
| `app/models/subscription.py` | 98 | 8 champs + dictionnaire SUBSCRIPTION_PLANS (PASS/ENTRY/ELITE avec prix, durée, features) | → enterprise |
| `app/models/__init__.py` | 11 | Import centralisé des 5 modèles | — |

#### Services (6 services, 7 fichiers)
| Fichier | Lignes | Rôle |
|---------|--------|------|
| `app/services/scraper.py` | 645 | ScraperService : scraping JAO Guinée (11 catégories) + DGCMP + TELEMO. Parsing HTML, déduplication, stockage en base. Mapping secteurs entreprises → catégories JAO. |
| `app/services/ai_analyzer.py` | 364 | AIAnalyzerService : appels Groq LLaMA 70B via SDK OpenAI. Résumé 200 mots, extraction structurée (secteur, budget, localisation, deadline). Analyse locale si texte < 300 car. Batch par 5 avec pauses. Recommandations personnalisées (2 ENTRY, 5 ELITE). |
| `app/services/scorer.py` | 285 | ScorerService : scoring 0-100 (secteur 35%, budget 30%, zone 20%, expérience 15%). Synonymes 20 catégories. Bonus mots-clés +30% max. Exclusion mots-clés (score=0). |
| `app/services/email_service.py` | 445 | EmailService : Mailjet API REST v3.1 (port 443). Template HTML premium. Nettoyage encodage/emojis. Email bienvenue. Rapport quotidien avec PDF joint. Gestion plans PENDING et PASS expiré. |
| `app/services/pdf_parser.py` | 112 | PDFParserService : extraction texte via PyPDF2, max 50 pages, nettoyage caractères. |
| `app/services/report_generator.py` | 544 | ReportGeneratorService : PDF A4 premium via ReportLab. Couverture bleu marine/or, sommaire exécutif avec KPIs, profil entreprise, top 10 avec barres de progression, recommandations, upsell ENTRY→ELITE. |
| `app/services/__init__.py` | 2 | Fichier init vide | — |

#### Routers FastAPI (3 routers, 4 fichiers)
| Fichier | Lignes | Endpoints |
|---------|--------|-----------|
| `app/routers/enterprises.py` | 145 | `POST /enterprises` (création + email bienvenue), `POST /{id}/logo` (upload), `GET /enterprises` (liste filtrée), `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `app/routers/tenders.py` | 120 | `GET /tenders` (liste paginée + filtres secteur/location/analyzed), `GET /{id}`, `GET /enterprises/{id}/report/pdf` (téléchargement PDF) |
| `app/routers/analyses.py` | 266 | `GET /analysis/{id}` (scoring), `GET /analysis/report/{id}`, `POST /analysis/send-report/{id}`, `POST /analysis/send-all-reports`, `POST /analysis/test-email/{id}` (cycle complet instantané) |

#### Scheduler (1 fichier)
| Fichier | Lignes | Jobs |
|---------|--------|------|
| `app/scheduler/jobs.py` | 220 | ~~`job_daily_cycle` (7h quotidien)~~ → **`job_weekly_cycle` (lundi 7h)** ✅ MIGRÉ, `job_elite_realtime_alert` (2h, 8h-20h ELITE), `init_scheduler()`, `shutdown_scheduler()` |

#### Schemas Pydantic (6 fichiers)
| Fichier | Classes |
|---------|---------|
| `enterprise.py` | EnterpriseBase, EnterpriseCreate, EnterpriseUpdate, EnterpriseResponse |
| `tender.py` | TenderResponse, TenderListResponse |
| `analysis.py` | AnalysisResponse, AnalysisDetailResponse |
| `email_log.py` | EmailLogResponse |
| `subscription.py` | SubscriptionCreate, SubscriptionResponse, PlanInfo |

#### Infra & Autres
| Fichier | État |
|---------|------|
| `Dockerfile` | ✅ Présent |
| `docker-compose.yml` | ✅ Présent (app + db PostgreSQL) |
| `requirements.txt` | ✅ Présent |
| `alembic.ini` | ⚠️ Fichier vide (pas de config Alembic active) |
| `supabase_init.sql` | ✅ Script SQL d'initialisation |
| `app/static/index.html` | ✅ Frontend actuel (segment entreprises uniquement) |
| `migrate_db.py` | ✅ Script de migration manuelle |

---

## 3. Conflits entre Code V1 et Spécifications V2

### Conflit 1 — Fréquence du Scheduler ✅ RÉSOLU (Étape 1)
| | V1 (avant) | V2 (après correction) |
|---|---|---|
| Cycle principal | `CronTrigger(hour=7)` — **quotidien** | `CronTrigger(day_of_week='mon', hour=7, minute=0)` — **lundi hebdomadaire** ✅ |
| Scraping | Intégré dans le cycle quotidien | Reste intégré pour l'instant. Séparation (samedi soir) prévue Étape 8 |
| ELITE temps réel | Toutes les 2h (8h-20h) | Conservé tel quel — sera ajusté Étape 8 |

### Conflit 2 — DGCMP Activé par Défaut
- **V1** : DGCMP scrapé activement dans `scrape_tenders()` (lignes 597-602 de scraper.py)
- **V2** : DGCMP doit être **désactivé par défaut** (code conservé mais non exécuté)
- **Résolution prévue** : Étape 3 (refactorisation ScraperService)

### Conflit 3 — Pas d'Anti-Blocage Structuré
- **V1** : Un seul User-Agent statique (Chrome 120.0), pas de délai aléatoire, pas de rotation
- **V2** : User-Agent rotatif (10 profils), délais 3-8s, scraping samedi soir uniquement
- **Résolution prévue** : Étape 3

### Conflit 4 — Sources Internationales Absentes
- **V1** : Uniquement JAO + DGCMP + TELEMO (Guinée locale)
- **V2** : Ajouter UNGM + UNDP (entreprises international), Upwork RSS + Freelancer API + LinkedIn (particuliers)
- **Résolution prévue** : Étapes 4 et 5

### Conflit 5 — Segment Particuliers Totalement Absent
- **V1** : Aucune infrastructure pour les particuliers
- **V2** : Modèle Individual (17 champs), FreelanceScraper, IndividualScorerService (50/25/15/10), email template, router /individuals
- **Résolution prévue** : Étapes 2, 5, 6, 7

### Conflit 6 — Descriptions et Labels (cosmétique)
- **V1** : Références à "quotidien", "24h/24", "DGCMP" dans main.py, email templates, subscription plans
- **V2** : Doit refléter "hebdomadaire", "lundi 7h", sources V2
- **Résolution** : main.py corrigé ✅. email_service.py et subscription.py seront mis à jour aux étapes appropriées sans toucher à leur logique (Section 9 du doc V2).

### Conflit 7 — Alembic Non Configuré
- **V1** : `alembic.ini` existe mais est **vide**. Pas de dossier `alembic/` avec migrations.
- **V2** : Le document demande une migration Alembic pour le modèle Individual
- **Résolution prévue** : Étape 2 — initialiser Alembic proprement

---

## 4. Proposition pour l'Étape 1 — Migration Scheduler ✅ TERMINÉE

### Ce qui a été fait

**Fichier 1 : `app/scheduler/jobs.py`** — 4 modifications :
1. Docstring module : "quotidien" → "Lundi 7h : Cycle complet hebdomadaire"
2. Fonction renommée : `job_daily_cycle()` → `job_weekly_cycle()`
3. CronTrigger modifié : `CronTrigger(hour=settings.SCRAPE_SCHEDULE_HOUR)` → `CronTrigger(day_of_week='mon', hour=7, minute=0)`
4. Tous les messages de log : "QUOTIDIEN" → "HEBDOMADAIRE" (4 occurrences)
5. ID et nom du job : `daily_cycle` → `weekly_cycle`

**Fichier 2 : `app/main.py`** — 2 modifications :
1. Docstring : "NOBILIS X" → "NOBILIS X V2"
2. Description FastAPI : sources JAO/TELEMO/UNGM/UNDP, "chaque lundi à 7h"

### Ce qui n'a PAS été modifié (conformément à la Section 9 du doc V2)
- Aucun modèle (Enterprise, Tender, Analysis, EmailLog, Subscription)
- Aucun service (scraper, ai_analyzer, scorer, email_service, pdf_parser, report_generator)
- Aucun router (enterprises, tenders, analyses)
- Aucun schema Pydantic

### Vérifications effectuées
- ✅ Syntaxe Python validée sur les deux fichiers
- ✅ Zéro référence résiduelle à `daily_cycle` dans tout le code
- ✅ Les références à "quotidien" restantes sont dans des fichiers non concernés par l'Étape 1 (email templates, subscription plans, index.html) — seront mises à jour aux étapes appropriées

---

## 5. Prochaine Étape : Étape 2 — Modèle Individual

En attente de ton approbation pour commencer. L'Étape 2 comprendra :
1. Créer `app/models/individual.py` avec les 17 champs de la Section 6
2. Créer `app/models/individual_email_log.py` (IndividualEmailLog)
3. Créer `app/schemas/individual.py` (IndividualCreate, IndividualUpdate, IndividualResponse)
4. Mettre à jour `app/models/__init__.py`
5. Mettre à jour `app/schemas/__init__.py`
6. Initialiser Alembic et créer la première migration

---

*NOBILIS X — Fait en Guinée. Conçu pour que les meilleurs gagnent.*
