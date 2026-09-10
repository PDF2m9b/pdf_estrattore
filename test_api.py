import requests

url = "http://127.0.0.1:5001/api/v1/extract"

with open("estratto_conto_commercialista.pdf", "rb") as f:
    files = {"file": f}
    risposta = requests.post(url, files=files)

print("Status:", risposta.status_code)
print("Risposta:")
print(risposta.text[:2000])