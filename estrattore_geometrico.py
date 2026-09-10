import pdfplumber
import re
import os
from decimal import Decimal, InvalidOperation


def normalizza_importo(valore):
    """Converte una stringa importo in Decimal."""
    if not valore:
        return None
    
    valore = str(valore).strip().replace('€', '').replace(' ', '')
    
    # Gestisce il formato italiano: 1.234,56 -> 1234.56
    if '.' in valore and ',' in valore:
        # Se ci sono due punti, il primo è separatore migliaia
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
    """Converte data formato 02/07 in 02/07/2026."""
    if not data_breve:
        return None
    
    data_breve = data_breve.strip()
    
    # Se è già nel formato GG/MM/AAAA
    if re.match(r'^\d{2}/\d{2}/\d{4}$', data_breve):
        return data_breve
    
    # Se è GG/MM, aggiungi anno
    if re.match(r'^\d{2}/\d{2}$', data_breve):
        return f"{data_breve}/{anno}"
    
    return data_breve


def estrai_movimenti_da_tabella(tabella):
    """Converte la tabella di pdfplumber in movimenti strutturati."""
    movimenti = []
    
    # Salta la prima riga (intestazione)
    for riga in tabella[1:]:
        if len(riga) >= 7:
            data_contabile = normalizza_data(riga[0])
            descrizione = riga[3].replace('\n', ' ').strip() if riga[3] else ''
            
            addebito = normalizza_importo(riga[4])
            accredito = normalizza_importo(riga[5])
            saldo = normalizza_importo(riga[6])
            
            if descrizione and (addebito or accredito):
                movimenti.append({
                    'data': data_contabile,
                    'descrizione': descrizione,
                    'entrata': accredito if accredito else None,
                    'uscita': addebito if addebito else None,
                    'saldo': saldo if saldo else None
                })
    
    return movimenti


def verifica_quadratura(movimenti, saldo_iniziale=None, saldo_finale=None):
    """Verifica se i movimenti quadrano con il saldo progressivo."""
    errori = []
    
    for i, mov in enumerate(movimenti):
        if mov['saldo'] is not None:
            # Calcola il saldo atteso
            if i == 0:
                saldo_atteso = mov['saldo']
            else:
                saldo_precedente = movimenti[i-1].get('saldo')
                if saldo_precedente is not None:
                    entrata = mov['entrata'] if mov['entrata'] else Decimal('0')
                    uscita = mov['uscita'] if mov['uscita'] else Decimal('0')
                    saldo_atteso = saldo_precedente + entrata - uscita
                    
                    if saldo_atteso != mov['saldo']:
                        errori.append({
                            'riga': i + 1,
                            'data': mov['data'],
                            'descrizione': mov['descrizione'][:50],
                            'saldo_atteso': str(saldo_atteso),
                            'saldo_trovato': str(mov['saldo'])
                        })
    
    return errori


def processa_pdf(percorso_pdf):
    """Processa un PDF estratto conto con pdfplumber."""
    if not os.path.exists(percorso_pdf):
        return None
    
    with pdfplumber.open(percorso_pdf) as pdf:
        prima_pagina = pdf.pages[0]
        tabelle = prima_pagina.extract_tables()
        
        if not tabelle:
            return None
        
        # Usa la prima tabella (quella dei movimenti)
        movimenti = estrai_movimenti_da_tabella(tabelle[0])
        
        if not movimenti:
            return None
        
        # Calcola totali
        totale_entrate = sum(m['entrata'] for m in movimenti if m['entrata'])
        totale_uscite = sum(m['uscita'] for m in movimenti if m['uscita'])
        
        # Verifica quadratura
        errori = verifica_quadratura(movimenti)
        
        return {
            'movimenti': movimenti,
            'totale_entrate': totale_entrate,
            'totale_uscite': totale_uscite,
            'saldo_netto': totale_entrate - totale_uscite,
            'numero_movimenti': len(movimenti),
            'errori_quadratura': errori
        }


if __name__ == "__main__":
    risultato = processa_pdf("estratto_conto_commercialista.pdf")
    
    if risultato:
        print("=== RISULTATO ESTRAZIONE GEOMETRICA ===")
        print(f"Movimenti trovati: {risultato['numero_movimenti']}")
        print(f"Totale entrate: {risultato['totale_entrate']}")
        print(f"Totale uscite: {risultato['totale_uscite']}")
        print(f"Saldo netto: {risultato['saldo_netto']}")
        print("")
        
        if risultato['errori_quadratura']:
            print("⚠️ ATTENZIONE: Errori di quadratura trovati:")
            for e in risultato['errori_quadratura']:
                print(f"  Riga {e['riga']} - {e['data']} - {e['descrizione']}")
                print(f"    Saldo atteso: {e['saldo_atteso']} - Saldo trovato: {e['saldo_trovato']}")
        else:
            print("✅ QUADRATURA PERFETTA: Tutti i saldi coincidono.")
        
        print("")
        print("Primi 5 movimenti:")
        for m in risultato['movimenti'][:5]:
            print(f"  {m['data']} | {m['descrizione'][:50]} | Entrata: {m['entrata']} | Uscita: {m['uscita']} | Saldo: {m['saldo']}")
    else:
        print("ERRORE: Impossibile processare il PDF.")