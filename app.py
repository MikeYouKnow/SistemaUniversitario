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
    """Opcional: protege rutas por rol actual."""
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


@app.route("/perfil/bibliotecario")
@login_required
@role_required("Bibliotecario")
def perfil_bibliotecario():
    return render_template("perfiles/profile_bibliotecario.html", user=current_user())


@app.route("/perfil/coordinador")
@login_required
@role_required("Coordinador")
def perfil_coordinador():
    return render_template("perfiles/profile_coordinador.html", user=current_user())


@app.route("/perfil/docente")
@login_required
@role_required("Docente")
def perfil_docente():
    return render_template("perfiles/profile_docente.html", user=current_user())


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

        # ---- Info estudiante para el encabezado (igual que /estudiante/informacion) ----
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
                c.clave AS carrera_clave,
                c.nombre AS carrera_nombre,
                m.clave AS materia_clave,
                m.nombre AS materia_nombre,
                cm.semestre,
                COUNT(ai.inscripcion_id) AS num_alumnos
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
            JOIN planes.materia m ON m.materia_id = cm.materia_id
            LEFT JOIN academico.alumno_inscripcion ai ON ai.fk_materia_alta = ma.materia_alta_id
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

        # Si POST: actualizar calificación
        if request.method == "POST":
            inscripcion_id = request.form.get("inscripcion_id")
            nueva_calif = request.form.get("calificacion")
            try:
                if nueva_calif == "":
                    nueva_val = None
                else:
                    nueva_val = float(nueva_calif)
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

        # Obtener primera materia del docente si no se manda por querystring
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

        if materia_alta_id:
            cur.execute("""
                SELECT
                    ai.inscripcion_id,
                    a.numero_control,
                    TRIM(a.nombre || ' ' || a.apellido_paterno || ' ' || COALESCE(a.apellido_materno,'')) AS alumno,
                    m.clave AS materia_clave,
                    m.nombre AS materia_nombre,
                    ai.calificacion
                FROM academico.alumno_inscripcion ai
                JOIN academico.alumnos a ON a.numero_control = ai.fk_alumno
                JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
                JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
                JOIN planes.materia m ON m.materia_id = cm.materia_id
                WHERE ai.fk_materia_alta = %s
                  AND ma.fk_personal = %s
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre;
            """, (materia_alta_id, personal_id))
            calificaciones = cur.fetchall()

        # También traer todas las materias del docente para un select en la vista
        cur.execute("""
            SELECT
                ma.materia_alta_id,
                ma.ciclo,
                m.clave || ' - ' || m.nombre AS etiqueta
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m ON m.materia_id = cm.materia_id
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

        # Obtener primera materia si no se manda
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

        if materia_alta_id:
            cur.execute("""
                SELECT
                    a.numero_control,
                    TRIM(a.nombre || ' ' || a.apellido_paterno || ' ' || COALESCE(a.apellido_materno,'')) AS alumno
                FROM academico.alumno_inscripcion ai
                JOIN academico.alumnos a ON a.numero_control = ai.fk_alumno
                JOIN planes.materia_alta ma ON ma.materia_alta_id = ai.fk_materia_alta
                WHERE ai.fk_materia_alta = %s
                  AND ma.fk_personal = %s
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre;
            """, (materia_alta_id, personal_id))
            lista = cur.fetchall()

        # materias del docente para un select en la vista
        cur.execute("""
            SELECT
                ma.materia_alta_id,
                ma.ciclo,
                m.clave || ' - ' || m.nombre AS etiqueta
            FROM planes.materia_alta ma
            JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
            JOIN planes.materia m ON m.materia_id = cm.materia_id
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
# DOCENTE – COMUNICACIÓN (DEMO)
# =====================================

@app.route("/docente/comunicacion")
@login_required
@role_required("Docente")
def docente_comunicacion():
    user = current_user()
    # Demo: avisos en memoria (en un futuro puede venir de una tabla)
    avisos = [
        {"titulo": "Entrega de proyecto final", "mensaje": "Recuerda subir tu proyecto antes del viernes."},
        {"titulo": "Examen parcial", "mensaje": "El examen será la próxima semana en horario de clase."},
    ]
    return render_template(
        "docente/comunicacion.html",
        user=user,
        avisos=avisos
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
                COALESCE(inv.cantidad, 0) AS cantidad,
                COALESCE(inv.cantidad_disponible, 0) AS cantidad_disponible
            FROM biblioteca.libros l
            LEFT JOIN biblioteca.clasificaciones c ON c.id_clasificacion = l.id_clasificacion
            LEFT JOIN biblioteca.editoriales e ON e.id_editorial = l.id_editorial
            LEFT JOIN biblioteca.inventario inv ON inv.id_libro = l.id_libro
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

    try:
        conn = get_connection()
        cur = conn.cursor()

        if request.method == "POST":
            prestamo_id = request.form.get("id_prestamo")
            try:
                # Marcar como devuelto (simple)
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
    # Demo: lista estática
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
# ADMIN – LISTA DE USUARIOS
# =====================================

@app.route("/admin/usuarios")
@login_required
@role_required("Administrador")
def admin_usuarios_list():
    user = current_user()
    usuarios = []

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                u.activo,
                COALESCE(ARRAY_AGG(r.nombre_rol ORDER BY r.nombre_rol)
                         FILTER (WHERE r.nombre_rol IS NOT NULL), '{}') AS roles
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            GROUP BY u.id_usuario, u.nombre_usuario, u.correo_electronico, u.activo
            ORDER BY u.id_usuario;
        """)
        usuarios = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Error cargando usuarios: {e}", "danger")

    return render_template(
        "admin/usuarios_list.html",
        user=user,
        usuarios=usuarios
    )


# =====================================
# ADMIN – CREAR NUEVO USUARIO (DEMO)
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

        # Obtener roles disponibles
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
                    # Crear usuario
                    cur.execute("""
                        INSERT INTO seguridad.usuarios(nombre_usuario, correo_electronico, contrasena_hash)
                        VALUES (%s, %s, %s)
                        RETURNING id_usuario;
                    """, (nombre_usuario, correo, contrasena))
                    nuevo_id = cur.fetchone()["id_usuario"]

                    # Asignar rol
                    cur.execute("""
                        INSERT INTO seguridad.usuario_rol(id_usuario, id_rol)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (nuevo_id, id_rol))

                    conn.commit()
                    flash("Usuario creado correctamente (demo, sin enlazar a alumno/personal).", "success")
                    return redirect(url_for("admin_usuarios_list"))
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
# ADMIN – EDITAR USUARIO (DEMO)
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

        # Usuario
        cur.execute("""
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                u.activo,
                COALESCE(ARRAY_AGG(r.id_rol)
                         FILTER (WHERE r.id_rol IS NOT NULL), '{}') AS roles_ids
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            WHERE u.id_usuario = %s
            GROUP BY u.id_usuario;
        """, (id_usuario,))
        usuario = cur.fetchone()
        if not usuario:
            cur.close()
            conn.close()
            abort(404)

        # Roles
        cur.execute("SELECT id_rol, nombre_rol FROM seguridad.roles ORDER BY nombre_rol;")
        roles = cur.fetchall()

        if request.method == "POST":
            correo = request.form.get("correo_electronico", "").strip()
            activo = request.form.get("activo") == "on"
            nuevos_roles = request.form.getlist("roles")  # lista de id_rol (str)

            try:
                # Actualizar usuario
                cur.execute("""
                    UPDATE seguridad.usuarios
                    SET correo_electronico = %s,
                        activo = %s
                    WHERE id_usuario = %s;
                """, (correo, activo, id_usuario))

                # Limpiar roles previos
                cur.execute("DELETE FROM seguridad.usuario_rol WHERE id_usuario = %s;", (id_usuario,))

                # Insertar nuevos roles
                for rid in nuevos_roles:
                    cur.execute("""
                        INSERT INTO seguridad.usuario_rol(id_usuario, id_rol)
                        VALUES (%s, %s);
                    """, (id_usuario, int(rid)))

                conn.commit()
                flash("Usuario actualizado.", "success")
                return redirect(url_for("admin_usuarios_list"))

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
# ADMIN – BLOCK / RESET PASSWORD (DEMO)
# =====================================

@app.route("/admin/usuarios/<int:id_usuario>/block", methods=["POST"])
@login_required
@role_required("Administrador")
def admin_usuario_block(id_usuario):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE seguridad.usuarios SET activo = FALSE WHERE id_usuario = %s;", (id_usuario,))
        conn.commit()
        cur.close()
        conn.close()
        flash("Usuario bloqueado.", "info")
    except Exception as e:
        flash(f"Error al bloquear usuario: {e}", "danger")
    return redirect(url_for("admin_usuarios_list"))


@app.route("/admin/usuarios/<int:id_usuario>/reset", methods=["POST"])
@login_required
@role_required("Administrador")
def admin_usuario_reset(id_usuario):
    try:
        conn = get_connection()
        cur = conn.cursor()
        nueva_pwd = generate_random_password(10)

        # Actualizar contrasena_hash (trigger hará el hash)
        cur.execute("""
            UPDATE seguridad.usuarios
            SET contrasena_hash = %s
            WHERE id_usuario = %s
            RETURNING correo_electronico;
        """, (nueva_pwd, id_usuario))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        correo = row["correo_electronico"] if row else None
        if correo:
            send_email(
                correo,
                "Restablecimiento de contraseña",
                f"Tu nueva contraseña temporal es: {nueva_pwd}"
            )

        flash("Contraseña restablecida y enviada por correo (demo).", "success")
    except Exception as e:
        flash(f"Error al restablecer contraseña: {e}", "danger")

    return redirect(url_for("admin_usuarios_list"))


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
# MAIN
# =====================================

if __name__ == "__main__":
    app.run(debug=True)
