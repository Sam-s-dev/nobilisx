# scripts/retest_mailjet_v1.py
import requests

def test_mailjet_v1():
    # Identifiants extraits exactement de votre copier-coller V1
    api_key = "97ffe0fca74582cd318dd06862fd9c86"
    api_secret = "447bffba0ab3cea380fdb268d83a2332"
    sender = "generalouki21@gmail.com"
    
    print(f"🚀 Retest ULTIME des clés V1 pour {sender}...")
    
    url = "https://api.mailjet.com/v3.1/send"
    
    payload = {
        "Messages": [
            {
                "From": {"Email": sender, "Name": "Nobilis X V1 Re-Test"},
                "To": [{"Email": sender}],
                "Subject": "Re-Test Ultime Clés V1",
                "TextPart": "Si cet email arrive, c'est que les clés V1 fonctionnent encore !",
                "HTMLPart": "<h3>Test réussi</h3>"
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, auth=(api_key, api_secret), timeout=30)
        print(f"Status Mailjet: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ MIRACLE ! Les clés V1 sont encore actives !")
            print(response.json())
        elif response.status_code == 401:
            print("❌ CONFIRMÉ (401) : Ces clés sont définitivement désactivées par Mailjet.")
        else:
            print(f"❓ Réponse inattendue ({response.status_code}): {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur réseau : {e}")

if __name__ == "__main__":
    test_mailjet_v1()
