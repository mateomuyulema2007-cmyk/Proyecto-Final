from datetime import datetime
import sqlite3

from flask import Flask, jsonify, render_template, request, redirect, session, url_for


app = Flask(__name__)
app.secret_key = "logicweb_uta_sesiones_seguras"
DB_NAME = "base_datos.db"


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
        ("profe_ruben", "1234", "docente"),
    )
    conn.commit()
    conn.close()


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
    historial = conn.execute(
        """SELECT profesor, nota1, nota2, nota3, promedio, estado
           FROM intentos ORDER BY id DESC LIMIT 8"""
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
    conn.close()

    return render_template(
        "index.html",
        usuario=session["usuario"],
        historial=historial,
        practicas=practicas,
        resumen=resumen,
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


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
