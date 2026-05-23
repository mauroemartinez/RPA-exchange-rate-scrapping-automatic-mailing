USE MacroeconomicAnalytics;
GO

DROP TABLE IF EXISTS Fact_Mercado_Macro;
GO

CREATE TABLE Fact_Mercado_Macro (
    Fecha DATE NOT NULL ,
    TCC_Blue DECIMAL(18,2),
    TCV_Blue DECIMAL(18,2),
    TCC_Billete DECIMAL(18,2),
    TCV_Billete DECIMAL(18,2),
    TCC_Divisas DECIMAL(18,2),
    TCV_Divisas DECIMAL(18,2),
    Solidario DECIMAL(18,2),
    TCV_MEP DECIMAL(18,2),
    riesgo_pais DECIMAL(18,2),
    TCC_Euro DECIMAL(18,2),
    TCV_Euro DECIMAL(18,2),
    fed_tea DECIMAL(18,4),
    bcra_tea DECIMAL(18,4)

    CONSTRAINT PK_Fact_Mercado PRIMARY KEY (Fecha)
);
GO

ALTER TABLE Fact_Mercado_Macro
ADD ai_paragraph VARCHAR(MAX) NULL;