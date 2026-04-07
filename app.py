from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, make_response
from functools import wraps
import sqlite3
from datetime import datetime
import json
import os
import uuid
from weasyprint import HTML

app = Flask(__name__)
app.secret_key = 'guidex_secret_key_2024'

# Configuración para subida de archivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'doc', 'mp4', 'webm', 'avi'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Crear carpeta uploads si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Función para conectar a la base de datos
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Decorador para verificar sesión
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta principal - Login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE correo = ? AND password = ?', (correo, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['user_nombre'] = user['nombre']
            session['user_email'] = user['correo']
            session['user_rol'] = user['rol']
            
            if user['rol'] == 'docente':
                return redirect(url_for('inicio_docente'))
            else:
                return redirect(url_for('inicio_orientadora'))
        else:
            return render_template('login.html', error='Credenciales incorrectas')
    
    return render_template('login.html')

# Cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Inicio Docente
@app.route('/inicio_docente')
@login_required
def inicio_docente():
    if session.get('user_rol') != 'docente':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Obtener reportes del docente
    reportes = conn.execute('''
        SELECT r.*, u.nombre as orientadora_nombre 
        FROM reportes r 
        LEFT JOIN usuarios u ON r.orientadora_id = u.id 
        WHERE r.docente_id = ? 
        ORDER BY r.fecha_creacion DESC
    ''', (session['user_id'],)).fetchall()
    
    # Obtener acuerdos del docente
    acuerdos = conn.execute('''
        SELECT a.*, u.nombre as estudiante_nombre 
        FROM acuerdos a 
        LEFT JOIN usuarios u ON a.estudiante_id = u.id 
        WHERE a.docente_id = ? 
        ORDER BY a.fecha_creacion DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('inicio_docente.html', 
                         reportes=reportes, 
                         acuerdos=acuerdos,
                         nombre=session.get('user_nombre'))

# Inicio Orientadora
@app.route('/inicio_orientadora')
@login_required
def inicio_orientadora():
    if session.get('user_rol') != 'orientadora':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Obtener reportes asignados a la orientadora
    reportes = conn.execute('''
        SELECT r.*, u.nombre as docente_nombre 
        FROM reportes r 
        LEFT JOIN usuarios u ON r.docente_id = u.id 
        WHERE r.orientadora_id = ? 
        ORDER BY r.fecha_creacion DESC
    ''', (session['user_id'],)).fetchall()
    
    # Obtener informes de la orientadora
    informes = conn.execute('''
        SELECT i.*
        FROM informes i 
        WHERE i.orientadora_id = ? 
        ORDER BY i.fecha_creacion DESC
    ''', (session['user_id'],)).fetchall()
    
    # Obtener acuerdos de la orientadora
    acuerdos = conn.execute('''
        SELECT a.*, u.nombre as estudiante_nombre 
        FROM acuerdos a 
        LEFT JOIN usuarios u ON a.estudiante_id = u.id 
        WHERE a.orientadora_id = ? 
        ORDER BY a.fecha_creacion DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('inicio_orientadora.html', 
                         reportes=reportes, 
                         informes=informes,
                         acuerdos=acuerdos,
                         nombre=session.get('user_nombre'))

# Crear Reporte
@app.route('/crear_reporte', methods=['GET', 'POST'])
@login_required
def crear_reporte():
    if session.get('user_rol') != 'docente':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        estudiante_nombre = request.form['estudiante_nombre']
        estudiante_grado = request.form['estudiante_grado']
        estudiante_seccion = request.form['estudiante_seccion']
        motivo = request.form['motivo']
        descripcion = request.form['descripcion']
        orientadora_id = request.form['orientadora_id']
        fecha_hora = request.form.get('fecha_hora')
        nombre_docente = request.form.get('nombre_docente')
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO reportes (docente_id, orientadora_id, estudiante_nombre, 
                                estudiante_grado, estudiante_seccion, motivo, descripcion, 
                                fecha_hora, nombre_docente, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], orientadora_id, estudiante_nombre, 
              estudiante_grado, estudiante_seccion, motivo, descripcion, 
              fecha_hora, nombre_docente, 'pendiente'))
        conn.commit()
        reporte_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Procesar evidencias si se enviaron
        archivos = request.files.getlist('evidencias')
        if archivos and archivos[0].filename:
            for archivo in archivos:
                if archivo and allowed_file(archivo.filename):
                    ext = archivo.filename.rsplit('.', 1)[1].lower()
                    nombre_unico = f"{uuid.uuid4().hex}.{ext}"
                    archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                    tamano = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                    tipo = get_file_type(archivo.filename)
                    
                    conn.execute('''
                        INSERT INTO evidencias (nombre_archivo, nombre_original, ruta, tipo, tamano, tipo_origen, origen_id, usuario_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (nombre_unico, archivo.filename, nombre_unico, tipo, tamano, 'reporte', reporte_id, session['user_id']))
            conn.commit()
        
        conn.close()
        
        return redirect(url_for('inicio_docente'))
    
    # Obtener orientadoras para el formulario
    conn = get_db_connection()
    orientadoras = conn.execute("SELECT * FROM usuarios WHERE rol = 'orientadora'").fetchall()
    conn.close()
    
    return render_template('crear_reporte.html', orientadoras=orientadoras)

# Ver Reportes
@app.route('/ver_reportes')
@login_required
def ver_reportes():
    conn = get_db_connection()
    
    if session.get('user_rol') == 'docente':
        reportes = conn.execute('''
            SELECT r.*, u.nombre as orientadora_nombre 
            FROM reportes r 
            LEFT JOIN usuarios u ON r.orientadora_id = u.id 
            WHERE r.docente_id = ? 
            ORDER BY r.fecha_creacion DESC
        ''', (session['user_id'],)).fetchall()
    else:
        reportes = conn.execute('''
            SELECT r.*, u.nombre as docente_nombre 
            FROM reportes r 
            LEFT JOIN usuarios u ON r.docente_id = u.id 
            WHERE r.orientadora_id = ? 
            ORDER BY r.fecha_creacion DESC
        ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('ver_reportes.html', reportes=reportes)

# Crear Informe
@app.route('/crear_informe', methods=['GET', 'POST'])
@login_required
def crear_informe():
    if session.get('user_rol') != 'orientadora':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        estudiante_nombre = request.form['estudiante_nombre']
        estudiante_grado = request.form['estudiante_grado']
        estudiante_seccion = request.form['estudiante_seccion']
        tipo_informe = request.form['tipo_informe']
        motivo = request.form['motivo']
        descripcion = request.form['descripcion']
        recomendaciones = request.form['recomendaciones']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO informes (orientadora_id, estudiante_nombre, estudiante_grado,
                                estudiante_seccion, tipo_informe, motivo, descripcion, recomendaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], estudiante_nombre, estudiante_grado,
              estudiante_seccion, tipo_informe, motivo, descripcion, recomendaciones))
        conn.commit()
        informe_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Procesar evidencias
        archivos = request.files.getlist('evidencias')
        if archivos and archivos[0].filename:
            for archivo in archivos:
                if archivo and allowed_file(archivo.filename):
                    ext = archivo.filename.rsplit('.', 1)[1].lower()
                    nombre_unico = f"{uuid.uuid4().hex}.{ext}"
                    archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                    tamano = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                    tipo = get_file_type(archivo.filename)
                    
                    conn.execute('''
                        INSERT INTO evidencias (nombre_archivo, nombre_original, ruta, tipo, tamano, tipo_origen, origen_id, usuario_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (nombre_unico, archivo.filename, nombre_unico, tipo, tamano, 'informe', informe_id, session['user_id']))
            conn.commit()
        
        conn.close()
        
        return redirect(url_for('inicio_orientadora'))
    
    return render_template('crear_informe.html')

# Acuerdos
@app.route('/acuerdos')
@login_required
def acuerdos():
    conn = get_db_connection()
    
    if session.get('user_rol') == 'docente':
        acuerdos = conn.execute('''
            SELECT a.*, u.nombre as estudiante_nombre 
            FROM acuerdos a 
            LEFT JOIN usuarios u ON a.estudiante_id = u.id 
            WHERE a.docente_id = ? 
            ORDER BY a.fecha_creacion DESC
        ''', (session['user_id'],)).fetchall()
    else:
        acuerdos = conn.execute('''
            SELECT a.*, u.nombre as estudiante_nombre 
            FROM acuerdos a 
            LEFT JOIN usuarios u ON a.estudiante_id = u.id 
            WHERE a.orientadora_id = ? 
            ORDER BY a.fecha_creacion DESC
        ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('acuerdos.html', acuerdos=acuerdos)

# Crear Acuerdo
@app.route('/crear_acuerdo', methods=['GET', 'POST'])
@login_required
def crear_acuerdo():
    if request.method == 'POST':
        estudiante_nombre = request.form['estudiante_nombre']
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        tipo_acuerdo = request.form['tipo_acuerdo']
        fecha_limite = request.form.get('fecha_limite')
        observaciones = request.form.get('observaciones')
        
        conn = get_db_connection()
        
        # Obtener estudiante_id si existe
        estudiante = conn.execute("SELECT id FROM usuarios WHERE nombre = ? AND rol = 'estudiante'", 
                                (estudiante_nombre,)).fetchone()
        estudiante_id = estudiante['id'] if estudiante else None
        
        if session.get('user_rol') == 'docente':
            conn.execute('''
                INSERT INTO acuerdos (docente_id, estudiante_id, estudiante_nombre, titulo, 
                                    descripcion, tipo_acuerdo, fecha_limite, observaciones, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')
            ''', (session['user_id'], estudiante_id, estudiante_nombre, titulo,
                  descripcion, tipo_acuerdo, fecha_limite, observaciones))
        else:
            conn.execute('''
                INSERT INTO acuerdos (orientadora_id, estudiante_id, estudiante_nombre, titulo,
                                    descripcion, tipo_acuerdo, fecha_limite, observaciones, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')
            ''', (session['user_id'], estudiante_id, estudiante_nombre, titulo,
                  descripcion, tipo_acuerdo, fecha_limite, observaciones))
        
        conn.commit()
        acuerdo_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Procesar evidencias
        archivos = request.files.getlist('evidencias')
        if archivos and archivos[0].filename:
            for archivo in archivos:
                if archivo and allowed_file(archivo.filename):
                    ext = archivo.filename.rsplit('.', 1)[1].lower()
                    nombre_unico = f"{uuid.uuid4().hex}.{ext}"
                    archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                    tamano = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                    tipo = get_file_type(archivo.filename)
                    
                    conn.execute('''
                        INSERT INTO evidencias (nombre_archivo, nombre_original, ruta, tipo, tamano, tipo_origen, origen_id, usuario_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (nombre_unico, archivo.filename, nombre_unico, tipo, tamano, 'acuerdo', acuerdo_id, session['user_id']))
            conn.commit()
        
        conn.close()
        
        return redirect(url_for('acuerdos'))
    
    return render_template('crear_acuerdo.html')

# Editar Acuerdo
@app.route('/editar_acuerdo/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_acuerdo(id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        tipo_acuerdo = request.form['tipo_acuerdo']
        estado = request.form['estado']
        fecha_limite = request.form.get('fecha_limite')
        observaciones = request.form.get('observaciones')
        
        conn.execute('''
            UPDATE acuerdos 
            SET titulo = ?, descripcion = ?, tipo_acuerdo = ?, estado = ?, 
                fecha_limite = ?, observaciones = ?
            WHERE id = ?
        ''', (titulo, descripcion, tipo_acuerdo, estado, fecha_limite, observaciones, id))
        conn.commit()
        conn.close()
        
        return redirect(url_for('acuerdos'))
    
    acuerdo = conn.execute('SELECT * FROM acuerdos WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if acuerdo is None:
        return redirect(url_for('acuerdos'))
    
    return render_template('editar_acuerdo.html', acuerdo=acuerdo)

# Eliminar Acuerdo
@app.route('/eliminar_acuerdo/<int:id>', methods=['DELETE'])
@login_required
def eliminar_acuerdo(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM acuerdos WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Actualizar Estado Reporte
@app.route('/actualizar_estado_reporte/<int:id>', methods=['POST'])
@login_required
def actualizar_estado_reporte(id):
    try:
        data = request.get_json()
        estado = data.get('estado')
        
        conn = get_db_connection()
        conn.execute('UPDATE reportes SET estado = ? WHERE id = ?', (estado, id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Obtener Reporte
@app.route('/obtener_reporte/<int:id>')
@login_required
def obtener_reporte(id):
    try:
        conn = get_db_connection()
        reporte = conn.execute('''
            SELECT r.*, 
                   docente.nombre as docente_nombre,
                   orientadora.nombre as orientadora_nombre
            FROM reportes r
            LEFT JOIN usuarios docente ON r.docente_id = docente.id
            LEFT JOIN usuarios orientadora ON r.orientadora_id = orientadora.id
            WHERE r.id = ?
        ''', (id,)).fetchone()
        
        # Obtener evidencias
        evidencias = conn.execute('''
            SELECT * FROM evidencias 
            WHERE tipo_origen = 'reporte' AND origen_id = ? AND usuario_id = ?
            ORDER BY fecha_subida DESC
        ''', (id, session['user_id'])).fetchall()
        
        conn.close()
        
        if reporte:
            return jsonify({
                'success': True,
                'reporte': {
                    'id': reporte['id'],
                    'estudiante_nombre': reporte['estudiante_nombre'],
                    'estudiante_grado': reporte['estudiante_grado'],
                    'estudiante_seccion': reporte['estudiante_seccion'],
                    'motivo': reporte['motivo'],
                    'descripcion': reporte['descripcion'],
                    'estado': reporte['estado'],
                    'fecha_creacion': reporte['fecha_creacion'],
                    'observaciones': reporte['observaciones'],
                    'docente_nombre': reporte['docente_nombre'],
                    'orientadora_nombre': reporte['orientadora_nombre']
                },
                'evidencias': [dict(e) for e in evidencias]
            })
        else:
            return jsonify({'success': False, 'error': 'Reporte no encontrado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# =========================================================================
# SISTEMA DE GESTIÓN DE ARCHIVOS
# =========================================================================

#Obtener estructura de carpetas para un usuario
def get_carpetas_structure(conn, usuario_id, parent_id=None):
    """Obtiene la estructura jerárquica de carpetas"""
    if parent_id is None:
        carpetas = conn.execute('''
            SELECT * FROM carpetas 
            WHERE usuario_id = ? AND parent_id IS NULL 
            ORDER BY orden, nombre
        ''', (usuario_id,)).fetchall()
    else:
        carpetas = conn.execute('''
            SELECT * FROM carpetas 
            WHERE usuario_id = ? AND parent_id = ? 
            ORDER BY orden, nombre
        ''', (usuario_id, parent_id)).fetchall()
    
    result = []
    for carpeta in carpetas:
        # Obtener subcarpetas
        subcarpetas = get_carpetas_structure(conn, usuario_id, carpeta['id'])
        # Obtener archivos en esta carpeta
        archivos = conn.execute('''
            SELECT * FROM archivos 
            WHERE carpeta_id = ? AND usuario_id = ?
            ORDER BY fecha_creacion DESC
        ''', (carpeta['id'], usuario_id)).fetchall()
        
        result.append({
            'id': carpeta['id'],
            'nombre': carpeta['nombre'],
            'parent_id': carpeta['parent_id'],
            'tipo_categoria': carpeta['tipo_categoria'],
            'color': carpeta['color'],
            'fecha_creacion': carpeta['fecha_creacion'],
            'fecha_modificacion': carpeta['fecha_modificacion'],
            'subcarpetas': subcarpetas,
            'archivos': [dict(a) for a in archivos]
        })
    
    return result

@app.route('/archivos')
@login_required
def archivos():
    """Página principal del sistema de gestión de archivos"""
    conn = get_db_connection()
    
    # Obtener carpetas organizadas por categoría
    categorias = {
        'acuerdos': [],
        'informes': [],
        'reportes': [],
        'general': []
    }
    
    # Obtener todas las carpetas del usuario
    carpetas = conn.execute('''
        SELECT * FROM carpetas 
        WHERE usuario_id = ? 
        ORDER BY tipo_categoria, orden, nombre
    ''', (session['user_id'],)).fetchall()
    
    for carpeta in carpetas:
        cat = carpeta['tipo_categoria']
        if cat in categorias:
            categorias[cat].append(dict(carpeta))
    
    # Obtener archivos recientes
    archivos_recientes = conn.execute('''
        SELECT a.*, c.nombre as carpeta_nombre 
        FROM archivos a
        LEFT JOIN carpetas c ON a.carpeta_id = c.id
        WHERE a.usuario_id = ?
        ORDER BY a.fecha_creacion DESC
        LIMIT 10
    ''', (session['user_id'],)).fetchall()
    
    # Obtener todos los tags
    tags = conn.execute('SELECT * FROM tags ORDER BY nombre').fetchall()
    
    # Obtener estadísticas
    stats = {
        'total_archivos': conn.execute('SELECT COUNT(*) FROM archivos WHERE usuario_id = ?', 
                                      (session['user_id'],)).fetchone()[0],
        'total_carpetas': conn.execute('SELECT COUNT(*) FROM carpetas WHERE usuario_id = ?', 
                                      (session['user_id'],)).fetchone()[0],
    }
    
    # Obtener archivos por tipo
    por_tipo = {}
    for tipo in ['acuerdo', 'informe', 'reporte', 'general']:
        count = conn.execute('SELECT COUNT(*) FROM archivos WHERE usuario_id = ? AND tipo_documento = ?',
                           (session['user_id'], tipo)).fetchone()[0]
        por_tipo[tipo] = count
    
    conn.close()
    
    return render_template('archivos.html', 
                         carpetas=carpetas,
                         archivos=archivos_recientes,
                         tags=tags,
                         stats=stats,
                         por_tipo=por_tipo,
                         categorias=categorias,
                         nombre=session.get('user_nombre'))

# API: Obtener estructura de carpetas
@app.route('/api/carpetas')
@login_required
def api_carpetas():
    """API para obtener la estructura de carpetas"""
    try:
        conn = get_db_connection()
        estructura = get_carpetas_structure(conn, session['user_id'])
        conn.close()
        return jsonify({'success': True, 'carpetas': estructura})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Crear carpeta
@app.route('/api/carpetas/crear', methods=['POST'])
@login_required
def crear_carpeta():
    """Crear una nueva carpeta"""
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        parent_id = data.get('parent_id')
        tipo_categoria = data.get('tipo_categoria', 'general')
        color = data.get('color', '#6366f1')
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO carpetas (nombre, parent_id, tipo_categoria, color, usuario_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, parent_id, tipo_categoria, color, session['user_id']))
        conn.commit()
        carpeta_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        
        return jsonify({'success': True, 'carpeta_id': carpeta_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Renombrar carpeta
@app.route('/api/carpetas/<int:id>/renombrar', methods=['POST'])
@login_required
def renombrar_carpeta(id):
    """Renombrar una carpeta"""
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        
        conn = get_db_connection()
        conn.execute('''
            UPDATE carpetas 
            SET nombre = ?, fecha_modificacion = CURRENT_TIMESTAMP
            WHERE id = ? AND usuario_id = ?
        ''', (nombre, id, session['user_id']))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Eliminar carpeta
@app.route('/api/carpetas/<int:id>', methods=['DELETE'])
@login_required
def eliminar_carpeta(id):
    """Eliminar una carpeta (y todos sus contenidos)"""
    try:
        conn = get_db_connection()
        
        # Verificar que la carpeta pertenece al usuario
        carpeta = conn.execute('SELECT * FROM carpetas WHERE id = ? AND usuario_id = ?', 
                           (id, session['user_id'])).fetchone()
        if not carpeta:
            conn.close()
            return jsonify({'success': False, 'error': 'Carpeta no encontrada'})
        
        # Mover archivos de la carpeta a null
        conn.execute('UPDATE archivos SET carpeta_id = NULL WHERE carpeta_id = ?', (id,))
        
        # Eliminar subcarpetas recursivamente
        def eliminar_subcarpetas(parent_id):
            subcarpetas = conn.execute('SELECT id FROM carpetas WHERE parent_id = ?', (parent_id,)).fetchall()
            for sub in subcarpetas:
                conn.execute('UPDATE archivos SET carpeta_id = NULL WHERE carpeta_id = ?', (sub['id'],))
                eliminar_subcarpetas(sub['id'])
                conn.execute('DELETE FROM carpetas WHERE id = ?', (sub['id'],))
        
        eliminar_subcarpetas(id)
        conn.execute('DELETE FROM carpetas WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Mover carpeta
@app.route('/api/carpetas/<int:id>/mover', methods=['POST'])
@login_required
def mover_carpeta(id):
    """Mover una carpeta a otra carpeta padre"""
    try:
        data = request.get_json()
        nuevo_parent_id = data.get('parent_id')
        
        # Evitar mover una carpeta a sí misma o a sus subcarpetas
        if nuevo_parent_id:
            conn = get_db_connection()
            # Obtener la carpeta destino
            destino = conn.execute('SELECT * FROM carpetas WHERE id = ? AND usuario_id = ?',
                               (nuevo_parent_id, session['user_id'])).fetchone()
            if not destino:
                conn.close()
                return jsonify({'success': False, 'error': 'Carpeta destino no encontrada'})
            
            # Verificar que no se está moviendo a sí misma
            if destino['id'] == id:
                conn.close()
                return jsonify({'success': False, 'error': 'No puedes mover una carpeta a sí misma'})
            
            conn.close()
        
        conn = get_db_connection()
        conn.execute('''
            UPDATE carpetas 
            SET parent_id = ?, fecha_modificacion = CURRENT_TIMESTAMP
            WHERE id = ? AND usuario_id = ?
        ''', (nuevo_parent_id, id, session['user_id']))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Obtener archivos de una carpeta
@app.route('/api/carpetas/<int:id>/archivos')
@login_required
def archivos_en_carpeta(id):
    """Obtener todos los archivos en una carpeta"""
    try:
        conn = get_db_connection()
        
        # Verificar que la carpeta pertenece al usuario
        carpeta = conn.execute('SELECT * FROM carpetas WHERE id = ? AND usuario_id = ?', 
                           (id, session['user_id'])).fetchone()
        if not carpeta:
            conn.close()
            return jsonify({'success': False, 'error': 'Carpeta no encontrada'})
        
        archivos = conn.execute('''
            SELECT a.*, c.nombre as carpeta_nombre 
            FROM archivos a
            LEFT JOIN carpetas c ON a.carpeta_id = c.id
            WHERE a.carpeta_id = ? AND a.usuario_id = ?
            ORDER BY a.fecha_creacion DESC
        ''', (id, session['user_id'])).fetchall()
        
        conn.close()
        
        return jsonify({'success': True, 'archivos': [dict(a) for a in archivos]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Buscar archivos con filtros avanzados
@app.route('/api/archivos/buscar')
@login_required
def buscar_archivos():
    """Búsqueda avanzada de archivos"""
    try:
        query = request.args.get('q', '')
        tipo = request.args.get('tipo')
        carpeta_id = request.args.get('carpeta_id')
        tags = request.args.getlist('tags')
        fechaDesde = request.args.get('fecha_desde')
        fechaHasta = request.args.get('fecha_hasta')
        
        conn = get_db_connection()
        
        # Construir consulta SQL
        sql = '''
            SELECT a.*, c.nombre as carpeta_nombre 
            FROM archivos a
            LEFT JOIN carpetas c ON a.carpeta_id = c.id
            WHERE a.usuario_id = ?
        '''
        params = [session['user_id']]
        
        if query:
            sql += ' AND (a.nombre LIKE ? OR a.contenido LIKE ? OR a.tags LIKE ?)'
            busqueda = f'%{query}%'
            params.extend([busqueda, busqueda, busqueda])
        
        if tipo:
            sql += ' AND a.tipo_documento = ?'
            params.append(tipo)
        
        if carpeta_id:
            sql += ' AND a.carpeta_id = ?'
            params.append(carpeta_id)
        
        if fechaDesde:
            sql += ' AND a.fecha_creacion >= ?'
            params.append(fechaDesde)
        
        if fechaHasta:
            sql += ' AND a.fecha_creacion <= ?'
            params.append(fechaHasta)
        
        if tags:
            for tag in tags:
                sql += ' AND a.tags LIKE ?'
                params.append(f'%{tag}%')
        
        sql += ' ORDER BY a.fecha_creacion DESC'
        
        archivos = conn.execute(sql, params).fetchall()
        conn.close()
        
        return jsonify({'success': True, 'archivos': [dict(a) for a in archivos]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Crear archivo
@app.route('/api/archivos/crear', methods=['POST'])
@login_required
def crear_archivo():
    """Crear un nuevo archivo"""
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        tipo_documento = data.get('tipo_documento')
        carpeta_id = data.get('carpeta_id')
        contenido = data.get('contenido', '')
        tags = data.get('tags', [])
        metadatos = data.get('metadatos', {})
        archivo_origen_tipo = data.get('archivo_origen_tipo')
        archivo_origen_id = data.get('archivo_origen_id')
        
        conn = get_db_connection()
        
        # Convertir tags a string
        tags_str = ','.join(tags) if tags else ''
        metadatos_json = json.dumps(metadatos) if metadatos else None
        
        conn.execute('''
            INSERT INTO archivos (nombre, tipo_documento, carpeta_id, contenido, tags, metadatos, 
                                archivo_origen_tipo, archivo_origen_id, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, tipo_documento, carpeta_id, contenido, tags_str, metadatos_json,
             archivo_origen_tipo, archivo_origen_id, session['user_id']))
        conn.commit()
        archivo_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Registrar en historial
        conn.execute('''
            INSERT INTO archivo_historial (archivo_id, accion, detalles, usuario_id)
            VALUES (?, 'crear', 'Archivo creado', ?)
        ''', (archivo_id, session['user_id']))
        conn.commit()
        
        conn.close()
        
        return jsonify({'success': True, 'archivo_id': archivo_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Mover archivo a carpeta
@app.route('/api/archivos/<int:id>/mover', methods=['POST'])
@login_required
def mover_archivo(id):
    """Mover un archivo a otra carpeta"""
    try:
        data = request.get_json()
        carpeta_id = data.get('carpeta_id')
        
        conn = get_db_connection()
        
        # Verificar que el archivo pertenece al usuario
        archivo = conn.execute('SELECT * FROM archivos WHERE id = ? AND usuario_id = ?',
                              (id, session['user_id'])).fetchone()
        if not archivo:
            conn.close()
            return jsonify({'success': False, 'error': 'Archivo no encontrado'})
        
        # Obtener nombre de carpeta destino
        carpeta_nombre = None
        if carpeta_id:
            carpeta = conn.execute('SELECT nombre FROM carpetas WHERE id = ? AND usuario_id = ?',
                               (carpeta_id, session['user_id'])).fetchone()
            if carpeta:
                carpeta_nombre = carpeta['nombre']
        
        detalles = f'Movido a carpeta: {carpeta_nombre}' if carpeta_nombre else 'Movido a raíz'
        
        conn.execute('''
            UPDATE archivos 
            SET carpeta_id = ?, fecha_modificacion = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (carpeta_id, id))
        
        # Registrar en historial
        conn.execute('''
            INSERT INTO archivo_historial (archivo_id, accion, detalles, usuario_id)
            VALUES (?, 'mover', ?, ?)
        ''', (id, detalles, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Actualizar archivo
@app.route('/api/archivos/<int:id>', methods=['POST'])
@login_required
def actualizar_archivo(id):
    """Actualizar un archivo"""
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        contenido = data.get('contenido')
        tags = data.get('tags', [])
        metadatos = data.get('metadatos', {})
        
        conn = get_db_connection()
        
        # Verificar que el archivo pertenece al usuario
        archivo = conn.execute('SELECT * FROM archivos WHERE id = ? AND usuario_id = ?',
                              (id, session['user_id'])).fetchone()
        if not archivo:
            conn.close()
            return jsonify({'success': False, 'error': 'Archivo no encontrado'})
        
        tags_str = ','.join(tags) if tags else ''
        metadatos_json = json.dumps(metadatos) if metadatos else None
        
        conn.execute('''
            UPDATE archivos 
            SET nombre = ?, contenido = ?, tags = ?, metadatos = ?, fecha_modificacion = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (nombre, contenido, tags_str, metadatos_json, id))
        
        # Registrar en historial
        conn.execute('''
            INSERT INTO archivo_historial (archivo_id, accion, detalles, usuario_id)
            VALUES (?, 'actualizar', 'Archivo actualizado', ?)
        ''', (id, session['user_id']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Eliminar archivo
@app.route('/api/archivos/<int:id>', methods=['DELETE'])
@login_required
def eliminar_archivo(id):
    """Eliminar un archivo"""
    try:
        conn = get_db_connection()
        
        # Verificar que el archivo pertenece al usuario
        archivo = conn.execute('SELECT * FROM archivos WHERE id = ? AND usuario_id = ?',
                              (id, session['user_id'])).fetchone()
        if not archivo:
            conn.close()
            return jsonify({'success': False, 'error': 'Archivo no encontrado'})
        
        # Registrar en historial antes de eliminar
        conn.execute('''
            INSERT INTO archivo_historial (archivo_id, accion, detalles, usuario_id)
            VALUES (?, 'eliminar', 'Archivo eliminado', ?)
        ''', (id, session['user_id']))
        
        conn.execute('DELETE FROM archivos WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Obtener un archivo
@app.route('/api/archivos/<int:id>')
@login_required
def obtener_archivo(id):
    """Obtener un archivo específico"""
    try:
        conn = get_db_connection()
        
        archivo = conn.execute('''
            SELECT a.*, c.nombre as carpeta_nombre 
            FROM archivos a
            LEFT JOIN carpetas c ON a.carpeta_id = c.id
            WHERE a.id = ? AND a.usuario_id = ?
        ''', (id, session['user_id'])).fetchone()
        
        if not archivo:
            conn.close()
            return jsonify({'success': False, 'error': 'Archivo no encontrado'})
        
        # Obtener historial
        historial = conn.execute('''
            SELECT h.*, u.nombre as usuario_nombre
            FROM archivo_historial h
            LEFT JOIN usuarios u ON h.usuario_id = u.id
            WHERE h.archivo_id = ?
            ORDER BY h.fecha DESC
        ''', (id,)).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True, 
            'archivo': dict(archivo),
            'historial': [dict(h) for h in historial]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Gestión de tags
@app.route('/api/tags', methods=['GET', 'POST'])
@login_required
def api_tags():
    """API para obtener o crear tags"""
    try:
        if request.method == 'GET':
            conn = get_db_connection()
            tags = conn.execute('SELECT * FROM tags ORDER BY nombre').fetchall()
            conn.close()
            return jsonify({'success': True, 'tags': [dict(t) for t in tags]})
        else:
            data = request.get_json()
            nombre = data.get('nombre')
            color = data.get('color', '#6366f1')
            
            conn = get_db_connection()
            try:
                conn.execute('INSERT INTO tags (nombre, color) VALUES (?, ?)', (nombre, color))
                conn.commit()
                tag_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                conn.close()
                return jsonify({'success': True, 'tag_id': tag_id})
            except sqlite3.IntegrityError:
                conn.close()
                return jsonify({'success': False, 'error': 'El tag ya existe'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# API: Eliminar tag
@app.route('/api/tags/<int:id>', methods=['DELETE'])
@login_required
def eliminar_tag(id):
    """Eliminar un tag"""
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM tags WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Página Acerca de
@app.route('/acerca')
@login_required
def acerca():
    """Página de información institucional"""
    return render_template('acerca.html', nombre=session.get('user_nombre'))

# API: Guardar documento existente al sistema de archivos
@app.route('/api/archivos/guardar_documento', methods=['POST'])
@login_required
def guardar_documento():
    """Guardar un documento (acuerdo, informe, reporte) al sistema de archivos"""
    try:
        data = request.get_json()
        doc_tipo = data.get('doc_tipo')  # 'acuerdo', 'informe', 'reporte'
        doc_id = data.get('doc_id')
        carpeta_id = data.get('carpeta_id')
        tags = data.get('tags', [])
        
        conn = get_db_connection()
        
        contenido = ""
        nombre = ""
        tipo = ""
        
        if doc_tipo == 'acuerdo':
            doc = conn.execute('SELECT * FROM acuerdos WHERE id = ?', (doc_id,)).fetchone()
            if doc:
                nombre = f"Acuerdo: {doc['titulo']}"
                contenido = f"Título: {doc['titulo']}\nDescripción: {doc['descripcion']}\nTipo: {doc['tipo_acuerdo']}\nEstado: {doc['estado']}\nEstudiante: {doc['estudiante_nombre']}"
                if doc['fecha_limite']:
                    contenido += f"\nFecha límite: {doc['fecha_limite']}"
                if doc['observaciones']:
                    contenido += f"\nObservaciones: {doc['observaciones']}"
                tipo = 'acuerdo'
        elif doc_tipo == 'informe':
            doc = conn.execute('SELECT * FROM informes WHERE id = ?', (doc_id,)).fetchone()
            if doc:
                nombre = f"Informe: {doc['estudiante_nombre']}"
                contenido = f"Estudiante: {doc['estudiante_nombre']}\nGrado: {doc['estudiante_grado']}\nSección: {doc['estudiante_seccion']}\nTipo: {doc['tipo_informe']}\nMotivo: {doc['motivo']}\nDescripción: {doc['descripcion']}\nRecomendaciones: {doc['recomendaciones']}"
                tipo = 'informe'
        elif doc_tipo == 'reporte':
            doc = conn.execute('SELECT * FROM reportes WHERE id = ?', (doc_id,)).fetchone()
            if doc:
                nombre = f"Reporte: {doc['estudiante_nombre']}"
                contenido = f"Estudiante: {doc['estudiante_nombre']}\nGrado: {doc['estudiante_grado']}\nSección: {doc['estudiante_seccion']}\nMotivo: {doc['motivo']}\nDescripción: {doc['descripcion']}\nEstado: {doc['estado']}"
                if doc['observaciones']:
                    contenido += f"\nObservaciones: {doc['observaciones']}"
                tipo = 'reporte'
        
        if not nombre:
            conn.close()
            return jsonify({'success': False, 'error': 'Documento no encontrado'})
        
        tags_str = ','.join(tags) if tags else ''
        
        conn.execute('''
            INSERT INTO archivos (nombre, tipo_documento, carpeta_id, contenido, tags, archivo_origen_tipo, archivo_origen_id, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, tipo, carpeta_id, contenido, tags_str, doc_tipo, doc_id, session['user_id']))
        conn.commit()
        archivo_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Registrar en historial
        conn.execute('''
            INSERT INTO archivo_historial (archivo_id, accion, detalles, usuario_id)
            VALUES (?, 'crear', 'Documento importado desde sistema', ?)
        ''', (archivo_id, session['user_id']))
        conn.commit()
        
        conn.close()
        
        return jsonify({'success': True, 'archivo_id': archivo_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# =========================================================================
# FIN SISTEMA DE GESTIÓN DE ARCHIVOS
# =========================================================================

# =========================================================================
# SISTEMA DE EVIDENCIAS (Archivos adjuntos)
# =========================================================================

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """Determina el tipo de archivo"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        return 'imagen'
    elif ext in ['pdf']:
        return 'documento'
    elif ext in ['docx', 'doc']:
        return 'documento'
    elif ext in ['mp4', 'webm', 'avi']:
        return 'video'
    return 'otro'

# Ruta para servir archivos subidos
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    """Sirve archivos de la carpeta uploads"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# API: Subir evidencias
@app.route('/api/evidencias/subir', methods=['POST'])
@login_required
def subir_evidencia():
    """Subir una o múltiples evidencias asociadas a un documento"""
    try:
        # Verificar que se envió un archivo
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se recibió ningún archivo'}), 400
        
        tipo_origen = request.form.get('tipo_origen')  # 'reporte', 'informe', 'acuerdo'
        origen_id = request.form.get('origen_id')
        
        if not tipo_origen or not origen_id:
            return jsonify({'success': False, 'error': 'Faltan datos del documento'}), 400
        
        archivos = request.files.getlist('archivo')
        if not archivos or archivos[0].filename == '':
            return jsonify({'success': False, 'error': 'No se seleccionó ningún archivo'}), 400
        
        conn = get_db_connection()
        evidencias_guardadas = []
        
        for archivo in archivos:
            if archivo and allowed_file(archivo.filename):
                # Generar nombre único
                ext = archivo.filename.rsplit('.', 1)[1].lower()
                nombre_unico = f"{uuid.uuid4().hex}.{ext}"
                nombre_original = archivo.filename
                
                # Guardar archivo
                archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                
                # Obtener tamaño
                tamano = os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico))
                
                # Determinar tipo
                tipo = get_file_type(archivo.filename)
                
                # Guardar en BD
                conn.execute('''
                    INSERT INTO evidencias (nombre_archivo, nombre_original, ruta, tipo, tamano, tipo_origen, origen_id, usuario_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (nombre_unico, nombre_original, nombre_unico, tipo, tamano, tipo_origen, origen_id, session['user_id']))
                
                evidencia_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                evidencias_guardadas.append({
                    'id': evidencia_id,
                    'nombre': nombre_original,
                    'tipo': tipo
                })
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'evidencias': evidencias_guardadas})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Obtener evidencias de un documento
@app.route('/api/evidencias/<tipo_origen>/<int:origen_id>')
@login_required
def obtener_evidencias(tipo_origen, origen_id):
    """Obtener todas las evidencias de un documento específico"""
    try:
        conn = get_db_connection()
        evidencias = conn.execute('''
            SELECT * FROM evidencias 
            WHERE tipo_origen = ? AND origen_id = ? AND usuario_id = ?
            ORDER BY fecha_subida DESC
        ''', (tipo_origen, origen_id, session['user_id'])).fetchall()
        conn.close()
        
        return jsonify({'success': True, 'evidencias': [dict(e) for e in evidencias]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API: Eliminar evidencia
@app.route('/api/evidencias/<int:id>', methods=['DELETE'])
@login_required
def eliminar_evidencia(id):
    """Eliminar una evidencia"""
    try:
        conn = get_db_connection()
        
        # Verificar que la evidencia pertenece al usuario
        evidencia = conn.execute('''
            SELECT * FROM evidencias WHERE id = ? AND usuario_id = ?
        ''', (id, session['user_id'])).fetchone()
        
        if not evidencia:
            conn.close()
            return jsonify({'success': False, 'error': 'Evidencia no encontrada'}), 404
        
        # Eliminar archivo físico
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], evidencia['nombre_archivo']))
        except:
            pass  # Si el archivo no existe, continuar
        
        # Eliminar de BD
        conn.execute('DELETE FROM evidencias WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =========================================================================
# FIN SISTEMA DE EVIDENCIAS
# =========================================================================

# =========================================================================
# DESCARGAR PDFs
# =========================================================================

@app.route('/descargar_reporte_pdf/<int:id>')
@login_required
def descargar_reporte_pdf(id):
    conn = get_db_connection()
    reporte = conn.execute('''
        SELECT r.*, 
               docente.nombre as docente_nombre,
               orientadora.nombre as orientadora_nombre
        FROM reportes r
        LEFT JOIN usuarios docente ON r.docente_id = docente.id
        LEFT JOIN usuarios orientadora ON r.orientadora_id = orientadora.id
        WHERE r.id = ?
    ''', (id,)).fetchone()
    conn.close()
    
    if not reporte:
        return "Reporte no encontrado", 404
    
    html = render_template('pdf_reporte.html', reporte=reporte)
    pdf = HTML(string=html).write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=reporte_{id}.pdf'
    return response

@app.route('/descargar_informe_pdf/<int:id>')
@login_required
def descargar_informe_pdf(id):
    conn = get_db_connection()
    informe = conn.execute('''
        SELECT i.*, u.nombre as orientadora_nombre
        FROM informes i
        LEFT JOIN usuarios u ON i.orientadora_id = u.id
        WHERE i.id = ?
    ''', (id,)).fetchone()
    conn.close()
    
    if not informe:
        return "Informe no encontrado", 404
    
    html = render_template('pdf_informe.html', informe=informe)
    pdf = HTML(string=html).write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=informe_{id}.pdf'
    return response

@app.route('/descargar_acuerdo_pdf/<int:id>')
@login_required
def descargar_acuerdo_pdf(id):
    conn = get_db_connection()
    acuerdo = conn.execute('SELECT * FROM acuerdos WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if not acuerdo:
        return "Acuerdo no encontrado", 404
    
    html = render_template('pdf_acuerdo.html', acuerdo=acuerdo)
    pdf = HTML(string=html).write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=acuerdo_{id}.pdf'
    return response

if __name__ == "__main__":
    app.run(debug=True)
