# 🤖 RPA - 📧 Mailing Automático de Reporte de Tipos de Cambio 💵
Este sistema automatiza el ciclo completo de datos macroeconómicos de Argentina aprovechando diferentes fuentes como APIs del BCRA y de la FED, así como también web scraping de diferentes fuentes. No es solo un bot de scraping; es un pipeline que extrae, procesa y distribuye inteligencia financiera diaria para la toma de decisiones. Si bien en un principo sólo extraía el tipo de cambio del dólar blue venta y lo colocaba en un excel, el proyecto fue evolucionando poco a poco en base a ideas propias que tenía de hace mucho tiempo antes de aprender analítica de datos o programación y el feedback recibido de los sucriptores.

## 🚀 Funcionalidades Clave
* **Ingesta Multi Fuente:** Extracción automatizada con `Selenium (Headless)` y consumo de `APIs` oficiales (BCRA y FED).
* **Data Processing:** Limpieza, normalización y cálculo de series temporales con `Pandas` y `Numpy`.
* **Visualización Avanzada:** Generación de gráficos estáticos de alta calidad con `Matplotlib` y `Seaborn` (Riesgo País, Inflación, Brechas Cambiarias).
* **Reporting Automatizado:** Distribución de reportes en formato `HTML` vía email y adjuntos mediante `SMTP` seguro (`SSL`).

---

## 🛠️ Stack Tecnológico y Librerías
El proyecto está modularizado para asegurar la robustez y escalabilidad del RPA:

### 📡 Extracción y Scraping
* `selenium`: Automatización de navegación para fuentes sin API.
* `requests` & `json`: Interacción con el API del Banco Central y la FED.
* `python-dotenv`: Gestión profesional de variables de entorno y credenciales sensibles.

### 🧮 Procesamiento y Análisis
* `pandas`: Motor principal para la manipulación de DataFrames.
* `numpy`: Cálculos vectorizados y manejo de matrices de datos.
* `locale`: Localización para el formateo de fechas en español.

### 📊 Visualización y Estética
* `matplotlib` & `seaborn`: Generación de assets visuales personalizados (fuentes, ticks y formatos).
* `tabulate`: Conversión de DataFrames a tablas HTML embebidas en el correo.

### 📧 Infraestructura de Notificación
* `smtplib` & `ssl`: Túnel cifrado para el envío de correos.
* `email.mime`: Construcción de mensajes multiparte (Cuerpo HTML + Imágenes embebidas).

---

## 🤖 Web Scraping
El proceso de web scraping se realiza utilizando Selenium para interactuar con las páginas web y recopilar los datos necesarios. Los datos se procesan y se convierten en un DataFrame de pandas para su posterior análisis.

## 📊 Manipulación y Visualización de Datos
Los datos recopilados se procesan y se visualizan utilizando pandas, numpy, matplotlib y seaborn. Se generan gráficos para visualizar los distintos tipos de cambio, el riesgo país y la inflación.

## 📧 Mailing Automático
El resumen y los gráficos se envían diariamente por correo electrónico a los suscriptores. El correo electrónico se personaliza utilizando varias librerías de Python para manejar el formato del correo electrónico y la seguridad del envío.

---

## 📚 Guías y Tutoriales Incluidos
El código fuente contiene secciones comentadas a modo de "autotutorial" para facilitar la configuración:
* **Seguridad Gmail:** Instrucciones paso a paso para obtener la **Contraseña de Aplicación** necesaria para el envío automático.
* **Manejo de Credenciales:** Uso de `getpass` para la entrada manual segura de contraseñas sin que queden visibles en pantalla.
* **Compatibilidad de Navegadores:** Configuración lista para alternar entre **Edge** y **Chrome** en modo *headless*.

---

## 🏔️ Roadmap: El Camino a la Cumbre
El proyecto se encuentra en una evolución técnica constante hacia los estándares más altos de la industria de datos. Este es el plan de vuelo:
- [ ] **🚀 Optimización de Motor:** Migración de `Pandas` a `Polars` para aprovechar el procesamiento multihilo y ganar velocidad en grandes volúmenes de datos.
- [ ] **🕸️ Modernización de Scraping:** Reemplazo de Selenium por `Playwright` para lograr una extracción más estable, rápida y con mejor manejo de asincronismo.
- [ ] **💾 Capa de Persistencia:** Integración de `DuckDB` como base de datos analítica local (OLAP), permitiendo consultas `SQL` de alto rendimiento sobre archivos Parquet.
- [ ] **☁️ Cloud Deployment:** El objetivo final y **cumbre del proyecto**. Despliegue en la nube (AWS/GCP/Azure) para una ejecución 24/7 totalmente automatizada y desatendida.

---

## 📬 Suscripción
Si estás interesado en recibir este resumen diario por correo electrónico, por favor, escribime a **martinezmauroezequiel@gmail.com** para suscribirte.
