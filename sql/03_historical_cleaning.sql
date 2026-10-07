USE MacroeconomicAnalytics

-- valores de TCV_Billete y TCC_Billete / 100 cuando pasen los 1000 antes de 2022
UPDATE Fact_Mercado_Macro
SET 
    TCV_Billete = TCC_Billete / 100
WHERE Fecha < '2022-01-01' 
  AND TCV_Billete > 1000;

UPDATE Fact_Mercado_Macro
SET 
    TCC_Billete = TCC_Billete / 100
WHERE Fecha < '2022-01-01' 
  AND TCC_Billete > 1000;

UPDATE Fact_Mercado_Macro
SET TCC_Divisas = 1383.50
WHERE Fecha = '2026-04-06';

