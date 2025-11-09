import os
import smtplib
from email.message import EmailMessage
import secrets
import string
from datetime import timedelta

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


# ===============================
# CONFIGURACIÓN BÁSICA
# ===============================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambia-esta-clave")
app.permanent_session_lifetime = timedelta(hours=4)


# ===============================
# CONEXIÓN A POSTGRES
# ===============================
def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "DB_universidad"),
        user=os.getenv("DB_USER", "backend_app"),
        password=os.getenv("DB_PASSWORD", "Backend123"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        cursor_factory=RealDictCursor,
    )


# ===============================
# FUNCIONES AUXILIARES
# ===============================
def current_user():
    """Devuelve info básica del usuario logueado desde la sesión."""
    if "user_id" not in session:
        return None
    return {
        "id_usuario": session.get("user_id"),
        "nombre_usuario": session.get("username"),
        "correo_electronico": session.get("email"),
        "roles": session.get("roles", []),
    }


def login_required(view_func):
    """Decorador sencillo para proteger rutas."""
    from functools import wraps

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión primero.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def send_email(to_email: str, subject: str, body: str):
    """
    Envía un correo simple usando smtplib y los datos de configuración
    definidos en .env (MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, etc.).
    """
    server = os.getenv("MAIL_SERVER")
    port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    username = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    default_sender = os.getenv("MAIL_DEFAULT_SENDER", username)

    if not (server and port and username and password):
        print("⚠️ Configuración de correo incompleta, no se envió el email.")
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
        print(f"📨 Correo enviado a {to_email}")


def generate_random_password(length: int = 10) -> str:
    """Genera una contraseña aleatoria sencilla."""
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


# ===============================
# RUTAS DE AUTENTICACIÓN
# ===============================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    identificador = request.form.get("identificador", "").strip()
    contrasena = request.form.get("contrasena", "").strip()
    selected_role = request.form.get("rol", "").strip()

    if not identificador or not contrasena:
        flash("Debes llenar usuario/correo y contraseña.", "danger")
        return render_template("login.html")

    if not selected_role or selected_role == "Selecciona tu rol":
        flash("Debes seleccionar tu rol.", "danger")
        return render_template("login.html")

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                u.id_usuario,
                u.nombre_usuario,
                u.correo_electronico,
                COALESCE(
                    ARRAY_AGG(r.nombre_rol ORDER BY r.nombre_rol)
                    FILTER (WHERE r.nombre_rol IS NOT NULL),
                    ARRAY[]::TEXT[]
                ) AS roles
            FROM seguridad.usuarios u
            LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN seguridad.roles r ON r.id_rol = ur.id_rol
            WHERE u.activo = TRUE
              AND (
                    LOWER(u.nombre_usuario) = LOWER(%s)
                 OR LOWER(u.correo_electronico) = LOWER(%s)
                  )
              AND u.contrasena_hash = crypt(%s, u.contrasena_hash)
            GROUP BY u.id_usuario, u.nombre_usuario, u.correo_electronico;
            """,
            (identificador, identificador, contrasena),
        )
        user = cur.fetchone()
        cur.close()
        if conn and not conn.closed:
            conn.close()

        if not user:
            flash("Credenciales incorrectas.", "danger")
            return render_template("login.html")

        roles_usuario = user["roles"] or []
        if selected_role not in roles_usuario:
            flash("El rol seleccionado no corresponde a tu cuenta.", "danger")
            return render_template("login.html")

        session.permanent = True
        session["user_id"] = user["id_usuario"]
        session["username"] = user["nombre_usuario"]
        session["email"] = user["correo_electronico"]
        session["roles"] = roles_usuario

        flash("Inicio de sesión exitoso.", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error al iniciar sesión: {e}", "danger")
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    user = current_user()
    roles_user = user["roles"] or []
    if "Administrador" not in roles_user:
        flash("Solo un administrador puede crear nuevas cuentas.", "danger")
        return redirect(url_for("dashboard"))

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        if request.method == "GET":
            cur.execute(
                """
                SELECT id_rol, nombre_rol
                FROM seguridad.roles
                ORDER BY nombre_rol;
                """
            )
            roles = cur.fetchall()
            cur.close()
            if conn and not conn.closed:
                conn.close()
            return render_template("register.html", roles=roles)

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role_id = request.form.get("role_id", "").strip()

        if not username or not email or not password or not role_id:
            flash("Todos los campos, incluyendo el rol, son obligatorios.", "danger")
            cur.execute(
                """
                SELECT id_rol, nombre_rol
                FROM seguridad.roles
                ORDER BY nombre_rol;
                """
            )
            roles = cur.fetchall()
            cur.close()
            if conn and not conn.closed:
                conn.close()
            return render_template("register.html", roles=roles)

        cur.execute(
            """
            SELECT 1
            FROM seguridad.usuarios
            WHERE LOWER(nombre_usuario) = LOWER(%s)
               OR LOWER(correo_electronico) = LOWER(%s);
            """,
            (username, email),
        )
        if cur.fetchone():
            flash("Ya existe un usuario con ese nombre o correo.", "danger")
            cur.execute(
                """
                SELECT id_rol, nombre_rol
                FROM seguridad.roles
                ORDER BY nombre_rol;
                """
            )
            roles = cur.fetchall()
            cur.close()
            if conn and not conn.closed:
                conn.close()
            return render_template("register.html", roles=roles)

        cur.execute(
            """
            INSERT INTO seguridad.usuarios (nombre_usuario, correo_electronico, contrasena_hash)
            VALUES (%s, %s, %s)
            RETURNING id_usuario;
            """,
            (username, email, password),
        )
        new_id = cur.fetchone()["id_usuario"]

        cur.execute(
            """
            INSERT INTO seguridad.usuario_rol (id_usuario, id_rol)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (new_id, int(role_id)),
        )

        conn.commit()
        cur.close()
        if conn and not conn.closed:
            conn.close()

        flash("Usuario creado correctamente.", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        if conn and not conn.closed:
            conn.rollback()
            conn.close()
        flash(f"Error al registrar usuario: {e}", "danger")
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id_rol, nombre_rol FROM seguridad.roles ORDER BY nombre_rol;"
            )
            roles = cur.fetchall()
            cur.close()
            if conn and not conn.closed:
                conn.close()
        except Exception:
            roles = []
        return render_template("register.html", roles=roles)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Debes ingresar un correo electrónico.", "danger")
        return render_template("forgot_password.html")

    conn = None
    user = None
    new_password = None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id_usuario, nombre_usuario, correo_electronico
            FROM seguridad.usuarios
            WHERE activo = TRUE
              AND LOWER(correo_electronico) = LOWER(%s)
            """,
            (email,),
        )
        user = cur.fetchone()

        if not user:
            cur.close()
            if conn and not conn.closed:
                conn.close()
            conn = None
            flash(
                "Si el correo existe en el sistema, se enviará una nueva contraseña.",
                "info",
            )
            return render_template("forgot_password.html")

        new_password = generate_random_password(10)

        cur.execute(
            """
            UPDATE seguridad.usuarios
               SET contrasena_hash = crypt(%s, gen_salt('bf', 12))
             WHERE id_usuario = %s;
            """,
            (new_password, user["id_usuario"]),
        )

        conn.commit()
        cur.close()
        if conn and not conn.closed:
            conn.close()
        conn = None

    except Exception as e:
        if conn is not None and not conn.closed:
            conn.rollback()
            conn.close()
        flash(f"Error al actualizar la contraseña: {e}", "danger")
        return render_template("forgot_password.html")

    try:
        cuerpo = f"""
Hola {user['nombre_usuario']},

Hemos recibido una solicitud para restablecer tu contraseña
del Sistema Universitario.

Tu nueva contraseña temporal es:

    {new_password}

Te recomendamos iniciar sesión y cambiarla lo antes posible.

Si tú no solicitaste este cambio, por favor contacta al administrador.
"""

        send_email(
            to_email=email,
            subject="Nueva contraseña temporal - Sistema Universitario",
            body=cuerpo,
        )

        flash(
            "Si el correo existe en el sistema, se ha enviado una nueva contraseña temporal.",
            "info",
        )

    except Exception as e:
        flash(
            f"La contraseña se actualizó, pero hubo un problema enviando el correo: {e}",
            "danger",
        )

    return render_template("forgot_password.html")


# ===============================
# RUTAS GENERALES / DASHBOARD
# ===============================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    roles = user["roles"] or []

    if "Administrador" in roles or "Coordinador" in roles:
        return render_template("dashboard_admin.html", user=user)
    elif "Docente" in roles:
        return render_template("dashboard_docente.html", user=user)
    elif "Estudiante" in roles:
        return render_template("dashboard_estudiante.html", user=user)
    else:
        return render_template("dashboard_estudiante.html", user=user)


# ===============================
# RUTAS DE MÓDULOS
# ===============================

@app.route("/planes/carreras")
@login_required
def planes_carreras():
    conn = None
    carreras = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT carrera_id, clave, nombre
            FROM planes.carrera
            ORDER BY clave;
            """
        )
        carreras = cur.fetchall()
        cur.close()
        if conn and not conn.closed:
            conn.close()
    except Exception as e:
        if conn and not conn.closed:
            conn.close()
        flash(f"Error al obtener las carreras: {e}", "danger")

    user = current_user()
    return render_template("planes_carreras.html", user=user, carreras=carreras)


# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
