# 🤖 RPA - 📧 Mailing Automático de Reporte de Tipos de Cambio 💵
Este proyecto utiliza Python para obtener datos de varias webs y la API del Banco Central de Argentina. Los datos recopilados incluyen los distintos tipos de cambio de Argentina, el riesgo país y la inflación. Estos datos se recogen diariamente y se envían en un resumen por correo electrónico junto con gráficos relevantes.

## 📚 Librerías utilizadas
Las librerías utilizadas en este proyecto son:

**time** y **datetime**: para manejar el tiempo y las fechas.
**locale**: para aplicar el formato de fecha en español.
**pandas** y **numpy**: para manipular los datos y realizar cálculos.
**json** y **requests**: para manejar la API del **BCRA**.
**selenium**: para realizar el web scraping.
**matplotlib** y **seaborn**: para crear gráficos.
**getpass**: para ocultar la contraseña durante la entrada del usuario.
**mimetypes**, **email.message**, **email.mime**: para personalizar el correo electrónico.
**smtplib** y **ssl**: para manejar la seguridad del envío automático de correos electrónicos.
**tabulate**: para personalizar el dataframe como una tabla HTML.

## 🤖 Web Scraping
El proceso de web scraping se realiza utilizando Selenium para interactuar con las páginas web y recopilar los datos necesarios. Los datos se procesan y se convierten en un DataFrame de pandas para su posterior análisis.

## 📊 Manipulación y Visualización de Datos
Los datos recopilados se procesan y se visualizan utilizando pandas, numpy, matplotlib y seaborn. Se generan gráficos para visualizar los distintos tipos de cambio, el riesgo país y la inflación.

## 📧 Mailing Automático
El resumen y los gráficos se envían diariamente por correo electrónico a los suscriptores. El correo electrónico se personaliza utilizando varias librerías de Python para manejar el formato del correo electrónico y la seguridad del envío.

## 📬 Suscripción
Si estás interesado en recibir este resumen diario por correo electrónico, por favor, envía un correo a **martinezmauroezequiel@gmail.com** para suscribirte.
