# scripts/test_full_flow.py
"""
Script de test complet pour NOBILIS X V2.
Vérifie l'inscription des Entreprises et des Freelances.
Cible : http://localhost:8000
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_enterprise_registration():
    print("🏢 Test Inscription Entreprise...")
    payload = {
        "name": "Test Enterprise V2",
        "sector": "Travaux Publics & Construction, Informatique & Telecommunications",
        "email": "test_ent@example.com",
        "zones": "Conakry, Kindia",
        "specific_keywords": "solaire, audit",
        "exclude_keywords": "maintenance",
        "min_budget": 50000000,
        "max_budget": 500000000,
        "experience_years": 5,
        "technical_capacity": "Entreprise de test certifiée ISO-9001.",
        "subscription_plan": "PASS"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/enterprises", json=payload)
        if response.status_code in [200, 201]:
            print("✅ Entreprise inscrite avec succès !")
            return response.json()["id"]
        else:
            print(f"❌ Erreur Entreprise ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return None

def test_freelance_registration():
    print("\n👨‍💻 Test Inscription Freelance...")
    payload = {
        "full_name": "Test Freelancer V2",
        "email": "test_free@example.com",
        "country": "Guinée",
        "domain": "Développement Web & Mobile, Intelligence Artificielle & Data",
        "skills": "Python, React, FastAPI, Machine Learning",
        "experience_level": "Intermédiaire",
        "experience_years": 4,
        "mission_type": "Les deux",
        "desired_rate": 60.0,
        "languages": "FR+EN",
        "portfolio_url": "https://test-portfolio.com",
        "bio": "Développeur full-stack passionné par l'automatisation.",
        "subscription_plan": "PASS",
        "whatsapp": "+224600112233"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/individuals", json=payload)
        if response.status_code in [200, 201]:
            print("✅ Freelance inscrit avec succès !")
            return response.json()["id"]
        else:
            print(f"❌ Erreur Freelance ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return None

def verify_cycle():
    print("\n📡 Vérification du Cycle Hebdomadaire (Simulation)...")
    # Note: On ne peut pas facilement déclencher le scheduler APScheduler via API 
    # sans endpoint dédié, mais on vérifie que les routes existent.
    try:
        resp = requests.get(f"http://localhost:8000/")
        if resp.status_code == 200:
            print("✅ Serveur actif et page d'accueil accessible.")
    except:
        print("❌ Serveur injoignable.")

if __name__ == "__main__":
    print("🚀 DÉMARRAGE DU TEST COMPLET NOBILIS X V2\n")
    
    ent_id = test_enterprise_registration()
    free_id = test_freelance_registration()
    
    verify_cycle()
    
    print("\n🏁 TEST TERMINÉ.")
    if ent_id and free_id:
        print("✨ BILAN : Le Backend est synchronisé avec le nouveau Frontend !")
    else:
        print("⚠️ BILAN : Des erreurs ont été détectées. Vérifiez les schémas.")
