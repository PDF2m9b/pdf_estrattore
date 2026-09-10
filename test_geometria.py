import pdfplumber
import os

def analizza_geometria_pdf(percorso_pdf):
    if not os.path.exists(percorso_pdf):
        print(f"File non trovato: {percorso_pdf}")
        return

    print("=== ANALISI COMPLETA ===")
    print("")
    
    with pdfplumber.open(percorso_pdf) as pdf:
        print(f"Numero pagine: {len(pdf.pages)}")
        print("")
        
        for num_pagina, pagina in enumerate(pdf.pages):
            print(f"=== PAGINA {num_pagina + 1} ===")
            testo = pagina.extract_text()
            if testo:
                print("TESTO ESTRATTO (primi 2000 caratteri):")
                print(testo[:2000])
            print("")
            
            tabelle = pagina.extract_tables()
            print(f"Tabelle trovate: {len(tabelle)}")
            for i, tabella in enumerate(tabelle):
                print(f"  Tabella {i}: {len(tabella)} righe x {len(tabella[0]) if tabella else 0} colonne")
                if tabella:
                    print(f"  Intestazione: {tabella[0]}")
            print("")

if __name__ == "__main__":
    analizza_geometria_pdf("estratto_conto_intesa_sanpaolo.pdf")