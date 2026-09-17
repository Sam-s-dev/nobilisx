# app/services/subscription.py
"""
Source de verite unique pour l'etat des abonnements.

Avant ce module, la duree de l'essai PASS etait codee en dur a trois endroits
avec trois valeurs differentes (2 jours dans les routes d'analyse, 7 jours dans
l'envoi des rapports, 7 jours a l'inscription). Un client perdait le tableau de
bord au bout de 48h tout en continuant a recevoir ses mails pendant 5 jours.

Toute verification d'abonnement doit passer par ici.

Etats d'un plan (champ `subscription_plan`) :
    PASS / ENTRY / ELITE      -> actif
    PENDING_ENTRY, PENDING_...-> inscrit mais paiement non valide
    SUSPENDED_ENTRY, ...      -> expire ou suspendu par l'admin
"""

from datetime import datetime, timedelta

# Duree de l'essai gratuit. Doit correspondre a la promesse de la page de vente.
PASS_TRIAL_DAYS = 7

# Duree d'un abonnement paye (ENTRY / ELITE).
PAID_PLAN_DAYS = 365

PENDING_PREFIX = "PENDING_"
SUSPENDED_PREFIX = "SUSPENDED_"


def raw_plan(user) -> str:
    """Plan tel qu'il est stocke, prefixes compris."""
    return (getattr(user, "subscription_plan", None) or "PASS").upper()


def plan_base(user) -> str:
    """Plan sans prefixe : PASS, ENTRY ou ELITE."""
    return raw_plan(user).replace(PENDING_PREFIX, "").replace(SUSPENDED_PREFIX, "")


def is_pending(user) -> bool:
    """Inscrit mais paiement pas encore valide par l'admin."""
    return raw_plan(user).startswith(PENDING_PREFIX)


def is_suspended(user) -> bool:
    """Expire, ou suspendu manuellement."""
    return raw_plan(user).startswith(SUSPENDED_PREFIX)


def is_elite(user) -> bool:
    return plan_base(user) == "ELITE"


def is_trial(user) -> bool:
    return plan_base(user) == "PASS"


def expires_at(user) -> datetime | None:
    """Date d'expiration. Retombe sur created_at + duree du plan si absente.

    Le fallback couvre les comptes crees avant l'ajout de la colonne
    subscription_expires_at.
    """
    explicit = getattr(user, "subscription_expires_at", None)
    if explicit:
        return explicit

    created = getattr(user, "created_at", None)
    if not created:
        return None

    days = PASS_TRIAL_DAYS if is_trial(user) else PAID_PLAN_DAYS
    return created + timedelta(days=days)


def is_expired(user, now: datetime | None = None) -> bool:
    """True si la date d'expiration est depassee."""
    deadline = expires_at(user)
    if not deadline:
        return False
    return (now or datetime.utcnow()) > deadline


def days_left(user, now: datetime | None = None) -> int | None:
    """Jours restants avant expiration (negatif si depasse)."""
    deadline = expires_at(user)
    if not deadline:
        return None
    return (deadline.date() - (now or datetime.utcnow()).date()).days


def is_active(user, now: datetime | None = None) -> bool:
    """True si le compte doit recevoir ses rapports et acceder au service.

    Un compte est actif s'il n'est ni en attente de paiement, ni suspendu,
    ni expire.
    """
    if is_pending(user) or is_suspended(user):
        return False
    return not is_expired(user, now)


def blocked_reason(user, now: datetime | None = None) -> str | None:
    """Message explicatif si le compte est bloque, sinon None."""
    if is_pending(user):
        return (
            f"Paiement en attente pour le plan {plan_base(user)}. "
            "Envoyez votre preuve de depot Orange Money au +224 627 27 13 97 sur WhatsApp."
        )
    if is_suspended(user):
        return "Abonnement suspendu. Contactez le +224 627 27 13 97 pour le retablir."
    if is_expired(user, now):
        if is_trial(user):
            return (
                f"Votre essai gratuit de {PASS_TRIAL_DAYS} jours est termine. "
                "Choisissez un plan NOBILIS ENTRY ou ELITE pour continuer."
            )
        return "Votre abonnement a expire. Renouvelez-le pour reprendre vos rapports."
    return None
