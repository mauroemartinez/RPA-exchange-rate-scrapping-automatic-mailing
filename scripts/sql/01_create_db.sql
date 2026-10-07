USE MacroeconomicAnalytics;
GO

TRUNCATE TABLE Fact_Mercado_Macro;
GO

BULK INSERT Fact_Mercado_Macro
-- Deben tener la DB y el CSV la misma estructura, columnas en mismo orden, mismo tipo
FROM 'C:\Users\siqui\OneDrive\Escritorio\Mauro\UNLaM\RPA Seguimiento Macroeconómico\Seguimiento Macroeconómico.csv'
WITH (
    FIELDTERMINATOR = ',',     
    ROWTERMINATOR = '\n',      
    FIRSTROW = 2,              -- Saltar encabezados
    KEEPIDENTITY	
);	
GO