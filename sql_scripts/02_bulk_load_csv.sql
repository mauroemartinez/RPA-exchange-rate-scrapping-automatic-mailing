USE MacroeconomicAnalytics;
GO

-- A simple vista veo valores de tipos de cambio billete que est+an multiplicados por 100
-- Habría que a los mayores de 1000 antes de 2020 dividrlos por 100
SELECT * FROM Fact_Mercado_Macro;



-- El riesgo país y las tasas de interés parecen ok
-- Sería bueno ver si puedo conseguir las tasas y el riesgo país de alguna API en vez de scraping
SELECT Fecha, riesgo_pais, bcra_tea, fed_tea FROM Fact_Mercado_Macro;

SELECT * FROM Fact_Mercado_Macro;

SELECT COUNT(*) FROM Fact_Mercado_Macro;

