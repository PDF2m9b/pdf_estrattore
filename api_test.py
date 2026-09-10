import os
import sys
import json
from flask import Flask, request, jsonify
from estrai import EstrattorePDF

# Creiamo un server di test locale completamente isolato
app = Flask(__name__)

@app.route('/api/v1/extract', methods=['POST'])
def api_estrai_documento():
    """Punto di accesso API puro per sviluppatori ed ecosistemi tecnici esterni."""
    if 'file' not in request.files:
        return jsonify({"stato": "errore", "messaggio": "Nessun file inviato nella richiesta"}), 400
        
    file_caricato = request.files['file']
    if file_caricato.filename == '':
        return jsonify({"stato": "errore", "messaggio": "Nome del file vuoto"}), 400
        
    if file_caricato and file_caricato.filename.lower().endswith('.pdf'):
        # Salvataggio in una cartella di test locale
        percorso_temp = os.path.join('instance', 'temp_api_test.pdf')
        file_caricato.save(percorso_temp)
        
        try:
            # Richiamiamo il tuo estrattore geometrico deterministico pdfplumber
            estrattore = EstrattorePDF()
            risultato_esistenza = estrattore.processa_pdf(percorso_temp)
            
            if os.path.exists(percorso_temp):
                os.remove(percorso_temp)
                
            if risultato_esistenza:
                return jsonify({
                    "stato": "successo",
                    "codice_risposta": 200,
                    "dati": risultato_esistenza
                }), 200
            else:
                return jsonify({"stato": "errore", "messaggio": "Impossibile decifrare la struttura geometrica del PDF"}), 422
                
        except Exception as e:
            if os.path.exists(percorso_temp):
                os.remove(percorso_temp)
            return jsonify({"stato": "errore", "messaggio": f"Errore server: {str(e)}"}), 500
            
    return jsonify({"stato": "errore", "messaggio": "Formato non supportato. Inviare solo PDF"}), 400

if __name__ == "__main__":
    # Facciamo girare questo server di test sulla porta 5001 per non andare in conflitto con nient'altro
    print("=== AVVIO SERVER API DI TEST ISOLATO ===")
    app.run(port=5001, debug=True)
