-- Fase 4 del roadmap: comentarios de Gemini por gráfico, generados en la misma
-- llamada que el párrafo diario.
--
-- PostgreSQL (Supabase). Se aplica UNA vez, a mano. Mientras la columna no
-- exista, el pipeline sigue generando solo el párrafo único de siempre; apenas
-- existe, pasa solo a la llamada estructurada. No hace falta coordinar el merge
-- con la migración.
--
-- La columna va al final de la tabla a propósito: el mail arma la tabla de
-- cotizaciones con df.iloc[:, :14], así que una columna nueva en el medio le
-- correría las columnas.
--
-- Contenido: {"paralelas": "...", "oficiales": "...", "riesgo_pais": "...",
--             "btc": "..." o null, "modelo": "gemini-..."}
-- El párrafo general sigue en ai_paragraph, como siempre.

ALTER TABLE "Fact_Mercado_Macro" ADD COLUMN IF NOT EXISTS ai_secciones jsonb;

COMMENT ON COLUMN "Fact_Mercado_Macro".ai_secciones IS
    'Comentarios de Gemini por gráfico (paralelas, oficiales, riesgo_pais, btc) y el modelo que los generó.';
