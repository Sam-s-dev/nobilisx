# Nobilis X

Solution automatisée de collecte, analyse et distribution d'appels d'offres en Guinée.

## 🚀 Fonctionnalités

- **Scraping Multi-Sources** : Collecte quotidienne depuis JAO Guinée, mais aussi **International** (UNGM, UNDP) et **Freelance** (Upwork, Freelancer.com).
- **Segments Entreprise & Particulier** : Support complet pour les entreprises (appels d'offres) et les freelances (missions spécifiques).
- **Analyse par IA (Groq)** : Synthèse automatique et extraction de données structurées (budget, lieu, deadline).
- **Matching Intelligent** : Calcul de score de pertinence personnalisé pour chaque profil (Entreprise ou Freelance).
- **Rapports Automatisés** : Envoi hebdomadaire par email des meilleures opportunités scorées.
- **20 Secteurs d'Activité** : Couverture complète des domaines économiques et techniques.

## 🛠️ Installation

```bash
# cloner le dépôt
git clone <repo_url>
cd tender-analyzer

# installer les dépendances
pip install -r requirements.txt

# configurer les variables d'environnement
cp .env.example .env # et remplir les clés API
```

## 🖥️ Lancement

```bash
uvicorn app.main:app --reload
```

L'application sera disponible sur `http://localhost:8000`.

## ⚙️ Configuration (.env)

- `GROQ_API_KEY` : Votre clé API Groq (gratuite et performante).
- `DATABASE_URL` : URL de votre base de données PostgreSQL.
- `SMTP_*` : Configuration de votre serveur d'envoi d'emails.

## 📄 Licence

Propriété de TrillionBerg / Luxe.


