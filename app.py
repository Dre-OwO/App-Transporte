import os
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for, send_from_directory

from database import (
    DatabaseError,
    authenticate_user,
    create_plan,
    create_route,
    create_station,
    create_subscription,
    create_subscription_for_user,
    create_user,
    delete_plan,
    delete_route,
    delete_station,
    delete_subscription,
    delete_user,
    get_dashboard_stats,
    get_plan,
    get_report_data,
    get_route,
    get_station,
    get_subscription,
    get_user,
    list_all_plans,
    list_public_plans,
    list_routes,
    list_stations,
    list_subscriptions,
    list_users,
    lookup_user_panel,
    register_validation,
    reset_user_password,
    update_plan,
    update_route,
    update_station,
    update_subscription,
    update_user,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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


def _blank_login_form():
    return {"correo": "", "password": ""}


def _login_form_from_request(form):
    return {
        "correo": form.get("correo", "").strip(),
        "password": form.get("password", "").strip(),
    }


def _blank_recovery_form():
    return {
        "correo": "",
        "telefono": "",
        "password": "",
        "password_confirm": "",
    }


def _recovery_form_from_request(form):
    return {
        "correo": form.get("correo", "").strip(),
        "telefono": form.get("telefono", "").strip(),
        "password": form.get("password", "").strip(),
        "password_confirm": form.get("password_confirm", "").strip(),
    }


def _start_session(user):
    session.clear()
    session["user_id"] = user["_id"]
    session["nombre"] = user["nombre"]
    session["correo"] = user.get("correo", "")
    session["rol"] = user["rol"]


def _current_session_user():
    if not session.get("user_id"):
        return None
    return {
        "id": session.get("user_id"),
        "nombre": session.get("nombre", ""),
        "correo": session.get("correo", ""),
        "rol": session.get("rol", ""),
        "is_admin": session.get("rol") == "admin",
    }


def _redirect_after_login(user):
    next_page = request.args.get("next", "").strip()
    if next_page.startswith("/") and not next_page.startswith("//"):
        return redirect(next_page)
    if user.get("rol") == "admin":
        return redirect(url_for("admin"))
    return redirect(url_for("panel_usuario", identificador=user["correo"]))


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


def _blank_station_form():
    return {
        "document_id": "",
        "nombre": "",
        "codigo": "",
        "descripcion": "",
        "activo": "true",
    }


def _station_form_from_request(form):
    return {
        "nombre": form.get("nombre", "").strip(),
        "codigo": form.get("codigo", "").strip(),
        "descripcion": form.get("descripcion", "").strip(),
        "activo": form.get("activo", "true"),
    }


def _station_form_from_document(document):
    form_data = _blank_station_form()
    form_data.update(
        {
            "document_id": document.get("_id", ""),
            "nombre": document.get("nombre", ""),
            "codigo": document.get("codigo", ""),
            "descripcion": document.get("descripcion", ""),
            "activo": "true" if document.get("activo", True) else "false",
        }
    )
    return form_data


def _blank_route_form():
    return {
        "document_id": "",
        "nombre": "",
        "descripcion": "",
        "estaciones": [],
        "activo": "true",
    }


def _route_form_from_request(form):
    return {
        "nombre": form.get("nombre", "").strip(),
        "descripcion": form.get("descripcion", "").strip(),
        "estaciones": form.getlist("estaciones"),
        "activo": form.get("activo", "true"),
    }


def _route_form_from_document(document):
    form_data = _blank_route_form()
    form_data.update(
        {
            "document_id": document.get("_id", ""),
            "nombre": document.get("nombre", ""),
            "descripcion": document.get("descripcion", ""),
            "estaciones": document.get("estaciones", []),
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


def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(**kwargs):
        if not _current_session_user():
            flash("Inicia sesion para continuar.", "error")
            return redirect(url_for("login", next=request.path))
        return view_function(**kwargs)

    return wrapped_view


def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(**kwargs):
        current_user = _current_session_user()
        if not current_user:
            flash("Inicia sesion para entrar al panel administrativo.", "error")
            return redirect(url_for("login", next=request.path))
        if not current_user["is_admin"]:
            flash("No tienes permisos para entrar al panel administrativo.", "error")
            return redirect(url_for("panel_usuario"))
        return view_function(**kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    return {"current_user": _current_session_user()}


@app.route("/")
def inicio():
    return render_template("public/inicio.html", titulo="Inicio")


@app.route("/login")
def login():
    current_user = _current_session_user()
    if current_user:
        if current_user["is_admin"]:
            return redirect(url_for("admin"))
        return redirect(url_for("panel_usuario"))
    return render_template("public/login.html", titulo="Login", form_data=_blank_login_form())


@app.route("/login", methods=["POST"])
def login_post():
    form_data = _login_form_from_request(request.form)

    try:
        user = authenticate_user(form_data["correo"], form_data["password"])
        _start_session(user)
        flash(f"Bienvenido, {user['nombre']}.", "success")
        return _redirect_after_login(user)
    except DatabaseError as exc:
        flash(str(exc), "error")

    return render_template("public/login.html", titulo="Login", form_data=form_data)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesion cerrada correctamente.", "success")
    return redirect(url_for("inicio"))


@app.route("/recuperar-contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    form_data = _blank_recovery_form()

    if request.method == "POST":
        form_data = _recovery_form_from_request(request.form)
        if form_data["password"] != form_data["password_confirm"]:
            flash("La confirmacion de contrasena no coincide.", "error")
        else:
            try:
                reset_user_password(form_data["correo"], form_data["telefono"], form_data["password"])
                flash("Contrasena actualizada. Ya puedes iniciar sesion.", "success")
                return redirect(url_for("login"))
            except DatabaseError as exc:
                flash(str(exc), "error")

    return render_template(
        "public/recuperar_contrasena.html",
        titulo="Recuperar contrasena",
        form_data=form_data,
    )


@app.route("/registro", methods=["GET", "POST"])
def registro():
    form_data = _blank_user_form()

    if request.method == "POST":
        form_data = _user_form_from_request(request.form)
        try:
            user_id = create_user({**form_data, "rol": "cliente", "activo": "true"})
            user = {
                "_id": user_id,
                "nombre": form_data["nombre"],
                "correo": form_data["correo"].strip().lower(),
                "rol": "cliente",
            }
            _start_session(user)
            flash("Cuenta creada correctamente. Bienvenido.", "success")
            return redirect(url_for("panel_usuario", identificador=user["correo"]))
        except DatabaseError as exc:
            flash(str(exc), "error")

    return render_template("public/registro.html", titulo="Registro", form_data=form_data)


@app.route("/panel-usuario")
@login_required
def panel_usuario():
    identificador = session.get("correo", "")

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


@app.route("/suscribirse/<plan_id>", methods=["POST"])
@login_required
def suscribirse(plan_id):
    try:
        create_subscription_for_user(session["user_id"], plan_id)
        flash("Suscripcion creada correctamente.", "success")
        return redirect(url_for("panel_usuario"))
    except DatabaseError as exc:
        flash(str(exc), "error")
        return redirect(url_for("planes"))


@app.route("/validar-viaje", methods=["GET", "POST"])
@login_required
def validar_viaje():
    form_data = _blank_validation_form()
    form_data["identificador"] = session.get("correo", "")
    resultado = None

    if request.method == "POST":
        form_data = _validation_form_from_request(request.form)
        form_data["identificador"] = session.get("correo", "")
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
@admin_required
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
@admin_required
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
@admin_required
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


@app.route("/admin/estaciones", methods=["GET", "POST"])
@admin_required
def admin_estaciones():
    if request.method == "POST":
        action = request.form.get("action", "")
        document_id = request.form.get("document_id", "").strip()
        payload = _station_form_from_request(request.form)

        try:
            if action == "create":
                create_station(payload)
                flash("Estacion creada correctamente.", "success")
                return redirect(url_for("admin_estaciones"))
            if action == "update":
                update_station(document_id, payload)
                flash("Estacion actualizada correctamente.", "success")
                return _redirect_to("admin_estaciones", document_id)
            if action == "delete":
                delete_station(document_id)
                flash("Estacion eliminada correctamente.", "success")
                return redirect(url_for("admin_estaciones"))
            flash("Accion invalida para estaciones.", "error")
        except DatabaseError as exc:
            flash(str(exc), "error")
            return _redirect_to("admin_estaciones", document_id if action == "update" else "")

    form_data = _blank_station_form()
    db_warning = None
    edit_id = request.args.get("edit", "").strip()

    if edit_id:
        try:
            form_data = _station_form_from_document(get_station(edit_id))
        except DatabaseError as exc:
            flash(str(exc), "error")

    try:
        estaciones = list_stations()
    except DatabaseError as exc:
        estaciones = []
        db_warning = str(exc)

    return render_template(
        "admin/estaciones.html",
        titulo="Admin Estaciones",
        estaciones=estaciones,
        form_data=form_data,
        db_warning=db_warning,
    )


@app.route("/admin/rutas", methods=["GET", "POST"])
@admin_required
def admin_rutas():
    if request.method == "POST":
        action = request.form.get("action", "")
        document_id = request.form.get("document_id", "").strip()
        payload = _route_form_from_request(request.form)

        try:
            if action == "create":
                create_route(payload)
                flash("Ruta creada correctamente.", "success")
                return redirect(url_for("admin_rutas"))
            if action == "update":
                update_route(document_id, payload)
                flash("Ruta actualizada correctamente.", "success")
                return _redirect_to("admin_rutas", document_id)
            if action == "delete":
                delete_route(document_id)
                flash("Ruta eliminada correctamente.", "success")
                return redirect(url_for("admin_rutas"))
            flash("Accion invalida para rutas.", "error")
        except DatabaseError as exc:
            flash(str(exc), "error")
            return _redirect_to("admin_rutas", document_id if action == "update" else "")

    form_data = _blank_route_form()
    db_warning = None
    edit_id = request.args.get("edit", "").strip()

    if edit_id:
        try:
            form_data = _route_form_from_document(get_route(edit_id))
        except DatabaseError as exc:
            flash(str(exc), "error")

    try:
        rutas = list_routes()
        estaciones = list_stations()
    except DatabaseError as exc:
        rutas = []
        estaciones = []
        db_warning = str(exc)

    return render_template(
        "admin/rutas.html",
        titulo="Admin Rutas",
        rutas=rutas,
        estaciones=estaciones,
        form_data=form_data,
        db_warning=db_warning,
    )


@app.route("/admin/suscripciones", methods=["GET", "POST"])
@admin_required
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
@admin_required
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

@app.route("/easter-egg")
def easter_egg():
    """Ruta para el Easter Egg oculto"""
    return render_template("easter-egg.html")


if __name__ == "__main__":
    app.run(debug=True)
