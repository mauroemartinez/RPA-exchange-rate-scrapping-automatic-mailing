-- ============================================================================
-- 06. Tabla Fact_Series_Macro: series macroeconómicas con su fecha y su unidad
-- ============================================================================
--
-- QUÉ HACE, EN SIMPLE
--   Crea una tabla nueva, vacía, para guardar series que no son de todos los
--   días hábiles: los agregados monetarios (base monetaria, M2, M3...), la
--   inflación, los indicadores de deuda y el tipo de cambio mayorista que sirve
--   para pasarlos a dólares. Cada fila es "una serie en una fecha", con su
--   valor, su unidad y de dónde salió. No toca ninguna tabla que ya exista.
--
-- POR QUÉ UNA TABLA APARTE
--   La tabla de siempre (Fact_Mercado_Macro) tiene una fila por día hábil. Estas
--   series tienen otras frecuencias (diarias con rezago, mensuales) y otras
--   unidades (millones de pesos, millones de dólares). Meterlas ahí obligaría a
--   inventar datos para los días que no existen.
--
-- CÓMO SE APLICA (una sola vez)
--   Supabase > SQL Editor > New query > pegar este archivo entero > Run.
--   Correrlo dos veces no hace daño: si la tabla ya existe, no hace nada.
--   Después, para cargar la historia completa (también una sola vez):
--       python scripts/agregados_monetarios.py --guardar
--   Desde ahí, la corrida diaria la mantiene al día sola.
--
-- SI NO SE APLICA
--   Nada se rompe: la corrida saltea el guardado de estas series y lo avisa en
--   el log. Los gráficos del mail se arman igual, con lo que baja cada día.
--
-- CÓMO SE VERIFICA
--   SELECT to_regclass('public."Fact_Series_Macro"');   -- devuelve el nombre si existe
--
-- CÓMO SE DESHACE (borra la tabla y sus datos)
--   DROP TABLE IF EXISTS "Fact_Series_Macro";
--
-- Detalle técnico: formato largo, una fila por (serie, Fecha), así conviven
-- series diarias y mensuales sin inventar datos, y cada valor queda con la
-- unidad en la que lo publicó la fuente.

CREATE TABLE IF NOT EXISTS "Fact_Series_Macro" (
    serie           text        NOT NULL,   -- clave estable: 'base_monetaria', 'm3', ...
    "Fecha"         date        NOT NULL,   -- fecha del dato según la fuente
    valor           numeric     NOT NULL,
    frecuencia      char(1)     NOT NULL CHECK (frecuencia IN ('D', 'M', 'T', 'A')),  -- diaria, mensual, trimestral, anual
    unidad          text        NOT NULL,   -- tal cual la publica la fuente
    fuente          text        NOT NULL,   -- 'BCRA', ...
    id_fuente       text,                   -- id de la variable en la fuente (BCRA: idVariable)
    actualizado_en  timestamptz NOT NULL DEFAULT now(),  -- última vez que cambió el valor
    PRIMARY KEY (serie, "Fecha")
);

COMMENT ON TABLE "Fact_Series_Macro" IS
    'Series macro en formato largo (serie, Fecha), con unidad y frecuencia de la fuente. La escribe pipeline.py.';

-- Seguridad, igual que en Fact_Mercado_Macro: RLS activado y sin políticas. El
-- pipeline se conecta como postgres, que no pasa por RLS; la API REST pública de
-- Supabase (roles anon y authenticated) queda sin acceso a la tabla.
ALTER TABLE "Fact_Series_Macro" ENABLE ROW LEVEL SECURITY;
