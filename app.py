from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/registro")
def registro():
    return render_template("registro.html")


@app.route("/panel-usuario")
def panel_usuario():
    return render_template("panel_usuario.html")


@app.route("/planes")
def planes():
    return render_template("planes.html")


@app.route("/validar-viaje")
def validar_viaje():
    return render_template("validar_viaje.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/reportes")
def reportes():
    return render_template("reportes.html")


if __name__ == "__main__":
    app.run(debug=True)
