import smtplib
from email import message_from_string

import pytest

import charts
import email_report as er
import transformations as t
from conftest import HOY, jpeg_minimo


@pytest.fixture
def df(resultados, historico):
    base = t.sumar_al_historico(t.armar_fila_nueva(resultados, HOY), historico)
    return t.agregar_brechas_y_variaciones(base)


@pytest.fixture
def inflacion_12(resultados):
    return t.ultimos_meses(t.serie_inflacion(resultados.bcra["inflacion_mensual"]))


@pytest.fixture
def imagenes():
    return {nombre: jpeg_minimo() for nombre in charts.ORDEN_EN_MAIL}


def test_pintar_variacion():
    assert "#1e8449" in er.pintar_variacion(0.012) and "1.20%" in er.pintar_variacion(0.012)
    assert "#c0392b" in er.pintar_variacion(-0.005)
    assert er.pintar_variacion("n/d") == "n/d"


def test_tabla_de_inflacion_va_de_vieja_a_nueva_y_la_interanual_es_la_ultima(inflacion_12):
    # Regresión: el reenvío manual mostraba la tabla al revés y la interanual de hace 12 meses
    tabla, interanual = er.tabla_inflacion(inflacion_12)
    assert interanual == f"{inflacion_12['Inflación Anual'].iloc[-1]:,.2f}%"
    primera = t.etiqueta_mes(inflacion_12["Fecha"].iloc[0])
    ultima = t.etiqueta_mes(inflacion_12["Fecha"].iloc[-1])
    assert tabla.index(primera) < tabla.index(ultima)


def test_preparar_df_mail_no_toca_el_original(df):
    original = df.copy()
    mail = er.preparar_df_mail(df)
    assert mail["fed_tea"].iloc[0] == "3.88%"
    assert mail["Fecha"].iloc[0] == HOY.strftime("%d/%m/%y")
    assert df.equals(original)


def test_renderizar_incluye_los_cuatro_graficos_por_defecto(df, inflacion_12):
    html = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "Párrafo de prueba", 12.3)
    assert "Párrafo de prueba" in html
    assert all(f"cid:image{i}" in html for i in range(1, 5))
    assert "12.30 segundos" in html


def test_renderizar_omite_los_graficos_que_faltan(df, inflacion_12):
    html = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0, graficos=["image1", "image3"])
    assert "cid:image1" in html and "cid:image3" in html
    assert "cid:image2" not in html and "cid:image4" not in html


def test_el_template_sin_la_variable_graficos_muestra_los_cuatro(df, inflacion_12):
    # El notebook renderiza el template sin pasar `graficos`
    contexto = er.contexto_template(df, inflacion_12, 2000.0, 2100.0, "x", 1.0)
    del contexto["graficos"]
    html = er.template().render(**contexto)
    assert all(f"cid:image{i}" in html for i in range(1, 5))


def test_cids_disponibles(imagenes):
    assert er.cids_disponibles(imagenes) == [f"image{i}" for i in range(1, 7)]
    del imagenes[charts.BTC]
    # Los cid son fijos por gráfico: sin BTC, los de agregados y deuda siguen siendo 5 y 6
    assert er.cids_disponibles(imagenes) == ["image1", "image2", "image3", "image5", "image6"]


def test_armar_mensaje(imagenes):
    del imagenes[charts.INFLACION]
    em = er.armar_mensaje("<p>hola</p>", imagenes, "Asunto", para="remitente@example.com",
                          cco=["a@example.com", "b@example.com"], csv="Fecha,TCV_Blue\n")
    msg = message_from_string(em.as_string())
    partes = [(p.get_content_type(), p.get("Content-ID")) for p in msg.walk() if not p.is_multipart()]
    assert partes == [("text/html", None), ("image/jpeg", "<image1>"), ("image/jpeg", "<image3>"),
                      ("image/jpeg", "<image4>"), ("image/jpeg", "<image5>"), ("image/jpeg", "<image6>"),
                      ("text/csv", None)]
    assert msg["Bcc"] == "a@example.com, b@example.com"
    assert msg["To"] == "remitente@example.com"


def test_sin_cco_no_hay_cabecera_bcc(imagenes):
    em = er.armar_mensaje("<p>x</p>", imagenes, "Asunto", para="alguien@example.com")
    assert em["Bcc"] is None


def test_envio_diario_en_dos_variantes(imagenes):
    enviados = []
    resultado = er.enviar_reporte_diario(
        "<p>x</p>", imagenes, HOY, csv="a,b\n", enviar_fn=lambda m, d: enviados.append((m, d))
    )
    assert resultado == {"sin_csv": None, "con_csv": None}
    sobres = sorted(d for _, d in enviados)
    assert sobres == sorted([
        ["uno@example.com", "dos@example.com", "remitente@example.com"],
        ["csv@example.com", "remitente@example.com"],
    ])
    con_csv = next(m for m, d in enviados if "csv@example.com" in d)
    assert any(p.get_content_type() == "text/csv" for p in con_csv.walk())


def test_un_envio_fallido_se_informa_y_el_otro_sale(imagenes):
    def enviar(mensaje, destinatarios):
        if "csv@example.com" in destinatarios:
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    resultado = er.enviar_reporte_diario("<p>x</p>", imagenes, HOY, csv=None, enviar_fn=enviar)
    assert resultado["sin_csv"] is None
    assert "SMTPAuthenticationError" in resultado["con_csv"]


def test_enviar_levanta_si_hay_destinatarios_rechazados(monkeypatch, imagenes):
    class SMTPFalso:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            pass

        def starttls(self, context=None):
            pass

        def login(self, usuario, clave):
            pass

        def sendmail(self, de, para, mensaje):
            return {"malo@example.com": (550, b"no existe")}

    monkeypatch.setattr(smtplib, "SMTP", SMTPFalso)
    em = er.armar_mensaje("<p>x</p>", imagenes, "Asunto", para="remitente@example.com")
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        er.enviar(em, ["malo@example.com"])


def test_asunto():
    assert er.asunto(HOY) == "📈 Reporte Macroeconómico - 06-10-2026"


def test_csv_historico(historico):
    texto = er.csv_historico(historico)
    lineas = texto.split("\n")
    assert lineas[0] == ",".join([*er.COLUMNAS_FILA, "ai_paragraph"])
    assert lineas[1].startswith(historico["Fecha"].iloc[0] + ",")
    assert "\r" not in texto
    assert "Párrafo del" in texto  # UTF-8 sin mojibake


def test_la_explicacion_va_debajo_de_su_grafico(df, inflacion_12):
    explicaciones = {"image5": {"titulo": "Agregados, en simple", "texto": "Texto con <b> & más", "dato": "Dato del día."}}
    html = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0, graficos=["image1", "image5"],
                         explicaciones=explicaciones)
    assert html.index("cid:image1") < html.index("cid:image5") < html.index('class="explicacion"')
    assert "Texto con &lt;b&gt; &amp; más" in html and "📌 Dato del día.</p>" in html

    sin_dato = {"image5": {**explicaciones["image5"], "dato": None}}
    html = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0, graficos=["image5"], explicaciones=sin_dato)
    assert 'class="explicacion"' in html and "Dato del día." not in html


def test_sin_explicaciones_el_html_no_cambia(df, inflacion_12):
    base = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0, graficos=["image1", "image2"])
    otra = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0, graficos=["image1", "image2"],
                         explicaciones={"image5": {"titulo": "t", "texto": "x", "dato": None}})
    assert 'class="explicacion"' not in base and base == otra


def test_las_tarjetas_de_ia_y_explicaciones_tienen_el_mismo_look(df, inflacion_12):
    """El párrafo de IA, los comentarios y las explicaciones: el mismo fondo oscuro y borde naranja."""
    explicaciones = {"image5": {"titulo": "Agregados", "texto": "Uno\nDos", "dato": "Dato A\nDato B"}}
    comentarios = {"image1": [("Paralelas", "Comentario")]}
    html = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0, graficos=["image1", "image5"],
                         comentarios=comentarios, explicaciones=explicaciones)
    for clase in ('class="ai-box"', 'class="comentario-ia"', 'class="explicacion"'):
        caja = html[html.index(clase):html.index(clase) + 400]
        assert "#1a252f" in caja and "border-left:4px solid #f39c12" in caja
    # Cada renglón del texto y del dato, en su propio párrafo
    assert ">Uno</p>" in html and ">Dos</p>" in html and "📌 Dato A</p>" in html and "📌 Dato B</p>" in html


def test_el_cierre_lleva_globalaize(df, inflacion_12):
    html = er.renderizar(df, inflacion_12, 2000.0, 2100.0, "x", 1.0)
    assert 'href="https://www.globalaize.com"' in html
    assert 'href="https://www.linkedin.com/company/globalaize"' in html
