# scripts/retest_mailjet_v1_new_sender.py
import requests

def test():
    api_key = "97ffe0fca74582cd318dd06862fd9c86"
    api_secret = "447bffba0ab3cea380fdb268d83a2332"
    sender = "sivoryprince@gmail.com" # Nouvel expéditeur demandé
    
    print(f"Test with {sender}...")
    url = "https://api.mailjet.com/v3.1/send"
    
    payload = {
        "Messages": [
            {
                "From": {"Email": sender, "Name": "Nobilis X New Sender"},
                "To": [{"Email": sender}],
                "Subject": "Test Nouvel Expéditeur",
                "TextPart": "Vérification de l'adresse sivoryprince@gmail.com"
            }
        ]
    }
    
    response = requests.post(url, json=payload, auth=(api_key, api_secret), timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    test()
