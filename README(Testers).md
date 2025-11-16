Guía de Pruebas — Sistema Universitario (Modo Desarrollo)
📘 Descripción

Este documento explica cómo ejecutar y probar el Sistema Universitario directamente desde el código fuente.
Está dirigido al equipo de testers, docentes y coordinadores que validarán las funciones del sistema sin necesidad de instalar ejecutables.

El sistema permite probar el inicio de sesión, la gestión de usuarios, y los paneles según cada rol (Administrador, Estudiante, Docente, etc.).

⚙️ Requisitos previos

Antes de comenzar, asegúrate de tener instalado:

🐍 Python 3.11 o superior
(Descargable desde https://www.python.org/downloads
)

🐘 PostgreSQL 15+
(Con la base de datos DB_universidad creada y configurada)

📦 Git (opcional) si vas a clonar el repositorio desde GitHub.

🚀 Pasos para ejecutar el sistema
1️⃣ Clonar o descargar el proyecto

Opción 1 (recomendada):

git clone https://github.com/MikeYouKnow/SistemaUniversitario.git
cd SistemaUniversitario


Opción 2: Descarga el ZIP desde GitHub → Descomprímelo y abre la carpeta.

2️⃣ Crear el entorno virtual

Esto permite mantener las dependencias aisladas del sistema:

python -m venv .venv


Activar el entorno:

En Windows:

.venv\Scripts\activate


En Linux/Mac:

source .venv/bin/activate

3️⃣ Instalar dependencias

Con el entorno activado, ejecuta:

pip install -r requirements.txt

4️⃣ Configurar el archivo .env

Crea un archivo llamado .env (enviado en el correo) en la raíz del proyecto con este contenido (ajusta tus credenciales):

FLASK_SECRET_KEY=clave_super_segura

DB_NAME=DB_universidad
DB_USER=backend_app
DB_PASSWORD=Backend123
DB_HOST=localhost
DB_PORT=5432

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=tu_correo@gmail.com
MAIL_PASSWORD=tu_contraseña_o_app_password
MAIL_DEFAULT_SENDER=Sistema Universitario <tu_correo@gmail.com>


⚠️ Importante: no subas este archivo a GitHub; contiene información sensible.

5️⃣ Cargar la base de datos inicial

Abre pgAdmin 4 o una consola SQL.

Ejecuta el script que viene en la carpeta BD/ o database/, por ejemplo:

database/Querys.sql


Este script creará los roles, usuarios y permisos iniciales.

Usuarios de prueba:

Rol	Usuario	Contraseña
🧑‍🎓 Estudiante	estu1	123456
👨‍🏫 Docente	doc1	123456
🧑‍💼 Coordinador	coord1	123456
🧑‍💻 Administrador	admin1	123456
📚 Bibliotecario	biblio1	123456
6️⃣ Ejecutar el sistema

Con el entorno activado, corre la aplicación:

python app.py


El sistema iniciará en:

👉 http://127.0.0.1:5000

🧭 Funcionalidades disponibles
🔐 Autenticación

Validación de usuario, contraseña y rol correcto.

Recuperación de contraseña mediante correo.

Cierre de sesión seguro.

🧑‍💻 Administrador

Crear nuevos usuarios.

Asignar roles.

Gestionar accesos.

🎓 Estudiante / Docente 

Acceso a sus respectivos paneles (dashboard_*).

Pruebas visuales y funcionales según el rol asignado.

🧰 Información técnica

Backend: Flask (Python 3.11)

Base de datos: PostgreSQL (Schemas: seguridad, academico, planes, infraestructura, biblioteca, rrhh)

Correo: SMTP (Gmail configurado en .env)

Frontend: HTML + Bootstrap 5

Entorno de pruebas: Visual Studio Code / pgAdmin4

⚠️ Notas importantes

No cierres la consola mientras pruebas; el sistema dejará de funcionar.

Si el puerto 5000 está ocupado, puedes modificarlo en la última línea de app.py:

app.run(debug=True, port=5050)


Los correos de recuperación de contraseña pueden tardar unos segundos.

En caso de error de conexión, revisa tus credenciales del .env y que PostgreSQL esté activo.
