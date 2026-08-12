-- Bulk Load desde un archivo CSV local o de red hacia SQL Server
BULK INSERT Fact_Mercado_Macro
FROM 'C:\TuRuta\Seguimiento Macroeconómico.csv' 
WITH (
    FIRSTROW = 2,                 
    FIELDTERMINATOR = ',',        
    ROWTERMINATOR = '\n',       
    TABLOCK,                      
    DATAFILETYPE = 'char',     
    CODEPAGE = '65001'
     )