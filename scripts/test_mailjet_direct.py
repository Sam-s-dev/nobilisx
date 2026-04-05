# scripts/test_mailjet_direct.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_mailjet():
    api_key = os.getenv("SMTP_USER")
    api_secret = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_SENDER")
    
    print(f"🚀 Testing Mailjet API with Key: {api_key[:5]}...")
    
    url = "https://api.mailjet.com/v3.1/send"
    
    payload = {
        "Messages": [
            {
                "From": {
                    "Email": sender,
                    "Name": "Nobilis X Test"
                },
                "To": [
                    {
                        "Email": sender,
                        "Name": "Admin"
                    }
                ],
                "Subject": "Test Mailjet V2",
                "TextPart": "Si vous recevez ceci, vos clés Mailjet pour la V2 sont VALIDES !",
                "HTMLPart": "<h3>Validation réussie</h3><p>Vos clés Mailjet sont parfaitement configurées.</p>"
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, auth=(api_key, api_secret))
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCÈS : L'email a été envoyé !")
            print(response.json())
        else:
            print(f"❌ ÉCHEC : {response.text}")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    test_mailjet()
