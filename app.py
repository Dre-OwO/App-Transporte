from flask import Flask, redirect, render_template, url_for

app = Flask(__name__)


@app.route("/")
def inicio():
    return render_template("public/inicio.html", titulo="Inicio")


@app.route("/login")
def login():
    return render_template("public/login.html", titulo="Login")


@app.route("/registro")
def registro():
    return render_template("public/registro.html", titulo="Registro")


@app.route("/panel-usuario")
def panel_usuario():
    return render_template("public/panel_usuario.html", titulo="Panel Usuario")


@app.route("/planes")
def planes():
    return render_template("public/planes.html", titulo="Planes")


@app.route("/validar-viaje")
def validar_viaje():
    return render_template("public/validar_viaje.html", titulo="Validar Viaje")


@app.route("/admin")
def admin():
    return render_template("admin/dashboard.html", titulo="Admin")


@app.route("/admin/usuarios")
def admin_usuarios():
    return render_template("admin/usuarios.html", titulo="Admin Usuarios")


@app.route("/admin/planes")
def admin_planes():
    return render_template("admin/planes.html", titulo="Admin Planes")


@app.route("/admin/suscripciones")
def admin_suscripciones():
    return render_template("admin/suscripciones.html", titulo="Admin Suscripciones")


@app.route("/reportes")
def reportes():
    return redirect(url_for("admin_reportes"))


@app.route("/admin/reportes")
def admin_reportes():
    return render_template("admin/reportes.html", titulo="Admin Reportes")


if __name__ == "__main__":
    app.run(debug=True)
