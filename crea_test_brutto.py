# Crea un file CSV molto brutto con:
# - separatore punto e virgola
# - righe vuote sparse
# - spazi dappertutto
# - celle vuote in mezzo
# - intestazioni strane

contenuto = """Nome ;Eta;   Citta;Telefono
   Mario   ;25;Napoli;
   
Luigi;  ;Milano;3331234567
;;
   Anna;28;; 3339876543 
   
   
Luca ;  35;  Roma ;;

Giulia;22;Torino; 3331112222

"""

with open("test_brutto.csv", "w", encoding="utf-8") as f:
    f.write(contenuto)

print("File test_brutto.csv creato")