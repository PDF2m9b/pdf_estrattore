import pandas as pd
import json
import os
import traceback


def normalizza_e_converti_foglio(percorso_file):
    print(f"Lettura del file in corso: {percorso_file}")
    
    try:
        # Rileva il tipo di file
        if percorso_file.lower().endswith('.csv'):
            try:
                df = pd.read_csv(percorso_file, sep=None, engine='python', on_bad_lines='skip')
            except:
                df = pd.read_csv(percorso_file, sep=';', engine='python', on_bad_lines='skip')
            
            if len(df.columns) == 1:
                for sep in [';', '\t', '|']:
                    try:
                        df_test = pd.read_csv(percorso_file, sep=sep, engine='python', on_bad_lines='skip')
                        if len(df_test.columns) > len(df.columns):
                            df = df_test
                            break
                    except:
                        pass
        else:
            df = pd.read_excel(percorso_file)
        
        # Pulisci i nomi delle colonne
        df.columns = [str(c).strip() for c in df.columns]
        
        # Rimuovi righe e colonne completamente vuote
        df = df.dropna(how='all')
        df = df.dropna(axis=1, how='all')
        
        # Sostituisci i NaN con stringa vuota
        df = df.fillna('')
        
        # Pulisci gli spazi da ogni cella
        for colonna in df.columns:
            try:
                df[colonna] = df[colonna].apply(
                    lambda x: x.strip() if isinstance(x, str) else x
                )
            except:
                pass
        
        # Rimuovi righe dove tutte le celle sono vuote
        df = df[~df.apply(lambda row: all(str(v).strip() == '' for v in row), axis=1)]
        
        # Converti in JSON
        risultato_json = json.loads(df.to_json(orient='records'))
        
        return {
            "stato": "successo",
            "info_file": {
                "nome": os.path.basename(percorso_file),
                "numero_righe_estratte": len(df),
                "numero_colonne_estratte": len(df.columns),
                "colonne": list(df.columns)
            },
            "dati_strutturati": risultato_json
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"stato": "errore", "messaggio": f"Impossibile convertire il file: {str(e)}"}


if __name__ == "__main__":
    print("=== AVVIO MOTORE UNIVERSALE CONVERSIONE DATI ===")
    
    report = normalizza_e_converti_foglio("test_brutto.csv")
    print(json.dumps(report, indent=2, ensure_ascii=False))