import os
import sys
import re
import json
from decimal import Decimal, InvalidOperation
import pdfplumber


def normalizza_importo(valore):
    if not valore:
        return None
    
    valore = str(valore).strip().replace('€', '').replace(' ', '')
    
    if '.' in valore and ',' in valore:
        if valore.rfind('.') < valore.rfind(','):
            valore = valore.replace('.', '')
            valore = valore.replace(',', '.')
        else:
            valore = valore.replace(',', '')
    elif ',' in valore:
        valore = valore.replace(',', '.')
    
    try:
        return Decimal(valore)
    except InvalidOperation:
        return None


def normalizza_data(data_breve, anno="2026"):
    if not data_breve:
        return None
    
    data_breve = data_breve.strip()
    
    if re.match(r'^\d{2}/\d{2}/\d{4}$', data_breve):
        return data_breve
    
    if re.match(r'^\d{2}/\d{2}$', data_breve):
        return f"{data_breve}/{anno}"
    
    return data_breve


class EstrattorePDF:
    def __init__(self):
        self.anno_predefinito = "2026"
    
    def estrai_dati_fattura(self, testo):
        dati = {
            'numero_fattura': None,
            'data_fattura': None,
            'totale': None,
            'partita_iva': None
        }
        
        match = re.search(r'(?:Fattura|FATTURA|FT|Numero|N\.?)\s*(?:N\.?|Numero)?\s*[:#]?\s*(\d{1,6})', testo)
        if match:
            dati['numero_fattura'] = match.group(1)
        
        match = re.search(r'(?:Data|DATA)\s*[:]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', testo)
        if match:
            dati['data_fattura'] = normalizza_data(match.group(1), self.anno_predefinito)
        
        match = re.search(r'(?:TOTALE|Totale|TOTALE DOCUMENTO|TOTALE FATTURA)\s*[:]?\s*(?:€)?\s*([\d\.,]+)', testo)
        if match:
            valore = normalizza_importo(match.group(1))
            if valore:
                dati['totale'] = float(valore)
        
        match = re.search(r'(?:P\.?\s*IVA|Partita IVA|P\.IVA)\s*[:]?\s*(\d{11})', testo)
        if match:
            dati['partita_iva'] = match.group(1)
        
        return dati
    
    def estrai_movimenti_da_tabella(self, tabella):
        movimenti = []
        
        for riga in tabella[1:]:
            if len(riga) >= 7:
                data_contabile = normalizza_data(riga[0], self.anno_predefinito)
                descrizione = riga[3].replace('\n', ' ').strip() if riga[3] else ''
                
                addebito = normalizza_importo(riga[4])
                accredito = normalizza_importo(riga[5])
                saldo = normalizza_importo(riga[6])
                
                if descrizione and (addebito or accredito):
                    movimenti.append({
                        'data': data_contabile,
                        'descrizione': descrizione,
                        'entrata': float(accredito) if accredito else None,
                        'uscita': float(addebito) if addebito else None,
                        'saldo': float(saldo) if saldo else None
                    })
        
        return movimenti
    
    def verifica_quadratura(self, movimenti):
        errori = []
        
        for i in range(1, len(movimenti)):
            saldo_precedente = movimenti[i-1].get('saldo')
            saldo_attuale = movimenti[i].get('saldo')
            
            if saldo_precedente is not None and saldo_attuale is not None:
                entrata = movimenti[i].get('entrata') or 0
                uscita = movimenti[i].get('uscita') or 0
                saldo_atteso = round(saldo_precedente + entrata - uscita, 2)
                
                if abs(saldo_atteso - saldo_attuale) > 0.01:
                    errori.append({
                        'riga': i + 1,
                        'data': movimenti[i]['data'],
                        'descrizione': movimenti[i]['descrizione'][:50],
                        'saldo_atteso': saldo_atteso,
                        'saldo_trovato': saldo_attuale
                    })
        
        return errori
    
    def processa_pdf(self, percorso_file):
        if not os.path.exists(percorso_file):
            return None
        
        try:
            with pdfplumber.open(percorso_file) as pdf:
                movimenti_totali = []
                
                anno_estratto = None
                prima_pagina = pdf.pages[0]
                testo_prima_pagina = prima_pagina.extract_text()
                
                if testo_prima_pagina:
                    match = re.search(r'Periodo:\s*\d{2}/\d{2}/(\d{4})', testo_prima_pagina)
                    if match:
                        anno_estratto = match.group(1)
                        self.anno_predefinito = anno_estratto
                
                tipo_documento = 'sconosciuto'
                testo_completo = ''
                for pagina in pdf.pages[:2]:
                    testo_pagina = pagina.extract_text()
                    if testo_pagina:
                        testo_completo += testo_pagina + '\n'
                
                testo_upper = testo_completo.upper()
                
                if 'ESTRATTO CONTO' in testo_upper or 'SALDO PROGRESSIVO' in testo_upper:
                    tipo_documento = 'estratto_conto'
                elif 'FATTURA' in testo_upper or 'NOTA DI CREDITO' in testo_upper:
                    tipo_documento = 'fattura'
                
                if tipo_documento == 'estratto_conto':
                    for pagina in pdf.pages:
                        tabelle = pagina.extract_tables()
                        
                        for tabella in tabelle:
                            if tabella and len(tabella) > 1 and len(tabella[0]) >= 7:
                                prima_cella = str(tabella[0][0]).lower() if tabella[0][0] else ''
                                if 'data' in prima_cella:
                                    movimenti = self.estrai_movimenti_da_tabella(tabella)
                                    movimenti_totali.extend(movimenti)
                    
                    if not movimenti_totali:
                        return None
                    
                    totale_entrate = sum(m['entrata'] for m in movimenti_totali if m['entrata'])
                    totale_uscite = sum(m['uscita'] for m in movimenti_totali if m['uscita'])
                    errori = self.verifica_quadratura(movimenti_totali)
                    
                    return {
                        'tipo_documento': 'estratto_conto',
                        'movimenti': movimenti_totali,
                        'totale_entrate': round(totale_entrate, 2),
                        'totale_uscite': round(totale_uscite, 2),
                        'saldo_netto': round(totale_entrate - totale_uscite, 2),
                        'numero_movimenti': len(movimenti_totali),
                        'errori_quadratura': errori
                    }
                
                elif tipo_documento == 'fattura':
                    dati_fattura = self.estrai_dati_fattura(testo_completo)
                    
                    return {
                        'tipo_documento': 'fattura',
                        'dati_fattura': dati_fattura,
                        'movimenti': [],
                        'totale_entrate': 0,
                        'totale_uscite': 0,
                        'saldo_netto': 0,
                        'numero_movimenti': 0
                    }
                
                else:
                    return None
        except Exception as e:
            print(f"Errore: {e}")
            return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python estrai.py nome_file.pdf")
    else:
        estrattore = EstrattorePDF()
        risultato = estrattore.processa_pdf(sys.argv[1])
        if risultato:
            print(json.dumps(risultato, indent=2))
        else:
            print("ERRORE: Impossibile processare il PDF.")