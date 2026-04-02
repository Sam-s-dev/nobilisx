# RÉSUMÉ TECHNIQUE - NOBILIS X V2

Ce fichier contient le détail des modifications apportées au code source pour la Version 2.

## Étape 4 : InternationalTenderScraper (Terminée ✅)

L'Étape 4 a été implémentée avec succès le 2026-04-02.

- [x] **app/models/tender.py** : Ajout de la colonne `source_country` (String 10) pour distinguer les marchés locaux (GN) et mondiaux (international).
- [x] **alembic/versions/7a2e4b3c1d5f_add_source_country_to_tenders.py** : Script de migration Alembic manuel créé pour mettre à jour votre base de données au déploiement.
- [x] **app/services/scraper_international.py** : Nouveau service de collecte globale utilisant la rotation d'agents, les délais furtifs et pilotant UNGM (ONU) et UNDP (PNUD).
- [x] **app/scheduler/jobs.py** : Le scraper international a été inséré dans le job du samedi à 22h30.

## Prochaine phase : Étape 5 (Freelance)
Nous préparons l'ajout des sources Upwork et Freelancer..com pour le segment particulier "Individual".
