from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from estrai import EstrattorePDF

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chiave-segreta-temporanea'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///utenti.db'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

estrattore = EstrattorePDF()

class Utente(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    crediti = db.Column(db.Integer, default=10)  # 10 elaborazioni gratis

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return Utente.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/registrati', methods=['GET', 'POST'])
def registrati():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if Utente.query.filter_by(email=email).first():
            return jsonify({'errore': 'Email già registrata'}), 400
        
        utente = Utente(email=email)
        utente.set_password(password)
        db.session.add(utente)
        db.session.commit()
        
        login_user(utente)
        return jsonify({'successo': True, 'crediti': utente.crediti})
    
    return render_template('registrati.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        utente = Utente.query.filter_by(email=email).first()
        
        if utente and utente.check_password(password):
            login_user(utente)
            return jsonify({'successo': True, 'crediti': utente.crediti})
        
        return jsonify({'errore': 'Credenziali non valide'}), 401
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/crediti')
@login_required
def crediti():
    return jsonify({'crediti': current_user.crediti})

@app.route('/elabora', methods=['POST'])
@login_required
def elabora():
    if current_user.crediti <= 0:
        return jsonify({'errore': 'Crediti esauriti. Acquista nuovi crediti.'}), 403
    
    if 'file' not in request.files:
        return jsonify({'errore': 'Nessun file caricato'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'errore': 'Nessun file selezionato'}), 400
    
    percorso_temp = 'temp.pdf'
    file.save(percorso_temp)
    
    risultato = estrattore.processa_pdf(percorso_temp)
    
    if os.path.exists(percorso_temp):
        os.remove(percorso_temp)
    
    if not risultato:
        return jsonify({'errore': 'Impossibile elaborare il PDF'}), 400
    
    current_user.crediti -= 1
    db.session.commit()
    
    risultato['crediti_rimasti'] = current_user.crediti
    
    return jsonify(risultato)

@app.route('/scarica-excel', methods=['POST'])
@login_required
def scarica_excel():
    dati = request.get_json()
    movimenti = dati.get('movimenti', [])
    
    if not movimenti:
        return jsonify({'errore': 'Nessun dato da scaricare'}), 400
    
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimenti"
    
    headers = ['Data', 'Descrizione', 'Entrate', 'Uscite', 'Saldo']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4ecca3", end_color="4ecca3", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    for row, mov in enumerate(movimenti, 2):
        ws.cell(row=row, column=1, value=mov.get('data', ''))
        ws.cell(row=row, column=2, value=mov.get('descrizione', ''))
        ws.cell(row=row, column=3, value=mov.get('entrata') if mov.get('entrata') else None)
        ws.cell(row=row, column=4, value=mov.get('uscita') if mov.get('uscita') else None)
        ws.cell(row=row, column=5, value=mov.get('saldo') if mov.get('saldo') else None)
    
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 50
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=movimenti.xlsx'}
    )


@app.route('/scarica-csv', methods=['POST'])
@login_required
def scarica_csv():
    dati = request.get_json()
    movimenti = dati.get('movimenti', [])
    
    if not movimenti:
        return jsonify({'errore': 'Nessun dato da scaricare'}), 400
    
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Descrizione', 'Entrate', 'Uscite', 'Saldo'])
    
    for mov in movimenti:
        writer.writerow([
            mov.get('data', ''),
            mov.get('descrizione', ''),
            mov.get('entrata', ''),
            mov.get('uscita', ''),
            mov.get('saldo', '')
        ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=dati_estratti.csv'}
    )


@app.route('/api/v1/converti', methods=['POST'])
def api_converti():
    # RapidAPI invia automaticamente questo header con una chiave proxy segreta
    chiave_ricevuta = request.headers.get('X-RapidAPI-Proxy-Secret')
    chiave_attesa = os.environ.get('RAPIDAPI_PROXY_SECRET', 'test-locale')
    
    # Se la variabile d'ambiente non è impostata, permetti test locale
    if chiave_attesa != 'test-locale' and chiave_ricevuta != chiave_attesa:
        return jsonify({"stato": "errore", "messaggio": "Autenticazione fallita"}), 401
    
    if 'file' not in request.files:
        return jsonify({"stato": "errore", "messaggio": "Nessun file inviato"}), 400
    
    file_caricato = request.files['file']
    if file_caricato.filename == '':
        return jsonify({"stato": "errore", "messaggio": "Nome file vuoto"}), 400
    
    nome_file = file_caricato.filename.lower()
    if not (nome_file.endswith('.csv') or nome_file.endswith('.xlsx') or nome_file.endswith('.xls')):
        return jsonify({"stato": "errore", "messaggio": "Formato non supportato"}), 400
    
    percorso_temp = os.path.join('instance', 'temp_converti_' + file_caricato.filename)
    file_caricato.save(percorso_temp)
    
    try:
        from trasforma_dati import normalizza_e_converti_foglio
        risultato = normalizza_e_converti_foglio(percorso_temp)
        
        if os.path.exists(percorso_temp):
            os.remove(percorso_temp)
        
        return jsonify(risultato), 200
    except Exception as e:
        if os.path.exists(percorso_temp):
            os.remove(percorso_temp)
        return jsonify({"stato": "errore", "messaggio": str(e)}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)