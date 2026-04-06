import sqlite3

with sqlite3.connect('database.db') as conn:
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        correo TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reportes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        docente_id INTEGER NOT NULL,
        orientadora_id INTEGER NOT NULL,
        estudiante_nombre TEXT NOT NULL,
        estudiante_grado TEXT NOT NULL,
        estudiante_seccion TEXT NOT NULL,
        motivo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        estado TEXT DEFAULT 'pendiente',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (docente_id) REFERENCES usuarios (id),
        FOREIGN KEY (orientadora_id) REFERENCES usuarios (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS informes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orientadora_id INTEGER NOT NULL,
        estudiante_nombre TEXT NOT NULL,
        estudiante_grado TEXT NOT NULL,
        estudiante_seccion TEXT NOT NULL,
        tipo_informe TEXT NOT NULL,
        motivo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        recomendaciones TEXT NOT NULL,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (orientadora_id) REFERENCES usuarios (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS acuerdos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        docente_id INTEGER,
        orientadora_id INTEGER,
        estudiante_id INTEGER,
        estudiante_nombre TEXT NOT NULL,
        titulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        tipo_acuerdo TEXT NOT NULL,
        fecha_limite TEXT,
        observaciones TEXT,
        estado TEXT DEFAULT 'pendiente',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (docente_id) REFERENCES usuarios (id),
        FOREIGN KEY (orientadora_id) REFERENCES usuarios (id),
        FOREIGN KEY (estudiante_id) REFERENCES usuarios (id)
    )
    ''')

    # ====== SISTEMA DE GESTIÓN DE ARCHIVOS ======
    
    # Tabla de carpetas - estructura jerárquica
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS carpetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        parent_id INTEGER,
        tipo_categoria TEXT NOT NULL,
        color TEXT DEFAULT '#6366f1',
        orden INTEGER DEFAULT 0,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES carpetas (id) ON DELETE CASCADE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )
    ''')

    # Tabla de archivos/documentos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS archivos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        tipo_documento TEXT NOT NULL,
        carpeta_id INTEGER,
        contenido TEXT,
        tags TEXT,
        metadatos TEXT,
        archivo_origen_tipo TEXT,
        archivo_origen_id INTEGER,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER NOT NULL,
        FOREIGN KEY (carpeta_id) REFERENCES carpetas (id) ON DELETE SET NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )
    ''')

    # Tabla de etiquetas/tags
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        color TEXT DEFAULT '#6366f1',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Tabla de historial de movimientos de archivos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS archivo_historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        archivo_id INTEGER NOT NULL,
        accion TEXT NOT NULL,
        detalles TEXT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER NOT NULL,
        FOREIGN KEY (archivo_id) REFERENCES archivos (id) ON DELETE CASCADE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )
    ''')

    # Tabla de evidencias (archivos adjuntos a reportes, informes, acuerdos)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evidencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_archivo TEXT NOT NULL,
        nombre_original TEXT NOT NULL,
        ruta TEXT NOT NULL,
        tipo TEXT NOT NULL,
        tamano INTEGER DEFAULT 0,
        tipo_origen TEXT NOT NULL,
        origen_id INTEGER NOT NULL,
        fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
    )
    ''')

    # Verificar si ya existen usuarios para evitar duplicados
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    count = cursor.fetchone()[0]

    if count == 0:
        # Crear usuarios base del sistema (contraseña: 1234)
        usuarios = [
            ("Docente", "docente@gmail.com", "1234", "docente"),
            ("Thelma Vallejo", "thelma@gmail.com", "1234", "orientadora"),
            ("Iris Castillo ", "iris@gmail.com", "1234", "orientadora"),
            ("Fiordaliza Herrera ", "fiordaliza@gmail.com", "1234", "orientadora"),
            ("Marisol Abreu ", "marisol@gmail.com", "1234", "orientadora"),
            ("Yahaira Herrera ", "yahaira@gmail.com", "1234", "orientadora"),
        ]

        cursor.executemany(
            "INSERT INTO usuarios (nombre, correo, password, rol) VALUES (?, ?, ?, ?)",
            usuarios
        )

        print("Base de datos creada con usuarios base")
    else:
        print("Base de datos verificada correctamente")

print("Base de datos lista")

# ====== SISTEMA DE GESTIÓN DE ARCHIVOS ======

# Crear carpetas por defecto para categorías de documentos
def crear_carpetas_iniciales(conn, usuario_id):
    cursor = conn.cursor()
    
    # Verificar si ya existen carpetas
    cursor.execute("SELECT COUNT(*) FROM carpetas WHERE usuario_id = ?", (usuario_id,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Crear carpetas raíz por categoría
        carpetas = [
            # Acuerdos
            ("Acuerdos", None, "acuerdos", "#10b981", 1),
            ("Pendientes", None, "acuerdos", "#f59e0b", 2),
            ("Completados", None, "acuerdos", "#6366f1", 3),
            # Informes
            ("Informes", None, "informes", "#3b82f6", 4),
            ("Psicológicos", None, "informes", "#8b5cf6", 5),
            ("Académicos", None, "informes", "#06b6d4", 6),
            # Reportes
            ("Reportes", None, "reportes", "#ef4444", 7),
            ("Pendientes", None, "reportes", "#f59e0b", 8),
            ("Atendidos", None, "reportes", "#10b981", 9),
            # General
            ("Documentos", None, "general", "#6b7280", 10),
            ("Archivos", None, "general", "#374151", 11),
        ]
        
        cursor.executemany(
            "INSERT INTO carpetas (nombre, parent_id, tipo_categoria, color, orden, usuario_id) VALUES (?, ?, ?, ?, ?, ?)",
            [(nombre, parent, tipo, color, orden, usuario_id) for nombre, parent, tipo, color, orden in carpetas]
        )
        
        print("Carpetas iniciales creadas")
    
    return cursor.lastrowid

# Ejecutar si es el script principal
if __name__ == "__main__":
    with sqlite3.connect('database.db') as conn:
        crear_carpetas_iniciales(conn, 1)
        print("Sistema de archivos inicializado")

