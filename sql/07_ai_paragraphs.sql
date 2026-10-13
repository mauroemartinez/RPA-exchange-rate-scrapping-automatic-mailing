ALTER TABLE "Fact_Mercado_Macro" ADD COLUMN IF NOT EXISTS ai_secciones jsonb;

COMMENT ON COLUMN "Fact_Mercado_Macro".ai_secciones IS
    'Comentarios de Gemini por gráfico (paralelas, oficiales, riesgo_pais, btc) y el modelo que los generó.';
