# Fase 3: agregados monetarios y endeudamiento

Estado al 6 de octubre de 2026: **los agregados monetarios están implementados pero todavía no van en el mail**, como pide el roadmap ("integrar los indicadores nuevos al correo una vez que las series y gráficos estén verificados"). **El endeudamiento está sin implementar a propósito**: el roadmap pide definir primero qué significa para el reporte, y esa definición es tuya. Abajo están las opciones, con fuente, frecuencia, unidad y rezago verificados.

## 1. Agregados monetarios

### Series elegidas

Todas salen de la API de estadísticas del BCRA (v4.0), la misma que ya usa el proyecto para la BADLAR y la inflación.

| Clave | Id BCRA | Serie | Frecuencia | Unidad (de la fuente) | Último dato al 06/10 | Var. interanual |
|---|---|---|---|---|---|---|
| `base_monetaria` | 15 | Base monetaria | Diaria | millones de ARS | 02/10/2026 | 14,0% |
| `circulacion_monetaria` | 16 | Circulación monetaria | Diaria | millones de ARS | 02/10/2026 | 22,2% |
| `billetes_publico` | 17 | Billetes y monedas en poder del público | Diaria | millones de ARS | 02/10/2026 | 24,0% |
| `m2` | 109 | M2 | Diaria | millones de ARS | 01/10/2026 | 20,9% |
| `m2_transaccional_privado` | 197 | M2 transaccional del sector privado | Diaria | millones de ARS | 01/10/2026 | 24,9% |
| `m3` | 1624 | M3 en moneda local | Mensual | miles de ARS | 31/07/2026 | 29,7% |
| `inflacion_mensual` | 27 | Inflación mensual | Mensual | porcentaje | 31/08/2026 | |
| `inflacion_interanual` | 28 | Inflación interanual | Mensual | porcentaje | 31/08/2026 | 33,5% (el valor) |

Rezagos: las diarias salen con 2 o 3 días hábiles; el M3 mensual, con unos dos meses.

Por qué estas y no otras:

- **M1, M2 y M3 diarios del "Informe Monetario Diario" (ids 1232, 1233, 1234) no sirven:** la API los lista, pero no tienen datos desde el 7 de mayo de 2026. Por eso el M2 diario sale de la variable 109 y el M3 de la mensual 1624.
- **Las dos inflaciones se guardan aunque ya se usen**: es la recomendación de [evaluacion-cache.md](evaluacion-cache.md). Con la serie en Supabase, el reenvío manual y cualquier análisis van a poder dejar de depender de la API del BCRA, cuando lean de `Fact_Series_Macro`; hoy nada lee de esa tabla todavía.
- **Se guardan en la unidad de la fuente.** La base monetaria en millones y el M3 en miles, tal cual los publica el BCRA. La conversión a billones es solo del gráfico.

### Qué hay en el código

| Pieza | Qué hace |
|---|---|
| `scrapers/agregados.py` | Catálogo de las series (clave, id, frecuencia, unidad) y descarga en paralelo, con paginación para traer la historia completa |
| `transformations.py` | `validar_serie` (vacía, fechas desordenadas, valores no finitos o no positivos, dato atrasado), `variacion_interanual`, `interanual_por_fecha` |
| `data_access.py` | Tabla `Fact_Series_Macro` y su upsert, que solo reescribe valores que cambiaron (el BCRA revisa datos ya publicados) |
| `sql/06_series_macro.sql` | La migración: formato largo `(serie, Fecha)`, con unidad, frecuencia y fuente; RLS activado como en `Fact_Mercado_Macro` |
| `charts.py` | `grafico_agregados`: niveles del último año en billones de ARS y variación interanual contra la inflación |
| `pipeline.py` | Etapa `series`: cada día vuelve a pedir los últimos 120 días y los guarda. Cada serie se valida y se guarda por separado, así que una discontinuada no frena a las demás. Sin la tabla se omite con un aviso; si falla, queda como advertencia y no pone la corrida en rojo |
| `scripts/agregados_monetarios.py` | Resumen por serie y gráfico de prueba; con `--guardar`, carga toda la historia |

Verificación: la migración, el upsert (1000 filas la primera vez, 0 al repetir, 1 al revisar un valor) y RLS se probaron contra un PostgreSQL 16 local descartable, no contra Supabase. El resto tiene tests sin red (`tests/test_agregados.py`).

### Lo que muestra el gráfico hoy

En el último año todos los agregados crecieron por debajo de la inflación interanual (33,5% en agosto): la base monetaria quedó por debajo desde abril de 2026 y hoy crece 14%, el M2 alrededor de 20% y el M3 entre 27% y 30%. Es una contracción en términos reales.

### Para activarlo (pasos tuyos)

1. Aplicar `sql/06_series_macro.sql` en el SQL Editor de Supabase. Es lo único que toca la base de producción, y por eso no lo hice yo.
2. Cargar la historia: `python scripts/agregados_monetarios.py --guardar` (unos 7.500 puntos por serie diaria, desde 1996).
3. Desde ahí, la corrida diaria mantiene la tabla al día sola.
4. Revisar el gráfico (`python scripts/agregados_monetarios.py` lo deja en una carpeta temporal) y decidir si entra en el mail: dónde va, si lleva texto propio y si conviene sumarlo a la respuesta estructurada de Gemini (fase 4).

## 2. Endeudamiento: decisión pendiente

"Endeudamiento" puede querer decir cosas muy distintas, con fuentes y frecuencias que no se parecen. Estas son las opciones que encontré, verificadas el 6 de octubre de 2026:

| | Qué mide | Fuente | Frecuencia y rezago | Unidad | Cómo se obtiene | Esfuerzo |
|---|---|---|---|---|---|---|
| **A** | Deuda bruta de la Administración Central (la "deuda pública" de los diarios: USD 496.676 millones en abril de 2026) | Secretaría de Finanzas | Mensual, ~5 semanas (agosto ya publicado) | millones de USD | Un único Excel, "Serie mensual 2019 - Agosto 2026", en argentina.gob.ar. Sin API | Medio: descargar y leer un Excel cuyo formato puede cambiar sin aviso |
| **B** | Deuda externa total, pública y privada (USD 321.783 millones al primer trimestre de 2026) | INDEC, "Balanza de pagos, posición de inversión internacional y deuda externa" | Trimestral, ~3 meses | millones de USD | Cuadros en Excel de indec.gob.ar | Medio, y para un reporte diario cambia cuatro veces por año |
| **C** | Pasivos del BCRA y financiamiento al Tesoro: letras del BCRA en pesos (id 1258) y en moneda extranjera (1259), posición neta de pases (1261), adelantos transitorios al Gobierno (1268) | BCRA | Diaria, 2 o 3 días hábiles | millones de ARS | La misma API de los agregados: se agregan filas al catálogo | Mínimo |
| **D** | Endeudamiento de familias y empresas: préstamos de las entidades al sector privado (id 26) | BCRA | Diaria, 2 o 3 días hábiles | millones de ARS | La misma API | Mínimo |

Lo que descarté: la API de series de tiempo de datos.gob.ar tiene series de deuda, pero las que encontré están discontinuadas (la deuda externa privada termina en 2017 y el gasto en servicios de deuda en 2023).

Mi recomendación, si el reporte tiene que seguir siendo diario: **C y D ya**, porque salen de la misma API con el mismo código y se actualizan todos los días; y **A como dato mensual** si lo que buscás es la deuda pública propiamente dicha, aceptando que depende de un Excel. B la dejaría afuera del mail diario.

Para avanzar necesito que me digas:

1. Qué opción u opciones (A, B, C, D, otra).
2. Si la deuda en dólares (A, B) se muestra en dólares o convertida a pesos, y con qué tipo de cambio.
3. Si va en el mail diario o en una sección que cambie solo cuando hay dato nuevo.
