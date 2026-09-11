import requests
import time
import sys

BASE_URL = "http://127.0.0.1:5000"

# Contatori
test_passati = 0
test_falliti = 0

def test(nome, condizione, dettaglio=""):
    global test_passati, test_falliti
    if condizione:
        print(f"✅ PASS | {nome}")
        test_passati += 1
    else:
        print(f"❌ FAIL | {nome} | {dettaglio}")
        test_falliti += 1

def aspetta_rate_limit():
    """Aspetta per evitare il rate limit (5 richieste/ora)."""
    print("\n⚠️  Rate limit: aspetto 5 secondi per test successivi...\n")
    time.sleep(5)

print("=" * 60)
print("TEST SUITE - DataCleaner API")
print("=" * 60)
print()

# ============================================================
# TEST 1: Endpoint /api/v1/info
# ============================================================
print("--- TEST 1: /api/v1/info ---")
try:
    r = requests.get(f"{BASE_URL}/api/v1/info", timeout=10)
    test("Status 200", r.status_code == 200, f"Ricevuto {r.status_code}")
    
    if r.status_code == 200:
        dati = r.json()
        test("Campo 'nome' presente", "nome" in dati)
        test("Campo 'endpoints' presente", "endpoints" in dati)
        test("Campo 'limiti' presente", "limiti" in dati)
        test("Almeno 3 endpoint elencati", len(dati.get("endpoints", [])) >= 3)
except Exception as e:
    test("Richiesta senza eccezioni", False, str(e))

aspetta_rate_limit()

# ============================================================
# TEST 2: /api/v1/converti con file valido
# ============================================================
print("--- TEST 2: /api/v1/converti con file valido ---")
try:
    with open("test_brutto.csv", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/v1/converti", files={"file": f}, timeout=10)
    
    test("Status 200", r.status_code == 200, f"Ricevuto {r.status_code}")
    
    if r.status_code == 200:
        dati = r.json()
        test("Campo 'stato' è 'successo'", dati.get("stato") == "successo")
        test("Almeno 1 riga elaborata", dati.get("info_file", {}).get("numero_righe_estratte", 0) > 0)
        test("Campo 'dati_strutturati' è una lista", isinstance(dati.get("dati_strutturati"), list))
except Exception as e:
    test("Richiesta senza eccezioni", False, str(e))

aspetta_rate_limit()

# ============================================================
# TEST 3: /api/v1/converti con file vuoto
# ============================================================
print("--- TEST 3: /api/v1/converti con file vuoto ---")
try:
    r = requests.post(
        f"{BASE_URL}/api/v1/converti",
        files={"file": ("vuoto.csv", b"")},
        timeout=10
    )
    test("Status 400", r.status_code == 400, f"Ricevuto {r.status_code}")
    
    if r.status_code == 400:
        dati = r.json()
        test("Messaggio 'file vuoto'", "vuoto" in dati.get("messaggio", "").lower())
except Exception as e:
    test("Richiesta senza eccezioni", False, str(e))

aspetta_rate_limit()

# ============================================================
# TEST 4: /api/v1/converti con estensione sbagliata
# ============================================================
print("--- TEST 4: /api/v1/converti con estensione sbagliata ---")
try:
    r = requests.post(
        f"{BASE_URL}/api/v1/converti",
        files={"file": ("test.txt", b"contenuto")},
        timeout=10
    )
    test("Status 400", r.status_code == 400, f"Ricevuto {r.status_code}")
    
    if r.status_code == 400:
        dati = r.json()
        test("Messaggio 'formato non supportato'", "formato" in dati.get("messaggio", "").lower())
except Exception as e:
    test("Richiesta senza eccezioni", False, str(e))

aspetta_rate_limit()

# ============================================================
# TEST 5: /api/v1/converti senza file
# ============================================================
print("--- TEST 5: /api/v1/converti senza file ---")
try:
    r = requests.post(f"{BASE_URL}/api/v1/converti", timeout=10)
    test("Status 400", r.status_code == 400, f"Ricevuto {r.status_code}")
except Exception as e:
    test("Richiesta senza eccezioni", False, str(e))

# ============================================================
# REPORT FINALE
# ============================================================
print()
print("=" * 60)
print("REPORT FINALE")
print("=" * 60)
print(f"✅ Test passati: {test_passati}")
print(f"❌ Test falliti: {test_falliti}")
print(f"📊 Totale: {test_passati + test_falliti}")

if test_falliti == 0:
    print()
    print("🎉 TUTTI I TEST PASSATI")
    sys.exit(0)
else:
    print()
    print("⚠️  ALCUNI TEST FALLITI")
    sys.exit(1)