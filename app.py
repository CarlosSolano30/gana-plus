from flask import Flask, render_template, request, redirect, session, url_for 
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'clave_super_secreta_ganaplus'

# Crear base de datos si no existe
def crear_tabla_usuarios():
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correo TEXT UNIQUE,
            telefono TEXT UNIQUE,
            contraseña TEXT,
            saldo INTEGER DEFAULT 0,
            tareas INTEGER DEFAULT 0,
            referidos INTEGER DEFAULT 0,
            referido_por INTEGER,
            es_admin INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS retiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            metodo TEXT,
            cuenta TEXT,
            valor INTEGER,
            estado TEXT DEFAULT 'pendiente'
        )
    ''')
    conn.commit()
    conn.close()

crear_tabla_usuarios()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    referido_id = request.args.get('ref')
    if request.method == 'POST':
        correo = request.form['correo']
        telefono = request.form['telefono']
        contraseña = request.form['contraseña']

        try:
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO usuarios (correo, telefono, contraseña, referido_por)
                VALUES (?, ?, ?, ?)
            ''', (correo, telefono, contraseña, referido_id))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Correo o teléfono ya registrados."

    return render_template('register.html')
def agregar_campo_referido():
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN referido_por INTEGER')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Ya existe
    conn.close()

agregar_campo_referido()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contraseña = request.form['contraseña']

        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE correo=? AND contraseña=?', (correo, contraseña))
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            session['usuario_id'] = usuario[0]
            session['correo'] = usuario[1]
            return redirect(url_for('dashboard'))
        else:
            return "Credenciales incorrectas."

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT saldo, tareas, referidos, referido_por FROM usuarios WHERE id=?', (session['usuario_id'],))
    datos = cursor.fetchone()
    conn.close()

    # Crear link único para referir
    link_referido = f"http://localhost:5000/register?ref={session['usuario_id']}"

    # Detectar si fue referido y aún no ha hecho 3 tareas
    mostrar_mensaje_bono = datos[3] is not None and datos[1] < 3

    return render_template(
        'dashboard.html',
        correo=session['correo'],
        saldo=datos[0],
        tareas=datos[1],
        referidos=datos[2],
        link_referido=link_referido,
        mostrar_mensaje_bono=mostrar_mensaje_bono
    )


@app.route('/tareas')
def tareas():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return render_template('tareas.html')

@app.route('/completar_tarea', methods=['POST'])
def completar_tarea():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    sumar_tarea(session['usuario_id'])
    return redirect(url_for('dashboard'))

def sumar_tarea(usuario_id):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET tareas = tareas + 1 WHERE id=?', (usuario_id,))
    conn.commit()
    cursor.execute('SELECT tareas, referido_por FROM usuarios WHERE id=?', (usuario_id,))
    tareas, referido_por = cursor.fetchone()
    if tareas == 3 and referido_por:
        cursor.execute('UPDATE usuarios SET saldo = saldo + 5000, referidos = referidos + 1 WHERE id=?', (referido_por,))
        conn.commit()
    conn.close()

@app.route('/solicitar_retiro', methods=['POST'])
def solicitar_retiro():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    metodo = request.form.get('metodo')
    cuenta = request.form.get('cuenta')
    valor = int(request.form.get('valor'))

    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()

    cursor.execute('SELECT saldo, tareas, referidos FROM usuarios WHERE id=?', (session['usuario_id'],))
    saldo, tareas, referidos = cursor.fetchone()

    if saldo < 25000:
        conn.close()
        return "Saldo insuficiente (mínimo $25.000 COP)."

    if tareas < 1 or referidos < 1:
        conn.close()
        return "Debes tener al menos 1 tarea y 1 referido para retirar."

    if valor > saldo:
        conn.close()
        return "No puedes retirar más de tu saldo actual."

    cursor.execute('INSERT INTO retiros (usuario_id, metodo, cuenta, valor) VALUES (?, ?, ?, ?)',
                   (session['usuario_id'], metodo, cuenta, valor))
    cursor.execute('UPDATE usuarios SET saldo = saldo - ? WHERE id=?', (valor, session['usuario_id']))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))
@app.route('/marcar_pagado/<int:retiro_id>')
def marcar_pagado(retiro_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()

    cursor.execute('SELECT es_admin FROM usuarios WHERE id=?', (session['usuario_id'],))
    admin_flag = cursor.fetchone()
    if not admin_flag or admin_flag[0] != 1:
        conn.close()
        return "Acceso denegado"

    cursor.execute('UPDATE retiros SET estado="pagado" WHERE id=?', (retiro_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))


@app.route('/terminos')
def terminos():
    return render_template('terms.html')
@app.route('/privacidad')
def privacidad():
    return render_template('terms.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
    @app.route('/ayet_callback', methods=['GET'])
def ayet_callback():
    user_id = request.args.get('user_id')
    amount = request.args.get('amount')
    transaction_id = request.args.get('transaction_id')

    print(f"Usuario: {user_id}, Ganó: {amount}, Transacción: {transaction_id}")

    return jsonify({'status': 'ok'}), 200

