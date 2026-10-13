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

ALTER TABLE "Fact_Series_Macro" ENABLE ROW LEVEL SECURITY;
