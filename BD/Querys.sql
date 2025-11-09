DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'backend_app'
  ) THEN
    CREATE ROLE backend_app LOGIN PASSWORD 'Backend123';
  END IF;
END$$;

-- Permiso para conectarse a la BD
GRANT CONNECT ON DATABASE "DB_universidad" TO backend_app;

-- Permisos en TODOS los schemas (para que después no te falle nada)
GRANT USAGE ON SCHEMA seguridad, academico, planes, infraestructura, biblioteca, rrhh TO backend_app;

-- Permisos sobre tablas y secuencias de cada schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA seguridad TO backend_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA seguridad TO backend_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA academico TO backend_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA academico TO backend_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA planes TO backend_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA planes TO backend_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA infraestructura TO backend_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA infraestructura TO backend_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA biblioteca TO backend_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA biblioteca TO backend_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rrhh TO backend_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA rrhh TO backend_app;

-- Para que tablas nuevas automáticamente den permisos a backend_app
ALTER DEFAULT PRIVILEGES IN SCHEMA seguridad
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO backend_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA seguridad
GRANT USAGE, SELECT ON SEQUENCES TO backend_app;

INSERT INTO seguridad.roles (nombre_rol, descripcion) VALUES
  ('Estudiante',    'Rol para estudiantes'),
  ('Docente',       'Rol para docentes'),
  ('Coordinador',   'Rol para coordinadores académicos'),
  ('Administrador', 'Rol para administradores del sistema'),
  ('Bibliotecario', 'Rol para personal de biblioteca')
ON CONFLICT (nombre_rol) DO NOTHING;

-- Usuarios de prueba (la contraseña REAL de todos será '123456')
INSERT INTO seguridad.usuarios (nombre_usuario, correo_electronico, contrasena_hash)
VALUES
  ('estu1',   'estudiante@example.com',    '123456'),
  ('doc1',    'docente@example.com',       '123456'),
  ('coord1',  'coordinador@example.com',   '123456'),
  ('admin1',  'admin@example.com',         '123456'),
  ('biblio1', 'bibliotecario@example.com', '123456')
ON CONFLICT (nombre_usuario) DO NOTHING;

-- Estudiante
INSERT INTO seguridad.usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM seguridad.usuarios u
JOIN seguridad.roles r ON r.nombre_rol = 'Estudiante'
WHERE u.nombre_usuario = 'estu1'
ON CONFLICT DO NOTHING;

-- Docente
INSERT INTO seguridad.usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM seguridad.usuarios u
JOIN seguridad.roles r ON r.nombre_rol = 'Docente'
WHERE u.nombre_usuario = 'doc1'
ON CONFLICT DO NOTHING;

-- Coordinador
INSERT INTO seguridad.usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM seguridad.usuarios u
JOIN seguridad.roles r ON r.nombre_rol = 'Coordinador'
WHERE u.nombre_usuario = 'coord1'
ON CONFLICT DO NOTHING;

-- Administrador
INSERT INTO seguridad.usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM seguridad.usuarios u
JOIN seguridad.roles r ON r.nombre_rol = 'Administrador'
WHERE u.nombre_usuario = 'admin1'
ON CONFLICT DO NOTHING;

-- Bibliotecario
INSERT INTO seguridad.usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM seguridad.usuarios u
JOIN seguridad.roles r ON r.nombre_rol = 'Bibliotecario'
WHERE u.nombre_usuario = 'biblio1'
ON CONFLICT DO NOTHING;