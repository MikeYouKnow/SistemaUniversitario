import os
import smtplib
from email.message import EmailMessage
import secrets
import string
from datetime import timedelta
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, abort
)
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN BÁSICA
# =====================================

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambia-esta-clave")
app.permanent_session_lifetime = timedelta(hours=4)


# =====================================
# CONEXIÓN A POSTGRES
# =====================================

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "DB_universidad"),
        user=os.getenv("DB_USER", "backend_app"),
        password=os.getenv("DB_PASSWORD", "Backend123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        cursor_factory=RealDictCursor,
    )


# =====================================
# FUNCIONES AUXILIARES
# =====================================

def current_user():
    """Obtiene al usuario en sesión."""
    if "user_id" not in session:
        return None
    return {
        "id_usuario": session.get("user_id"),
        "nombre_usuario": session.get("username"),
        "correo_electronico": session.get("email"),
        "roles": session.get("roles", []),
        "rol_actual": session.get("rol_actual"),
    }


def login_required(view_func):
    """Protege rutas contra usuarios no autenticados."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def role_required(*roles_permitidos):
    """Protege rutas por rol actual."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            rol = session.get("rol_actual")
            if rol not in roles_permitidos:
                flash("No tienes permisos para acceder a esta sección.", "danger")
                return redirect(url_for("dashboard"))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def send_email(to_email: str, subject: str, body: str):
    """Envío de correo con smtplib."""
    server = os.getenv("MAIL_SERVER")
    port = int(os.getenv("MAIL_PORT", "587"))
    username = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    default_sender = os.getenv("MAIL_DEFAULT_SENDER", username)

    if not all([server, port, username, password]):
        print("⚠ Configuración SMTP incompleta")
        return

    msg = EmailMessage()
    msg["From"] = default_sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(server, port) as smtp:
        if use_tls:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(msg)


def generate_random_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


# =====================================
# MAPEO DE ROLES
# =====================================

ROLE_DASHBOARD_MAP = {
    "Administrador": "perfil_administrador",
    "Coordinador": "perfil_coordinador",
    "Docente": "perfil_docente",
    "Bibliotecario": "perfil_bibliotecario",
    "Estudiante": "est_perfil_informacion",
}


# =====================================
# LOGIN / LOGOUT
# =====================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    identificador = request.form.get("identificador", "").strip()
    contrasena = request.form.get("contrasena", "").strip()
    selected_role = request.form.get("rol", "").strip()

    if not identificador or not contrasena:
        flash("Debes ingresar usuario/correo y contraseña.", "danger")
        return render_template("login.html")

    if not selected_role:
        flash("Debes seleccionar un rol.", "danger")
        return render_template("login.html")

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                ARRAY_AGG(r.nombre_rol) AS roles
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            WHERE u.activo = TRUE
              AND (
                LOWER(u.nombre_usuario) = LOWER(%s)
                OR LOWER(u.correo_electronico) = LOWER(%s)
              )
              AND u.contrasena_hash = crypt(%s, u.contrasena_hash)
            GROUP BY u.id_usuario;
        """, (identificador, identificador, contrasena))

        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user:
            flash("Credenciales incorrectas.", "danger")
            return render_template("login.html")

        if selected_role not in user["roles"]:
            flash("El rol no pertenece a tu cuenta.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id_usuario"]
        session["username"] = user["nombre_usuario"]
        session["email"] = user["correo_electronico"]
        session["roles"] = user["roles"]
        session["rol_actual"] = selected_role

        endpoint = ROLE_DASHBOARD_MAP.get(selected_role)
        if not endpoint:
            flash("No se encontró dashboard para tu rol.", "warning")
            return redirect(url_for("dashboard"))

        return redirect(url_for(endpoint))

    except Exception as e:
        if conn:
            conn.close()
        flash(f"Error al iniciar sesión: {e}", "danger")
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    # Mostrar el formulario
    if request.method == "GET":
        return render_template("forgot_password.html")

    # Procesar el formulario
    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Debes ingresar tu correo para recuperar la contraseña.", "warning")
        return render_template("forgot_password.html")

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Buscar usuario por correo
        cur.execute(
            """
            SELECT id_usuario, correo_electronico
            FROM seguridad.usuarios
            WHERE LOWER(correo_electronico) = %s
            """,
            (email,),
        )
        user = cur.fetchone()

        if not user:
            flash("No se encontró un usuario con ese correo.", "danger")
            cur.close()
            conn.close()
            return render_template("forgot_password.html")

        # Generar contraseña temporal
        temp_password = generate_random_password(10)

        # Actualizar contrasena_hash (el trigger la hashea)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE seguridad.usuarios
            SET contrasena_hash = %s
            WHERE id_usuario = %s
            """,
            (temp_password, user["id_usuario"]),
        )
        conn.commit()
        cur.close()
        conn.close()

        # Enviar correo (si SMTP está configurado)
        try:
            send_email(
                user["correo_electronico"],
                "Recuperación de contraseña - Sistema Universitario",
                f"Tu nueva contraseña temporal es: {temp_password}\n\n"
                "Por seguridad, cambia la contraseña después de iniciar sesión.",
            )
        except Exception as e:
            # Si el correo falla, al menos avisamos
            print(f"Error enviando correo de recuperación: {e}")

        flash(
            "Se ha enviado una contraseña temporal a tu correo (si está configurado el servidor de correo).",
            "success",
        )
        return redirect(url_for("login"))

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        flash(f"Error al procesar la recuperación de contraseña: {e}", "danger")
        return render_template("forgot_password.html")


# =====================================
# DASHBOARD PRINCIPAL
# =====================================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    rol = session.get("rol_actual")
    endpoint = ROLE_DASHBOARD_MAP.get(rol)
    if endpoint:
        return redirect(url_for(endpoint))
    return render_template("dashboard_estudiante.html", user=current_user())


# =====================================
# PERFILES POR ROL
# =====================================

@app.route("/perfil/administrador")
@login_required
@role_required("Administrador")
def perfil_administrador():
    return render_template("perfiles/profile_admin.html", user=current_user())





@app.route("/perfil/estudiante")
@login_required
@role_required("Estudiante")
def perfil_estudiante_main():
    return render_template("perfiles/profile_estudiante.html", user=current_user())


# =====================================
# FUNCIONES AUX. ESPECÍFICAS
# =====================================

def _get_numero_control(conn, user_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT numero_control
        FROM seguridad.auth_user_alumno
        WHERE user_id = %s;
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    return row["numero_control"] if row else None


def _get_personal_id(conn, user_id):
    """Obtiene id_personal de rrhh.personal a partir de seguridad.usuarios.id_usuario."""
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id_personal
        FROM rrhh.personal p
        WHERE p.fk_id_usuario = %s;
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    return row["id_personal"] if row else None


# =====================================
# ESTUDIANTE – INFORMACIÓN GENERAL
# =====================================

@app.route("/estudiante/informacion")
@login_required
@role_required("Estudiante")
def est_perfil_informacion():
    user = current_user()
    info_estudiante = None

    conn = None
    try:
        conn = get_connection()
        nc = _get_numero_control(conn, user["id_usuario"])
        if not nc:
            raise Exception("No hay número de control asociado a este usuario.")

        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.numero_control AS matricula,
                TRIM(
                    a.nombre || ' ' ||
                    a.apellido_paterno || ' ' ||
                    COALESCE(a.apellido_materno, '')
                ) AS nombre_completo,
                a.curp,
                COALESCE(cto.correo_institucional, cto.correo_personal) AS correo,
                cto.telefono,
                plan_info.carrera_nombre,
                plan_info.semestre,
                plan_info.tutor_nombre,
                plan_info.tutor_correo
            FROM academico.alumnos a
            LEFT JOIN academico.vw_contacto_actual cto
              ON cto.numero_control = a.numero_control
            LEFT JOIN LATERAL (
                SELECT
                    c.nombre AS carrera_nombre,
                    cm.semestre,
                    TRIM(
                        COALESCE(p.nombre,'') || ' ' ||
                        COALESCE(p.apellido_paterno,'') || ' ' ||
                        COALESCE(p.apellido_materno,'')
                    ) AS tutor_nombre,
                    p.correo_institucional AS tutor_correo
                FROM academico.alumno_inscripcion ai
                JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
                JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
                JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
                LEFT JOIN rrhh.personal p ON p.id_personal = ma.fk_personal
                WHERE ai.fk_alumno = a.numero_control
                ORDER BY cm.semestre DESC, ma.materia_alta_id DESC
                LIMIT 1
            ) AS plan_info ON TRUE
            WHERE a.numero_control = %s
            LIMIT 1;
        """, (nc,))
        info_estudiante = cur.fetchone()
        cur.close()
        if conn and not conn.closed:
            conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error obteniendo información del estudiante: {e}", "danger")

    return render_template(
        "estudiante/perfil_estudiante.html",
        user=user,
        info_estudiante=info_estudiante,
    )


# =====================================
# ESTUDIANTE – MATERIAS & HORARIO
# =====================================

@app.route("/estudiante/materias-horario")
@login_required
@role_required("Estudiante")
def est_perfil_materias_horario():
    user = current_user()
    materias = []
    horario = []
    info_estudiante = None

    conn = None
    try:
        conn = get_connection()
        nc = _get_numero_control(conn, user["id_usuario"])
        if not nc:
            raise Exception("No hay número de control asociado a este usuario.")

        cur = conn.cursor()

        # ---- Info estudiante para el encabezado ----
        cur.execute("""
            SELECT
                a.numero_control AS matricula,
                TRIM(
                    a.nombre || ' ' ||
                    a.apellido_paterno || ' ' ||
                    COALESCE(a.apellido_materno, '')
                ) AS nombre_completo,
                a.curp,
                COALESCE(cto.correo_institucional, cto.correo_personal) AS correo,
                cto.telefono,
                plan_info.carrera_nombre,
                plan_info.semestre,
                plan_info.tutor_nombre,
                plan_info.tutor_correo
            FROM academico.alumnos a
            LEFT JOIN academico.vw_contacto_actual cto
              ON cto.numero_control = a.numero_control
            LEFT JOIN LATERAL (
                SELECT
                    c.nombre AS carrera_nombre,
                    cm.semestre,
                    TRIM(
                        COALESCE(p.nombre,'') || ' ' ||
                        COALESCE(p.apellido_paterno,'') || ' ' ||
                        COALESCE(p.apellido_materno,'')
                    ) AS tutor_nombre,
                    p.correo_institucional AS tutor_correo
                FROM academico.alumno_inscripcion ai
                JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
                JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
                JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
                LEFT JOIN rrhh.personal p ON p.id_personal = ma.fk_personal
                WHERE ai.fk_alumno = a.numero_control
                ORDER BY cm.semestre DESC, ma.materia_alta_id DESC
                LIMIT 1
            ) AS plan_info ON TRUE
            WHERE a.numero_control = %s
            LIMIT 1;
        """, (nc,))
        info_estudiante = cur.fetchone()

        # ---- Materias ----
        cur.execute("""
            SELECT
                m.clave,
                m.nombre AS nombre_materia,
                TRIM(
                    COALESCE(p.nombre,'') || ' ' ||
                    COALESCE(p.apellido_paterno,'') || ' ' ||
                    COALESCE(p.apellido_materno,'')
                ) AS docente,
                cm.horas_totales AS creditos
            FROM academico.alumno_inscripcion ai
            JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
            JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m ON m.materia_id = cm.materia_id
            LEFT JOIN rrhh.personal p ON p.id_personal = ma.fk_personal
            WHERE ai.fk_alumno = %s
            ORDER BY m.clave;
        """, (nc,))
        materias = cur.fetchall()

        # ---- Horario ----
        cur.execute("""
            SELECT
                CASE h.dia_semana
                    WHEN 1 THEN 'Lunes'
                    WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles'
                    WHEN 4 THEN 'Jueves'
                    WHEN 5 THEN 'Viernes'
                    WHEN 6 THEN 'Sábado'
                    ELSE 'Domingo'
                END AS dia,
                h.hora_inicio,
                h.hora_fin,
                m.nombre AS materia,
                a.clave || ' (Edif. ' || e.numero || ')' AS aula
            FROM academico.alumno_inscripcion ai
            JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
            JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m ON m.materia_id = cm.materia_id
            LEFT JOIN infraestructura.horario_asignacion h ON h.fk_materia_alta = ma.materia_alta_id
            LEFT JOIN infraestructura.aula a ON a.aula_id = h.fk_aula
            LEFT JOIN infraestructura.edificio e ON e.edificio_id = a.edificio_id
            WHERE ai.fk_alumno = %s
            ORDER BY h.dia_semana, h.hora_inicio;
        """, (nc,))
        horario = cur.fetchall()

        cur.close()
        if conn and not conn.closed:
            conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error al cargar materias/horario: {e}", "danger")

    return render_template(
        "estudiante/perfil_materias_horario.html",
        user=user,
        info_estudiante=info_estudiante,
        materias=materias,
        horario=horario,
    )


# =====================================
# ESTUDIANTE – BIBLIOTECA
# =====================================

@app.route("/estudiante/biblioteca")
@login_required
@role_required("Estudiante")
def est_perfil_biblioteca():
    user = current_user()
    prestamos_activos = []
    historial_prestamos = []
    info_estudiante = None

    conn = None
    try:
        conn = get_connection()
        nc = _get_numero_control(conn, user["id_usuario"])
        if not nc:
            raise Exception("No hay número de control asociado a este usuario.")

        cur = conn.cursor()

        # ---- Info estudiante para el encabezado ----
        cur.execute("""
            SELECT
                a.numero_control AS matricula,
                TRIM(
                    a.nombre || ' ' ||
                    a.apellido_paterno || ' ' ||
                    COALESCE(a.apellido_materno, '')
                ) AS nombre_completo,
                a.curp,
                COALESCE(cto.correo_institucional, cto.correo_personal) AS correo,
                cto.telefono,
                plan_info.carrera_nombre,
                plan_info.semestre,
                plan_info.tutor_nombre,
                plan_info.tutor_correo
            FROM academico.alumnos a
            LEFT JOIN academico.vw_contacto_actual cto
              ON cto.numero_control = a.numero_control
            LEFT JOIN LATERAL (
                SELECT
                    c.nombre AS carrera_nombre,
                    cm.semestre,
                    TRIM(
                        COALESCE(p.nombre,'') || ' ' ||
                        COALESCE(p.apellido_paterno,'') || ' ' ||
                        COALESCE(p.apellido_materno,'')
                    ) AS tutor_nombre,
                    p.correo_institucional AS tutor_correo
                FROM academico.alumno_inscripcion ai
                JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
                JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
                JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
                LEFT JOIN rrhh.personal p ON p.id_personal = ma.fk_personal
                WHERE ai.fk_alumno = a.numero_control
                ORDER BY cm.semestre DESC, ma.materia_alta_id DESC
                LIMIT 1
            ) AS plan_info ON TRUE
            WHERE a.numero_control = %s
            LIMIT 1;
        """, (nc,))
        info_estudiante = cur.fetchone()

        # ---- Préstamos activos ----
        cur.execute("""
            SELECT
                p.id_prestamo,
                l.titulo_libro                 AS titulo_libro,
                p.fecha_prestamo,
                p.fecha_devolucion_estimada    AS fecha_limite,
                p.fecha_devolucion_real,
                p.estado
            FROM biblioteca.prestamos p
            JOIN biblioteca.libros l ON l.id_libro = p.id_libro
            WHERE p.fk_alumno = %s
              AND p.estado <> 'Devuelto'
            ORDER BY p.fecha_prestamo DESC;
        """, (nc,))
        prestamos_activos = cur.fetchall()

        # ---- Historial (devueltos) ----
        cur.execute("""
            SELECT
                p.id_prestamo,
                l.titulo_libro                 AS titulo_libro,
                p.fecha_prestamo,
                p.fecha_devolucion_real        AS fecha_devolucion,
                p.estado
            FROM biblioteca.prestamos p
            JOIN biblioteca.libros l ON l.id_libro = p.id_libro
            WHERE p.fk_alumno = %s
              AND p.estado = 'Devuelto'
            ORDER BY p.fecha_devolucion_real DESC NULLS LAST;
        """, (nc,))
        historial_prestamos = cur.fetchall()

        cur.close()
        if conn and not conn.closed:
            conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error al cargar información de biblioteca: {e}", "danger")

    return render_template(
        "estudiante/perfil_biblioteca.html",
        user=user,
        info_estudiante=info_estudiante,
        prestamos_activos=prestamos_activos,
        historial_prestamos=historial_prestamos,
    )


@app.route("/estudiante/solicitar-libro", methods=["GET", "POST"])
@login_required
@role_required("Estudiante")
def est_solicitar_libro_modal():
    user = current_user()
    resultados = []
    conn = None

    try:
        conn = get_connection()
        nc = _get_numero_control(conn, user["id_usuario"])
        if not nc:
            raise Exception("No hay número de control asociado a este usuario.")

        cur = conn.cursor()

        if request.method == "POST":
            id_libro = request.form.get("id_libro")
            if not id_libro:
                flash("No se seleccionó un libro válido.", "danger")
            else:
                cur.execute("""
                    INSERT INTO biblioteca.prestamos
                        (fk_alumno, fk_personal, id_libro,
                         fecha_prestamo, fecha_devolucion_estimada, estado)
                    VALUES
                        (%s, NULL, %s,
                         NOW(), NOW() + INTERVAL '7 days', 'Activo');
                """, (nc, int(id_libro)))
                conn.commit()
                flash("Solicitud de préstamo registrada correctamente.", "success")
                cur.close()
                if conn and not conn.closed:
                    conn.close()
                return redirect(url_for("est_perfil_biblioteca"))

        # GET: búsqueda de libros
        q = request.args.get("q", "").strip()
        if q:
            cur.execute("""
                SELECT
                    l.id_libro,
                    l.titulo_libro                AS titulo,
                    COALESCE(inv.cantidad_disponible, 0) AS ejemplares_disponibles
                FROM biblioteca.libros l
                LEFT JOIN biblioteca.inventario inv
                  ON inv.id_libro = l.id_libro
                WHERE LOWER(l.titulo_libro) LIKE LOWER(%s)
                ORDER BY l.titulo_libro
                LIMIT 50;
            """, (f"%{q}%",))
            resultados = cur.fetchall()

        cur.close()
        if conn and not conn.closed:
            conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error al procesar solicitud de libro: {e}", "danger")

    return render_template(
        "estudiante/solicitar_libro_modal.html",
        user=user,
        resultados=resultados,
    )


# =====================================
# ESTUDIANTE – AULAS
# =====================================

@app.route("/estudiante/aulas")
@login_required
@role_required("Estudiante")
def est_perfil_aulas():
    user = current_user()

    # Filtros desde la URL
    q = request.args.get("q", "").strip()
    edificio = request.args.get("edificio", "").strip()
    piso = request.args.get("piso", "").strip()
    tipo = request.args.get("tipo", "").strip()

    aulas = []
    edificios = []
    tipos_aula = []
    pisos = []

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # --- Edificios ---
        cur.execute("""
            SELECT edificio_id, numero
            FROM infraestructura.edificio
            ORDER BY numero;
        """)
        edificios = cur.fetchall()

        # --- Tipos de aula ---
        cur.execute("""
            SELECT tipo_id, nombre
            FROM infraestructura.tipo_aula
            ORDER BY nombre;
        """)
        tipos_aula = cur.fetchall()

        # --- Pisos disponibles ---
        cur.execute("""
            SELECT DISTINCT piso
            FROM infraestructura.aula
            ORDER BY piso;
        """)
        pisos_rows = cur.fetchall()
        pisos = [r["piso"] for r in pisos_rows]

        # --- Consulta principal de aulas ---
        base_sql = """
            SELECT
                a.aula_id,
                a.clave,
                e.numero AS edificio,
                a.piso,
                a.capacidad,
                ta.nombre AS tipo_nombre,
                COALESCE(a.observaciones, '') AS observaciones
            FROM infraestructura.aula a
            JOIN infraestructura.edificio e
              ON e.edificio_id = a.edificio_id
            JOIN infraestructura.tipo_aula ta
              ON ta.tipo_id = a.tipo_id
            WHERE TRUE
        """

        filtros = []
        params = []

        if q:
            filtros.append("(a.clave ILIKE %s OR a.observaciones ILIKE %s)")
            like = f"%{q}%"
            params.extend([like, like])

        if edificio:
            filtros.append("e.numero = %s")
            params.append(int(edificio))

        if piso:
            filtros.append("a.piso = %s")
            params.append(int(piso))

        if tipo:
            filtros.append("ta.nombre = %s")
            params.append(tipo)

        if filtros:
            base_sql += " AND " + " AND ".join(filtros)

        base_sql += " ORDER BY e.numero, a.piso, a.clave;"

        cur.execute(base_sql, params)
        aulas = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error al cargar aulas: {e}", "danger")

    return render_template(
        "estudiante/perfil_aulas.html",
        user=user,
        aulas=aulas,
        edificios=edificios,
        tipos_aula=tipos_aula,
        pisos=pisos,
        active_tab="aulas",
    )


# =====================================
# ESTUDIANTE – MÁS PÁGINAS SIMPLES
# =====================================

@app.route("/estudiante/documentos")
@login_required
@role_required("Estudiante")
def est_perfil_documentos():
    return render_template("estudiante/perfil_documentos.html", user=current_user())


@app.route("/estudiante/formularios")
@login_required
@role_required("Estudiante")
def est_perfil_formularios():
    return render_template("estudiante/perfil_formularios.html", user=current_user())


@app.route("/estudiante/administrativo")
@login_required
@role_required("Estudiante")
def est_perfil_administrativo():
    return render_template("estudiante/perfil_administrativo.html", user=current_user())


@app.route("/estudiante/notificaciones")
@login_required
@role_required("Estudiante")
def est_notificaciones_all():
    return render_template("estudiante/notificaciones_all.html", user=current_user())


# =====================================
# FUNCIONES AUX. ESPECÍFICAS DOCENTE
# =====================================

def _get_personal_id(conn, user_id):
    """
    Obtiene rrhh.personal.id_personal a partir de seguridad.usuarios.id_usuario.
    Devuelve None si no hay vínculo.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id_personal
        FROM rrhh.personal p
        WHERE p.fk_id_usuario = %s;
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    return row["id_personal"] if row else None


# =====================================
# DOCENTE – PANEL / PERFIL PRINCIPAL
# =====================================

@app.route("/perfil/docente")
@login_required
@role_required("Docente")
def perfil_docente():
    """
    Panel principal del docente.

    Construye:
      - resumen global (total_materias, total_grupos, total_alumnos)
      - resumen_ciclo: lista de filas {ciclo, materias, grupos, alumnos}
    y los envía a templates/perfiles/profile_docente.html
    """
    user = current_user()

    # Valores por defecto por si algo falla
    resumen = {
        "total_materias": 0,
        "total_grupos": 0,
        "total_alumnos": 0,
    }
    resumen_ciclo = []

    conn = None
    try:
        conn = get_connection()
        personal_id = _get_personal_id(conn, user["id_usuario"])
        if not personal_id:
            raise Exception("No se encontró registro en rrhh.personal para este docente.")

        cur = conn.cursor()

        # --------- Resumen global ----------
        cur.execute("""
            SELECT
                COUNT(DISTINCT m.materia_id)       AS total_materias,
                COUNT(DISTINCT ma.materia_alta_id) AS total_grupos,
                COUNT(DISTINCT ai.fk_alumno)       AS total_alumnos
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m
              ON m.materia_id = cm.materia_id
            LEFT JOIN academico.alumno_inscripcion ai
              ON ai.fk_materia_alta = ma.materia_alta_id
            WHERE ma.fk_personal = %s;
        """, (personal_id,))
        row = cur.fetchone()
        if row:
            resumen["total_materias"] = row["total_materias"] or 0
            resumen["total_grupos"] = row["total_grupos"] or 0
            resumen["total_alumnos"] = row["total_alumnos"] or 0

        # --------- Resumen por ciclo ----------
        cur.execute("""
            SELECT
                ma.ciclo,
                COUNT(DISTINCT m.materia_id)       AS materias,
                COUNT(DISTINCT ma.materia_alta_id) AS grupos,
                COUNT(DISTINCT ai.fk_alumno)       AS alumnos
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m
              ON m.materia_id = cm.materia_id
            LEFT JOIN academico.alumno_inscripcion ai
              ON ai.fk_materia_alta = ma.materia_alta_id
            WHERE ma.fk_personal = %s
            GROUP BY ma.ciclo
            ORDER BY ma.ciclo DESC;
        """, (personal_id,))
        resumen_ciclo = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando resumen del docente: {e}", "warning")

    return render_template(
        "perfiles/profile_docente.html",
        user=user,
        resumen=resumen,
        resumen_ciclo=resumen_ciclo
    )


# =====================================
# DOCENTE – GRUPOS Y MATERIAS
# =====================================

@app.route("/docente/grupos-materias")
@login_required
@role_required("Docente")
def docente_grupos_materias():
    user = current_user()
    grupos = []

    try:
        conn = get_connection()
        personal_id = _get_personal_id(conn, user["id_usuario"])
        if not personal_id:
            raise Exception("No se encontró registro en rrhh.personal para este docente.")

        cur = conn.cursor()
        cur.execute("""
            SELECT
                ma.materia_alta_id,
                ma.ciclo,
                c.clave  AS carrera_clave,
                c.nombre AS carrera_nombre,
                m.clave  AS materia_clave,
                m.nombre AS materia_nombre,
                cm.semestre,
                COUNT(ai.inscripcion_id) AS num_alumnos
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.carrera c
              ON c.carrera_id = cm.carrera_id
            JOIN planes.materia m
              ON m.materia_id = cm.materia_id
            LEFT JOIN academico.alumno_inscripcion ai
              ON ai.fk_materia_alta = ma.materia_alta_id
            WHERE ma.fk_personal = %s
            GROUP BY
                ma.materia_alta_id, ma.ciclo,
                c.clave, c.nombre,
                m.clave, m.nombre,
                cm.semestre
            ORDER BY ma.ciclo, cm.semestre, m.clave;
        """, (personal_id,))
        grupos = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        flash(f"Error cargando grupos del docente: {e}", "danger")

    return render_template(
        "docente/grupos_materias.html",
        user=user,
        grupos=grupos
    )


# =====================================
# DOCENTE – EVALUACIONES
# =====================================

@app.route("/docente/evaluaciones", methods=["GET", "POST"])
@login_required
@role_required("Docente")
def docente_evaluaciones():
    user = current_user()
    calificaciones = []
    materia_alta_id = request.args.get("materia_alta_id")

    try:
        conn = get_connection()
        personal_id = _get_personal_id(conn, user["id_usuario"])
        if not personal_id:
            raise Exception("No se encontró registro de docente.")

        cur = conn.cursor()

        # --- Si POST: actualizar calificación ---
        if request.method == "POST":
            inscripcion_id = request.form.get("inscripcion_id")
            nueva_calif = request.form.get("calificacion")

            try:
                nueva_val = None if nueva_calif == "" else float(nueva_calif)
                cur.execute("""
                    UPDATE academico.alumno_inscripcion ai
                    SET calificacion = %s
                    WHERE ai.inscripcion_id = %s
                      AND ai.fk_materia_alta IN (
                          SELECT ma.materia_alta_id
                          FROM planes.materia_alta ma
                          WHERE ma.fk_personal = %s
                      );
                """, (nueva_val, inscripcion_id, personal_id))
                conn.commit()
                flash("Calificación actualizada.", "success")
            except Exception as e_upd:
                conn.rollback()
                flash(f"Error al actualizar calificación: {e_upd}", "danger")

        # --- Materia seleccionada (o primera del docente) ---
        if not materia_alta_id:
            cur.execute("""
                SELECT ma.materia_alta_id
                FROM planes.materia_alta ma
                WHERE ma.fk_personal = %s
                ORDER BY ma.ciclo, ma.materia_alta_id
                LIMIT 1;
            """, (personal_id,))
            row = cur.fetchone()
            materia_alta_id = row["materia_alta_id"] if row else None

        # --- Lista de calificaciones ---
        if materia_alta_id:
            cur.execute("""
                SELECT
                    ai.inscripcion_id,
                    a.numero_control,
                    TRIM(a.nombre || ' ' || a.apellido_paterno || ' ' ||
                         COALESCE(a.apellido_materno,'')) AS alumno,
                    m.clave  AS materia_clave,
                    m.nombre AS materia_nombre,
                    ai.calificacion
                FROM academico.alumno_inscripcion ai
                JOIN academico.alumnos a
                  ON a.numero_control = ai.fk_alumno
                JOIN planes.materia_alta ma
                  ON ma.materia_alta_id = ai.fk_materia_alta
                JOIN planes.carrera_materia cm
                  ON cm.carrera_materia_id = ma.carrera_materia_id
                JOIN planes.materia m
                  ON m.materia_id = cm.materia_id
                WHERE ai.fk_materia_alta = %s
                  AND ma.fk_personal = %s
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre;
            """, (materia_alta_id, personal_id))
            calificaciones = cur.fetchall()

        # --- Todas las materias del docente para el <select> ---
        cur.execute("""
            SELECT
                ma.materia_alta_id,
                ma.ciclo,
                m.clave || ' - ' || m.nombre AS etiqueta
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m
              ON m.materia_id = cm.materia_id
            WHERE ma.fk_personal = %s
            ORDER BY ma.ciclo, m.clave;
        """, (personal_id,))
        materias_docente = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        flash(f"Error cargando evaluaciones: {e}", "danger")
        materias_docente = []

    return render_template(
        "docente/evaluaciones.html",
        user=user,
        calificaciones=calificaciones,
        materias_docente=materias_docente,
        materia_alta_id=materia_alta_id
    )


# =====================================
# DOCENTE – ASISTENCIAS (VISTA SIMPLE)
# =====================================

@app.route("/docente/asistencias")
@login_required
@role_required("Docente")
def docente_asistencias():
    user = current_user()
    lista = []
    materia_alta_id = request.args.get("materia_alta_id")

    try:
        conn = get_connection()
        personal_id = _get_personal_id(conn, user["id_usuario"])
        if not personal_id:
            raise Exception("No se encontró registro de docente.")

        cur = conn.cursor()

        # Materia por defecto (primera asignada)
        if not materia_alta_id:
            cur.execute("""
                SELECT ma.materia_alta_id
                FROM planes.materia_alta ma
                WHERE ma.fk_personal = %s
                ORDER BY ma.ciclo, ma.materia_alta_id
                LIMIT 1;
            """, (personal_id,))
            row = cur.fetchone()
            materia_alta_id = row["materia_alta_id"] if row else None

        # Lista de alumnos
        if materia_alta_id:
            cur.execute("""
                SELECT
                    a.numero_control,
                    TRIM(a.nombre || ' ' || a.apellido_paterno || ' ' ||
                         COALESCE(a.apellido_materno,'')) AS alumno
                FROM academico.alumno_inscripcion ai
                JOIN academico.alumnos a
                  ON a.numero_control = ai.fk_alumno
                JOIN planes.materia_alta ma
                  ON ma.materia_alta_id = ai.fk_materia_alta
                WHERE ai.fk_materia_alta = %s
                  AND ma.fk_personal = %s
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre;
            """, (materia_alta_id, personal_id))
            lista = cur.fetchall()

        # Materias del docente para el <select>
        cur.execute("""
            SELECT
                ma.materia_alta_id,
                ma.ciclo,
                m.clave || ' - ' || m.nombre AS etiqueta
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m
              ON m.materia_id = cm.materia_id
            WHERE ma.fk_personal = %s
            ORDER BY ma.ciclo, m.clave;
        """, (personal_id,))
        materias_docente = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        flash(f"Error cargando lista de asistencia: {e}", "danger")
        materias_docente = []

    return render_template(
        "docente/asistencias.html",
        user=user,
        lista_alumnos=lista,
        materias_docente=materias_docente,
        materia_alta_id=materia_alta_id
    )


# =====================================
# DOCENTE – COMUNICACIÓN (DEMO, PERO FUNCIONAL)
# =====================================

@app.route("/docente/comunicacion")
@login_required
@role_required("Docente")
def docente_comunicacion():
    """
    De momento es demo, pero ya respeta la estructura
    que espera templates/docente/comunicacion.html.
    """
    user = current_user()

    # En el futuro aquí puedes leer una tabla real de avisos.
    # Por ahora son datos simulados con las claves correctas.
    avisos = [
        {
            "titulo": "Entrega de proyecto final",
            "ciclo": "2025-1",
            "materia_clave": "PROG1",
            "materia_nombre": "Programación I",
            "creado_en": "2025-11-20",
            "mensaje": "Recuerda subir tu proyecto antes del viernes."
        },
        {
            "titulo": "Examen parcial",
            "ciclo": "2025-1",
            "materia_clave": "PROG2",
            "materia_nombre": "Programación II",
            "creado_en": "2025-11-25",
            "mensaje": "El examen será la próxima semana en horario de clase."
        },
    ]

    return render_template(
        "docente/comunicacion.html",
        user=user,
        avisos=avisos
    )


# =====================================
# PERFIL – BIBLIOTECARIO
# =====================================

@app.route("/perfil/bibliotecario")
@login_required
@role_required("Bibliotecario")
def perfil_bibliotecario():
    user = current_user()
    q = request.args.get("q", "").strip()   # texto de búsqueda

    # Estructura base del resumen para la tarjeta superior
    resumen = {
        "total_libros": 0,
        "prestamos_activos": 0,
        "estudiantes_con_prestamo": 0,
        "prestamos_retrasados": 0,
    }
    libros = []
    conn = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # --------------------- RESUMEN DE LA BIBLIOTECA ----------------------
        # 1) Libros en catálogo
        cur.execute("SELECT COUNT(*) AS total FROM biblioteca.libros;")
        resumen["total_libros"] = cur.fetchone()["total"]

        # 2) Préstamos activos
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM biblioteca.prestamos
            WHERE estado = 'Activo';
        """)
        resumen["prestamos_activos"] = cur.fetchone()["total"]

        # 3) Estudiantes con préstamo (distintos)
        cur.execute("""
            SELECT COUNT(DISTINCT fk_alumno) AS total
            FROM biblioteca.prestamos
            WHERE estado = 'Activo' AND fk_alumno IS NOT NULL;
        """)
        resumen["estudiantes_con_prestamo"] = cur.fetchone()["total"]

        # 4) Préstamos retrasados
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM biblioteca.prestamos
            WHERE estado = 'Vencido'
               OR (estado = 'Activo' AND fecha_devolucion_estimada < NOW());
        """)
        resumen["prestamos_retrasados"] = cur.fetchone()["total"]

        # --------------------- LISTA / BÚSQUEDA DE LIBROS --------------------
        if q:
            patron = f"%{q}%"
            cur.execute("""
                SELECT
                    l.id_libro,
                    l.titulo_libro,
                    c.codigo_clasificacion,
                    e.nombre_editorial,
                    l.anio_edicion,
                    l.isbn,
                    COALESCE(inv.cantidad, 0)            AS cantidad,
                    COALESCE(inv.cantidad_disponible, 0) AS cantidad_disponible
                FROM biblioteca.libros l
                LEFT JOIN biblioteca.clasificaciones c
                       ON c.id_clasificacion = l.id_clasificacion
                LEFT JOIN biblioteca.editoriales e
                       ON e.id_editorial = l.id_editorial
                LEFT JOIN biblioteca.inventario inv
                       ON inv.id_libro = l.id_libro
                WHERE l.titulo_libro ILIKE %s
                   OR e.nombre_editorial ILIKE %s
                   OR c.codigo_clasificacion ILIKE %s
                ORDER BY l.titulo_libro;
            """, (patron, patron, patron))
        else:
            # Sin búsqueda: mostrar todo el catálogo
            cur.execute("""
                SELECT
                    l.id_libro,
                    l.titulo_libro,
                    c.codigo_clasificacion,
                    e.nombre_editorial,
                    l.anio_edicion,
                    l.isbn,
                    COALESCE(inv.cantidad, 0)            AS cantidad,
                    COALESCE(inv.cantidad_disponible, 0) AS cantidad_disponible
                FROM biblioteca.libros l
                LEFT JOIN biblioteca.clasificaciones c
                       ON c.id_clasificacion = l.id_clasificacion
                LEFT JOIN biblioteca.editoriales e
                       ON e.id_editorial = l.id_editorial
                LEFT JOIN biblioteca.inventario inv
                       ON inv.id_libro = l.id_libro
                ORDER BY l.titulo_libro;
            """)

        libros = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando panel del bibliotecario: {e}", "danger")

    return render_template(
        "perfiles/profile_bibliotecario.html",
        user=user,
        resumen=resumen,   # si en tu template usas otro nombre, cámbialo aquí
        libros=libros,
        q=q
    )


# =====================================
# BIBLIOTECARIO – CATÁLOGO
# =====================================

@app.route("/biblioteca/catalogo")
@login_required
@role_required("Bibliotecario")
def bib_catalogo():
    user = current_user()
    libros = []

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                l.id_libro,
                l.titulo_libro,
                c.codigo_clasificacion,
                e.nombre_editorial,
                l.anio_edicion,
                l.isbn,
                COALESCE(inv.cantidad, 0)            AS cantidad,
                COALESCE(inv.cantidad_disponible, 0) AS cantidad_disponible
            FROM biblioteca.libros l
            LEFT JOIN biblioteca.clasificaciones c ON c.id_clasificacion = l.id_clasificacion
            LEFT JOIN biblioteca.editoriales     e ON e.id_editorial     = l.id_editorial
            LEFT JOIN biblioteca.inventario     inv ON inv.id_libro      = l.id_libro
            ORDER BY l.titulo_libro;
        """)
        libros = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando catálogo de libros: {e}", "danger")

    return render_template(
        "biblioteca/catalogo.html",
        user=user,
        libros=libros
    )


# =====================================
# BIBLIOTECARIO – PRÉSTAMOS
# =====================================

@app.route("/biblioteca/prestamos", methods=["GET", "POST"])
@login_required
@role_required("Bibliotecario")
def bib_prestamos():
    user = current_user()
    prestamos = []

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Si viene POST, marcar un préstamo como devuelto
        if request.method == "POST":
            prestamo_id = request.form.get("id_prestamo")
            try:
                cur.execute("""
                    UPDATE biblioteca.prestamos
                    SET estado = 'Devuelto',
                        fecha_devolucion_real = NOW()
                    WHERE id_prestamo = %s
                      AND estado = 'Activo';
                """, (prestamo_id,))
                conn.commit()
                flash("Préstamo marcado como devuelto.", "success")
            except Exception as e_upd:
                conn.rollback()
                flash(f"Error al marcar devolución: {e_upd}", "danger")

        # Listar préstamos activos
        cur.execute("""
            SELECT
                p.id_prestamo,
                l.titulo_libro,
                p.fk_alumno,
                p.fk_personal,
                p.fecha_prestamo,
                p.fecha_devolucion_estimada,
                p.estado
            FROM biblioteca.prestamos p
            JOIN biblioteca.libros l ON l.id_libro = p.id_libro
            WHERE p.estado = 'Activo'
            ORDER BY p.fecha_prestamo DESC;
        """)
        prestamos = cur.fetchall()

        cur.close()
        conn.close()
    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando préstamos: {e}", "danger")

    return render_template(
        "biblioteca/prestamos.html",
        user=user,
        prestamos=prestamos
    )


# =====================================
# BIBLIOTECARIO – HISTORIAL
# =====================================

@app.route("/biblioteca/historial")
@login_required
@role_required("Bibliotecario")
def bib_historial():
    user = current_user()
    historial = []

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                p.id_prestamo,
                l.titulo_libro,
                p.fk_alumno,
                p.fk_personal,
                p.fecha_prestamo,
                p.fecha_devolucion_real,
                p.estado
            FROM biblioteca.prestamos p
            JOIN biblioteca.libros l ON l.id_libro = p.id_libro
            WHERE p.estado IN ('Devuelto', 'Vencido')
            ORDER BY p.fecha_prestamo DESC;
        """)
        historial = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando historial de préstamos: {e}", "danger")

    return render_template(
        "biblioteca/historial.html",
        user=user,
        historial=historial
    )


# =====================================
# BIBLIOTECARIO – NOTIFICACIONES (DEMO)
# =====================================

@app.route("/biblioteca/notificaciones")
@login_required
@role_required("Bibliotecario")
def bib_notificaciones():
    user = current_user()
    # Por ahora solo demo estático; luego se puede ligar a una tabla
    notificaciones = [
        {"destinatario": "2501E0001", "mensaje": "Tu préstamo está por vencer."},
        {"destinatario": "2501E0002", "mensaje": "Por favor devuelve el libro pendiente."},
    ]
    return render_template(
        "biblioteca/notificaciones.html",
        user=user,
        notificaciones=notificaciones
    )

# =====================================
# BIBLIOTECARIO – DETALLE DE LIBRO
# =====================================

@app.route("/biblioteca/libro/<int:id_libro>")
@login_required
@role_required("Bibliotecario")
def biblioteca_libro_detalle(id_libro):
    """
    Muestra el detalle de un libro del catálogo (solo para bibliotecario).
    """
    user = current_user()
    conn = None
    libro = None
    historial_prestamos = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Datos principales del libro + inventario
        cur.execute("""
            SELECT
                l.id_libro,
                l.titulo_libro,
                c.codigo_clasificacion,
                c.descripcion        AS clasificacion_descripcion,
                e.nombre_editorial,
                l.edicion,
                l.anio_edicion,
                l.isbn,
                l.fuente_recurso,
                l.incluye_cd,
                COALESCE(inv.cantidad, 0)            AS cantidad,
                COALESCE(inv.cantidad_disponible, 0) AS cantidad_disponible
            FROM biblioteca.libros l
            LEFT JOIN biblioteca.clasificaciones c
                   ON c.id_clasificacion = l.id_clasificacion
            LEFT JOIN biblioteca.editoriales e
                   ON e.id_editorial = l.id_editorial
            LEFT JOIN biblioteca.inventario inv
                   ON inv.id_libro = l.id_libro
            WHERE l.id_libro = %s;
        """, (id_libro,))
        libro = cur.fetchone()

        # Si no existe el libro, 404
        if not libro:
            cur.close()
            conn.close()
            abort(404)

        # Historial reciente de préstamos de ese libro (opcional)
        cur.execute("""
            SELECT
                p.id_prestamo,
                p.fk_alumno,
                p.fk_personal,
                p.fecha_prestamo,
                p.fecha_devolucion_estimada,
                p.fecha_devolucion_real,
                p.estado
            FROM biblioteca.prestamos p
            WHERE p.id_libro = %s
            ORDER BY p.fecha_prestamo DESC
            LIMIT 20;
        """, (id_libro,))
        historial_prestamos = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando detalle del libro: {e}", "danger")

    return render_template(
        "biblioteca/libro_detalle.html",
        user=user,
        libro=libro,
        historial_prestamos=historial_prestamos
    )


# =====================================
# ADMIN – LISTA DE USUARIOS (con modos)
# =====================================

@app.route("/admin/usuarios")
@login_required
@role_required("Administrador")
def admin_usuarios_list():
    user = current_user()
    modo = request.args.get("modo", "todos")  # todos, edit, baja, block, reset, buscar
    q = request.args.get("q", "").strip()

    usuarios = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        base_sql = """
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                u.activo,
                COALESCE(
                    ARRAY_AGG(r.nombre_rol ORDER BY r.nombre_rol)
                    FILTER (WHERE r.nombre_rol IS NOT NULL),
                    '{}'
                ) AS roles
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            WHERE 1=1
        """

        params = []
        if q:
            base_sql += """
                AND (
                    u.nombre_usuario ILIKE %s
                    OR u.correo_electronico ILIKE %s
                    OR EXISTS (
                        SELECT 1
                        FROM seguridad.usuario_rol ur2
                        JOIN seguridad.roles r2 ON r2.id_rol = ur2.id_rol
                        WHERE ur2.id_usuario = u.id_usuario
                          AND r2.nombre_rol ILIKE %s
                    )
                )
            """
            like_q = f"%{q}%"
            params.extend([like_q, like_q, like_q])

        base_sql += """
            GROUP BY u.id_usuario, u.nombre_usuario, u.correo_electronico, u.activo
            ORDER BY u.id_usuario;
        """

        cur.execute(base_sql, params)
        usuarios = cur.fetchall()

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando usuarios: {e}", "danger")

    return render_template(
        "admin/usuarios_list.html",
        user=user,
        usuarios=usuarios,
        modo=modo,
        q=q
    )


# =====================================
# ADMIN – CREAR NUEVO USUARIO (ALTA)
# =====================================

@app.route("/admin/usuarios/nuevo", methods=["GET", "POST"])
@login_required
@role_required("Administrador")
def admin_usuario_nuevo():
    user = current_user()
    roles = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Roles disponibles
        cur.execute("SELECT id_rol, nombre_rol FROM seguridad.roles ORDER BY nombre_rol;")
        roles = cur.fetchall()

        if request.method == "POST":
            nombre_usuario = request.form.get("nombre_usuario", "").strip()
            correo = request.form.get("correo_electronico", "").strip()
            contrasena = request.form.get("contrasena", "").strip()
            id_rol = request.form.get("id_rol")

            if not nombre_usuario or not correo or not contrasena or not id_rol:
                flash("Todos los campos son obligatorios.", "danger")
            else:
                try:
                    # Crear usuario (el trigger se encarga de hashear la contraseña)
                    cur.execute(
                        """
                        INSERT INTO seguridad.usuarios(nombre_usuario, correo_electronico, contrasena_hash)
                        VALUES (%s, %s, %s)
                        RETURNING id_usuario;
                        """,
                        (nombre_usuario, correo, contrasena),
                    )
                    nuevo_id_row = cur.fetchone()
                    nuevo_id = nuevo_id_row["id_usuario"] if nuevo_id_row else None

                    # Asignar rol
                    if nuevo_id is not None:
                        cur.execute(
                            """
                            INSERT INTO seguridad.usuario_rol(id_usuario, id_rol)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                            """,
                            (nuevo_id, id_rol),
                        )

                    conn.commit()
                    flash("Usuario creado correctamente.", "success")
                    return redirect(url_for("admin_usuarios_list", modo="edit"))
                except Exception as e_ins:
                    conn.rollback()
                    flash(f"Error al crear usuario: {e_ins}", "danger")

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando formulario de usuario: {e}", "danger")

    return render_template(
        "admin/usuario_form.html",
        user=user,
        roles=roles,
        modo="nuevo",
        usuario=None
    )


# =====================================
# ADMIN – EDITAR USUARIO
# =====================================

@app.route("/admin/usuarios/<int:id_usuario>/editar", methods=["GET", "POST"])
@login_required
@role_required("Administrador")
def admin_usuario_editar(id_usuario):
    user = current_user()
    roles = []
    usuario = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Usuario + roles actuales
        cur.execute(
            """
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                u.activo,
                COALESCE(
                    ARRAY_AGG(r.id_rol)
                    FILTER (WHERE r.id_rol IS NOT NULL),
                    '{}'
                ) AS roles_ids
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            WHERE u.id_usuario = %s
            GROUP BY u.id_usuario;
            """,
            (id_usuario,),
        )
        usuario = cur.fetchone()
        if not usuario:
            cur.close()
            conn.close()
            abort(404)

        # Roles disponibles
        cur.execute("SELECT id_rol, nombre_rol FROM seguridad.roles ORDER BY nombre_rol;")
        roles = cur.fetchall()

        if request.method == "POST":
            correo = request.form.get("correo_electronico", "").strip()
            activo = request.form.get("activo") == "on"
            nuevos_roles = request.form.getlist("roles")  # lista de id_rol (str)

            try:
                # Actualizar usuario
                cur.execute(
                    """
                    UPDATE seguridad.usuarios
                    SET correo_electronico = %s,
                        activo = %s
                    WHERE id_usuario = %s;
                    """,
                    (correo, activo, id_usuario),
                )

                # Limpiar roles previos
                cur.execute(
                    "DELETE FROM seguridad.usuario_rol WHERE id_usuario = %s;",
                    (id_usuario,),
                )

                # Insertar nuevos roles
                for rid in nuevos_roles:
                    cur.execute(
                        """
                        INSERT INTO seguridad.usuario_rol(id_usuario, id_rol)
                        VALUES (%s, %s);
                        """,
                        (id_usuario, int(rid)),
                    )

                conn.commit()
                flash("Usuario actualizado.", "success")
                return redirect(url_for("admin_usuarios_list", modo="edit"))

            except Exception as e_upd:
                conn.rollback()
                flash(f"Error al actualizar usuario: {e_upd}", "danger")

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error al cargar usuario: {e}", "danger")

    return render_template(
        "admin/usuario_form.html",
        user=user,
        roles=roles,
        usuario=usuario,
        modo="editar"
    )


# =====================================
# ADMIN – BAJA (eliminar usuario)
# =====================================

@app.route("/admin/usuarios/<int:id_usuario>/baja", methods=["POST"])
@login_required
@role_required("Administrador")
def admin_usuario_baja(id_usuario):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Primero borrar sus roles
        cur.execute(
            "DELETE FROM seguridad.usuario_rol WHERE id_usuario = %s;",
            (id_usuario,),
        )
        # Luego borrar usuario
        cur.execute(
            "DELETE FROM seguridad.usuarios WHERE id_usuario = %s;",
            (id_usuario,),
        )

        conn.commit()
        cur.close()
        conn.close()
        flash("Usuario dado de baja (eliminado).", "info")
    except Exception as e:
        flash(f"Error al dar de baja al usuario: {e}", "danger")

    return redirect(url_for("admin_usuarios_list", modo="baja"))


# =====================================
# ADMIN – BLOCK / UNBLOCK
# =====================================

@app.route("/admin/usuarios/<int:id_usuario>/block", methods=["POST"])
@login_required
@role_required("Administrador")
def admin_usuario_block(id_usuario):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Alternar activo
        cur.execute(
            """
            UPDATE seguridad.usuarios
            SET activo = NOT activo
            WHERE id_usuario = %s
            RETURNING activo;
            """,
            (id_usuario,),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if row and row["activo"]:
            flash("Usuario desbloqueado.", "success")
        else:
            flash("Usuario bloqueado.", "warning")

    except Exception as e:
        flash(f"Error al bloquear/desbloquear usuario: {e}", "danger")

    return redirect(url_for("admin_usuarios_list", modo="block"))


# =====================================
# ADMIN – RESET PASSWORD
# =====================================

@app.route("/admin/usuarios/<int:id_usuario>/reset", methods=["POST"])
@login_required
@role_required("Administrador")
def admin_usuario_reset(id_usuario):
    try:
        conn = get_connection()
        cur = conn.cursor()
        nueva_pwd = generate_random_password(10)

        # Actualizar contrasena_hash (trigger hará el hash)
        cur.execute(
            """
            UPDATE seguridad.usuarios
            SET contrasena_hash = %s
            WHERE id_usuario = %s
            RETURNING correo_electronico;
            """,
            (nueva_pwd, id_usuario),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        correo = row["correo_electronico"] if row else None
        if correo:
            send_email(
                correo,
                "Restablecimiento de contraseña",
                f"Tu nueva contraseña temporal es: {nueva_pwd}",
            )

        flash(
            "Contraseña restablecida y enviada por correo (si SMTP está configurado).",
            "success",
        )
    except Exception as e:
        flash(f"Error al restablecer contraseña: {e}", "danger")

    return redirect(url_for("admin_usuarios_list", modo="reset"))


# =====================================
# ADMIN – PARÁMETROS GLOBALES
# =====================================

@app.route("/admin/parametros-globales", methods=["GET", "POST"])
@login_required
@role_required("Administrador")
def admin_parametros_globales():
    user = current_user()

    # Valores por defecto
    creditos_maximos = {
        "normal": 24,
        "sobrecarga": 32,
        "max_reprobadas": 3,
    }
    periodos = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Si viene POST, guardamos límites de créditos en academico.parametros_globales
        if request.method == "POST":
            try:
                normal = int(request.form.get("creditos_normales", "24"))
                sobrecarga = int(request.form.get("creditos_sobrecarga", "32"))
                max_rep = int(request.form.get("max_reprobadas", "3"))

                # No vamos a dejar que pongan cosas absurdas
                if normal <= 0 or sobrecarga <= 0 or max_rep < 0:
                    raise ValueError("Valores inválidos de créditos.")

                data = [
                    ("creditos_normales", str(normal)),
                    ("creditos_sobrecarga", str(sobrecarga)),
                    ("max_materias_reprobadas", str(max_rep)),
                ]

                for clave, valor in data:
                    cur.execute(
                        """
                        INSERT INTO academico.parametros_globales (clave, valor_texto, descripcion, categoria)
                        VALUES (%s, %s, %s, 'inscripciones')
                        ON CONFLICT (clave) DO UPDATE
                          SET valor_texto = EXCLUDED.valor_texto,
                              descripcion = EXCLUDED.descripcion,
                              categoria   = EXCLUDED.categoria;
                        """,
                        (
                            clave,
                            valor,
                            "Parámetro actualizado desde panel de administrador",
                        ),
                    )

                conn.commit()
                flash("Límites de créditos actualizados.", "success")
            except Exception as e_upd:
                conn.rollback()
                flash(f"Error al guardar límites de créditos: {e_upd}", "danger")

        # Cargar periodos desde planes.materia_alta
        cur.execute(
            """
            SELECT
                ma.ciclo,
                COUNT(*) AS grupos,
                MIN(cm.semestre) AS min_semestre,
                MAX(cm.semestre) AS max_semestre
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            GROUP BY ma.ciclo
            ORDER BY ma.ciclo DESC;
            """
        )
        periodos = cur.fetchall()

        # Leer valores de créditos desde academico.parametros_globales (si existen)
        cur.execute(
            """
            SELECT clave, valor_texto
            FROM academico.parametros_globales
            WHERE clave IN ('creditos_normales', 'creditos_sobrecarga', 'max_materias_reprobadas');
            """
        )
        rows = cur.fetchall()
        for row in rows:
            if row["clave"] == "creditos_normales":
                creditos_maximos["normal"] = int(row["valor_texto"])
            elif row["clave"] == "creditos_sobrecarga":
                creditos_maximos["sobrecarga"] = int(row["valor_texto"])
            elif row["clave"] == "max_materias_reprobadas":
                creditos_maximos["max_reprobadas"] = int(row["valor_texto"])

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando parámetros globales: {e}", "danger")

    return render_template(
        "admin/parametros_globales.html",
        user=user,
        periodos=periodos,
        creditos_maximos=creditos_maximos,
    )


# =====================================
# ADMIN – CATÁLOGOS ACADÉMICOS (con CRUD simple sobre carrera_materia)
# =====================================

@app.route("/admin/catalogos-academicos", methods=["GET", "POST"])
@login_required
@role_required("Administrador")
def admin_catalogos():
    user = current_user()
    accion = request.args.get("accion", "ver")  # ver | agregar | editar
    carreras = []
    materias = []
    carreras_materias = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # POST: alta / edición / baja de relación carrera-materia
        if request.method == "POST":
            form_accion = request.form.get("form_accion")

            try:
                if form_accion == "guardar_relacion":
                    carrera_id = int(request.form.get("carrera_id"))
                    materia_id = int(request.form.get("materia_id"))
                    semestre = int(request.form.get("semestre"))

                    if semestre < 1 or semestre > 12:
                        raise ValueError("El semestre debe estar entre 1 y 12.")

                    # Alta o actualización (CRUD básico sobre carrera_materia)
                    cur.execute(
                        """
                        INSERT INTO planes.carrera_materia
                            (carrera_id, materia_id, semestre, horas_teoricas, horas_practicas)
                        VALUES (%s, %s, %s, 2, 2)
                        ON CONFLICT (carrera_id, materia_id)
                        DO UPDATE SET semestre = EXCLUDED.semestre;
                        """,
                        (carrera_id, materia_id, semestre),
                    )
                    conn.commit()
                    flash("Relación carrera–materia guardada correctamente.", "success")

                elif form_accion == "eliminar_relacion":
                    cm_id = int(request.form.get("carrera_materia_id"))
                    cur.execute(
                        "DELETE FROM planes.carrera_materia WHERE carrera_materia_id = %s;",
                        (cm_id,),
                    )
                    conn.commit()
                    flash("Relación carrera–materia eliminada.", "info")

            except Exception as crud_err:
                conn.rollback()
                flash(f"Error en la operación de catálogos: {crud_err}", "danger")

            # PRG: redirigimos para evitar reenvío de formulario
            return redirect(url_for("admin_catalogos", accion=accion))

        # GET: cargar listados
        # Carreras
        cur.execute(
            """
            SELECT carrera_id, clave, nombre
            FROM planes.carrera
            ORDER BY clave;
            """
        )
        carreras = cur.fetchall()

        # Materias
        cur.execute(
            """
            SELECT materia_id, clave, nombre
            FROM planes.materia
            ORDER BY clave;
            """
        )
        materias = cur.fetchall()

        # Relación carrera-materia (plan de estudios)
        cur.execute(
            """
            SELECT
                cm.carrera_materia_id,
                c.clave AS carrera_clave,
                c.nombre AS carrera_nombre,
                m.clave AS materia_clave,
                m.nombre AS materia_nombre,
                cm.semestre
            FROM planes.carrera_materia cm
            JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
            JOIN planes.materia m ON m.materia_id = cm.materia_id
            ORDER BY c.clave, cm.semestre, m.clave;
            """
        )
        carreras_materias = cur.fetchall()

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando catálogos académicos: {e}", "danger")

    return render_template(
        "admin/catalogos_academicos.html",
        user=user,
        accion=accion,
        carreras=carreras,
        materias=materias,
        carreras_materias=carreras_materias,
    )


# =====================================
# ADMIN – FORMULARIOS Y ACADÉMICO
# =====================================

@app.route("/admin/formularios-academico")
@login_required
@role_required("Administrador")
def admin_formularios():
    user = current_user()
    formularios = []

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id_formulario, nombre, tipo, version, descripcion
            FROM academico.formularios_institucionales
            ORDER BY id_formulario;
        """)
        formularios = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando formularios institucionales: {e}", "danger")

    return render_template(
        "admin/formularios_academico.html",
        user=user,
        formularios=formularios
    )


# =====================================
# ADMIN – FORMULARIOS: CREAR NUEVO Y ENVIAR AL DISEÑADOR
# =====================================

@app.route("/admin/formularios-academico/nuevo", methods=["POST"])
@login_required
@role_required("Administrador")
def admin_formulario_nuevo():
    user = current_user()  # por si lo quieres usar en logs
    conn = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Valores por defecto del borrador
        cur.execute("""
            INSERT INTO academico.formularios_institucionales
                (nombre, tipo, version, descripcion)
            VALUES
                (%s, %s, %s, %s)
            RETURNING id_formulario;
        """, (
            "Nuevo formulario (borrador)",
            "Alumno",
            1.0,
            "Borrador creado desde el panel de administración."
        ))

        row = cur.fetchone()
        nuevo_id = row["id_formulario"]

        conn.commit()
        cur.close()
        conn.close()

        flash("Se creó un nuevo formulario en estado borrador.", "success")
        return redirect(url_for("admin_formulario_disenar",
                                id_formulario=nuevo_id))

    except Exception as e:
        if conn:
            conn.rollback()
        flash(f"Error al crear nuevo formulario: {e}", "danger")
        return redirect(url_for("admin_formularios"))


# =====================================
# ADMIN – FORMULARIOS: DISEÑAR / EDITAR METADATOS
# =====================================

@app.route("/admin/formularios-academico/<int:id_formulario>/disenar",
           methods=["GET", "POST"])
@login_required
@role_required("Administrador")
def admin_formulario_disenar(id_formulario):
    user = current_user()
    conn = None
    formulario = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        if request.method == "POST":
            nombre = request.form.get("nombre", "").strip()
            tipo = request.form.get("tipo", "").strip()
            version = request.form.get("version", "").strip()
            descripcion = request.form.get("descripcion", "").strip()

            # Versión segura a float
            try:
                version_val = float(version)
            except ValueError:
                version_val = 1.0

            cur.execute("""
                UPDATE academico.formularios_institucionales
                SET nombre = %s,
                    tipo = %s,
                    version = %s,
                    descripcion = %s
                WHERE id_formulario = %s;
            """, (nombre, tipo, version_val, descripcion, id_formulario))

            conn.commit()
            flash("Cambios del formulario guardados correctamente.", "success")

        # Cargar datos actualizados
        cur.execute("""
            SELECT id_formulario, nombre, tipo, version, descripcion
            FROM academico.formularios_institucionales
            WHERE id_formulario = %s;
        """, (id_formulario,))
        formulario = cur.fetchone()

        if not formulario:
            cur.close()
            conn.close()
            abort(404)

        cur.close()
        conn.close()

    except Exception as e:
        if conn:
            conn.rollback()
        flash(f"Error al cargar/guardar formulario: {e}", "danger")

    return render_template(
        "admin/formulario_disenar.html",
        user=user,
        formulario=formulario
    )


# =====================================
# ADMIN – FORMULARIOS: ELIMINAR
# =====================================

@app.route("/admin/formularios-academico/<int:id_formulario>/eliminar",
           methods=["POST"])
@login_required
@role_required("Administrador")
def admin_formulario_eliminar(id_formulario):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM academico.formularios_institucionales
            WHERE id_formulario = %s;
        """, (id_formulario,))
        conn.commit()
        cur.close()
        conn.close()
        flash("Formulario eliminado correctamente.", "info")
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f"Error al eliminar formulario: {e}", "danger")

    return redirect(url_for("admin_formularios"))


# =====================================
# ADMIN – DATOS Y SEGURIDAD
# =====================================

@app.route("/admin/datos-seguridad")
@login_required
@role_required("Administrador")
def admin_datos_seguridad():
    user = current_user()
    resumen = []
    usuarios = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Resumen por rol y estado (activo/bloqueado)
        cur.execute(
            """
            SELECT
                COALESCE(r.nombre_rol, 'Sin rol') AS rol,
                CASE WHEN u.activo THEN 'Activo' ELSE 'Bloqueado' END AS estado,
                COUNT(*) AS total
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            GROUP BY rol, estado
            ORDER BY rol, estado;
            """
        )
        resumen = cur.fetchall()

        # Lista de usuarios (solo lectura)
        cur.execute(
            """
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                u.activo,
                COALESCE(
                    STRING_AGG(DISTINCT r.nombre_rol, ', ' ORDER BY r.nombre_rol),
                    'Sin rol'
                ) AS roles
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            GROUP BY u.id_usuario, u.nombre_usuario, u.correo_electronico, u.activo
            ORDER BY u.id_usuario;
            """
        )
        usuarios = cur.fetchall()

        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando datos y seguridad: {e}", "danger")

    return render_template(
        "admin/datos_seguridad.html",
        user=user,
        resumen=resumen,      # lista de tuplas (rol, estado, total)
        usuarios=usuarios     # lista de tuplas (id, nombre, correo, activo, roles)
    )


# =====================================
# ADMIN – CONSOLA DE EVENTOS
# =====================================

@app.route("/admin/eventos")
@login_required
@role_required("Administrador")
def admin_eventos():
    user = current_user()
    eventos = []

    try:
        conn = get_connection()
        cur = conn.cursor()
        # Usamos seguridad.intentos_login como "eventos" (demo)
        cur.execute(
            """
            SELECT
                il.id_intento,
                il.intentado_en,
                il.identificador,
                il.direccion_ip,
                il.agente_usuario,
                il.exitoso,
                u.nombre_usuario
            FROM seguridad.intentos_login il
            LEFT JOIN seguridad.usuarios u
              ON u.id_usuario = il.id_usuario
            ORDER BY il.intentado_en DESC
            LIMIT 50;
            """
        )
        eventos = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(
            f"Error cargando consola de eventos (intentos de login): {e}",
            "danger",
        )

    return render_template(
        "admin/eventos.html",
        user=user,
        eventos=eventos,
    )




# =====================================
# ESTADOS DE PRUEBA
# =====================================

@app.route("/estado/error")
def estado_error_demo():
    return render_template("components/error_state.html")


@app.route("/estado/cargando")
def estado_loading_demo():
    return render_template("components/loading_state.html")


@app.route("/estado/recargar")
def estado_reload_demo():
    return render_template("components/reload_state.html")

# =====================================
# PERFIL – COORDINADOR
# =====================================

@app.route("/perfil/coordinador")
@login_required
@role_required("Coordinador")
def perfil_coordinador():
    """
    Panel principal del coordinador.

    Muestra:
      - Resumen académico (carreras, materias, docentes, alumnos) por ciclo.
      - Tabla de grupos/materias usando planes.vw_materia_alta_detalle.

    Además calcula un ciclo_actual:
      1) academico.parametros_globales (clave='ciclo_activo')
      2) en su defecto, el último ciclo existente en planes.materia_alta
      3) y si no hay datos, '2025-1' como fallback.
    """
    user = current_user()
    conn = None

    resumen = {
        "carreras_activas": 0,
        "materias_en_plan": 0,
        "docentes": 0,
        "alumnos": 0,
    }
    materias = []
    ciclo_actual = None
    primer_grupo_id = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        # ------------------ CICLO ACTUAL ------------------
        cur.execute("""
            SELECT valor_texto
            FROM academico.parametros_globales
            WHERE clave = 'ciclo_activo';
        """)
        row = cur.fetchone()
        if row and row["valor_texto"]:
            ciclo_actual = row["valor_texto"]

        # Si no hay parámetro, tomamos el último ciclo que exista en materia_alta
        if not ciclo_actual:
            cur.execute("""
                SELECT DISTINCT ciclo
                FROM planes.materia_alta
                ORDER BY ciclo DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            if row:
                ciclo_actual = row["ciclo"]

        # Fallback duro si la tabla está vacía
        if not ciclo_actual:
            ciclo_actual = "2025-1"

        # ------------------ RESUMEN ACADÉMICO ------------------
        # Carreras, materias y docentes desde la vista de detalle
        cur.execute("""
            SELECT
                COUNT(DISTINCT carrera_clave) AS carreras_activas,
                COUNT(DISTINCT materia_clave) AS materias_en_plan,
                COUNT(
                    DISTINCT COALESCE(profesor_nombre, '') || ' ' ||
                             COALESCE(profesor_ap, '')
                ) AS docentes
            FROM planes.vw_materia_alta_detalle
            WHERE ciclo = %s
              AND esta_activo = TRUE;
        """, (ciclo_actual,))
        row = cur.fetchone()
        if row:
            resumen["carreras_activas"] = row["carreras_activas"] or 0
            resumen["materias_en_plan"] = row["materias_en_plan"] or 0
            resumen["docentes"] = row["docentes"] or 0

        # Alumnos distintos con inscripción en ese ciclo
        cur.execute("""
            SELECT COUNT(DISTINCT ai.fk_alumno) AS alumnos
            FROM academico.alumno_inscripcion ai
            JOIN planes.materia_alta ma
              ON ma.materia_alta_id = ai.fk_materia_alta
            WHERE ma.ciclo = %s;
        """, (ciclo_actual,))
        row = cur.fetchone()
        if row:
            resumen["alumnos"] = row["alumnos"] or 0

        # ------------------ TABLA GRUPOS Y MATERIAS ------------------
        cur.execute("""
            SELECT
              materia_alta_id,
              carrera_clave,
              carrera_nombre,
              materia_clave,
              materia_nombre,
              semestre,
              COALESCE(profesor_nombre || ' ' || profesor_ap, 'Sin asignar') AS docente,
              esta_activo
            FROM planes.vw_materia_alta_detalle
            WHERE ciclo = %s
            ORDER BY semestre, materia_clave;
        """, (ciclo_actual,))
        materias = cur.fetchall()
        if materias:
            primer_grupo_id = materias[0]["materia_alta_id"]

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando panel del coordinador: {e}", "danger")

    return render_template(
        "perfiles/profile_coordinador.html",
        user=user,
        resumen=resumen,
        ciclo_actual=ciclo_actual,
        materias=materias,
        primer_grupo_id=primer_grupo_id,
    )


# =====================================
# COORDINADOR – ASIGNACIÓN DE ESPACIOS
# (vista sencilla de horarios/aulas por ciclo)
# =====================================

@app.route("/coordinador/asignacion-espacios")
@login_required
@role_required("Coordinador")
def coord_asignacion_espacios():
    user = current_user()
    conn = None
    ciclo_actual = None
    asignaciones = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Reutilizamos la lógica de ciclo_actual
        cur.execute("""
            SELECT valor_texto
            FROM academico.parametros_globales
            WHERE clave = 'ciclo_activo';
        """)
        row = cur.fetchone()
        if row and row["valor_texto"]:
            ciclo_actual = row["valor_texto"]
        else:
            cur.execute("""
                SELECT DISTINCT ciclo
                FROM planes.materia_alta
                ORDER BY ciclo DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            ciclo_actual = row["ciclo"] if row else "2025-1"

        cur.execute("""
            SELECT
                ha.horario_id,
                ma.ciclo,
                m.clave  AS materia_clave,
                m.nombre AS materia_nombre,
                ha.dia_semana,
                ha.hora_inicio,
                ha.hora_fin,
                au.clave AS aula_clave,
                ed.numero AS edificio_numero
            FROM infraestructura.horario_asignacion ha
            JOIN planes.materia_alta ma
              ON ma.materia_alta_id = ha.fk_materia_alta
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m
              ON m.materia_id = cm.materia_id
            JOIN infraestructura.aula au
              ON au.aula_id = ha.fk_aula
            JOIN infraestructura.edificio ed
              ON ed.edificio_id = au.edificio_id
            WHERE ma.ciclo = %s
            ORDER BY ha.dia_semana, ha.hora_inicio, m.clave;
        """, (ciclo_actual,))
        asignaciones = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando asignación de espacios: {e}", "danger")

    return render_template(
        "coordinador/asignacion_espacios.html",
        user=user,
        ciclo_actual=ciclo_actual,
        asignaciones=asignaciones,
    )


# =====================================
# COORDINADOR – REPORTES ACADÉMICOS
# (resumen simple por carrera/materia)
# =====================================

@app.route("/coordinador/reportes")
@login_required
@role_required("Coordinador")
def coord_reportes_academicos():
    user = current_user()
    conn = None
    ciclo_actual = None
    resumen_carrera = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # ciclo_actual
        cur.execute("""
            SELECT valor_texto
            FROM academico.parametros_globales
            WHERE clave = 'ciclo_activo';
        """)
        row = cur.fetchone()
        if row and row["valor_texto"]:
            ciclo_actual = row["valor_texto"]
        else:
            cur.execute("""
                SELECT DISTINCT ciclo
                FROM planes.materia_alta
                ORDER BY ciclo DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            ciclo_actual = row["ciclo"] if row else "2025-1"

        # Resumen por carrera
        cur.execute("""
            SELECT
              v.carrera_clave,
              v.carrera_nombre,
              COUNT(DISTINCT v.materia_clave)      AS materias,
              COUNT(DISTINCT v.materia_alta_id)    AS grupos,
              COUNT(DISTINCT v.profesor_nombre || ' ' || v.profesor_ap) AS docentes
            FROM planes.vw_materia_alta_detalle v
            WHERE v.ciclo = %s
            GROUP BY v.carrera_clave, v.carrera_nombre
            ORDER BY v.carrera_clave;
        """, (ciclo_actual,))
        resumen_carrera = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando reportes académicos: {e}", "danger")

    return render_template(
        "coordinador/reportes_academicos.html",
        user=user,
        ciclo_actual=ciclo_actual,
        resumen_carrera=resumen_carrera,
    )


# =====================================
# COORDINADOR – DETALLE DE GRUPO
# =====================================

@app.route("/coordinador/grupo/<int:materia_alta_id>")
@login_required
@role_required("Coordinador")
def coord_detalle_grupo(materia_alta_id):
    user = current_user()
    conn = None
    grupo = None
    alumnos = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Datos del grupo/materia
        cur.execute("""
            SELECT
              v.materia_alta_id,
              v.ciclo,
              v.carrera_clave,
              v.carrera_nombre,
              v.materia_clave,
              v.materia_nombre,
              v.semestre,
              COALESCE(v.profesor_nombre || ' ' || v.profesor_ap, 'Sin asignar') AS docente,
              v.esta_activo
            FROM planes.vw_materia_alta_detalle v
            WHERE v.materia_alta_id = %s;
        """, (materia_alta_id,))
        grupo = cur.fetchone()

        # Alumnos inscritos
        cur.execute("""
            SELECT
              a.numero_control,
              TRIM(a.nombre || ' ' || a.apellido_paterno || ' ' ||
                   COALESCE(a.apellido_materno, '')) AS alumno,
              ai.calificacion
            FROM academico.alumno_inscripcion ai
            JOIN academico.alumnos a
              ON a.numero_control = ai.fk_alumno
            WHERE ai.fk_materia_alta = %s
            ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre;
        """, (materia_alta_id,))
        alumnos = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando detalle del grupo: {e}", "danger")

    return render_template(
        "coordinador/detalle_grupo.html",
        user=user,
        grupo=grupo,
        alumnos=alumnos,
    )


# =====================================
# COORDINADOR – AJUSTE DE CARGA (solo lectura por ahora)
# =====================================

@app.route("/coordinador/carga-academica")
@login_required
@role_required("Coordinador")
def coord_carga_academica():
    user = current_user()
    conn = None
    ciclo_actual = None
    carga = []

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT valor_texto
            FROM academico.parametros_globales
            WHERE clave = 'ciclo_activo';
        """)
        row = cur.fetchone()
        if row and row["valor_texto"]:
            ciclo_actual = row["valor_texto"]
        else:
            cur.execute("""
                SELECT DISTINCT ciclo
                FROM planes.materia_alta
                ORDER BY ciclo DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            ciclo_actual = row["ciclo"] if row else "2025-1"

        cur.execute("""
            SELECT
              v.materia_alta_id,
              v.ciclo,
              v.carrera_clave,
              v.materia_clave,
              v.materia_nombre,
              v.semestre,
              COALESCE(v.profesor_nombre || ' ' || v.profesor_ap, 'Sin asignar') AS docente,
              v.esta_activo,
              cm.horas_teoricas,
              cm.horas_practicas,
              cm.horas_totales
            FROM planes.vw_materia_alta_detalle v
            JOIN planes.carrera_materia cm
              ON cm.carrera_materia_id = v.carrera_materia_id
            WHERE v.ciclo = %s
            ORDER BY v.semestre, v.materia_clave;
        """, (ciclo_actual,))
        carga = cur.fetchall()

        cur.close()
        conn.close()

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error cargando carga académica: {e}", "danger")

    return render_template(
        "coordinador/carga_academica.html",
        user=user,
        ciclo_actual=ciclo_actual,
        carga=carga,
    )




# =====================================
# MAIN
# =====================================

if __name__ == "__main__":
    app.run(debug=True)
