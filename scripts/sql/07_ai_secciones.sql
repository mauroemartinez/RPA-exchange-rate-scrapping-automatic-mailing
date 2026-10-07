-- ============================================================================
-- 07. Columna ai_secciones: los comentarios de la IA para cada gráfico
-- ============================================================================
--
-- QUÉ HACE, EN SIMPLE
--   Agrega una columna nueva, vacía, al final de la tabla de siempre
--   (Fact_Mercado_Macro), al lado de ai_paragraph. Ahí se guardan, en formato
--   JSON, los comentarios que Gemini escribe para cada gráfico del mail. No
--   modifica ni borra ningún dato que ya exista.
--
-- POR QUÉ
--   El párrafo general ya se guardaba en ai_paragraph, y ahí sigue. Los
--   comentarios por gráfico son varios textos por día; guardarlos en la misma
--   fila, como JSON, permite reenviar el mail de un día con sus comentarios
--   (scripts/reenvio_manual.py) sin volver a pedírselos a Gemini.
--
-- QUÉ GUARDA (ejemplo)
--   {"paralelas": "...", "oficiales": "...", "riesgo_pais": "...",
--    "btc": "..." o null, "modelo": "gemini-..."}
--
-- CÓMO SE APLICA (una sola vez)
--   Supabase > SQL Editor > New query > pegar este archivo entero > Run.
--   Correrlo dos veces no hace daño (IF NOT EXISTS).
--   Es seguro aunque sigas usando el notebook: el notebook arma la tabla del mail
--   con las primeras 14 columnas y guarda una lista fija de columnas, así que una
--   columna nueva al final no lo afecta.
--
-- QUÉ CAMBIA DESPUÉS
--   Desde la primera corrida de pipeline.py con la columna, se pide a Gemini el
--   resumen y un comentario por gráfico en una sola llamada, y van debajo de cada
--   gráfico del mail. Sin la columna, sigue el párrafo único de siempre.
--
-- CÓMO SE VERIFICA
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'Fact_Mercado_Macro' AND column_name = 'ai_secciones';
--
-- CÓMO SE DESHACE (borra los comentarios; los párrafos quedan)
--   ALTER TABLE "Fact_Mercado_Macro" DROP COLUMN IF EXISTS ai_secciones;
--
-- Detalle técnico: la columna va al final a propósito. El mail arma la tabla de
-- cotizaciones con df.iloc[:, :14]; una columna nueva en el medio le correría
-- las columnas.

ALTER TABLE "Fact_Mercado_Macro" ADD COLUMN IF NOT EXISTS ai_secciones jsonb;

COMMENT ON COLUMN "Fact_Mercado_Macro".ai_secciones IS
    'Comentarios de Gemini por gráfico (paralelas, oficiales, riesgo_pais, btc) y el modelo que los generó.';
