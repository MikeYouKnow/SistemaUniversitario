-- =================================================================
-- BASE DE DATOS UNIFICADA DEL SISTEMA UNIVERSITARIO v9.3
-- SCRIPT DE ESTRUCTURA (DDL) PARA POSTGRESQL
-- =================================================================

BEGIN;

-- ======================================
-- 0) EXTENSIONES GLOBALES
-- ======================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ======================================
-- 1) ESQUEMAS
-- ======================================
CREATE SCHEMA IF NOT EXISTS seguridad;
CREATE SCHEMA IF NOT EXISTS academico;
CREATE SCHEMA IF NOT EXISTS planes;
CREATE SCHEMA IF NOT EXISTS infraestructura;
CREATE SCHEMA IF NOT EXISTS biblioteca;
CREATE SCHEMA IF NOT EXISTS rrhh;

-- Establecer el orden de búsqueda
SET search_path = seguridad, academico, planes, infraestructura, biblioteca, rrhh, public;

-- ======================================
-- 2) TODAS LAS TABLAS DE CATÁLOGO PRIMERO
-- ======================================

-- Catálogos de Seguridad
CREATE TABLE IF NOT EXISTS seguridad.roles (
  id_rol       SMALLSERIAL PRIMARY KEY,
  nombre_rol   VARCHAR(50) NOT NULL UNIQUE,
  descripcion  TEXT
);
CREATE TABLE IF NOT EXISTS seguridad.permisos (
  id_permiso    SMALLSERIAL PRIMARY KEY,
  codigo        VARCHAR(80) NOT NULL UNIQUE,
  descripcion   TEXT
);

-- Catálogos de RRHH (algunos son globales)
CREATE TABLE IF NOT EXISTS rrhh.cat_puestos (id_puesto SERIAL PRIMARY KEY, clave VARCHAR(50) UNIQUE NOT NULL, nombre VARCHAR(255), nivel VARCHAR(50));
CREATE TABLE IF NOT EXISTS rrhh.cat_centros_trabajo (id_centro_trabajo SERIAL PRIMARY KEY, nombre VARCHAR(255) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS rrhh.cat_nacionalidades (id_nacionalidad SERIAL PRIMARY KEY, nombre VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS rrhh.cat_sexos (id_sexo SERIAL PRIMARY KEY, nombre VARCHAR(50) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS rrhh.cat_ubicaciones (id_ubicacion SERIAL PRIMARY KEY, codigo_postal VARCHAR(10), colonia VARCHAR(150), ciudad VARCHAR(100), estado VARCHAR(100), UNIQUE(codigo_postal, colonia, ciudad, estado));
CREATE TABLE IF NOT EXISTS rrhh.cat_tipos_documento (id_tipo_documento SERIAL PRIMARY KEY, nombre VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS rrhh.cat_grados_academicos (id_grado SERIAL PRIMARY KEY, nombre VARCHAR(100) UNIQUE NOT NULL);

-- Catálogos de Academico
CREATE TABLE IF NOT EXISTS academico.cat_genero (genero_id SMALLSERIAL PRIMARY KEY, nombre VARCHAR(40) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_estado_civil (estado_civil_id SMALLSERIAL PRIMARY KEY, nombre VARCHAR(40) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_tenencia_vivienda (tenencia_id SMALLSERIAL PRIMARY KEY, nombre VARCHAR(50) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_escolaridad (escolaridad_id SMALLSERIAL PRIMARY KEY, nombre VARCHAR(60) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_ocupacion (ocupacion_id SMALLSERIAL PRIMARY KEY, nombre VARCHAR(80) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_beca (beca_id SMALLSERIAL PRIMARY KEY, nombre VARCHAR(100) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_campus (campus_id SERIAL PRIMARY KEY, nombre VARCHAR(80) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_modalidad (modalidad_id SERIAL PRIMARY KEY, nombre VARCHAR(50) UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS academico.cat_estado_inscripcion (estado_id SERIAL PRIMARY KEY, nombre VARCHAR(50) UNIQUE NOT NULL);

-- Catálogos de Infraestructura
CREATE TABLE IF NOT EXISTS infraestructura.tipo_aula (tipo_id SERIAL PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS infraestructura.edificio (edificio_id SERIAL PRIMARY KEY, numero SMALLINT NOT NULL UNIQUE, nombre TEXT); -- **MOVIDO AQUÍ**

-- Catálogos de Biblioteca
CREATE TABLE IF NOT EXISTS biblioteca.Clasificaciones (id_clasificacion SERIAL PRIMARY KEY, codigo_clasificacion VARCHAR(20) UNIQUE NOT NULL, descripcion VARCHAR(100));
CREATE TABLE IF NOT EXISTS biblioteca.Editoriales (id_editorial SERIAL PRIMARY KEY, nombre_editorial VARCHAR(150) UNIQUE NOT NULL, pais VARCHAR(50));
CREATE TABLE IF NOT EXISTS biblioteca.Autores (id_autor SERIAL PRIMARY KEY, nombre_autor VARCHAR(150) UNIQUE NOT NULL, nacionalidad VARCHAR(50));
CREATE TABLE IF NOT EXISTS biblioteca.Temas (id_tema SERIAL PRIMARY KEY, nombre_tema VARCHAR(100) UNIQUE NOT NULL);

-- ======================================
-- 3) TABLAS PRINCIPALES Y RELACIONALES
-- ======================================

-- ESQUEMA: seguridad (continuación)
CREATE TABLE IF NOT EXISTS seguridad.usuarios (
  id_usuario         BIGSERIAL PRIMARY KEY,
  nombre_usuario     VARCHAR(50)  NOT NULL UNIQUE,
  correo_electronico VARCHAR(255) NOT NULL UNIQUE,
  contrasena_hash    TEXT         NOT NULL,
  activo             BOOLEAN      NOT NULL DEFAULT TRUE,
  creado_en          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  actualizado_en     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  ultimo_acceso_en   TIMESTAMPTZ,
  CONSTRAINT ck_usuarios_pwd_bcrypt CHECK (contrasena_hash ~ '^\$2[aby]\$')
);
CREATE TABLE IF NOT EXISTS seguridad.usuario_rol (
  id_usuario BIGINT NOT NULL REFERENCES seguridad.usuarios(id_usuario) ON DELETE CASCADE,
  id_rol     SMALLINT NOT NULL REFERENCES seguridad.roles(id_rol) ON DELETE CASCADE,
  PRIMARY KEY (id_usuario, id_rol)
);
CREATE TABLE IF NOT EXISTS seguridad.rol_permiso (
  id_rol       SMALLINT NOT NULL REFERENCES seguridad.roles(id_rol) ON DELETE CASCADE,
  id_permiso   SMALLINT NOT NULL REFERENCES seguridad.permisos(id_permiso) ON DELETE CASCADE,
  PRIMARY KEY (id_rol, id_permiso)
);
CREATE TABLE IF NOT EXISTS seguridad.intentos_login (
  id_intento     BIGSERIAL PRIMARY KEY,
  id_usuario     BIGINT REFERENCES seguridad.usuarios(id_usuario) ON DELETE SET NULL,
  identificador  VARCHAR(255) NOT NULL,
  direccion_ip   INET,
  agente_usuario TEXT,
  exitoso        BOOLEAN NOT NULL,
  intentado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS seguridad.sesiones (
  id_sesion      BIGSERIAL PRIMARY KEY,
  id_usuario     BIGINT NOT NULL REFERENCES seguridad.usuarios(id_usuario) ON DELETE CASCADE,
  token          TEXT   NOT NULL UNIQUE,
  creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expira_en      TIMESTAMPTZ NOT NULL,
  revocado_en    TIMESTAMPTZ,
  direccion_ip   INET,
  agente_usuario TEXT,
  CONSTRAINT ck_sesiones_fechas CHECK (expira_en > creado_en)
);
CREATE TABLE IF NOT EXISTS seguridad.reseteo_contrasena (
  id_reseteo   BIGSERIAL PRIMARY KEY,
  id_usuario   BIGINT NOT NULL REFERENCES seguridad.usuarios(id_usuario) ON DELETE CASCADE,
  token        TEXT   NOT NULL UNIQUE,
  creado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expira_en    TIMESTAMPTZ NOT NULL,
  usado_en     TIMESTAMPTZ
);

-- ESQUEMA: rrhh (continuación)
CREATE TABLE IF NOT EXISTS rrhh.ipsset (
    id_ipsset     INTEGER PRIMARY KEY,
    ipsset_numero VARCHAR(50) UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS rrhh.personal (
    id_personal       BIGSERIAL PRIMARY KEY,
    id_ipsset         INTEGER UNIQUE REFERENCES rrhh.ipsset(id_ipsset) ON DELETE SET NULL,
    nombre            VARCHAR(100) NOT NULL,
    apellido_paterno  VARCHAR(100) NOT NULL,
    apellido_materno  VARCHAR(100),
    fecha_nacimiento  DATE,
    correo_institucional VARCHAR(255) UNIQUE CHECK (correo_institucional IS NULL OR correo_institucional ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    rfc_text          VARCHAR(13) UNIQUE NOT NULL,
    curp_text         VARCHAR(18) UNIQUE,
    fk_nacionalidad   INT REFERENCES rrhh.cat_nacionalidades(id_nacionalidad),
    fk_centro_trabajo INT REFERENCES rrhh.cat_centros_trabajo(id_centro_trabajo),
    fk_sexo           INT REFERENCES rrhh.cat_sexos(id_sexo),
    fk_estado_civil   SMALLINT REFERENCES academico.cat_estado_civil(estado_civil_id),
    fk_ubicacion      INT REFERENCES rrhh.cat_ubicaciones(id_ubicacion),
    calle             VARCHAR(255),
    numero_exterior   VARCHAR(50),
    tel_casa          VARCHAR(20),
    tel_celular       VARCHAR(20),
    observaciones     TEXT NULL,
    creado_en         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    actualizado_en    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fk_id_usuario     BIGINT UNIQUE REFERENCES seguridad.usuarios(id_usuario) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS rrhh.personal_documentos (
    id_documento      BIGSERIAL PRIMARY KEY,
    fk_personal       BIGINT NOT NULL REFERENCES rrhh.personal(id_personal) ON DELETE CASCADE,
    fk_tipo_documento INT NOT NULL REFERENCES rrhh.cat_tipos_documento(id_tipo_documento),
    folio_texto       VARCHAR(100) NULL,
    archivo_pdf       BYTEA NULL,
    UNIQUE(fk_personal, fk_tipo_documento)
);
CREATE TABLE IF NOT EXISTS rrhh.personal_historial_laboral (
    id_historial      BIGSERIAL PRIMARY KEY,
    fk_personal       BIGINT NOT NULL REFERENCES rrhh.personal(id_personal) ON DELETE CASCADE,
    fk_puesto         INT NOT NULL REFERENCES rrhh.cat_puestos(id_puesto),
    fecha_inicio      DATE,
    fecha_conclusion  DATE NULL,
    hrs_asignadas     SMALLINT NULL,
    UNIQUE(fk_personal, fk_puesto, fecha_inicio)
);
CREATE TABLE IF NOT EXISTS rrhh.personal_titulos (
    id_titulo         BIGSERIAL PRIMARY KEY,
    fk_personal       BIGINT NOT NULL REFERENCES rrhh.personal(id_personal) ON DELETE CASCADE,
    fk_grado          INT REFERENCES rrhh.cat_grados_academicos(id_grado),
    titulo_grado_text VARCHAR(255),
    titulo_cedula_int BIGINT NULL,
    titulo_pdf        BYTEA NULL
);

-- ESQUEMA: academico (continuación)
CREATE TABLE IF NOT EXISTS academico.alumnos (
  numero_control   VARCHAR(20) PRIMARY KEY,
  curp             VARCHAR(18) UNIQUE,
  nombre           VARCHAR(100) NOT NULL,
  apellido_paterno VARCHAR(100) NOT NULL,
  apellido_materno VARCHAR(100),
  fecha_nacimiento DATE,
  genero_id        SMALLINT REFERENCES academico.cat_genero(genero_id),
  estado_civil_id  SMALLINT REFERENCES academico.cat_estado_civil(estado_civil_id),
  fk_nacionalidad  INT REFERENCES rrhh.cat_nacionalidades(id_nacionalidad),
  fk_campus        INT REFERENCES academico.cat_campus(campus_id),
  fk_modalidad     INT REFERENCES academico.cat_modalidad(modalidad_id),
  creado_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_alumnos_curp_formato CHECK (curp IS NULL OR curp ~* '^[A-ZÑ]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$')
);
CREATE TABLE IF NOT EXISTS academico.contacto (
  contacto_id        BIGSERIAL PRIMARY KEY,
  numero_control     VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  correo_institucional VARCHAR(150),
  correo_personal    VARCHAR(150),
  telefono           VARCHAR(32),
  direccion          TEXT,
  creado_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_contacto_correo_inst CHECK (correo_institucional IS NULL OR correo_institucional ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  CONSTRAINT chk_contacto_correo_pers CHECK (correo_personal IS NULL OR correo_personal ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
CREATE TABLE IF NOT EXISTS academico.contacto_emergencia (
  emergencia_id    BIGSERIAL PRIMARY KEY,
  numero_control   VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  nombre           VARCHAR(150),
  parentesco       VARCHAR(80),
  telefono         VARCHAR(32),
  creado_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS academico.estudio_socioeconomico (
  es_id              BIGSERIAL PRIMARY KEY,
  numero_control     VARCHAR(20) NOT NULL UNIQUE REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  vive_con           VARCHAR(120),
  tenencia_id        SMALLINT REFERENCES academico.cat_tenencia_vivienda(tenencia_id),
  trabaja_actualmente BOOLEAN,
  ingresos_mensuales NUMERIC(12,2) CHECK (ingresos_mensuales IS NULL OR ingresos_mensuales >= 0),
  egresos_mensuales  NUMERIC(12,2) CHECK (egresos_mensuales IS NULL OR egresos_mensuales >= 0),
  apoyo_beca_id      SMALLINT REFERENCES academico.cat_beca(beca_id),
  comentarios        TEXT
);
CREATE TABLE IF NOT EXISTS academico.integrantes_hogar (
  integrante_id   BIGSERIAL PRIMARY KEY,
  numero_control  VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  nombre          VARCHAR(150) NOT NULL,
  parentesco      VARCHAR(80) NOT NULL,
  edad            SMALLINT CHECK (edad IS NULL OR (edad >= 0 AND edad <= 120)),
  escolaridad_id  SMALLINT REFERENCES academico.cat_escolaridad(escolaridad_id),
  ocupacion_id    SMALLINT REFERENCES academico.cat_ocupacion(ocupacion_id),
  ingreso_mensual NUMERIC(12,2) CHECK (ingreso_mensual IS NULL OR ingreso_mensual >= 0),
  CONSTRAINT uq_integrantes_unico UNIQUE (numero_control, nombre, parentesco)
);
CREATE TABLE IF NOT EXISTS academico.ficha_identificacion (
  fi_id             BIGSERIAL PRIMARY KEY,
  numero_control    VARCHAR(20) NOT NULL UNIQUE REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  nss               VARCHAR(20),
  rfc               VARCHAR(13),
  discapacidad      BOOLEAN,
  tipo_discapacidad VARCHAR(120),
  alergias          TEXT,
  tipo_sangre       VARCHAR(5),
  tutor_nombre      VARCHAR(150),
  tutor_telefono    VARCHAR(32),
  tutor_correo      VARCHAR(150),
  CONSTRAINT chk_fi_nss_formato CHECK (nss IS NULL OR nss ~ '^\d{11}$'),
  CONSTRAINT chk_fi_rfc_formato CHECK (rfc IS NULL OR rfc ~* '^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')
);
CREATE TABLE IF NOT EXISTS academico.entrevista (
  entrevista_id BIGSERIAL PRIMARY KEY,
  numero_control VARCHAR(20) NOT NULL UNIQUE REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  fecha         DATE,
  medio         VARCHAR(100),
  observaciones TEXT
);
CREATE TABLE IF NOT EXISTS academico.entrevista_hermanos (
  eh_id          BIGSERIAL PRIMARY KEY,
  numero_control VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  nombre         VARCHAR(150) NOT NULL,
  edad           SMALLINT CHECK (edad IS NULL OR (edad >= 0 AND edad <= 120)),
  escolaridad_id SMALLINT REFERENCES academico.cat_escolaridad(escolaridad_id)
);
CREATE TABLE IF NOT EXISTS academico.entrevista_desajustes (
  ed_id          BIGSERIAL PRIMARY KEY,
  numero_control VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  categoria      VARCHAR(120) NOT NULL,
  descripcion    TEXT,
  severidad      SMALLINT CHECK (severidad IS NULL OR (severidad BETWEEN 1 AND 5))
);
CREATE TABLE IF NOT EXISTS academico.entrevista_autopercepcion (
  ea_id          BIGSERIAL PRIMARY KEY,
  numero_control VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
  dimension      VARCHAR(120) NOT NULL,
  valor          SMALLINT CHECK (valor IS NULL OR (valor BETWEEN 1 AND 5)),
  comentario     TEXT
);

-- ESQUEMA: planes (Tablas)
CREATE TABLE IF NOT EXISTS planes.carrera (
  carrera_id SERIAL PRIMARY KEY,
  clave      TEXT UNIQUE NOT NULL,
  nombre     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planes.materia (
  materia_id SERIAL PRIMARY KEY,
  clave      TEXT UNIQUE NOT NULL,
  nombre     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS planes.carrera_materia (
  carrera_materia_id SERIAL PRIMARY KEY,
  carrera_id       INT NOT NULL REFERENCES planes.carrera(carrera_id) ON DELETE CASCADE,
  materia_id       INT NOT NULL REFERENCES planes.materia(materia_id) ON DELETE CASCADE,
  semestre         INT NOT NULL CHECK (semestre BETWEEN 1 AND 12),
  horas_teoricas   INT NOT NULL CHECK (horas_teoricas >= 0),
  horas_practicas  INT NOT NULL CHECK (horas_practicas >= 0),
  horas_totales    INT GENERATED ALWAYS AS (horas_teoricas + horas_practicas) STORED,
  CONSTRAINT uq_carrera_materia UNIQUE (carrera_id, materia_id)
);
CREATE TABLE IF NOT EXISTS planes.materia_prerrequisito (
  materia_id      INT NOT NULL REFERENCES planes.materia(materia_id) ON DELETE CASCADE,
  prerequisito_id INT NOT NULL REFERENCES planes.materia(materia_id) ON DELETE RESTRICT,
  PRIMARY KEY (materia_id, prerequisito_id),
  CONSTRAINT ck_no_autodep CHECK (materia_id <> prerequisito_id)
);
CREATE TABLE IF NOT EXISTS planes.materia_alta (
  materia_alta_id    SERIAL PRIMARY KEY,
  ciclo              TEXT NOT NULL,
  carrera_materia_id INT NOT NULL REFERENCES planes.carrera_materia(carrera_materia_id) ON DELETE CASCADE,
  fk_personal        BIGINT REFERENCES rrhh.personal(id_personal) ON DELETE SET NULL,
  esta_activo        BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en          TIMESTAMP NOT NULL DEFAULT now(),
  actualizado_en     TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_ciclo_carrera_materia UNIQUE (ciclo, carrera_materia_id)
);

-- ESQUEMA: infraestructura (Tablas)
CREATE TABLE IF NOT EXISTS infraestructura.aula (
  aula_id     SERIAL PRIMARY KEY,
  clave       TEXT NOT NULL,
  edificio_id INT NOT NULL REFERENCES infraestructura.edificio(edificio_id) ON DELETE RESTRICT,
  piso        SMALLINT NOT NULL,
  posicion    SMALLINT,
  capacidad   SMALLINT,
  observaciones TEXT,
  tipo_id     INT NOT NULL REFERENCES infraestructura.tipo_aula(tipo_id) ON DELETE RESTRICT,
  CONSTRAINT aula_unica UNIQUE (clave, edificio_id)
);
CREATE TABLE IF NOT EXISTS planes.carrera_materia_aula_tipo ( -- Depende de infraestructura.tipo_aula
  carrera_materia_id INT NOT NULL REFERENCES planes.carrera_materia(carrera_materia_id) ON DELETE CASCADE,
  tipo_id            INT NOT NULL REFERENCES infraestructura.tipo_aula(tipo_id),
  PRIMARY KEY (carrera_materia_id, tipo_id)
);
CREATE TABLE IF NOT EXISTS infraestructura.horario_asignacion (
    horario_id SERIAL PRIMARY KEY,
    fk_materia_alta INT NOT NULL REFERENCES planes.materia_alta(materia_alta_id) ON DELETE CASCADE,
    fk_aula INT NOT NULL REFERENCES infraestructura.aula(aula_id) ON DELETE RESTRICT,
    dia_semana SMALLINT NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    CONSTRAINT uq_horario_aula_tiempo UNIQUE (fk_aula, dia_semana, hora_inicio),
    CONSTRAINT uq_horario_clase_tiempo UNIQUE (fk_materia_alta, dia_semana, hora_inicio),
    CONSTRAINT ck_horario_fin_mayor_inicio CHECK (hora_fin > hora_inicio)
);

-- ESQUEMA: biblioteca (Tablas)
CREATE TABLE IF NOT EXISTS biblioteca.Libros (
  id_libro SERIAL PRIMARY KEY,
  id_clasificacion INT NOT NULL REFERENCES biblioteca.Clasificaciones(id_clasificacion),
  titulo_libro VARCHAR(255) NOT NULL,
  id_editorial INT NOT NULL REFERENCES biblioteca.Editoriales(id_editorial),
  edicion INT,
  anio_edicion INT,
  isbn BIGINT UNIQUE,
  fuente_recurso VARCHAR(100),
  incluye_cd BOOLEAN DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS biblioteca.Libros_Temas (
  id_libro_tema SERIAL PRIMARY KEY,
  id_libro INT NOT NULL REFERENCES biblioteca.Libros(id_libro) ON DELETE CASCADE,
  id_tema INT NOT NULL REFERENCES biblioteca.Temas(id_tema) ON DELETE CASCADE,
  CONSTRAINT uk_libro_tema UNIQUE (id_libro, id_tema)
);
CREATE TABLE IF NOT EXISTS biblioteca.Inventario (
  id_inventario SERIAL PRIMARY KEY,
  id_libro INT NOT NULL UNIQUE REFERENCES biblioteca.Libros(id_libro) ON DELETE CASCADE,
  cantidad INT NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
  cantidad_disponible INT NOT NULL DEFAULT 0 CHECK (cantidad_disponible >= 0),
  ubicacion VARCHAR(50)
);
CREATE TABLE IF NOT EXISTS biblioteca.Autores_Libros (
  id_autor_libro SERIAL PRIMARY KEY,
  id_libro INT NOT NULL REFERENCES biblioteca.Libros(id_libro) ON DELETE CASCADE,
  id_autor INT NOT NULL REFERENCES biblioteca.Autores(id_autor) ON DELETE CASCADE,
  tipo_autor VARCHAR(20) DEFAULT 'Principal',
  CONSTRAINT uk_libro_autor UNIQUE (id_libro, id_autor)
);
CREATE TABLE IF NOT EXISTS biblioteca.Prestamos (
  id_prestamo BIGSERIAL PRIMARY KEY,
  fk_alumno VARCHAR(20) NULL REFERENCES academico.alumnos(numero_control) ON DELETE SET NULL,
  fk_personal BIGINT NULL REFERENCES rrhh.personal(id_personal) ON DELETE SET NULL,
  id_libro INT NOT NULL REFERENCES biblioteca.Libros(id_libro),
  fecha_prestamo TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_devolucion_estimada TIMESTAMP NOT NULL,
  fecha_devolucion_real TIMESTAMP NULL,
  estado VARCHAR(20) NOT NULL DEFAULT 'Activo' CHECK (estado IN ('Activo', 'Devuelto', 'Vencido')),
  CONSTRAINT ck_prestamo_un_usuario CHECK
      ((fk_alumno IS NOT NULL AND fk_personal IS NULL) OR (fk_alumno IS NULL AND fk_personal IS NOT NULL))
);

-- ESQUEMA: TABLAS DE VINCULACIÓN INTER-MÓDULO
CREATE TABLE IF NOT EXISTS seguridad.auth_user_alumno (
    user_id BIGINT PRIMARY KEY REFERENCES seguridad.usuarios(id_usuario) ON DELETE CASCADE,
    numero_control VARCHAR(20) NOT NULL UNIQUE REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS academico.alumno_inscripcion (
    inscripcion_id BIGSERIAL PRIMARY KEY,
    fk_alumno VARCHAR(20) NOT NULL REFERENCES academico.alumnos(numero_control) ON DELETE CASCADE,
    fk_materia_alta INT NOT NULL REFERENCES planes.materia_alta(materia_alta_id) ON DELETE CASCADE,
    fk_estado INT NOT NULL REFERENCES academico.cat_estado_inscripcion(estado_id),
    calificacion NUMERIC(5,2) CHECK (calificacion IS NULL OR (calificacion >= 0 AND calificacion <= 100)),
    fecha_inscripcion TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_alumno_materia_ciclo UNIQUE (fk_alumno, fk_materia_alta)
);

-- ======================================
-- 4) VISTAS, FUNCIONES Y TRIGGERS
-- ======================================

-- Funciones y Triggers de Seguridad
CREATE OR REPLACE FUNCTION seguridad.fn_actualizar_timestamp()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.actualizado_en := NOW();
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS tg_usuarios_actualizado ON seguridad.usuarios;
CREATE TRIGGER tg_usuarios_actualizado
BEFORE UPDATE ON seguridad.usuarios
FOR EACH ROW EXECUTE FUNCTION seguridad.fn_actualizar_timestamp();

CREATE OR REPLACE FUNCTION seguridad.fn_hashear_contrasena()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.contrasena_hash IS NULL OR LENGTH(NEW.contrasena_hash) = 0 THEN
    RAISE EXCEPTION 'contrasena_hash no puede ser NULL ni vacío';
  END IF;
  IF NEW.contrasena_hash !~ '^\$2[aby]\$' THEN
    NEW.contrasena_hash := crypt(NEW.contrasena_hash, gen_salt('bf', 12));
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS tg_usuarios_hash_ins ON seguridad.usuarios;
DROP TRIGGER IF EXISTS tg_usuarios_hash_upd ON seguridad.usuarios;
CREATE TRIGGER tg_usuarios_hash_ins
BEFORE INSERT ON seguridad.usuarios
FOR EACH ROW EXECUTE FUNCTION seguridad.fn_hashear_contrasena();

CREATE TRIGGER tg_usuarios_hash_upd
BEFORE UPDATE OF contrasena_hash ON seguridad.usuarios
FOR EACH ROW EXECUTE FUNCTION seguridad.fn_hashear_contrasena();

CREATE OR REPLACE FUNCTION seguridad.autenticar(
  p_identificador TEXT, p_contrasena TEXT, p_direccion_ip INET DEFAULT NULL, p_agente_usuario TEXT DEFAULT NULL
)
RETURNS TABLE(id_usuario BIGINT, nombre_usuario TEXT, correo_electronico TEXT, roles TEXT[], exitoso BOOLEAN)
LANGUAGE plpgsql AS $$
DECLARE
  v_usuario seguridad.usuarios%ROWTYPE;
  v_ok   BOOLEAN := FALSE;
BEGIN
  SELECT * INTO v_usuario FROM seguridad.usuarios
  WHERE activo = TRUE AND (LOWER(usuarios.nombre_usuario) = LOWER(p_identificador) OR LOWER(usuarios.correo_electronico) = LOWER(p_identificador))
  LIMIT 1;

  IF FOUND THEN v_ok := (crypt(p_contrasena, v_usuario.contrasena_hash) = v_usuario.contrasena_hash);
  ELSE v_ok := FALSE; END IF;

  INSERT INTO seguridad.intentos_login(id_usuario, identificador, direccion_ip, agente_usuario, exitoso)
  VALUES (CASE WHEN FOUND THEN v_usuario.id_usuario ELSE NULL END, p_identificador, p_direccion_ip, p_agente_usuario, v_ok);

  IF v_ok THEN
    UPDATE seguridad.usuarios SET ultimo_acceso_en = NOW() WHERE usuarios.id_usuario = v_usuario.id_usuario;
    RETURN QUERY SELECT v_usuario.id_usuario, v_usuario.nombre_usuario, v_usuario.correo_electronico,
           COALESCE((SELECT ARRAY_AGG(r.nombre_rol ORDER BY r.nombre_rol)
                     FROM seguridad.usuario_rol ur JOIN seguridad.roles r ON r.id_rol = ur.id_rol
                     WHERE ur.id_usuario = v_usuario.id_usuario), ARRAY[]::TEXT[]), TRUE;
  ELSE
    RETURN QUERY SELECT NULL::BIGINT, NULL::TEXT, NULL::TEXT, ARRAY[]::TEXT[], FALSE;
  END IF;
END$$;

CREATE OR REPLACE FUNCTION seguridad.crear_sesion(
  p_id_usuario BIGINT, p_expira_en TIMESTAMPTZ, p_direccion_ip INET DEFAULT NULL, p_agente_usuario TEXT DEFAULT NULL
)
RETURNS TABLE(id_sesion BIGINT, token TEXT, expira_en TIMESTAMPTZ)
LANGUAGE plpgsql AS $$
DECLARE v_token TEXT;
BEGIN
  v_token := encode(gen_random_bytes(32), 'base64');
  INSERT INTO seguridad.sesiones(id_usuario, token, expira_en, direccion_ip, agente_usuario)
  VALUES (p_id_usuario, v_token, p_expira_en, p_direccion_ip, p_agente_usuario)
  RETURNING sesiones.id_sesion, sesiones.token, sesiones.expira_en
  INTO id_sesion, token, expira_en;
  RETURN;
END$$;

-- Trigger para updated_at en rrhh.personal
DROP TRIGGER IF EXISTS tg_personal_actualizado ON rrhh.personal;
CREATE TRIGGER tg_personal_actualizado
BEFORE UPDATE ON rrhh.personal
FOR EACH ROW EXECUTE FUNCTION seguridad.fn_actualizar_timestamp();

-- Trigger para updated_at en planes.materia_alta
DROP TRIGGER IF EXISTS trg_materia_alta_actualizado ON planes.materia_alta;
CREATE TRIGGER trg_materia_alta_actualizado
BEFORE UPDATE ON planes.materia_alta
FOR EACH ROW EXECUTE FUNCTION seguridad.fn_actualizar_timestamp();

-- Vistas de RRHH
CREATE OR REPLACE VIEW rrhh.v_personal_con_estado AS
SELECT
    p.*,
    COALESCE(est.estado, 'Inactivo') AS estado_laboral,
    est.puesto_actual_id, est.puesto_actual_nombre, est.puesto_actual_clave,
    est.fecha_ingreso_reciente, est.hrs_asignadas_actuales
FROM rrhh.personal p
LEFT JOIN LATERAL (
    SELECT 'Activo' AS estado, phl.fk_puesto AS puesto_actual_id,
           cp.nombre AS puesto_actual_nombre, cp.clave AS puesto_actual_clave,
           phl.fecha_inicio AS fecha_ingreso_reciente, phl.hrs_asignadas AS hrs_asignadas_actuales
    FROM rrhh.personal_historial_laboral phl JOIN rrhh.cat_puestos cp ON phl.fk_puesto = cp.id_puesto
    WHERE phl.fk_personal = p.id_personal AND phl.fecha_conclusion IS NULL
    ORDER BY phl.fecha_inicio DESC LIMIT 1
) est ON true;

-- Vistas de Academico
CREATE OR REPLACE VIEW academico.vw_contacto_actual AS
SELECT DISTINCT ON (c.numero_control)
  c.numero_control, c.correo_institucional, c.correo_personal, c.telefono, c.direccion, c.creado_en
FROM academico.contacto c ORDER BY c.numero_control, c.creado_en DESC;

CREATE OR REPLACE VIEW academico.vw_contacto_emergencia_actual AS
SELECT DISTINCT ON (e.numero_control)
  e.numero_control, e.nombre, e.parentesco, e.telefono, e.creado_en
FROM academico.contacto_emergencia e ORDER BY e.numero_control, e.creado_en DESC;

-- Vistas de Planes
CREATE OR REPLACE VIEW planes.vw_materia_alta_detalle AS
SELECT
  ma.materia_alta_id, ma.ciclo, ma.esta_activo, ma.creado_en, ma.actualizado_en,
  c.clave AS carrera_clave, c.nombre AS carrera_nombre,
  m.clave AS materia_clave, m.nombre AS materia_nombre,
  cm.semestre,
  p.nombre AS profesor_nombre, p.apellido_paterno AS profesor_ap,
  cm.carrera_materia_id
FROM planes.materia_alta ma
JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
JOIN planes.materia m ON m.materia_id = cm.materia_id
LEFT JOIN rrhh.personal p ON p.id_personal = ma.fk_personal
ORDER BY ma.ciclo, c.clave, cm.semestre, m.clave;

CREATE OR REPLACE VIEW planes.vw_plan_por_carrera AS
SELECT
  c.clave AS carrera_clave, c.nombre AS carrera_nombre,
  m.clave AS materia_clave, m.nombre AS materia_nombre,
  cm.semestre, cm.horas_teoricas, cm.horas_practicas, cm.horas_totales,
  (EXISTS (SELECT 1 FROM planes.carrera_materia_aula_tipo cmat WHERE cmat.carrera_materia_id = cm.carrera_materia_id)) AS aula_especial,
  ARRAY_AGG(ta.nombre ORDER BY ta.nombre) FILTER (WHERE ta.nombre IS NOT NULL) AS tipos_aula
FROM planes.carrera_materia cm
JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
JOIN planes.materia m ON m.materia_id = cm.materia_id
LEFT JOIN planes.carrera_materia_aula_tipo cmat ON cmat.carrera_materia_id = cm.carrera_materia_id
LEFT JOIN infraestructura.tipo_aula ta ON ta.tipo_id = cmat.tipo_id
GROUP BY c.clave, c.nombre, m.clave, m.nombre, cm.semestre, cm.horas_teoricas, cm.horas_practicas, cm.horas_totales, cm.carrera_materia_id
ORDER BY c.clave, cm.semestre, m.clave;

CREATE OR REPLACE VIEW planes.vw_prerrequisitos AS
SELECT
  m.clave AS materia_clave, m.nombre AS materia_nombre,
  ARRAY_AGG(mp_req.clave ORDER BY mp_req.clave) AS prereq_claves,
  ARRAY_AGG(mp_req.nombre ORDER BY mp_req.clave) AS prereq_nombres
FROM planes.materia m
JOIN planes.materia_prerrequisito mp ON mp.materia_id = m.materia_id
JOIN planes.materia mp_req ON mp_req.materia_id = mp.prerequisito_id
GROUP BY m.clave, m.nombre
ORDER BY m.clave;

-- ======================================
-- 5) ÍNDICES ADICIONALES
-- ======================================
-- Índices FTS
CREATE INDEX IF NOT EXISTS idx_materia_nombre_fts ON planes.materia USING gin (to_tsvector('spanish', nombre));
CREATE INDEX IF NOT EXISTS idx_carrera_nombre_fts ON planes.carrera USING gin (to_tsvector('spanish', nombre));
CREATE INDEX IF NOT EXISTS idx_libros_titulo_fts ON biblioteca.Libros USING gin (to_tsvector('spanish', titulo_libro));
CREATE INDEX IF NOT EXISTS idx_personal_nombre_fts ON rrhh.personal USING gin (to_tsvector('spanish', nombre || ' ' || apellido_paterno || ' ' || COALESCE(apellido_materno,'')));
CREATE INDEX IF NOT EXISTS idx_alumnos_nombre_fts ON academico.alumnos USING gin (to_tsvector('spanish', nombre || ' ' || apellido_paterno || ' ' || COALESCE(apellido_materno,'')));

-- Índices en FKs comunes
CREATE INDEX IF NOT EXISTS idx_personal_fk_user_id ON rrhh.personal(fk_id_usuario);
CREATE INDEX IF NOT EXISTS idx_auth_user_alumno_num_control ON seguridad.auth_user_alumno(numero_control);
CREATE INDEX IF NOT EXISTS idx_materia_alta_fk_personal ON planes.materia_alta(fk_personal);
CREATE INDEX IF NOT EXISTS idx_horario_asignacion_fk_aula ON infraestructura.horario_asignacion(fk_aula);
CREATE INDEX IF NOT EXISTS idx_alumno_inscripcion_fk_alumno ON academico.alumno_inscripcion(fk_alumno);
CREATE INDEX IF NOT EXISTS idx_prestamos_fk_libro ON biblioteca.Prestamos(id_libro);
CREATE INDEX IF NOT EXISTS idx_prestamos_fk_alumno ON biblioteca.Prestamos(fk_alumno) WHERE fk_alumno IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prestamos_fk_personal ON biblioteca.Prestamos(fk_personal) WHERE fk_personal IS NOT NULL;

-- Índices específicos de las tablas originales
CREATE INDEX IF NOT EXISTS idx_alumnos_apellidos ON academico.alumnos (apellido_paterno, apellido_materno, nombre);
CREATE INDEX IF NOT EXISTS idx_alumnos_curp ON academico.alumnos (curp);
CREATE INDEX IF NOT EXISTS idx_contacto_numctrl_created ON academico.contacto (numero_control, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_cemerg_numctrl_created ON academico.contacto_emergencia (numero_control, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_integrantes_numctrl ON academico.integrantes_hogar (numero_control);
CREATE INDEX IF NOT EXISTS idx_eh_numctrl ON academico.entrevista_hermanos (numero_control);
CREATE INDEX IF NOT EXISTS idx_ed_numctrl ON academico.entrevista_desajustes (numero_control);
CREATE INDEX IF NOT EXISTS idx_ea_numctrl ON academico.entrevista_autopercepcion (numero_control);
CREATE INDEX IF NOT EXISTS idx_entrevista_fecha ON academico.entrevista (fecha);
CREATE INDEX IF NOT EXISTS idx_aula_edificio ON infraestructura.aula(edificio_id);
CREATE INDEX IF NOT EXISTS idx_aula_tipo ON infraestructura.aula(tipo_id);
CREATE INDEX IF NOT EXISTS idx_aula_piso ON infraestructura.aula(piso);
CREATE INDEX IF NOT EXISTS idx_libros_isbn ON biblioteca.Libros(isbn);
CREATE INDEX IF NOT EXISTS idx_prestamos_estado ON biblioteca.Prestamos(estado);
CREATE INDEX IF NOT EXISTS idx_prestamos_fechas ON biblioteca.Prestamos(fecha_prestamo, fecha_devolucion_estimada);
CREATE INDEX IF NOT EXISTS ix_materia_clave ON planes.materia (clave);
CREATE INDEX IF NOT EXISTS ix_carrera_clave ON planes.carrera (clave);
CREATE INDEX IF NOT EXISTS ix_cm_semestre ON planes.carrera_materia (semestre);
CREATE INDEX IF NOT EXISTS ix_cm_materia ON planes.carrera_materia (materia_id);
CREATE INDEX IF NOT EXISTS ix_cma_tipo ON planes.carrera_materia_aula_tipo (tipo_id);
CREATE INDEX IF NOT EXISTS ix_auth_login_attempt_ident ON seguridad.intentos_login (LOWER(identificador));
CREATE INDEX IF NOT EXISTS ix_auth_session_user ON seguridad.sesiones (id_usuario);


COMMIT;




CREATE TABLE IF NOT EXISTS academico.avisos_docente (
    aviso_id        SERIAL PRIMARY KEY,
    fk_materia_alta INT REFERENCES planes.materia_alta(materia_alta_id) ON DELETE CASCADE,
    titulo          VARCHAR(200) NOT NULL,
    mensaje         TEXT NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ======================================
-- 3.x) TABLA DE EVENTOS DE SEGURIDAD (NUEVA)
-- ======================================
CREATE TABLE IF NOT EXISTS seguridad.eventos (
  id_evento   BIGSERIAL PRIMARY KEY,
  fecha       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  tipo        VARCHAR(50) NOT NULL,          -- p.ej. 'login', 'bloqueo', 'alta_usuario'
  usuario_id  BIGINT REFERENCES seguridad.usuarios(id_usuario) ON DELETE SET NULL,
  descripcion TEXT,
  datos       JSONB                           -- info extra opcional
);

CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON seguridad.eventos(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_eventos_tipo  ON seguridad.eventos(tipo);
CREATE INDEX IF NOT EXISTS idx_eventos_usuario ON seguridad.eventos(usuario_id);

-- ======================================
-- 3.y) TABLAS PARA PARÁMETROS Y FORMULARIOS (NUEVAS)
-- ======================================

-- Parámetros globales del módulo académico
CREATE TABLE IF NOT EXISTS academico.parametros_globales (
  id_parametro  SERIAL PRIMARY KEY,
  clave         VARCHAR(80) NOT NULL UNIQUE,    -- p.ej. 'ciclo_activo'
  valor_texto   VARCHAR(255),
  descripcion   TEXT,
  categoria     VARCHAR(50) DEFAULT 'general',
  actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION academico.fn_parametros_globales_touch()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.actualizado_en := NOW();
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS tg_parametros_globales_actualizado ON academico.parametros_globales;
CREATE TRIGGER tg_parametros_globales_actualizado
BEFORE UPDATE ON academico.parametros_globales
FOR EACH ROW EXECUTE FUNCTION academico.fn_parametros_globales_touch();

-- Formularios institucionales (para el módulo "Formularios y académico")
CREATE TABLE IF NOT EXISTS academico.formularios_institucionales (
  id_formulario SERIAL PRIMARY KEY,
  nombre        VARCHAR(200) NOT NULL,
  tipo          VARCHAR(40)  NOT NULL,         -- 'Alumno', 'Administrativo', etc.
  version       NUMERIC(3,1) NOT NULL DEFAULT 1.0,
  descripcion   TEXT,
  CONSTRAINT uq_form_nombre_version UNIQUE (nombre, version)
);

-- ======================================
-- 4.x) VISTA PARA RESUMEN DE ROLES Y ESTADO (NUEVA)
-- ======================================
CREATE OR REPLACE VIEW seguridad.vw_resumen_roles_estados AS
SELECT
  COALESCE(r.nombre_rol, 'Sin rol') AS rol,
  CASE WHEN u.activo THEN 'Activo' ELSE 'Bloqueado' END AS estado,
  COUNT(*) AS cantidad
FROM seguridad.usuarios u
LEFT JOIN seguridad.usuario_rol ur ON ur.id_usuario = u.id_usuario
LEFT JOIN seguridad.roles r        ON r.id_rol     = ur.id_rol
GROUP BY rol, estado
ORDER BY rol, estado;