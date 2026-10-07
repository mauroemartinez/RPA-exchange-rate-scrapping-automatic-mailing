# Evaluación: presentación en PowerPoint y dashboard en Streamlit

Roadmap, fase 5: *evaluar la generación automática de un PowerPoint ejecutivo* y *evaluar un dashboard en Streamlit conectado al histórico completo*, sin que ninguno se convierta en otra implementación del pipeline diario.

Para evaluar con algo concreto hice un prototipo de cada uno. **El PowerPoint ya es parte de la corrida diaria** (la decisión está abajo); el dashboard sigue siendo un prototipo que se corre a mano y solo lee.

## PowerPoint: `presentacion.py`

```bash
python scripts/presentacion_ejecutiva.py                # .pptx en una carpeta temporal
python scripts/presentacion_ejecutiva.py --salida DIR
```

`python-pptx` ya viene pineado en `requirements-dev.txt`; la imagen de producción no lo instala.

Arma seis diapositivas en 16:9 con lo que la corrida ya dejó: portada; un tablero con blue, MEP, billete, riesgo país, BADLAR y el forward de Fisher, cada uno con su variación; el párrafo de IA; y tres de gráficos (tipos de cambio y riesgo país, inflación con variaciones acumuladas, BTC). Si la fila tiene los comentarios por gráfico de la fase 4, van al lado de cada gráfico (debajo, en el de BTC). Usa los colores del mail.

Lo que salió de la prueba, con los datos del 6 de octubre:

- **Funciona y se ve bien.** Lo exporté a imágenes con PowerPoint para revisarlo. El archivo pesa unos 460 KB.
- **No suma llamadas ni datos nuevos.** Lee el histórico de Supabase (solo lectura), del que usa las dos últimas filas, y los .jpg de `Previews/`, y reutiliza `transformations`, `email_report` e `ia_generator`.
- **Costo:** una dependencia (`python-pptx`, que trae `lxml`) y unas 200 líneas. El armado es posicional: si cambia el tamaño de un gráfico, hay que retocar la ubicación.
- **No exporta a PDF.** `python-pptx` solo escribe .pptx; para PDF hace falta PowerPoint o LibreOffice en la máquina que corre.

Mi recomendación era semanal y fuera de git, por el peso. **La decisión (7 de octubre de 2026) fue diaria y en git**, para que GitHub tenga siempre la última: la corrida la arma en la etapa `presentacion` y la commitea con los gráficos como `Previews/Reporte Ejecutivo.pptx`, con el mismo nombre todos los días. En la corrida usa los datos y los textos de IA que ya tiene en memoria, así que no suma consultas; `scripts/presentacion_ejecutiva.py` sigue sirviendo para armarla a mano desde Supabase.

El costo, para tenerlo a la vista: el repo pesa hoy unos 49 MB, casi todo de los gráficos diarios (unos 550 KB por día hábil). La presentación agrega unos 460 KB por día, así que el repo pasa a crecer unos 250 MB por año en vez de 140. GitHub recomienda que un repo no pase de 1 GB, así que hay margen para varios años. Si algún día molesta, la presentación se puede mover a una rama aparte que guarde solo la última.

## Streamlit: `dashboard/app.py`

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Muestra los indicadores del día, un período elegible (seis meses por defecto) y pestañas de cotizaciones, brechas, riesgo país, tasas, los últimos párrafos de IA y los datos, con descarga a CSV. Probado contra Supabase: levanta las 7.107 ruedas desde 1998.

Decisiones del prototipo:

- **No importa `config.py`.** `config` exige todas las credenciales del pipeline (mail, Gemini, FRED). Un dashboard publicado no tiene por qué tenerlas: le alcanza con `DASHBOARD_DB_URL`, la URL de un usuario de solo lectura, que toma de los secrets de Streamlit o del entorno. Si no está, usa `SUPABASE_DB_URL` (secrets, entorno o `.env`) y lo avisa en pantalla, para que nadie lo publique así sin darse cuenta.
- **Solo lee.** Cada consulta corre en una transacción `READ ONLY`, y el resultado se cachea una hora (`st.cache_data`), así que la base recibe a lo sumo una consulta por hora por proceso.
- **También lee el CSV del mail** (`DASHBOARD_CSV=...`), sin base: sirve para explorar offline y es como lo prueban los tests.
- **Dependencias aparte** (`dashboard/requirements.txt`): Streamlit trae pyarrow y altair, que el pipeline no necesita.

### Si se publica: un usuario de solo lectura

Publicarlo con la URL actual sería exponer el usuario `postgres`, que puede escribir y borrar todo. Antes de publicarlo hay que crear un rol de solo lectura. Ojo con RLS: `Fact_Mercado_Macro` tiene RLS activado y sin políticas, así que un rol nuevo vería la tabla **vacía** hasta que se le dé una política:

```sql
CREATE ROLE dashboard_lectura LOGIN PASSWORD '<una clave nueva>';
GRANT USAGE ON SCHEMA public TO dashboard_lectura;
GRANT SELECT ON "Fact_Mercado_Macro" TO dashboard_lectura;
CREATE POLICY lectura_dashboard ON "Fact_Mercado_Macro" FOR SELECT TO dashboard_lectura USING (true);
```

Con el pooler de Supabase, el usuario de la URL lleva el id del proyecto: `dashboard_lectura.<id-del-proyecto>`, y esa URL es la que va en `DASHBOARD_DB_URL`. No lo ejecuté: es un cambio de permisos en la base de producción.

Recomendación: **vale la pena si hay alguien que lo vaya a usar.** Para vos solo, alcanza con correrlo local. Para suscriptores, Streamlit Community Cloud es gratis para repos públicos (este lo es), con el rol de solo lectura de arriba en los secrets. Lo que no recomiendo es sumarle escritura, refresco del pipeline o cálculos propios: en ese momento pasaría a ser una segunda implementación del reporte.
