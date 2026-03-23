import os

from flask import Flask, flash, redirect, render_template, request, url_for

from database import (
    DatabaseError,
    create_plan,
    create_subscription,
    create_user,
    delete_plan,
    delete_subscription,
    delete_user,
    get_dashboard_stats,
    get_plan,
    get_report_data,
    get_subscription,
    get_user,
    list_all_plans,
    list_public_plans,
    list_subscriptions,
    list_users,
    lookup_user_panel,
    register_validation,
    update_plan,
    update_subscription,
    update_user,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")


def _blank_user_form():
    return {
        "document_id": "",
        "nombre": "",
        "correo": "",
        "telefono": "",
        "password": "",
        "rol": "cliente",
        "activo": "true",
    }


def _user_form_from_request(form):
    return {
        "nombre": form.get("nombre", "").strip(),
        "correo": form.get("correo", "").strip(),
        "telefono": form.get("telefono", "").strip(),
        "password": form.get("password", "").strip(),
        "rol": form.get("rol", "cliente").strip(),
        "activo": form.get("activo", "true"),
    }


def _user_form_from_document(document):
    form_data = _blank_user_form()
    form_data.update(
        {
            "document_id": document.get("_id", ""),
            "nombre": document.get("nombre", ""),
            "correo": document.get("correo", ""),
            "telefono": document.get("telefono", ""),
            "rol": document.get("rol", "cliente"),
            "activo": "true" if document.get("activo", True) else "false",
        }
    )
    return form_data


def _blank_plan_form():
    return {
        "document_id": "",
        "nombre": "",
        "descripcion": "",
        "precio_anual": "",
        "limite_viajes_diarios": "",
        "activo": "true",
    }


def _plan_form_from_request(form):
    return {
        "nombre": form.get("nombre", "").strip(),
        "descripcion": form.get("descripcion", "").strip(),
        "precio_anual": form.get("precio_anual", "").strip(),
        "limite_viajes_diarios": form.get("limite_viajes_diarios", "").strip(),
        "activo": form.get("activo", "true"),
    }


def _plan_form_from_document(document):
    form_data = _blank_plan_form()
    form_data.update(
        {
            "document_id": document.get("_id", ""),
            "nombre": document.get("nombre", ""),
            "descripcion": document.get("descripcion", ""),
            "precio_anual": document.get("precio_anual", ""),
            "limite_viajes_diarios": document.get("limite_viajes_diarios", ""),
            "activo": "true" if document.get("activo", True) else "false",
        }
    )
    return form_data


def _blank_subscription_form():
    return {
        "document_id": "",
        "usuario_id": "",
        "plan_id": "",
        "fecha_inicio": "",
        "fecha_fin": "",
        "estado": "activa",
    }


def _subscription_form_from_request(form):
    return {
        "usuario_id": form.get("usuario_id", "").strip(),
        "plan_id": form.get("plan_id", "").strip(),
        "fecha_inicio": form.get("fecha_inicio", "").strip(),
        "fecha_fin": form.get("fecha_fin", "").strip(),
        "estado": form.get("estado", "activa").strip(),
    }


def _subscription_form_from_document(document):
    form_data = _blank_subscription_form()
    form_data.update(
        {
            "document_id": document.get("_id", ""),
            "usuario_id": document.get("usuario_id", ""),
            "plan_id": document.get("plan_id", ""),
            "fecha_inicio": document.get("fecha_inicio", ""),
            "fecha_fin": document.get("fecha_fin", ""),
            "estado": document.get("estado", "activa"),
        }
    )
    return form_data


def _blank_validation_form():
    return {"identificador": "", "ruta": "", "estacion": ""}


def _validation_form_from_request(form):
    return {
        "identificador": form.get("identificador", "").strip(),
        "ruta": form.get("ruta", "").strip(),
        "estacion": form.get("estacion", "").strip(),
    }


def _redirect_to(endpoint, edit_id=""):
    if edit_id:
        return redirect(url_for(endpoint, edit=edit_id))
    return redirect(url_for(endpoint))


@app.route("/")
def inicio():
    return render_template("public/inicio.html", titulo="Inicio")


@app.route("/login")
def login():
    return render_template("public/login.html", titulo="Login")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    form_data = _blank_user_form()

    if request.method == "POST":
        form_data = _user_form_from_request(request.form)
        try:
            create_user({**form_data, "rol": "cliente", "activo": "true"})
            flash("Usuario registrado correctamente. Ya puedes usar el correo para consultar tu panel.", "success")
            return redirect(url_for("registro"))
        except DatabaseError as exc:
            flash(str(exc), "error")

    return render_template("public/registro.html", titulo="Registro", form_data=form_data)


@app.route("/panel-usuario")
def panel_usuario():
    identificador = request.args.get("identificador", "").strip()
    resumen = None
    db_warning = None

    if identificador:
        try:
            resumen = lookup_user_panel(identificador)
        except DatabaseError as exc:
            db_warning = str(exc)

    return render_template(
        "public/panel_usuario.html",
        titulo="Panel Usuario",
        identificador=identificador,
        resumen=resumen,
        db_warning=db_warning,
    )


@app.route("/planes")
def planes():
    db_warning = None
    planes_disponibles = []

    try:
        planes_disponibles = list_public_plans()
    except DatabaseError as exc:
        db_warning = str(exc)

    return render_template(
        "public/planes.html",
        titulo="Planes",
        planes=planes_disponibles,
        db_warning=db_warning,
    )


@app.route("/validar-viaje", methods=["GET", "POST"])
def validar_viaje():
    form_data = _blank_validation_form()
    resultado = None

    if request.method == "POST":
        form_data = _validation_form_from_request(request.form)
        try:
            resultado = register_validation(form_data)
            flash("Validacion registrada correctamente.", "success")
        except DatabaseError as exc:
            flash(str(exc), "error")

    return render_template(
        "public/validar_viaje.html",
        titulo="Validar Viaje",
        form_data=form_data,
        resultado=resultado,
    )


@app.route("/admin")
def admin():
    stats = {
        "usuarios": 0,
        "usuarios_activos": 0,
        "suscripciones_activas": 0,
        "planes": 0,
        "validaciones_hoy": 0,
    }
    db_warning = None

    try:
        stats = get_dashboard_stats()
    except DatabaseError as exc:
        db_warning = str(exc)

    return render_template("admin/dashboard.html", titulo="Admin", stats=stats, db_warning=db_warning)


@app.route("/admin/usuarios", methods=["GET", "POST"])
def admin_usuarios():
    if request.method == "POST":
        action = request.form.get("action", "")
        document_id = request.form.get("document_id", "").strip()
        payload = _user_form_from_request(request.form)

        try:
            if action == "create":
                create_user(payload)
                flash("Usuario creado correctamente.", "success")
                return redirect(url_for("admin_usuarios"))
            if action == "update":
                update_user(document_id, payload)
                flash("Usuario actualizado correctamente.", "success")
                return _redirect_to("admin_usuarios", document_id)
            if action == "delete":
                delete_user(document_id)
                flash("Usuario eliminado correctamente.", "success")
                return redirect(url_for("admin_usuarios"))
            flash("Accion invalida para usuarios.", "error")
        except DatabaseError as exc:
            flash(str(exc), "error")
            return _redirect_to("admin_usuarios", document_id if action == "update" else "")

    form_data = _blank_user_form()
    db_warning = None
    edit_id = request.args.get("edit", "").strip()

    if edit_id:
        try:
            form_data = _user_form_from_document(get_user(edit_id))
        except DatabaseError as exc:
            flash(str(exc), "error")

    try:
        usuarios = list_users()
    except DatabaseError as exc:
        usuarios = []
        db_warning = str(exc)

    return render_template(
        "admin/usuarios.html",
        titulo="Admin Usuarios",
        usuarios=usuarios,
        form_data=form_data,
        db_warning=db_warning,
    )


@app.route("/admin/planes", methods=["GET", "POST"])
def admin_planes():
    if request.method == "POST":
        action = request.form.get("action", "")
        document_id = request.form.get("document_id", "").strip()
        payload = _plan_form_from_request(request.form)

        try:
            if action == "create":
                create_plan(payload)
                flash("Plan creado correctamente.", "success")
                return redirect(url_for("admin_planes"))
            if action == "update":
                update_plan(document_id, payload)
                flash("Plan actualizado correctamente.", "success")
                return _redirect_to("admin_planes", document_id)
            if action == "delete":
                delete_plan(document_id)
                flash("Plan eliminado correctamente.", "success")
                return redirect(url_for("admin_planes"))
            flash("Accion invalida para planes.", "error")
        except DatabaseError as exc:
            flash(str(exc), "error")
            return _redirect_to("admin_planes", document_id if action == "update" else "")

    form_data = _blank_plan_form()
    db_warning = None
    edit_id = request.args.get("edit", "").strip()

    if edit_id:
        try:
            form_data = _plan_form_from_document(get_plan(edit_id))
        except DatabaseError as exc:
            flash(str(exc), "error")

    try:
        planes_registrados = list_all_plans()
    except DatabaseError as exc:
        planes_registrados = []
        db_warning = str(exc)

    return render_template(
        "admin/planes.html",
        titulo="Admin Planes",
        planes=planes_registrados,
        form_data=form_data,
        db_warning=db_warning,
    )


@app.route("/admin/suscripciones", methods=["GET", "POST"])
def admin_suscripciones():
    if request.method == "POST":
        action = request.form.get("action", "")
        document_id = request.form.get("document_id", "").strip()
        payload = _subscription_form_from_request(request.form)

        try:
            if action == "create":
                create_subscription(payload)
                flash("Suscripcion creada correctamente.", "success")
                return redirect(url_for("admin_suscripciones"))
            if action == "update":
                update_subscription(document_id, payload)
                flash("Suscripcion actualizada correctamente.", "success")
                return _redirect_to("admin_suscripciones", document_id)
            if action == "delete":
                delete_subscription(document_id)
                flash("Suscripcion eliminada correctamente.", "success")
                return redirect(url_for("admin_suscripciones"))
            flash("Accion invalida para suscripciones.", "error")
        except DatabaseError as exc:
            flash(str(exc), "error")
            return _redirect_to("admin_suscripciones", document_id if action == "update" else "")

    form_data = _blank_subscription_form()
    db_warning = None
    edit_id = request.args.get("edit", "").strip()

    if edit_id:
        try:
            form_data = _subscription_form_from_document(get_subscription(edit_id))
        except DatabaseError as exc:
            flash(str(exc), "error")

    try:
        suscripciones = list_subscriptions()
        usuarios = list_users()
        planes_registrados = list_all_plans()
    except DatabaseError as exc:
        suscripciones = []
        usuarios = []
        planes_registrados = []
        db_warning = str(exc)

    return render_template(
        "admin/suscripciones.html",
        titulo="Admin Suscripciones",
        suscripciones=suscripciones,
        usuarios=usuarios,
        planes=planes_registrados,
        form_data=form_data,
        db_warning=db_warning,
    )


@app.route("/reportes")
def reportes():
    return redirect(url_for("admin_reportes"))


@app.route("/admin/reportes")
def admin_reportes():
    report_data = {
        "suscripciones_mes": 0,
        "usuarios_activos": 0,
        "promedio_validaciones": 0,
        "validaciones_totales": 0,
        "top_planes": [],
        "validaciones_recientes": [],
    }
    db_warning = None

    try:
        report_data = get_report_data()
    except DatabaseError as exc:
        db_warning = str(exc)

    return render_template(
        "admin/reportes.html",
        titulo="Admin Reportes",
        report_data=report_data,
        db_warning=db_warning,
    )


if __name__ == "__main__":
    app.run(debug=True)
