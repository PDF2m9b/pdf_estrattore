import os
import sys
import pandas as pd
import re
import json

try:
    import fitz
except:
    os.system("pip install PyMuPDF")
    import fitz


class EstrattorePDF:
    def __init__(self):
        self.mesi = {
            'gennaio': '01', 'febbraio': '02', 'marzo': '03',
            'aprile': '04', 'maggio': '05', 'giugno': '06',
            'luglio': '07', 'agosto': '08', 'settembre': '09',
            'ottobre': '10', 'novembre': '11', 'dicembre': '12'
        }
        
        self.parole_uscita = [
            'PAGAM', 'PAGAMENTO', 'PRELIEVO', 'ADDEBITO', 'CANONE',
            'POS', 'COMMISSIONI', 'ACQ', 'F24', 'ASSICURAZIONE',
            'CARTA', 'ENERGIA', 'TELEFONO', 'AFFITTO', 'MATERIALE'
        ]
        
        self.parole_entrata = [
            'BONIFICO', 'INCASSO', 'RIMBORSO', 'STIPENDIO',
            'ACCREDITO', 'ENTRATA', 'VERSAMENTO'
        ]
    
    def leggi_pdf(self, percorso_file):
        if not os.path.exists(percorso_file):
            return None
        
        testo_completo = ""
        try:
            documento = fitz.open(percorso_file)
            for pagina in documento:
                testo_completo += pagina.get_text()
            documento.close()
        except:
            return None
        
        return testo_completo
    
    def rileva_tipo_documento(self, testo):
        """Rileva se il PDF è un estratto conto o una fattura."""
        testo_upper = testo.upper()
        
        # Parole chiave per fattura
        parole_fattura = ['FATTURA', 'RICEVUTA', 'NOTA DI CREDITO', 'DOCUMENTO FISCALE']
        
        # Parole chiave per estratto conto
        parole_estratto = ['ESTRATTO CONTO', 'SALDO PROGRESSIVO', 'SALDO INIZIALE', 'SALDO FINALE']
        
        for parola in parole_estratto:
            if parola in testo_upper:
                return 'estratto_conto'
        
        for parola in parole_fattura:
            if parola in testo_upper:
                return 'fattura'
        
        return 'sconosciuto'
    
    def normalizza_data(self, data):
        data = data.strip()
        
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', data):
            parti = data.split('/')
            return f"{parti[0].zfill(2)}/{parti[1].zfill(2)}/{parti[2]}"
        
        if re.match(r'^\d{1,2}/\d{1,2}/\d{2}$', data):
            parti = data.split('/')
            return f"{parti[0].zfill(2)}/{parti[1].zfill(2)}/20{parti[2]}"
        
        if re.match(r'^\d{2}-\d{2}-\d{2}$', data):
            parti = data.split('-')
            return f"{parti[0]}/{parti[1]}/20{parti[2]}"
        
        if re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', data):
            parti = data.split('-')
            return f"{parti[0].zfill(2)}/{parti[1].zfill(2)}/{parti[2]}"
        
        if re.match(r'^\d{1,2}-\d{1,2}-\d{2}$', data):
            parti = data.split('-')
            return f"{parti[0].zfill(2)}/{parti[1].zfill(2)}/20{parti[2]}"
        
        for mese_nome, mese_num in self.mesi.items():
            if mese_nome in data.lower():
                match = re.search(r'(\d{1,2})\s+' + mese_nome + r'\s+(\d{4})', data.lower())
                if match:
                    giorno = match.group(1).zfill(2)
                    anno = match.group(2)
                    return f"{giorno}/{mese_num}/{anno}"
        
        return data
    
    def normalizza_numero(self, valore):
        valore = valore.strip()
        valore = valore.replace('€', '').replace(' ', '').replace('-', '')
        
        if ',' in valore and '.' in valore:
            if valore.rfind(',') > valore.rfind('.'):
                valore = valore.replace('.', '')
                valore = valore.replace(',', '.')
            else:
                valore = valore.replace(',', '')
        elif ',' in valore:
            valore = valore.replace('.', '')
            valore = valore.replace(',', '.')
        
        try:
            return float(valore)
        except:
            return None
    
    def estrai_movimenti_estratto(self, testo):
        """Estrae movimenti da estratti conto con formati diversi."""
        righe = [r.strip() for r in testo.split("\n") if r.strip()]
        movimenti = []
        
        # Pattern per date in vari formati
        pattern_data = re.compile(
            r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})$|^(\d{1,2}\s+\w+\s+\d{4})$'
        )
        
        # Pattern per numeri (importi)
        pattern_numero = re.compile(r'^[-+]?[\d\.,\s€]+$')
        
        i = 0
        while i < len(righe):
            riga = righe[i]
            
            # Cerca date anche dentro righe più complesse
            match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', riga)
            
            if match_data:
                data = self.normalizza_data(match_data.group(1))
                
                # Cerca descrizione nelle righe successive
                descrizione = ""
                j = i + 1
                while j < len(righe) and j < i + 5:
                    if pattern_numero.match(righe[j]):
                        break
                    descrizione += " " + righe[j]
                    j += 1
                
                descrizione = descrizione.strip()
                i = j
                
                # Cerca importi nelle righe successive
                entrata = None
                uscita = None
                saldo = None
                
                while i < len(righe) and i < j + 3:
                    if pattern_numero.match(righe[i]):
                        importo = self.normalizza_numero(righe[i])
                        if importo is not None:
                            # Determina se è entrata o uscita
                            if 'PAGAM' in descrizione.upper() or 'ADDEBITO' in descrizione.upper() or 'PRELIEVO' in descrizione.upper() or 'COMMISSIONE' in descrizione.upper() or 'PENALE' in descrizione.upper() or 'MORA' in descrizione.upper() or 'TAX' in descrizione.upper() or 'BOLLO' in descrizione.upper() or 'RECUPERO' in descrizione.upper() or 'CONVERSIONE' in descrizione.upper() or 'GIROCONTO' in descrizione.upper() or 'IMPOSTA' in descrizione.upper() or 'CANONE' in descrizione.upper():
                                uscita = importo
                            elif 'BONIFICO' in descrizione.upper() or 'STIPENDIO' in descrizione.upper() or 'ACCREDITO' in descrizione.upper() or 'RIMBORSO' in descrizione.upper() or 'INCASSO' in descrizione.upper():
                                entrata = importo
                            else:
                                # Controlla se il testo originale ha segno negativo
                                if '-' in righe[i]:
                                    uscita = importo
                                elif '+' in righe[i]:
                                    entrata = importo
                                else:
                                    # Default: se la descrizione contiene parole di spesa
                                    if any(p in descrizione.upper() for p in self.parole_uscita):
                                        uscita = importo
                                    else:
                                        entrata = importo
                        
                        # Il secondo numero potrebbe essere il saldo
                        if saldo is None:
                            saldo = importo
                        i += 1
                    else:
                        i += 1
                
                if descrizione and (entrata or uscita):
                    movimenti.append({
                        'data': data,
                        'descrizione': descrizione,
                        'entrata': entrata,
                        'uscita': uscita,
                        'saldo': saldo
                    })
            else:
                i += 1
        
        return movimenti
        righe = [r.strip() for r in testo.split("\n") if r.strip()]
        movimenti = []
        
        pattern_data = re.compile(
            r'^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})$|^(\d{1,2}\s+\w+\s+\d{4})$'
        )
        
        pattern_numero = re.compile(r'^[\d\.,\s€-]+$')
        
        i = 0
        while i < len(righe):
            riga = righe[i]
            
            if pattern_data.match(riga):
                data = self.normalizza_data(riga)
                
                if i + 1 < len(righe):
                    descrizione = righe[i + 1]
                    i += 2
                    
                    entrata = None
                    uscita = None
                    
                    if i < len(righe) and pattern_numero.match(righe[i]):
                        importo = self.normalizza_numero(righe[i])
                        if importo is not None:
                            descrizione_upper = descrizione.upper()
                            
                            if any(p in descrizione_upper for p in self.parole_uscita):
                                uscita = importo
                            elif any(p in descrizione_upper for p in self.parole_entrata):
                                entrata = importo
                            else:
                                if '€' in righe[i] or '-' in righe[i]:
                                    uscita = importo
                                else:
                                    entrata = importo
                        i += 1
                    
                    saldo = None
                    if i < len(righe) and pattern_numero.match(righe[i]):
                        saldo = self.normalizza_numero(righe[i])
                        i += 1
                    
                    movimenti.append({
                        'data': data,
                        'descrizione': descrizione,
                        'entrata': entrata,
                        'uscita': uscita,
                        'saldo': saldo
                    })
            else:
                i += 1
        
        return movimenti
    
    def estrai_dati_fattura(self, testo):
        """Estrae i dati principali da una fattura."""
        righe = [r.strip() for r in testo.split("\n") if r.strip()]
        
        dati_fattura = {
            'numero_fattura': None,
            'data_fattura': None,
            'fornitore': None,
            'cliente': None,
            'totale': None,
            'totale_iva': None,
            'partita_iva': None
        }
        
        testo_completo = ' '.join(righe)
        
        # Cerca il numero fattura
        match = re.search(r'(?:Fattura|FATTURA|FT|Numero|N\.?)\s*(?:N\.?|Numero)?\s*[:#]?\s*(\d{1,6})', testo_completo)
        if match:
            dati_fattura['numero_fattura'] = match.group(1)
        
        # Cerca la data
        match = re.search(r'(?:Data|DATA)\s*[:]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', testo_completo)
        if match:
            dati_fattura['data_fattura'] = self.normalizza_data(match.group(1))
        
        # Cerca il totale
        match = re.search(r'(?:TOTALE|Totale|TOTALE DOCUMENTO|TOTALE FATTURA)\s*[:]?\s*(?:€)?\s*([\d\.,]+)', testo_completo)
        if match:
            dati_fattura['totale'] = self.normalizza_numero(match.group(1))
        
        # Cerca l'IVA (importo, non partita IVA)
        match = re.search(r'(?:IVA|Iva)\s*(?:\d+%|al\s*\d+%|€|:)?\s*[:]?\s*(?:€)?\s*([\d\.,]+)', testo_completo)
        if match:
            valore_iva = self.normalizza_numero(match.group(1))
            if valore_iva and valore_iva < 1000:
                dati_fattura['totale_iva'] = valore_iva
        
        # Cerca la partita IVA
        match = re.search(r'(?:P\.?\s*IVA|Partita IVA|P\.IVA)\s*[:]?\s*(\d{11})', testo_completo)
        if match:
            dati_fattura['partita_iva'] = match.group(1)
        
        return dati_fattura
    
    def processa_pdf(self, percorso_file):
        testo = self.leggi_pdf(percorso_file)
        if not testo:
            return None
        
        tipo = self.rileva_tipo_documento(testo)
        
        if tipo == 'estratto_conto':
            movimenti = self.estrai_movimenti_estratto(testo)
            
            entrate_totali = sum(m['entrata'] for m in movimenti if m['entrata'])
            uscite_totali = sum(m['uscita'] for m in movimenti if m['uscita'])
            
            risultato = {
                'tipo_documento': 'estratto_conto',
                'movimenti': movimenti,
                'totale_entrate': round(entrate_totali, 2),
                'totale_uscite': round(uscite_totali, 2),
                'saldo_netto': round(entrate_totali - uscite_totali, 2),
                'numero_movimenti': len(movimenti)
            }
            
        elif tipo == 'fattura':
            dati = self.estrai_dati_fattura(testo)
            
            risultato = {
                'tipo_documento': 'fattura',
                'dati_fattura': dati,
                'movimenti': [],
                'totale_entrate': 0,
                'totale_uscite': 0,
                'saldo_netto': 0,
                'numero_movimenti': 0
            }
            
        else:
            risultato = {
                'tipo_documento': 'sconosciuto',
                'movimenti': [],
                'totale_entrate': 0,
                'totale_uscite': 0,
                'saldo_netto': 0,
                'numero_movimenti': 0
            }
        
        return risultato


def main():
    print("=" * 60)
    print("ESTRATTORE PDF PROFESSIONALE v2.0")
    print("Riconoscimento automatico: Estratti Conto + Fatture")
    print("=" * 60)
    print("")
    
    estrattore = EstrattorePDF()
    
    if len(sys.argv) < 2:
        print("Uso: python estrai.py nome_file.pdf")
        return
    
    percorso = sys.argv[1]
    print(f"Elaborazione: {percorso}")
    print("")
    
    risultato = estrattore.processa_pdf(percorso)
    
    if not risultato:
        print("ERRORE: Impossibile elaborare il PDF.")
        return
    
    print(f"Tipo documento rilevato: {risultato['tipo_documento']}")
    print("")
    
    if risultato['tipo_documento'] == 'estratto_conto':
        movimenti = risultato['movimenti']
        if movimenti:
            df = pd.DataFrame(movimenti)
            df.columns = ['Data', 'Descrizione', 'Entrate', 'Uscite', 'Saldo']
            print(df.to_string(index=False))
            print("")
            print(f"Movimenti trovati: {risultato['numero_movimenti']}")
            print(f"Totale entrate: € {risultato['totale_entrate']:.2f}")
            print(f"Totale uscite: € {risultato['totale_uscite']:.2f}")
            print(f"Saldo netto: € {risultato['saldo_netto']:.2f}")
    
    elif risultato['tipo_documento'] == 'fattura':
        dati = risultato['dati_fattura']
        print("Dati fattura estratti:")
        for chiave, valore in dati.items():
            if valore:
                print(f"  {chiave}: {valore}")


if __name__ == "__main__":
    main()