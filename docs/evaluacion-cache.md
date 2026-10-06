# Evaluación: caché de consultas a las fuentes

Roadmap, fase 2: *evaluar una caché para las consultas repetidas, definida por fuente, período y fecha de publicación*.

**Conclusión: no conviene implementar una caché hoy.** Ninguna fuente HTTP pesa ni tarda lo suficiente para que valga la complejidad, y la parte lenta de la corrida es un dato en vivo que por definición no se puede reutilizar. Abajo están las mediciones y lo que sí recomiendo.

## Mediciones (6 de octubre de 2026, desde la PC de desarrollo)

Cada fuente medida por separado, una sola vez, con solo lecturas.

| Fuente | Qué devuelve | Tamaño | Tiempo |
|---|---|---|---|
| BNA (Playwright) | Billete y divisas del momento | página web | 12,8 s |
| Ámbito (Playwright) | MEP y euro blue del momento | página web | 4,0 s |
| DolarHoy (Playwright) | Blue del momento | página web | 1,8 s |
| Riesgo país (ArgentinaDatos `/ultimo`) | Último cierre publicado | 43 bytes | 0,45 s |
| BCRA variable 140 (BADLAR) | Serie entera: 1000 puntos, ago/2022 a hoy | 46 KB | 0,21 s |
| BCRA variable 27 (inflación) | Serie entera: 1000 puntos, may/1943 a hoy | 45 KB | 0,12 s |
| FRED (EFFR) | Últimas 10 observaciones | 1,2 KB | 0,65 s |
| Yahoo Finance (BTC) | 406 velas diarias | | 1,1 s |

En la corrida real las seis primeras fuentes van en paralelo y la etapa de scraping tarda unos 25 s, dominada por BNA (los tres Chromium compiten por la misma máquina).

## Fuente por fuente

| Fuente | Cada cuánto cambia el dato | ¿Caché? | Por qué |
|---|---|---|---|
| BNA, DolarHoy, Ámbito | Durante el día | No | Es la cotización del momento: reutilizarla sería guardar un valor viejo como si fuera de hoy. |
| Riesgo país | Una vez por día hábil, con un día de rezago | No | 43 bytes. La fecha real del dato ya viaja con el valor (`riesgo_pais_fecha`). |
| BADLAR (BCRA 140) | Una vez por día hábil, con dos días de rezago | No; mejor pedir menos | Se descargan 1000 puntos para usar el último. Si algún día pesa, alcanza con pedir un rango de fechas en vez de la serie entera. |
| Inflación (BCRA 27) | Una vez por mes, a mediados de mes | Es la única candidata | Cambia una vez por mes, pero ahorraría 0,1 s. El valor real está en otro lado: ver abajo. |
| EFFR (FRED) | Una vez por día hábil de EE.UU. | No | 1,2 KB. |
| BTC (Yahoo) | Continuo | No | La vela del día cambia hasta el cierre en UTC. |
| Párrafo de Gemini | Uno por día | Ya está resuelto | Se guarda en `ai_paragraph`. El reenvío manual lo reutiliza y una corrida con `--forzar` lo regenera a propósito. |
| Historial de Supabase | Una fila por día | No | 1,4 s para 7107 filas, y la corrida necesita la tabla completa para el CSV adjunto. |

## Lo que sí recomiendo

1. **Persistir la serie de inflación en Supabase** en lugar de cachearla. Es lo que proponía el README ("API Data Persistence in Supabase") y encaja con la fase 3, que va a necesitar una tabla para series mensuales con su fecha de publicación. Con la inflación guardada, `scripts/reenvio_manual.py` dejaría de depender de la API del BCRA, que hoy es lo único que vuelve a consultar.
2. **Si hace falta acelerar la corrida, el lugar es BNA**, no las APIs: son 13 de los 25 segundos. Por ejemplo, bloquear imágenes y fuentes con `page.route()` antes del `goto`. Es una optimización de scraping y conviene medirla aparte, porque toca un selector que ya se rompió una vez.
3. **No mezclar caché con la detección de datos viejos.** Hoy el pipeline avisa cuando el riesgo país o la BADLAR no son del día; una caché mal invalidada ocultaría exactamente ese aviso.
