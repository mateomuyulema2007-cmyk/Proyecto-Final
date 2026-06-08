from datetime import datetime
import sqlite3
import textwrap

from flask import Flask, Response, jsonify, render_template, request, redirect, session, url_for


app = Flask(__name__)
app.secret_key = "logicweb_uta_sesiones_seguras"
DB_NAME = "base_datos.db"
DOCENTE_PREDETERMINADO = "profe_ruben"


def conectar():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = conectar()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            password TEXT,
            rol TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS intentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profesor TEXT,
            nota1 REAL,
            nota2 REAL,
            nota3 REAL,
            promedio REAL,
            estado TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS practicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            modulo TEXT,
            ejercicio TEXT,
            respuesta TEXT,
            resultado TEXT,
            retroalimentacion TEXT,
            fecha TEXT
        )"""
    )
    c.execute(
        "INSERT OR IGNORE INTO usuarios (usuario, password, rol) VALUES (?, ?, ?)",
        (DOCENTE_PREDETERMINADO, "1234", "docente"),
    )
    c.execute(
        "UPDATE usuarios SET rol='docente' WHERE usuario=?",
        (DOCENTE_PREDETERMINADO,),
    )
    conn.commit()
    conn.close()


def es_docente():
    return session.get("usuario") == DOCENTE_PREDETERMINADO and session.get("rol") == "docente"


def consultar_reporte_docente(conn):
    resumen = conn.execute(
        """SELECT
              usuario,
              modulo,
              COUNT(*) AS total,
              SUM(CASE WHEN resultado='Correcto' THEN 1 ELSE 0 END) AS correctos,
              SUM(CASE WHEN resultado='Incorrecto' THEN 1 ELSE 0 END) AS incorrectos,
              SUM(CASE WHEN resultado NOT IN ('Correcto', 'Incorrecto') THEN 1 ELSE 0 END) AS refuerzo,
              ROUND(SUM(CASE WHEN resultado='Correcto' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS calificacion
           FROM practicas
           GROUP BY usuario, modulo
           ORDER BY usuario, modulo"""
    ).fetchall()
    detalle = conn.execute(
        """SELECT usuario, modulo, ejercicio, respuesta, resultado, retroalimentacion, fecha
           FROM practicas
           ORDER BY id DESC"""
    ).fetchall()
    return resumen, detalle


def limpiar_pdf_texto(valor):
    texto = str(valor if valor is not None else "")
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", " ")


def cortar_texto(valor, limite):
    texto = str(valor if valor is not None else "")
    return texto if len(texto) <= limite else texto[: limite - 3] + "..."


def pdf_color(color):
    return " ".join(str(c) for c in color)


def pdf_rect(x, y, w, h, fill, stroke=None):
    comandos = [f"q {pdf_color(fill)} rg"]
    if stroke:
        comandos.append(f"{pdf_color(stroke)} RG")
        comandos.append(f"{x} {y} {w} {h} re B")
    else:
        comandos.append(f"{x} {y} {w} {h} re f")
    comandos.append("Q")
    return "\n".join(comandos)


def pdf_texto(x, y, texto, size=10, bold=False, color=(0, 0, 0)):
    fuente = "F2" if bold else "F1"
    return (
        f"BT {pdf_color(color)} rg /{fuente} {size} Tf "
        f"{x} {y} Td ({limpiar_pdf_texto(texto)}) Tj ET"
    )


def crear_pdf_documento(paginas):
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    referencias_paginas = []

    for comandos in paginas:
        contenido_bytes = "\n".join(comandos).encode("latin-1", "replace")
        pagina_num = len(objetos) + 1
        contenido_num = pagina_num + 1
        referencias_paginas.append(f"{pagina_num} 0 R")
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {contenido_num} 0 R >>".encode("ascii")
        )
        objetos.append(
            f"<< /Length {len(contenido_bytes)} >>\nstream\n".encode("ascii")
            + contenido_bytes
            + b"\nendstream"
        )

    objetos[1] = (
        f"<< /Type /Pages /Kids [{' '.join(referencias_paginas)}] /Count {len(referencias_paginas)} >>"
    ).encode("ascii")
    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    for i, objeto in enumerate(objetos, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode("ascii") + objeto + b"\nendobj\n"
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objetos) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode("ascii")
    return pdf


def construir_reporte_pdf(resumen, detalle):
    paginas = []
    ancho = 595
    alto = 842
    margen = 34
    y = 0
    total_actividades = sum((r["total"] or 0) for r in resumen)
    total_correctas = sum((r["correctos"] or 0) for r in resumen)
    total_incorrectas = sum((r["incorrectos"] or 0) for r in resumen)
    estudiantes = len({r["usuario"] for r in resumen})
    efectividad = round(total_correctas * 100 / total_actividades, 1) if total_actividades else 0

    def nueva_pagina():
        nonlocal y
        comandos = [
            pdf_rect(0, alto - 82, ancho, 82, (0.06, 0.07, 0.09)),
            pdf_rect(0, alto - 86, ancho, 5, (0.31, 0.84, 0.77)),
            pdf_texto(margen, 800, "LogicWeb UTA", 22, True, (1, 1, 1)),
            pdf_texto(margen, 780, "Reporte docente de actividades y progreso", 11, False, (0.78, 0.84, 0.9)),
            pdf_texto(380, 802, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 9, False, (0.78, 0.84, 0.9)),
            pdf_texto(380, 786, f"Docente: {session.get('usuario', '')}", 9, False, (0.78, 0.84, 0.9)),
        ]
        paginas.append(comandos)
        y = 735

    def pagina_actual():
        return paginas[-1]

    def asegurar_espacio(alto_bloque):
        if y - alto_bloque < 58:
            nueva_pagina()

    def titulo_seccion(texto):
        nonlocal y
        asegurar_espacio(38)
        pagina_actual().append(pdf_texto(margen, y, texto, 15, True, (0.08, 0.1, 0.14)))
        pagina_actual().append(pdf_rect(margen, y - 10, 70, 3, (0.31, 0.84, 0.77)))
        y -= 30

    def tarjeta(x, titulo, valor, color):
        pagina_actual().append(pdf_rect(x, y - 56, 125, 62, (0.96, 0.97, 0.98), (0.83, 0.86, 0.9)))
        pagina_actual().append(pdf_rect(x, y - 56, 5, 62, color))
        pagina_actual().append(pdf_texto(x + 14, y - 15, titulo, 8, False, (0.35, 0.39, 0.46)))
        pagina_actual().append(pdf_texto(x + 14, y - 39, valor, 20, True, (0.08, 0.1, 0.14)))

    nueva_pagina()
    tarjeta(margen, "ESTUDIANTES", str(estudiantes), (0.31, 0.84, 0.77))
    tarjeta(margen + 134, "ACTIVIDADES", str(total_actividades), (0.4, 0.65, 1))
    tarjeta(margen + 268, "CORRECTAS", str(total_correctas), (0.52, 0.88, 0.56))
    tarjeta(margen + 402, "EFECTIVIDAD", f"{efectividad}%", (0.95, 0.78, 0.36))
    y -= 92

    titulo_seccion("Resumen por estudiante y modulo")
    columnas = [70, 130, 62, 62, 66, 58, 66]
    encabezados = ["Usuario", "Modulo", "Acts.", "Correct.", "Incorrect.", "Ref.", "Nota"]
    x = margen
    pagina_actual().append(pdf_rect(margen, y - 18, sum(columnas), 24, (0.08, 0.1, 0.14)))
    for ancho_col, encabezado in zip(columnas, encabezados):
        pagina_actual().append(pdf_texto(x + 5, y - 10, encabezado, 8, True, (1, 1, 1)))
        x += ancho_col
    y -= 28

    if resumen:
        fila = 0
        for r in resumen:
            asegurar_espacio(24)
            fill = (0.985, 0.988, 0.992) if fila % 2 == 0 else (1, 1, 1)
            pagina_actual().append(pdf_rect(margen, y - 14, sum(columnas), 21, fill, (0.88, 0.9, 0.93)))
            valores = [
                cortar_texto(r["usuario"], 12),
                cortar_texto(r["modulo"], 26),
                r["total"],
                r["correctos"] or 0,
                r["incorrectos"] or 0,
                r["refuerzo"] or 0,
                f"{r['calificacion'] or 0}%",
            ]
            x = margen
            for ancho_col, valor in zip(columnas, valores):
                pagina_actual().append(pdf_texto(x + 5, y - 8, valor, 8, False, (0.14, 0.17, 0.22)))
                x += ancho_col
            y -= 21
            fila += 1
    else:
        pagina_actual().append(pdf_texto(margen, y, "No hay actividades registradas.", 10, False, (0.35, 0.39, 0.46)))
        y -= 24

    y -= 22
    titulo_seccion("Detalle de respuestas")
    if detalle:
        for d in detalle:
            respuesta = textwrap.wrap(f"Respuesta: {d['respuesta']}", width=86) or ["Respuesta:"]
            retro = textwrap.wrap(f"Retroalimentacion: {d['retroalimentacion']}", width=86) or ["Retroalimentacion:"]
            alto_tarjeta = 74 + (len(respuesta) + len(retro)) * 12
            asegurar_espacio(alto_tarjeta)
            estado_color = (0.52, 0.88, 0.56) if d["resultado"] == "Correcto" else (1, 0.48, 0.48)
            pagina_actual().append(pdf_rect(margen, y - alto_tarjeta + 10, 527, alto_tarjeta, (0.985, 0.988, 0.992), (0.83, 0.86, 0.9)))
            pagina_actual().append(pdf_rect(margen, y - 18, 527, 28, (0.93, 0.96, 0.98)))
            pagina_actual().append(pdf_rect(margen, y - alto_tarjeta + 10, 5, alto_tarjeta, estado_color))
            pagina_actual().append(pdf_texto(margen + 15, y - 8, cortar_texto(d["ejercicio"], 62), 10, True, (0.08, 0.1, 0.14)))
            pagina_actual().append(pdf_texto(margen + 390, y - 8, str(d["resultado"]), 9, True, estado_color))
            pagina_actual().append(pdf_texto(margen + 15, y - 26, f"{d['fecha']} | {d['usuario']} | {d['modulo']}", 8, False, (0.35, 0.39, 0.46)))
            y_linea = y - 48
            for linea in respuesta:
                pagina_actual().append(pdf_texto(margen + 15, y_linea, linea, 8, False, (0.14, 0.17, 0.22)))
                y_linea -= 12
            for linea in retro:
                pagina_actual().append(pdf_texto(margen + 15, y_linea, linea, 8, False, (0.14, 0.17, 0.22)))
                y_linea -= 12
            y -= alto_tarjeta + 12
    else:
        pagina_actual().append(pdf_texto(margen, y, "No existen respuestas registradas.", 10, False, (0.35, 0.39, 0.46)))

    for index, comandos in enumerate(paginas, start=1):
        comandos.append(pdf_texto(margen, 28, "LogicWeb UTA - Reporte docente", 8, False, (0.45, 0.49, 0.55)))
        comandos.append(pdf_texto(505, 28, f"Pagina {index}", 8, False, (0.45, 0.49, 0.55)))
    return crear_pdf_documento(paginas)


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"].strip()
        pwd = request.form["password"].strip()

        conn = conectar()
        usuario_valido = conn.execute(
            "SELECT * FROM usuarios WHERE usuario=? AND password=?", (user, pwd)
        ).fetchone()
        conn.close()

        if usuario_valido:
            session["usuario"] = user
            session["rol"] = usuario_valido["rol"]
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Credenciales incorrectas. Intenta de nuevo.")

    return render_template("login.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        user = request.form["usuario"].strip()
        pwd = request.form["password"].strip()

        if len(user) < 3 or len(pwd) < 4:
            return render_template(
                "registro.html",
                error="Usa un usuario de al menos 3 caracteres y una clave de al menos 4.",
            )

        conn = conectar()
        try:
            conn.execute(
                "INSERT INTO usuarios (usuario, password, rol) VALUES (?, ?, 'estudiante')",
                (user, pwd),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("registro.html", error="Ese nombre de usuario ya existe.")
        conn.close()
        return redirect(url_for("login"))

    return render_template("registro.html")


@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))

    conn = conectar()
    usuario_actual = conn.execute(
        "SELECT rol FROM usuarios WHERE usuario=?", (session["usuario"],)
    ).fetchone()
    rol = usuario_actual["rol"] if usuario_actual else session.get("rol", "estudiante")
    session["rol"] = rol
    historial = conn.execute(
        """SELECT profesor, nota1, nota2, nota3, promedio, estado
           FROM intentos WHERE profesor=? ORDER BY id DESC LIMIT 8""",
        (session["usuario"],),
    ).fetchall()
    practicas = conn.execute(
        """SELECT modulo, ejercicio, respuesta, resultado, retroalimentacion, fecha
           FROM practicas WHERE usuario=? ORDER BY id DESC LIMIT 12""",
        (session["usuario"],),
    ).fetchall()
    resumen = conn.execute(
        """SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN resultado='Correcto' THEN 1 ELSE 0 END) AS correctos
           FROM practicas WHERE usuario=?""",
        (session["usuario"],),
    ).fetchone()
    reporte_resumen = []
    reporte_detalle = []
    puede_ver_reportes = es_docente()
    if puede_ver_reportes:
        reporte_resumen, reporte_detalle = consultar_reporte_docente(conn)
        reporte_detalle = reporte_detalle[:80]
    conn.close()

    return render_template(
        "index.html",
        usuario=session["usuario"],
        rol=rol,
        historial=historial,
        practicas=practicas,
        resumen=resumen,
        reporte_resumen=reporte_resumen,
        reporte_detalle=reporte_detalle,
        puede_ver_reportes=puede_ver_reportes,
    )


@app.route("/procesar_ejercicio", methods=["POST"])
def procesar_ejercicio():
    if "usuario" not in session:
        return redirect(url_for("login"))

    try:
        n1 = float(request.form["nota1"])
        n2 = float(request.form["nota2"])
        n3 = float(request.form["nota3"])
    except ValueError:
        return redirect(url_for("dashboard"))

    promedio = round((n1 + n2 + n3) / 3, 2)
    estado = "Aprobado" if promedio >= 7 else "Reprobado"
    retro = (
        "Buen rendimiento. Puedes subir de nivel con ejercicios de condicionales anidados."
        if estado == "Aprobado"
        else "Refuerza acumuladores y validacion de datos antes de repetir el ejercicio."
    )

    conn = conectar()
    conn.execute(
        """INSERT INTO intentos
           (profesor, nota1, nota2, nota3, promedio, estado)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session["usuario"], n1, n2, n3, promedio, estado),
    )
    conn.execute(
        """INSERT INTO practicas
           (usuario, modulo, ejercicio, respuesta, resultado, retroalimentacion, fecha)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            session["usuario"],
            "Promedios",
            "Calculo de promedio academico",
            f"{n1}, {n2}, {n3}",
            "Correcto" if estado == "Aprobado" else "En refuerzo",
            f"Promedio: {promedio}. Estado: {estado}. {retro}",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/registrar_practica", methods=["POST"])
def registrar_practica():
    if "usuario" not in session:
        return jsonify({"ok": False, "mensaje": "Debes iniciar sesion."}), 401

    data = request.get_json(silent=True) or {}
    conn = conectar()
    conn.execute(
        """INSERT INTO practicas
           (usuario, modulo, ejercicio, respuesta, resultado, retroalimentacion, fecha)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            session["usuario"],
            data.get("modulo", "Practica"),
            data.get("ejercicio", "Ejercicio interactivo"),
            data.get("respuesta", ""),
            data.get("resultado", "Registrado"),
            data.get("retroalimentacion", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/reporte_docente")
def reporte_docente():
    if "usuario" not in session:
        return redirect(url_for("login"))
    if not es_docente():
        return jsonify({"ok": False, "mensaje": "Solo el docente puede ver reportes."}), 403

    conn = conectar()
    filas = conn.execute(
        """SELECT usuario, modulo, ejercicio, respuesta, resultado, retroalimentacion, fecha
           FROM practicas
           ORDER BY id DESC"""
    ).fetchall()
    conn.close()
    return jsonify({"ok": True, "reporte": [dict(f) for f in filas]})


@app.route("/descargar_reporte_pdf")
def descargar_reporte_pdf():
    if "usuario" not in session:
        return redirect(url_for("login"))
    if not es_docente():
        return jsonify({"ok": False, "mensaje": "Solo el docente predeterminado puede descargar reportes."}), 403

    conn = conectar()
    resumen, detalle = consultar_reporte_docente(conn)
    conn.close()
    pdf = construir_reporte_pdf(resumen, detalle)
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=reporte_logicweb_{fecha}.pdf"},
    )


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    session.pop("rol", None)
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
