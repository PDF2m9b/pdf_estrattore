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
    
    def normalizza_numero(self, valore):
        return normalizza_importo(valore)
    
    def normalizza_data(self, data_grezza, anno="2026"):
        return normalizza_data(data_grezza, anno)
    
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
        
        if not tabella or len(tabella) < 2:
            return movimenti
        
        # FASE 1: Rileva gli indici delle colonne dall'intestazione
        intestazione = [str(c).strip().lower() if c else '' for c in tabella[0]]
        
        idx_data = -1
        idx_desc = -1
        idx_importo = -1
        idx_add = -1
        idx_acc = -1
        idx_saldo = -1
        
        for i, col in enumerate(intestazione):
            if 'data' in col and idx_data == -1:
                idx_data = i
            elif 'descrizione' in col or 'causale' in col or 'operazione' in col:
                idx_desc = i
            elif 'importo' in col:
                idx_importo = i
            elif 'addebit' in col or 'dare' in col or 'uscita' in col:
                idx_add = i
            elif 'accredit' in col or 'avere' in col or 'entrata' in col:
                idx_acc = i
            elif 'saldo' in col:
                idx_saldo = i
        
        if idx_data == -1 or idx_desc == -1:
            return movimenti
        
        # FASE 2: Estrai i movimenti
        for riga in tabella[1:]:
            if len(riga) <= max(idx_data, idx_desc):
                continue
            
            data_grezza = str(riga[idx_data]).strip() if riga[idx_data] else ''
            if not data_grezza or not re.search(r'\d', data_grezza):
                continue
            
            data_pulita = normalizza_data(data_grezza, self.anno_predefinito)
            descrizione = str(riga[idx_desc]).replace('\n', ' ').strip() if riga[idx_desc] else ''
            
            if 'SALDO INIZIALE' in descrizione.upper() or 'SALDO FINALE' in descrizione.upper():
                continue
            
            entrata = None
            uscita = None
            saldo = None
            
            # CASO A: colonna importo unica (+/-)
            if idx_importo != -1:
                importo_grezzo = str(riga[idx_importo]).strip() if riga[idx_importo] else ''
                
                if importo_grezzo and re.search(r'\d', importo_grezzo):
                    importo_num = normalizza_importo(importo_grezzo)
                    
                    if importo_num is not None:
                        if '-' in importo_grezzo:
                            uscita = abs(float(importo_num))
                        else:
                            entrata = float(importo_num)
            
            # CASO B: colonne separate addebito/accredito
            elif idx_add != -1 or idx_acc != -1:
                if idx_add != -1 and riga[idx_add]:
                    val = normalizza_importo(str(riga[idx_add]))
                    if val is not None and val > 0:
                        uscita = float(val)
                
                if idx_acc != -1 and riga[idx_acc]:
                    val = normalizza_importo(str(riga[idx_acc]))
                    if val is not None and val > 0:
                        entrata = float(val)
            
            if idx_saldo != -1 and riga[idx_saldo]:
                val = normalizza_importo(str(riga[idx_saldo]))
                if val is not None:
                    saldo = float(val)
            
            if descrizione and (entrata is not None or uscita is not None):
                movimenti.append({
                    'data': data_pulita,
                    'descrizione': descrizione,
                    'entrata': entrata,
                    'uscita': uscita,
                    'saldo': saldo
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
                
                prima_pagina = pdf.pages[0]
                testo_prima_pagina = prima_pagina.extract_text()
                
                if testo_prima_pagina:
                    match = re.search(r'Periodo:\s*\d{2}/\d{2}/(\d{4})', testo_prima_pagina)
                    if match:
                        self.anno_predefinito = match.group(1)
                
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
                            if tabella and len(tabella) > 1:
                                intestazione = str(tabella[0]).lower()
                                if 'data' in intestazione and ('importo' in intestazione or 'addebit' in intestazione or 'accredit' in intestazione or 'saldo' in intestazione):
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