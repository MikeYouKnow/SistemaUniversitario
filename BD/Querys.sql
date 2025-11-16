BEGIN;

-- =========================================
-- 1) CATÁLOGOS BÁSICOS
-- =========================================

-- RRHH
INSERT INTO rrhh.cat_nacionalidades(nombre) VALUES ('Mexicana') ON CONFLICT DO NOTHING;

INSERT INTO rrhh.cat_sexos(nombre)
VALUES ('Hombre'), ('Mujer')
ON CONFLICT DO NOTHING;

INSERT INTO rrhh.cat_centros_trabajo(nombre)
VALUES ('Campus Principal')
ON CONFLICT DO NOTHING;

INSERT INTO rrhh.cat_puestos(clave, nombre, nivel)
VALUES
  ('ADM', 'Administrador de sistema', 'A'),
  ('DOC', 'Docente de asignatura', 'B'),
  ('BIB', 'Bibliotecario', 'C'),
  ('COO', 'Coordinador académico', 'B')
ON CONFLICT DO NOTHING;

INSERT INTO rrhh.cat_grados_academicos(nombre)
VALUES ('Licenciatura'), ('Maestría')
ON CONFLICT DO NOTHING;

INSERT INTO rrhh.cat_tipos_documento(nombre)
VALUES ('INE'), ('Título'), ('Cédula profesional')
ON CONFLICT DO NOTHING;


-- ACADÉMICO
INSERT INTO academico.cat_genero(nombre)
VALUES ('Masculino'), ('Femenino')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_estado_civil(nombre)
VALUES ('Soltero'), ('Casado')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_tenencia_vivienda(nombre)
VALUES ('Propia'), ('Rentada')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_escolaridad(nombre)
VALUES ('Primaria'), ('Secundaria'), ('Bachillerato'), ('Licenciatura')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_ocupacion(nombre)
VALUES ('Estudiante'), ('Empleado'), ('Docente')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_beca(nombre)
VALUES ('Ninguna'), ('Beca institucional')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_campus(nombre)
VALUES ('Campus Mante')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_modalidad(nombre)
VALUES ('Escolarizada')
ON CONFLICT DO NOTHING;

INSERT INTO academico.cat_estado_inscripcion(nombre)
VALUES ('Inscrito'), ('Baja')
ON CONFLICT DO NOTHING;


-- INFRAESTRUCTURA
INSERT INTO infraestructura.tipo_aula(nombre)
VALUES
  ('Aula teórica'),
  ('Laboratorio de cómputo'),
  ('Taller de redes'),
  ('Taller industrial')
ON CONFLICT DO NOTHING;

INSERT INTO infraestructura.edificio(numero, nombre)
VALUES
  (1, 'Edificio 1'),
  (2, 'Edificio 2')
ON CONFLICT DO NOTHING;


-- BIBLIOTECA
INSERT INTO biblioteca.Temas(nombre_tema)
VALUES ('Programación'), ('Bases de Datos'), ('Redes'), ('Matemáticas')
ON CONFLICT DO NOTHING;

INSERT INTO biblioteca.Clasificaciones(codigo_clasificacion, descripcion)
VALUES
  ('QA76', 'Computación'),
  ('QA276', 'Probabilidad y estadística')
ON CONFLICT DO NOTHING;

INSERT INTO biblioteca.Editoriales(nombre_editorial, pais)
VALUES
  ('Pearson', 'México'),
  ('McGraw-Hill', 'México')
ON CONFLICT DO NOTHING;

INSERT INTO biblioteca.Autores(nombre_autor, nacionalidad)
VALUES
  ('Abraham Silberschatz', 'Estados Unidos'),
  ('Andrew S. Tanenbaum', 'Países Bajos')
ON CONFLICT DO NOTHING;


-- =========================================
-- 2) ROLES Y USUARIOS
-- =========================================

INSERT INTO seguridad.roles(nombre_rol, descripcion)
VALUES
  ('Administrador', 'Administrador del sistema'),
  ('Docente', 'Profesor'),
  ('Estudiante', 'Alumno'),
  ('Bibliotecario', 'Gestor de biblioteca'),
  ('Coordinador', 'Coordinador académico')
ON CONFLICT DO NOTHING;


-- Usuarios (contraseña sin hash → Trigger la cifra)
INSERT INTO seguridad.usuarios(nombre_usuario, correo_electronico, contrasena_hash)
VALUES
  ('admin1',  'admin@demo.edu.mx',    'Admin123*'),
  ('doc1',    'docente1@demo.edu.mx', 'Docente123*'),
  ('doc2',    'docente2@demo.edu.mx', 'Docente123*'),
  ('biblio1', 'biblio1@demo.edu.mx',  'Biblio123*'),
  ('coord1',  'coord1@demo.edu.mx',   'Coord123*'),
  ('estu1',   'estu1@demo.edu.mx',    'Estu123*'),
  ('estu2',   'estu2@demo.edu.mx',    'Estu123*')
ON CONFLICT DO NOTHING;


-- Asignación de roles
INSERT INTO seguridad.usuario_rol(id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
FROM seguridad.usuarios u
JOIN seguridad.roles r
 ON (
      (u.nombre_usuario='admin1'   AND r.nombre_rol='Administrador') OR
      (u.nombre_usuario='doc1'     AND r.nombre_rol='Docente')       OR
      (u.nombre_usuario='doc2'     AND r.nombre_rol='Docente')       OR
      (u.nombre_usuario='biblio1'  AND r.nombre_rol='Bibliotecario') OR
      (u.nombre_usuario='coord1'   AND r.nombre_rol='Coordinador')   OR
      (u.nombre_usuario='estu1'    AND r.nombre_rol='Estudiante')    OR
      (u.nombre_usuario='estu2'    AND r.nombre_rol='Estudiante')
 )
ON CONFLICT DO NOTHING;


-- =========================================
-- 3) RRHH: PERSONAL
-- =========================================

-- Admin
INSERT INTO rrhh.personal(
  nombre, apellido_paterno, apellido_materno,
  fecha_nacimiento, correo_institucional,
  rfc_text, curp_text,
  fk_nacionalidad, fk_centro_trabajo, fk_sexo, fk_estado_civil,
  fk_id_usuario
)
VALUES (
  'Carlos', 'Administrador', 'Demo',
  '1985-01-01', 'admin@demo.edu.mx',
  'AADC850101XXX', 'AADC850101HDFRRL01',
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT id_centro_trabajo FROM rrhh.cat_centros_trabajo WHERE nombre='Campus Principal'),
  (SELECT id_sexo FROM rrhh.cat_sexos WHERE nombre='Hombre'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Soltero'),
  (SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='admin1')
)
ON CONFLICT DO NOTHING;


-- Docente 1
INSERT INTO rrhh.personal(
  nombre, apellido_paterno, apellido_materno,
  fecha_nacimiento, correo_institucional,
  rfc_text, curp_text,
  fk_nacionalidad, fk_centro_trabajo, fk_sexo, fk_estado_civil,
  fk_id_usuario
)
VALUES (
  'Juan', 'Pérez', 'Lozano',
  '1980-05-10', 'docente1@demo.edu.mx',
  'PELJ800510XXX', 'PELJ800510HDFLRN01',
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT id_centro_trabajo FROM rrhh.cat_centros_trabajo WHERE nombre='Campus Principal'),
  (SELECT id_sexo FROM rrhh.cat_sexos WHERE nombre='Hombre'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Casado'),
  (SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='doc1')
)
ON CONFLICT DO NOTHING;

-- Docente 2
INSERT INTO rrhh.personal(
  nombre, apellido_paterno, apellido_materno,
  fecha_nacimiento, correo_institucional,
  rfc_text, curp_text,
  fk_nacionalidad, fk_centro_trabajo, fk_sexo, fk_estado_civil,
  fk_id_usuario
)
VALUES (
  'María', 'Gómez', 'Ríos',
  '1988-03-15', 'docente2@demo.edu.mx',
  'GORM880315XXX', 'GORM880315MDFLRS09',
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT id_centro_trabajo FROM rrhh.cat_centros_trabajo WHERE nombre='Campus Principal'),
  (SELECT id_sexo FROM rrhh.cat_sexos WHERE nombre='Mujer'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Soltero'),
  (SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='doc2')
)
ON CONFLICT DO NOTHING;

-- Bibliotecario
INSERT INTO rrhh.personal(
  nombre, apellido_paterno, apellido_materno,
  fecha_nacimiento, correo_institucional,
  rfc_text, curp_text,
  fk_nacionalidad, fk_centro_trabajo, fk_sexo, fk_estado_civil,
  fk_id_usuario
)
VALUES (
  'Luis', 'Ramírez', 'Castro',
  '1985-06-20', 'biblio1@demo.edu.mx',
  'RACL850620XXX', 'RACL850620HDFRTS07',
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT id_centro_trabajo FROM rrhh.cat_centros_trabajo WHERE nombre='Campus Principal'),
  (SELECT id_sexo FROM rrhh.cat_sexos WHERE nombre='Hombre'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Casado'),
  (SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='biblio1')
)
ON CONFLICT DO NOTHING;

-- Coordinador
INSERT INTO rrhh.personal(
  nombre, apellido_paterno, apellido_materno,
  fecha_nacimiento, correo_institucional,
  rfc_text, curp_text,
  fk_nacionalidad, fk_centro_trabajo, fk_sexo, fk_estado_civil,
  fk_id_usuario
)
VALUES (
  'Ana', 'López', 'Coordinadora',
  '1987-09-09', 'coord1@demo.edu.mx',
  'LOCA870909XXX', 'LOCA870909MDFRNN03',
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT id_centro_trabajo FROM rrhh.cat_centros_trabajo WHERE nombre='Campus Principal'),
  (SELECT id_sexo FROM rrhh.cat_sexos WHERE nombre='Mujer'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Soltero'),
  (SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='coord1')
)
ON CONFLICT DO NOTHING;


-- =========================================
-- 4) AULAS
-- =========================================

INSERT INTO infraestructura.aula(
  clave, edificio_id, piso, posicion, capacidad, observaciones, tipo_id
)
VALUES
  ('A-101',
   (SELECT edificio_id FROM infraestructura.edificio WHERE numero=1),
   1, 1, 40, 'Aula teórica piso 1',
   (SELECT tipo_id FROM infraestructura.tipo_aula WHERE nombre='Aula teórica')),

  ('A-201',
   (SELECT edificio_id FROM infraestructura.edificio WHERE numero=1),
   2, 1, 40, 'Aula teórica piso 2',
   (SELECT tipo_id FROM infraestructura.tipo_aula WHERE nombre='Aula teórica')),

  ('LABC-1',
   (SELECT edificio_id FROM infraestructura.edificio WHERE numero=2),
   1, 1, 30, 'Laboratorio de cómputo',
   (SELECT tipo_id FROM infraestructura.tipo_aula WHERE nombre='Laboratorio de cómputo')),

  ('RED-1',
   (SELECT edificio_id FROM infraestructura.edificio WHERE numero=2),
   1, 2, 25, 'Taller de redes',
   (SELECT tipo_id FROM infraestructura.tipo_aula WHERE nombre='Taller de redes'))
ON CONFLICT DO NOTHING;


-- =========================================
-- 5) PLANES
-- =========================================

INSERT INTO planes.carrera(clave, nombre)
VALUES ('ISC', 'Ingeniería en Sistemas Computacionales')
ON CONFLICT DO NOTHING;

INSERT INTO planes.materia(clave, nombre)
VALUES
  ('PROG1', 'Programación I'),
  ('PROG2', 'Programación II'),
  ('BD1',   'Taller de Bases de Datos'),
  ('REDES', 'Redes de Computadoras')
ON CONFLICT DO NOTHING;

-- carrera_materia
INSERT INTO planes.carrera_materia(carrera_id, materia_id, semestre, horas_teoricas, horas_practicas)
SELECT
  c.carrera_id, m.materia_id,
  CASE m.clave
    WHEN 'PROG1' THEN 1
    WHEN 'PROG2' THEN 2
    WHEN 'BD1'   THEN 4
    WHEN 'REDES' THEN 4
  END,
  2, 2
FROM planes.carrera c
JOIN planes.materia m ON TRUE
WHERE c.clave='ISC'
ON CONFLICT DO NOTHING;


-- materia_alta
INSERT INTO planes.materia_alta(ciclo, carrera_materia_id, fk_personal, esta_activo)
SELECT
  '2025-1',
  cm.carrera_materia_id,
  CASE m.clave
    WHEN 'PROG1' THEN (SELECT id_personal FROM rrhh.personal p JOIN seguridad.usuarios u ON p.fk_id_usuario=u.id_usuario WHERE u.nombre_usuario='doc1')
    WHEN 'PROG2' THEN (SELECT id_personal FROM rrhh.personal p JOIN seguridad.usuarios u ON p.fk_id_usuario=u.id_usuario WHERE u.nombre_usuario='doc1')
    WHEN 'BD1'   THEN (SELECT id_personal FROM rrhh.personal p JOIN seguridad.usuarios u ON p.fk_id_usuario=u.id_usuario WHERE u.nombre_usuario='doc2')
    WHEN 'REDES' THEN (SELECT id_personal FROM rrhh.personal p JOIN seguridad.usuarios u ON p.fk_id_usuario=u.id_usuario WHERE u.nombre_usuario='doc2')
  END,
  TRUE
FROM planes.carrera_materia cm
JOIN planes.materia m ON cm.materia_id = m.materia_id
JOIN planes.carrera c ON c.carrera_id = cm.carrera_id
WHERE c.clave='ISC'
ON CONFLICT DO NOTHING;

-- Relación tipo de aula
INSERT INTO planes.carrera_materia_aula_tipo(carrera_materia_id, tipo_id)
SELECT cm.carrera_materia_id, ta.tipo_id
FROM planes.carrera_materia cm
JOIN planes.materia m ON m.materia_id = cm.materia_id
JOIN infraestructura.tipo_aula ta
 ON (
      (m.clave='BD1'   AND ta.nombre='Laboratorio de cómputo') OR
      (m.clave='REDES' AND ta.nombre='Taller de redes')
    )
ON CONFLICT DO NOTHING;


-- horario
INSERT INTO infraestructura.horario_asignacion(
  fk_materia_alta, fk_aula, dia_semana, hora_inicio, hora_fin
)
VALUES (
  (SELECT ma.materia_alta_id
   FROM planes.materia_alta ma
   JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
   JOIN planes.materia m ON m.materia_id = cm.materia_id
   WHERE ma.ciclo='2025-1' AND m.clave='BD1'
   LIMIT 1),
  (SELECT aula_id FROM infraestructura.aula WHERE clave='LABC-1'),
  1, TIME '08:00', TIME '10:00'
)
ON CONFLICT DO NOTHING;


-- =========================================
-- 6) ALUMNOS
-- =========================================

INSERT INTO academico.alumnos(
  numero_control, curp, nombre, apellido_paterno, apellido_materno,
  fecha_nacimiento, genero_id, estado_civil_id,
  fk_nacionalidad, fk_campus, fk_modalidad
)
VALUES
(
  '2501E0001', 'TEST050101HDFLRS01', 'Miguel', 'Cabrera', 'Torres',
  '2005-01-01',
  (SELECT genero_id FROM academico.cat_genero WHERE nombre='Masculino'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Soltero'),
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT campus_id FROM academico.cat_campus WHERE nombre='Campus Mante'),
  (SELECT modalidad_id FROM academico.cat_modalidad WHERE nombre='Escolarizada')
),
(
  '2501E0002', 'TEST050202HDFLRS02', 'Laura', 'Hernández', 'Pérez',
  '2005-02-02',
  (SELECT genero_id FROM academico.cat_genero WHERE nombre='Femenino'),
  (SELECT estado_civil_id FROM academico.cat_estado_civil WHERE nombre='Soltero'),
  (SELECT id_nacionalidad FROM rrhh.cat_nacionalidades WHERE nombre='Mexicana'),
  (SELECT campus_id FROM academico.cat_campus WHERE nombre='Campus Mante'),
  (SELECT modalidad_id FROM academico.cat_modalidad WHERE nombre='Escolarizada')
)
ON CONFLICT DO NOTHING;


-- Contacto
INSERT INTO academico.contacto(
  numero_control, correo_institucional, correo_personal, telefono, direccion
)
VALUES
('2501E0001', '2501E0001@itsemante.edu.mx', 'estu1@mail.com', '8341000001', 'Calle 1, Mante'),
('2501E0002', '2501E0002@itsemante.edu.mx', 'estu2@mail.com', '8341000002', 'Calle 2, Mante')
ON CONFLICT DO NOTHING;


-- Relación usuario-alumno
INSERT INTO seguridad.auth_user_alumno(user_id, numero_control)
VALUES
((SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='estu1'), '2501E0001'),
((SELECT id_usuario FROM seguridad.usuarios WHERE nombre_usuario='estu2'), '2501E0002')
ON CONFLICT DO NOTHING;


-- Inscripción (BD1 para estu1)
INSERT INTO academico.alumno_inscripcion(
  fk_alumno, fk_materia_alta, fk_estado, calificacion
)
VALUES (
  '2501E0001',
  (SELECT ma.materia_alta_id
   FROM planes.materia_alta ma
   JOIN planes.carrera_materia cm ON cm.carrera_materia_id = ma.carrera_materia_id
   JOIN planes.materia m ON m.materia_id = cm.materia_id
   WHERE ma.ciclo='2025-1' AND m.clave='BD1'
   LIMIT 1),
  (SELECT estado_id FROM academico.cat_estado_inscripcion WHERE nombre='Inscrito'),
  NULL
)
ON CONFLICT DO NOTHING;


-- =========================================
-- 7) BIBLIOTECA
-- =========================================

INSERT INTO biblioteca.Libros(
  id_clasificacion, titulo_libro, id_editorial,
  edicion, anio_edicion, isbn, fuente_recurso, incluye_cd
)
VALUES
(
  (SELECT id_clasificacion FROM biblioteca.Clasificaciones WHERE codigo_clasificacion='QA76'),
  'Sistemas Operativos Modernos',
  (SELECT id_editorial FROM biblioteca.Editoriales WHERE nombre_editorial='Pearson'),
  4, 2015, 9780133591620, 'Compra', FALSE
),
(
  (SELECT id_clasificacion FROM biblioteca.Clasificaciones WHERE codigo_clasificacion='QA76'),
  'Fundamentos de Bases de Datos',
  (SELECT id_editorial FROM biblioteca.Editoriales WHERE nombre_editorial='McGraw-Hill'),
  6, 2011, 9780073523323, 'Compra', FALSE
)
ON CONFLICT DO NOTHING;


INSERT INTO biblioteca.Libros_Temas(id_libro, id_tema)
SELECT l.id_libro, t.id_tema
FROM biblioteca.Libros l
JOIN biblioteca.Temas t ON (
  (l.titulo_libro='Sistemas Operativos Modernos' AND t.nombre_tema='Programación') OR
  (l.titulo_libro='Fundamentos de Bases de Datos' AND t.nombre_tema='Bases de Datos')
)
ON CONFLICT DO NOTHING;


INSERT INTO biblioteca.Autores_Libros(id_libro, id_autor)
SELECT l.id_libro, a.id_autor
FROM biblioteca.Libros l
JOIN biblioteca.Autores a ON (
  (l.titulo_libro='Sistemas Operativos Modernos' AND a.nombre_autor='Andrew S. Tanenbaum') OR
  (l.titulo_libro='Fundamentos de Bases de Datos' AND a.nombre_autor='Abraham Silberschatz')
)
ON CONFLICT DO NOTHING;


INSERT INTO biblioteca.Inventario(id_libro, cantidad, cantidad_disponible, ubicacion)
SELECT id_libro, 5, 4, 'Estante A'
FROM biblioteca.Libros
WHERE titulo_libro IN ('Sistemas Operativos Modernos', 'Fundamentos de Bases de Datos')
ON CONFLICT DO NOTHING;


INSERT INTO biblioteca.Prestamos(
  fk_alumno, id_libro, fecha_devolucion_estimada, estado
)
VALUES (
  '2501E0001',
  (SELECT id_libro FROM biblioteca.Libros WHERE titulo_libro='Fundamentos de Bases de Datos'),
  NOW() + INTERVAL '7 days',
  'Activo'
)
ON CONFLICT DO NOTHING;


COMMIT;
