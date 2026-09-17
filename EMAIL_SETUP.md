# Configuration de l'envoi d'emails (production)

## Pourquoi ça marche en local mais pas une fois déployé

En local, l'application envoie via **SMTP Gmail** (port 587). Sur Render, Railway
ou Fly.io, **les ports SMTP sortants (25, 465, 587) sont bloqués** : la connexion
n'aboutit jamais et aucun mail ne part.

La seule méthode fiable en production est une **API REST en HTTPS (port 443)**,
jamais bloquée. L'application essaie maintenant les fournisseurs dans cet ordre :

```
brevo  ->  smtp2go  ->  resend  ->  mailjet  ->  smtp
```

Le premier configuré qui accepte le message l'emporte ; si un fournisseur tombe
en panne ou atteint son quota, le suivant prend automatiquement le relais.

## Pourquoi Resend seul ne suffit pas ici

Resend **exige un nom de domaine vérifié par DNS** pour écrire à des
destinataires quelconques. Sans domaine, le seul expéditeur autorisé est
`onboarding@resend.dev`, qui n'accepte **que l'adresse du propriétaire du
compte** comme destinataire — tout envoi vers un client renvoie une erreur HTTP 403.

Comme l'expéditeur du projet est une adresse Gmail (`trillionnx@gmail.com`),
Resend est inutilisable tel quel. Il reste en place dans la cascade : le jour
où un domaine est acheté et vérifié, il suffit de renseigner `RESEND_FROM`.

## Solution recommandée : Brevo (gratuit, sans domaine)

300 mails/jour gratuits, et **aucun nom de domaine requis** : si le domaine de
l'expéditeur n'est pas authentifié, Brevo réécrit automatiquement l'expéditeur
en `@brevosend.com` et l'envoi passe quand même.

1. Créer un compte sur [brevo.com](https://www.brevo.com) (gratuit, sans carte).
2. **Senders, Domains & Dedicated IPs > Senders > Add a sender**
   → saisir `trillionnx@gmail.com`, puis valider avec le code reçu sur cette boîte.
3. **SMTP & API > API Keys > Generate a new API key** → copier la clé.
4. Sur Render : **Dashboard > votre service > Environment > Add Environment Variable**

   | Clé | Valeur |
   |---|---|
   | `BREVO_API_KEY` | la clé copiée à l'étape 3 |
   | `EMAIL_FROM` | `trillionnx@gmail.com` |
   | `EMAIL_FROM_NAME` | `NOBILIS X` |

5. Redéployer (Render redémarre automatiquement après l'ajout des variables).

## Secours recommandé : SMTP2GO (gratuit, sans domaine)

1 000 mails/mois, également sans domaine. Utile quand le quota Brevo du jour est
atteint — la cascade bascule toute seule.

1. Compte sur [smtp2go.com](https://www.smtp2go.com).
2. **Sending > Verified Senders > Single Sender Emails** → ajouter et valider
   `trillionnx@gmail.com`.
3. **Sending > API Keys** → créer une clé.
4. Sur Render, ajouter `SMTP2GO_API_KEY`.

> Sans domaine vérifié, SMTP2GO limite le compte à 25 envois/heure. C'est
> suffisant pour un rôle de secours.

## Option long terme : Resend + un domaine (~1 à 10 €/an)

Meilleure délivrabilité (les mails partent de votre propre domaine, pas de
mention « via brevosend.com ») et 3 000 mails/mois.

1. Acheter un domaine (Namecheap, OVH, Cloudflare…).
2. [resend.com/domains](https://resend.com/domains) > **Add Domain**, puis poser
   les enregistrements DNS proposés (SPF, DKIM) chez le registrar.
3. Une fois le statut `verified`, ajouter sur Render :
   `RESEND_FROM=contact@votre-domaine.com`
4. Pour le mettre en tête de la cascade : `EMAIL_PROVIDER_ORDER=resend,brevo,smtp2go`

## Vérifier la configuration

### Depuis le navigateur (sur l'app déployée)

```
https://votre-app.onrender.com/admin/email_config?password=VOTRE_MOT_DE_PASSE
```

Affiche l'expéditeur, l'ordre des fournisseurs, les clés détectées et les
avertissements — **sans envoyer de mail**.

```
https://votre-app.onrender.com/admin/test_email?email=vous@exemple.com&password=VOTRE_MOT_DE_PASSE
```

Envoie un mail de test et indique **quel fournisseur a été utilisé**. En cas
d'échec, le champ `error` contient la réponse exacte de l'API (et non plus un
simple « 403 Forbidden »).

```
https://votre-app.onrender.com/admin/email_logs?password=VOTRE_MOT_DE_PASSE
```

Historique des envois avec le motif d'échec de chacun.

### En ligne de commande (local ou Shell Render)

```bash
python scripts/test_email.py --config-only              # état de la config
python scripts/test_email.py vous@exemple.com           # teste chaque fournisseur
python scripts/test_email.py vous@exemple.com --provider brevo
```

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `EMAIL_FROM` | Adresse expéditeur (défaut : `SMTP_FROM`) |
| `EMAIL_FROM_NAME` | Nom affiché (défaut : `NOBILIS X`) |
| `EMAIL_PROVIDER` | `auto` (défaut) ou un seul fournisseur : `brevo`, `smtp2go`, `resend`, `mailjet`, `smtp` |
| `EMAIL_PROVIDER_ORDER` | Ordre personnalisé, ex. `resend,brevo,smtp` |
| `BREVO_API_KEY` | Clé API Brevo |
| `SMTP2GO_API_KEY` / `SMTP2GO_FROM` | Clé API SMTP2GO, expéditeur dédié (optionnel) |
| `RESEND_API_KEY` / `RESEND_FROM` | Clé API Resend, expéditeur **sur domaine vérifié** |
| `MAILJET_API_KEY` / `MAILJET_SECRET_KEY` | Clés Mailjet |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS` | SMTP classique (local uniquement) |

## En cas de problème

| Symptôme | Cause | Correctif |
|---|---|---|
| `Aucun fournisseur d'email configuré` | Aucune clé API sur Render | Ajouter `BREVO_API_KEY` |
| `connexion à smtp.gmail.com:587 impossible` | Ports SMTP bloqués par l'hébergeur | Ajouter `BREVO_API_KEY` |
| `l'expéditeur n'est pas un domaine vérifié` (Resend) | Expéditeur Gmail | Utiliser Brevo, ou vérifier un domaine et renseigner `RESEND_FROM` |
| Brevo HTTP 400 `sender not valid` | Expéditeur non validé dans Brevo | Refaire l'étape 2 (Add a sender) |
| Mails en spam | Domaine non authentifié | Acheter un domaine et l'authentifier (SPF/DKIM) chez le fournisseur |
