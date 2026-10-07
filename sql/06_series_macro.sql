-- Fase 3 del roadmap: series macro con su fecha, frecuencia y unidad originales.
--
-- PostgreSQL (Supabase). Se aplica UNA vez, a mano, desde el SQL Editor de
-- Supabase o con psql. Mientras la tabla no exista, el pipeline omite la etapa
-- "series" y sigue; no hace falta coordinar el merge con la migración.
--
-- Formato largo: una fila por serie y fecha. Así conviven series diarias
-- (base monetaria) y mensuales (M3, inflación) sin inventar datos para los días
-- que no existen, y cada valor queda con la unidad en la que lo publicó la fuente.

CREATE TABLE IF NOT EXISTS "Fact_Series_Macro" (
    serie           text        NOT NULL,   -- clave estable: 'base_monetaria', 'm3', ...
    "Fecha"         date        NOT NULL,   -- fecha del dato según la fuente
    valor           numeric     NOT NULL,
    frecuencia      char(1)     NOT NULL CHECK (frecuencia IN ('D', 'M', 'T', 'A')),
    unidad          text        NOT NULL,   -- tal cual la publica la fuente
    fuente          text        NOT NULL,   -- 'BCRA', ...
    id_fuente       text,                   -- id de la variable en la fuente (BCRA: idVariable)
    actualizado_en  timestamptz NOT NULL DEFAULT now(),  -- última vez que cambió el valor
    PRIMARY KEY (serie, "Fecha")
);

COMMENT ON TABLE "Fact_Series_Macro" IS
    'Series macro en formato largo (serie, Fecha), con unidad y frecuencia de la fuente. La escribe pipeline.py.';

-- Igual que Fact_Mercado_Macro: RLS activado y sin políticas. El pipeline se
-- conecta como postgres, que no pasa por RLS; la API REST pública de Supabase
-- (roles anon y authenticated) queda sin acceso a la tabla.
ALTER TABLE "Fact_Series_Macro" ENABLE ROW LEVEL SECURITY;
