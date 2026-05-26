import os
import re
from datetime import date, datetime, time, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

try:
    from bson import ObjectId
    from pymongo import ASCENDING, MongoClient
    from pymongo.errors import DuplicateKeyError, PyMongoError
except ImportError as exc:  # pragma: no cover - handled at runtime
    ObjectId = None
    MongoClient = None
    ASCENDING = 1
    DuplicateKeyError = RuntimeError
    PyMongoError = RuntimeError
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class DatabaseError(Exception):
    pass


class ValidationError(DatabaseError):
    pass


class DuplicateRecordError(DatabaseError):
    pass


class NotFoundError(DatabaseError):
    pass


_client = None
_db = None
_indexes_ready = False
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value):
    return (value or "").strip().lower()


def _validate_email(value):
    email = _normalize_email(value)
    if not email or not _EMAIL_PATTERN.match(email):
        raise ValidationError("Ingresa un correo valido.")
    return email


def _validate_password(value):
    password = (value or "").strip()
    if len(password) < 6:
        raise ValidationError("La contrasena debe tener al menos 6 caracteres.")
    return password


def _now():
    return datetime.now()


def _require_driver():
    if _IMPORT_ERROR is not None:
        raise DatabaseError(
            "PyMongo no esta instalado en el entorno virtual. Instala dependencias y vuelve a intentar."
        )


def _get_database():
    global _client, _db, _indexes_ready

    _require_driver()

    if _db is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        db_name = os.getenv("MONGO_DB_NAME", "app_transporte")

        try:
            _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2500)
            _client.admin.command("ping")
            _db = _client[db_name]
        except PyMongoError as exc:
            raise DatabaseError(
                "No se pudo conectar a MongoDB. Revisa MONGO_URI o que el servicio este encendido."
            ) from exc

    if not _indexes_ready:
        try:
            _db.usuarios.create_index([("correo", ASCENDING)], unique=True)
            _db.planes.create_index([("nombre", ASCENDING)], unique=True)
            _db.estaciones.create_index([("nombre", ASCENDING)], unique=True)
            _db.estaciones.create_index([("codigo", ASCENDING)], unique=True, sparse=True)
            _db.rutas.create_index([("nombre", ASCENDING)], unique=True)
            _db.rutas.create_index([("estaciones", ASCENDING)])
            _db.suscripciones.create_index([("usuario_id", ASCENDING), ("estado", ASCENDING)])
            _db.validaciones.create_index([("usuario_id", ASCENDING), ("fecha_hora", ASCENDING)])
        except PyMongoError as exc:
            raise DatabaseError("No se pudieron crear los indices necesarios en MongoDB.") from exc
        _indexes_ready = True

    return _db


def _object_id(value, field_name="id"):
    if not value:
        raise ValidationError(f"Falta el valor de {field_name}.")
    try:
        return ObjectId(str(value))
    except Exception as exc:
        raise ValidationError(f"El valor de {field_name} no es un ObjectId valido.") from exc


def _parse_bool(value):
    return str(value).strip().lower() in {"1", "true", "si", "activo", "on", "yes"}


def _normalize_station_code(value):
    return (value or "").strip().upper()


def _parse_float(value, field_name):
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except ValueError as exc:
        raise ValidationError(f"El campo {field_name} debe ser numerico.") from exc


def _parse_int(value, field_name):
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValidationError(f"El campo {field_name} debe ser un entero.") from exc


def _parse_date(value, field_name):
    if not value:
        raise ValidationError(f"El campo {field_name} es obligatorio.")
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f"El campo {field_name} debe tener formato YYYY-MM-DD.") from exc


def _date_to_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _serialize_value(value):
    if ObjectId is not None and isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.time() == time.min:
            return value.date().isoformat()
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _serialize_document(document):
    if not document:
        return None
    return {key: _serialize_value(value) for key, value in document.items()}


def _find_user_by_identifier(identifier):
    db = _get_database()
    normalized = (identifier or "").strip()
    if not normalized:
        raise ValidationError("Debes indicar un correo o un ObjectId de usuario.")

    if "@" in normalized:
        return db.usuarios.find_one({"correo": _normalize_email(normalized)})

    try:
        return db.usuarios.find_one({"_id": _object_id(normalized, "usuario")})
    except ValidationError:
        return db.usuarios.find_one({"correo": _normalize_email(normalized)})


def _find_user_by_email(email):
    db = _get_database()
    return db.usuarios.find_one({"correo": _validate_email(email)})


def _build_subscription_document(payload, current_id=None):
    db = _get_database()
    user_id = _object_id(payload.get("usuario_id"), "usuario")
    plan_id = _object_id(payload.get("plan_id"), "plan")
    estado = (payload.get("estado") or "").strip().lower()

    if estado not in {"activa", "pendiente", "cancelada"}:
        raise ValidationError("El estado de la suscripcion debe ser activa, pendiente o cancelada.")

    usuario = db.usuarios.find_one({"_id": user_id})
    if not usuario:
        raise ValidationError("El usuario seleccionado no existe.")

    plan = db.planes.find_one({"_id": plan_id})
    if not plan:
        raise ValidationError("El plan seleccionado no existe.")

    if not plan.get("activo", True):
        raise ValidationError("No se puede asignar una suscripcion con un plan inactivo.")

    fecha_inicio = _parse_date(payload.get("fecha_inicio"), "fecha_inicio")
    fecha_fin_raw = payload.get("fecha_fin")
    fecha_fin = _parse_date(fecha_fin_raw, "fecha_fin") if fecha_fin_raw else fecha_inicio + timedelta(days=365)

    if fecha_fin < fecha_inicio:
        raise ValidationError("La fecha de fin no puede ser anterior a la fecha de inicio.")

    if estado == "activa":
        active_filter = {"usuario_id": user_id, "estado": "activa"}
        active_subscription = db.suscripciones.find_one(active_filter)
        if active_subscription and str(active_subscription["_id"]) != str(current_id or ""):
            raise ValidationError("El usuario ya tiene una suscripcion activa.")

    return {
        "usuario_id": user_id,
        "usuario_nombre": usuario["nombre"],
        "usuario_correo": usuario["correo"],
        "plan_id": plan_id,
        "plan_nombre": plan["nombre"],
        "precio_anual": plan["precio_anual"],
        "limite_viajes_diarios": plan["limite_viajes_diarios"],
        "fecha_inicio": _date_to_datetime(fecha_inicio),
        "fecha_fin": _date_to_datetime(fecha_fin),
        "estado": estado,
        "updated_at": _now(),
    }


def _build_user_subscription_document(user_id, plan_id):
    db = _get_database()
    user_oid = _object_id(user_id, "usuario")
    plan_oid = _object_id(plan_id, "plan")

    usuario = db.usuarios.find_one({"_id": user_oid})
    if not usuario:
        raise ValidationError("No se encontro la cuenta del usuario.")

    plan = db.planes.find_one({"_id": plan_oid})
    if not plan:
        raise ValidationError("No se encontro el plan seleccionado.")
    if not plan.get("activo", True):
        raise ValidationError("El plan seleccionado no esta disponible.")

    active_subscription = db.suscripciones.find_one({"usuario_id": user_oid, "estado": "activa"})
    if active_subscription:
        raise ValidationError("Ya tienes una suscripcion activa.")

    fecha_inicio = date.today()
    fecha_fin = fecha_inicio + timedelta(days=365)

    return {
        "usuario_id": user_oid,
        "usuario_nombre": usuario["nombre"],
        "usuario_correo": usuario["correo"],
        "plan_id": plan_oid,
        "plan_nombre": plan["nombre"],
        "precio_anual": plan["precio_anual"],
        "limite_viajes_diarios": plan["limite_viajes_diarios"],
        "fecha_inicio": _date_to_datetime(fecha_inicio),
        "fecha_fin": _date_to_datetime(fecha_fin),
        "estado": "activa",
        "created_at": _now(),
        "updated_at": _now(),
    }


def list_users():
    db = _get_database()
    documents = db.usuarios.find().sort("created_at", -1)
    return [_serialize_document(document) for document in documents]


def get_user(user_id):
    db = _get_database()
    document = db.usuarios.find_one({"_id": _object_id(user_id, "usuario")})
    if not document:
        raise NotFoundError("No se encontro el usuario solicitado.")
    return _serialize_document(document)


def get_user_by_email(email):
    document = _find_user_by_email(email)
    if not document:
        raise NotFoundError("No se encontro una cuenta con ese correo.")
    return _serialize_document(document)


def count_admin_users():
    db = _get_database()
    return db.usuarios.count_documents({"rol": "admin", "activo": True})


def create_user(payload):
    db = _get_database()
    nombre = (payload.get("nombre") or "").strip()
    correo = _validate_email(payload.get("correo"))
    telefono = (payload.get("telefono") or "").strip()
    password = _validate_password(payload.get("password"))
    rol = (payload.get("rol") or "cliente").strip().lower()

    if not nombre:
        raise ValidationError("El nombre es obligatorio.")
    if rol not in {"cliente", "admin"}:
        raise ValidationError("El rol debe ser cliente o admin.")

    document = {
        "nombre": nombre,
        "correo": correo,
        "telefono": telefono,
        "password_hash": generate_password_hash(password),
        "rol": rol,
        "activo": _parse_bool(payload.get("activo", True)),
        "created_at": _now(),
        "updated_at": _now(),
    }

    try:
        result = db.usuarios.insert_one(document)
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe un usuario registrado con ese correo.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo guardar el usuario en MongoDB.") from exc

    return str(result.inserted_id)


def update_user(user_id, payload):
    db = _get_database()
    user_oid = _object_id(user_id, "usuario")
    nombre = (payload.get("nombre") or "").strip()
    correo = _validate_email(payload.get("correo"))
    telefono = (payload.get("telefono") or "").strip()
    rol = (payload.get("rol") or "cliente").strip().lower()
    password = (payload.get("password") or "").strip()

    if not nombre:
        raise ValidationError("El nombre es obligatorio.")
    if rol not in {"cliente", "admin"}:
        raise ValidationError("El rol debe ser cliente o admin.")

    updates = {
        "nombre": nombre,
        "correo": correo,
        "telefono": telefono,
        "rol": rol,
        "activo": _parse_bool(payload.get("activo", True)),
        "updated_at": _now(),
    }

    if password:
        updates["password_hash"] = generate_password_hash(_validate_password(password))

    try:
        result = db.usuarios.update_one({"_id": user_oid}, {"$set": updates})
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe un usuario registrado con ese correo.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo actualizar el usuario.") from exc

    if result.matched_count == 0:
        raise NotFoundError("No se encontro el usuario que intentas actualizar.")


def authenticate_user(email, password):
    user = _find_user_by_email(email)
    if not user:
        raise ValidationError("Correo o contrasena incorrectos.")

    if not user.get("activo", True):
        raise ValidationError("Esta cuenta esta desactivada.")

    password_hash = user.get("password_hash", "")
    if not password_hash or not check_password_hash(password_hash, password or ""):
        raise ValidationError("Correo o contrasena incorrectos.")

    return _serialize_document(user)


def reset_user_password(email, telefono, new_password):
    db = _get_database()
    user = _find_user_by_email(email)
    if not user:
        raise ValidationError("No se encontro una cuenta con esos datos.")

    saved_phone = (user.get("telefono") or "").strip()
    submitted_phone = (telefono or "").strip()
    if not saved_phone or saved_phone != submitted_phone:
        raise ValidationError("No se encontro una cuenta con esos datos.")

    result = db.usuarios.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": generate_password_hash(_validate_password(new_password)),
                "updated_at": _now(),
            }
        },
    )

    if result.matched_count == 0:
        raise NotFoundError("No se pudo actualizar la contrasena.")


def delete_user(user_id):
    db = _get_database()
    user_oid = _object_id(user_id, "usuario")

    try:
        result = db.usuarios.delete_one({"_id": user_oid})
        db.suscripciones.delete_many({"usuario_id": user_oid})
        db.validaciones.delete_many({"usuario_id": user_oid})
    except PyMongoError as exc:
        raise DatabaseError("No se pudo eliminar el usuario.") from exc

    if result.deleted_count == 0:
        raise NotFoundError("No se encontro el usuario que intentas eliminar.")


def list_all_plans():
    db = _get_database()
    documents = db.planes.find().sort("created_at", -1)
    return [_serialize_document(document) for document in documents]


def list_public_plans():
    db = _get_database()
    documents = db.planes.find({"activo": True}).sort("precio_anual", 1)
    return [_serialize_document(document) for document in documents]


def get_plan(plan_id):
    db = _get_database()
    document = db.planes.find_one({"_id": _object_id(plan_id, "plan")})
    if not document:
        raise NotFoundError("No se encontro el plan solicitado.")
    return _serialize_document(document)


def create_plan(payload):
    db = _get_database()
    nombre = (payload.get("nombre") or "").strip()
    descripcion = (payload.get("descripcion") or "").strip()

    if not nombre:
        raise ValidationError("El nombre del plan es obligatorio.")

    document = {
        "nombre": nombre,
        "descripcion": descripcion,
        "precio_anual": _parse_float(payload.get("precio_anual"), "precio_anual"),
        "limite_viajes_diarios": _parse_int(payload.get("limite_viajes_diarios"), "limite_viajes_diarios"),
        "activo": _parse_bool(payload.get("activo", True)),
        "created_at": _now(),
        "updated_at": _now(),
    }

    try:
        result = db.planes.insert_one(document)
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe un plan con ese nombre.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo guardar el plan en MongoDB.") from exc

    return str(result.inserted_id)


def update_plan(plan_id, payload):
    db = _get_database()
    updates = {
        "nombre": (payload.get("nombre") or "").strip(),
        "descripcion": (payload.get("descripcion") or "").strip(),
        "precio_anual": _parse_float(payload.get("precio_anual"), "precio_anual"),
        "limite_viajes_diarios": _parse_int(payload.get("limite_viajes_diarios"), "limite_viajes_diarios"),
        "activo": _parse_bool(payload.get("activo", True)),
        "updated_at": _now(),
    }

    if not updates["nombre"]:
        raise ValidationError("El nombre del plan es obligatorio.")

    try:
        result = db.planes.update_one({"_id": _object_id(plan_id, "plan")}, {"$set": updates})
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe un plan con ese nombre.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo actualizar el plan.") from exc

    if result.matched_count == 0:
        raise NotFoundError("No se encontro el plan que intentas actualizar.")


def delete_plan(plan_id):
    db = _get_database()
    plan_oid = _object_id(plan_id, "plan")

    if db.suscripciones.find_one({"plan_id": plan_oid}):
        raise ValidationError("No puedes eliminar un plan que ya tiene suscripciones asociadas.")

    try:
        result = db.planes.delete_one({"_id": plan_oid})
    except PyMongoError as exc:
        raise DatabaseError("No se pudo eliminar el plan.") from exc

    if result.deleted_count == 0:
        raise NotFoundError("No se encontro el plan que intentas eliminar.")


def list_stations():
    db = _get_database()
    documents = db.estaciones.find().sort("nombre", 1)
    return [_serialize_document(document) for document in documents]


def list_active_stations():
    db = _get_database()
    documents = db.estaciones.find({"activo": True}).sort("nombre", 1)
    return [_serialize_document(document) for document in documents]


def get_station(station_id):
    db = _get_database()
    document = db.estaciones.find_one({"_id": _object_id(station_id, "estacion")})
    if not document:
        raise NotFoundError("No se encontro la estacion solicitada.")
    return _serialize_document(document)


def create_station(payload):
    db = _get_database()
    nombre = (payload.get("nombre") or "").strip()
    codigo = _normalize_station_code(payload.get("codigo"))
    descripcion = (payload.get("descripcion") or "").strip()

    if not nombre:
        raise ValidationError("El nombre de la estacion es obligatorio.")

    document = {
        "nombre": nombre,
        "descripcion": descripcion,
        "activo": _parse_bool(payload.get("activo", True)),
        "created_at": _now(),
        "updated_at": _now(),
    }

    if codigo:
        document["codigo"] = codigo

    try:
        result = db.estaciones.insert_one(document)
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe una estacion registrada con ese nombre o codigo.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo guardar la estacion en MongoDB.") from exc

    return str(result.inserted_id)


def update_station(station_id, payload):
    db = _get_database()
    station_oid = _object_id(station_id, "estacion")
    nombre = (payload.get("nombre") or "").strip()
    codigo = _normalize_station_code(payload.get("codigo"))

    if not nombre:
        raise ValidationError("El nombre de la estacion es obligatorio.")

    updates = {
        "nombre": nombre,
        "descripcion": (payload.get("descripcion") or "").strip(),
        "activo": _parse_bool(payload.get("activo", True)),
        "updated_at": _now(),
    }

    update_operation = {"$set": updates}
    if codigo:
        updates["codigo"] = codigo
    else:
        update_operation["$unset"] = {"codigo": ""}

    try:
        result = db.estaciones.update_one({"_id": station_oid}, update_operation)
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe una estacion registrada con ese nombre o codigo.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo actualizar la estacion.") from exc

    if result.matched_count == 0:
        raise NotFoundError("No se encontro la estacion que intentas actualizar.")


def delete_station(station_id):
    db = _get_database()
    station_oid = _object_id(station_id, "estacion")

    if db.rutas.find_one({"estaciones": station_oid}):
        raise ValidationError("No puedes eliminar una estacion asociada a una ruta.")

    try:
        result = db.estaciones.delete_one({"_id": station_oid})
    except PyMongoError as exc:
        raise DatabaseError("No se pudo eliminar la estacion.") from exc

    if result.deleted_count == 0:
        raise NotFoundError("No se encontro la estacion que intentas eliminar.")


def _station_ids_from_payload(payload):
    if hasattr(payload, "getlist"):
        raw_values = payload.getlist("estaciones")
    else:
        raw_values = payload.get("estaciones", [])

    if isinstance(raw_values, str):
        raw_values = raw_values.split(",")
    elif raw_values is None:
        raw_values = []
    elif not isinstance(raw_values, (list, tuple, set)):
        raw_values = [raw_values]

    station_ids = []
    seen = set()
    for value in raw_values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        station_ids.append(_object_id(normalized, "estacion"))
        seen.add(normalized)

    if not station_ids:
        raise ValidationError("Selecciona al menos una estacion para la ruta.")

    return station_ids


def _route_station_documents(db, station_ids, require_all=True):
    documents = list(db.estaciones.find({"_id": {"$in": station_ids}}))
    documents_by_id = {str(document["_id"]): document for document in documents}

    if require_all and len(documents_by_id) != len(station_ids):
        raise ValidationError("Una o mas estaciones seleccionadas no existen.")

    return [documents_by_id[str(station_id)] for station_id in station_ids if str(station_id) in documents_by_id]


def _serialize_route_document(document):
    if not document:
        return None

    db = _get_database()
    serialized = _serialize_document(document)
    station_ids = document.get("estaciones", [])
    station_documents = _route_station_documents(db, station_ids, require_all=False) if station_ids else []
    serialized["estaciones_detalle"] = [_serialize_document(station) for station in station_documents]
    return serialized


def _build_route_document(payload):
    db = _get_database()
    nombre = (payload.get("nombre") or "").strip()
    descripcion = (payload.get("descripcion") or "").strip()
    station_ids = _station_ids_from_payload(payload)
    _route_station_documents(db, station_ids)

    if not nombre:
        raise ValidationError("El nombre de la ruta es obligatorio.")

    return {
        "nombre": nombre,
        "descripcion": descripcion,
        "estaciones": station_ids,
        "activo": _parse_bool(payload.get("activo", True)),
        "updated_at": _now(),
    }


def list_routes():
    db = _get_database()
    documents = db.rutas.find().sort("nombre", 1)
    return [_serialize_route_document(document) for document in documents]


def list_active_routes():
    db = _get_database()
    documents = db.rutas.find({"activo": True}).sort("nombre", 1)
    return [_serialize_route_document(document) for document in documents]


def get_route(route_id):
    db = _get_database()
    document = db.rutas.find_one({"_id": _object_id(route_id, "ruta")})
    if not document:
        raise NotFoundError("No se encontro la ruta solicitada.")
    return _serialize_route_document(document)


def create_route(payload):
    db = _get_database()
    document = _build_route_document(payload)
    document["created_at"] = _now()

    try:
        result = db.rutas.insert_one(document)
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe una ruta registrada con ese nombre.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo guardar la ruta en MongoDB.") from exc

    return str(result.inserted_id)


def update_route(route_id, payload):
    db = _get_database()
    route_oid = _object_id(route_id, "ruta")
    updates = _build_route_document(payload)

    try:
        result = db.rutas.update_one({"_id": route_oid}, {"$set": updates})
    except DuplicateKeyError as exc:
        raise DuplicateRecordError("Ya existe una ruta registrada con ese nombre.") from exc
    except PyMongoError as exc:
        raise DatabaseError("No se pudo actualizar la ruta.") from exc

    if result.matched_count == 0:
        raise NotFoundError("No se encontro la ruta que intentas actualizar.")


def delete_route(route_id):
    db = _get_database()
    route_oid = _object_id(route_id, "ruta")

    if db.validaciones.find_one({"ruta_id": route_oid}):
        raise ValidationError("No puedes eliminar una ruta que ya tiene validaciones asociadas.")

    try:
        result = db.rutas.delete_one({"_id": route_oid})
    except PyMongoError as exc:
        raise DatabaseError("No se pudo eliminar la ruta.") from exc

    if result.deleted_count == 0:
        raise NotFoundError("No se encontro la ruta que intentas eliminar.")


def list_subscriptions():
    db = _get_database()
    documents = db.suscripciones.find().sort("created_at", -1)
    return [_serialize_document(document) for document in documents]


def get_subscription(subscription_id):
    db = _get_database()
    document = db.suscripciones.find_one({"_id": _object_id(subscription_id, "suscripcion")})
    if not document:
        raise NotFoundError("No se encontro la suscripcion solicitada.")
    return _serialize_document(document)


def create_subscription(payload):
    db = _get_database()
    document = _build_subscription_document(payload)
    document["created_at"] = _now()

    try:
        result = db.suscripciones.insert_one(document)
    except PyMongoError as exc:
        raise DatabaseError("No se pudo guardar la suscripcion en MongoDB.") from exc

    return str(result.inserted_id)


def create_subscription_for_user(user_id, plan_id):
    db = _get_database()
    document = _build_user_subscription_document(user_id, plan_id)

    try:
        result = db.suscripciones.insert_one(document)
    except PyMongoError as exc:
        raise DatabaseError("No se pudo crear la suscripcion.") from exc

    return str(result.inserted_id)


def update_subscription(subscription_id, payload):
    db = _get_database()
    subscription_oid = _object_id(subscription_id, "suscripcion")
    updates = _build_subscription_document(payload, current_id=subscription_oid)

    try:
        result = db.suscripciones.update_one({"_id": subscription_oid}, {"$set": updates})
    except PyMongoError as exc:
        raise DatabaseError("No se pudo actualizar la suscripcion.") from exc

    if result.matched_count == 0:
        raise NotFoundError("No se encontro la suscripcion que intentas actualizar.")


def delete_subscription(subscription_id):
    db = _get_database()

    try:
        subscription_oid = _object_id(subscription_id, "suscripcion")
        result = db.suscripciones.delete_one({"_id": subscription_oid})
        db.validaciones.delete_many({"suscripcion_id": subscription_oid})
    except PyMongoError as exc:
        raise DatabaseError("No se pudo eliminar la suscripcion.") from exc

    if result.deleted_count == 0:
        raise NotFoundError("No se encontro la suscripcion que intentas eliminar.")


def lookup_user_panel(identifier):
    db = _get_database()
    usuario = _find_user_by_identifier(identifier)
    if not usuario:
        raise NotFoundError("No se encontro un usuario con ese identificador.")

    suscripciones = list(db.suscripciones.find({"usuario_id": usuario["_id"]}).sort("fecha_inicio", -1))
    validaciones = list(db.validaciones.find({"usuario_id": usuario["_id"]}).sort("fecha_hora", -1).limit(5))

    suscripcion_actual = None
    for subscription in suscripciones:
        if subscription.get("estado") == "activa":
            suscripcion_actual = subscription
            break

    return {
        "usuario": _serialize_document(usuario),
        "suscripcion_actual": _serialize_document(suscripcion_actual),
        "suscripciones": [_serialize_document(subscription) for subscription in suscripciones],
        "validaciones": [_serialize_document(validation) for validation in validaciones],
    }


def register_validation(payload):
    db = _get_database()
    identificador = (payload.get("identificador") or "").strip()
    ruta = (payload.get("ruta") or "").strip()
    estacion = (payload.get("estacion") or "").strip()
    route_id_raw = (payload.get("ruta_id") or "").strip()
    station_id_raw = (payload.get("estacion_id") or "").strip()

    if route_id_raw:
        route_oid = _object_id(route_id_raw, "ruta")
        route = db.rutas.find_one({"_id": route_oid, "activo": True})
        if not route:
            raise ValidationError("La ruta seleccionada no existe o esta inactiva.")

        if not station_id_raw:
            raise ValidationError("Selecciona una estacion para validar el viaje.")

        station_oid = _object_id(station_id_raw, "estacion")
        station = db.estaciones.find_one({"_id": station_oid, "activo": True})
        if not station:
            raise ValidationError("La estacion seleccionada no existe o esta inactiva.")
        if station_oid not in route.get("estaciones", []):
            raise ValidationError("La estacion seleccionada no pertenece a la ruta.")

        ruta = route["nombre"]
        estacion = station["nombre"]
    else:
        route_oid = None
        station_oid = None

    if not identificador or not ruta:
        raise ValidationError("Identificador y ruta son obligatorios para validar un viaje.")

    usuario = _find_user_by_identifier(identificador)
    suscripcion = None
    resultado = "rechazada"
    motivo = "Usuario no encontrado."

    if usuario:
        suscripcion = db.suscripciones.find_one(
            {
                "usuario_id": usuario["_id"],
                "estado": "activa",
                "fecha_fin": {"$gte": _date_to_datetime(date.today())},
            },
            sort=[("fecha_fin", -1)],
        )
        if suscripcion:
            limite_diario = suscripcion.get("limite_viajes_diarios")
            if limite_diario is None:
                plan = db.planes.find_one({"_id": suscripcion.get("plan_id")})
                limite_diario = plan.get("limite_viajes_diarios") if plan else None

            if limite_diario is None:
                resultado = "aceptada"
                motivo = "Suscripcion activa encontrada."
            else:
                start_of_day = datetime.combine(date.today(), time.min)
                end_of_day = start_of_day + timedelta(days=1)
                viajes_hoy = db.validaciones.count_documents(
                    {
                        "usuario_id": usuario["_id"],
                        "resultado": "aceptada",
                        "fecha_hora": {"$gte": start_of_day, "$lt": end_of_day},
                    }
                )
                if viajes_hoy >= int(limite_diario):
                    motivo = f"Limite diario de {limite_diario} viajes alcanzado."
                else:
                    resultado = "aceptada"
                    motivo = f"Suscripcion activa encontrada. Viaje {viajes_hoy + 1} de {limite_diario} permitido hoy."
        else:
            motivo = "El usuario existe pero no tiene una suscripcion activa."

    document = {
        "identificador": identificador,
        "usuario_id": usuario["_id"] if usuario else None,
        "usuario_nombre": usuario.get("nombre") if usuario else None,
        "suscripcion_id": suscripcion["_id"] if suscripcion else None,
        "ruta_id": route_oid,
        "estacion_id": station_oid,
        "ruta": ruta,
        "estacion": estacion,
        "resultado": resultado,
        "motivo": motivo,
        "fecha_hora": _now(),
    }

    try:
        result = db.validaciones.insert_one(document)
    except PyMongoError as exc:
        raise DatabaseError("No se pudo registrar la validacion del viaje.") from exc

    created = db.validaciones.find_one({"_id": result.inserted_id})
    return _serialize_document(created)


def get_dashboard_stats():
    db = _get_database()
    start_of_day = datetime.combine(date.today(), datetime.min.time())

    return {
        "usuarios": db.usuarios.count_documents({}),
        "usuarios_activos": db.usuarios.count_documents({"activo": True}),
        "suscripciones_activas": db.suscripciones.count_documents({"estado": "activa"}),
        "planes": db.planes.count_documents({}),
        "validaciones_hoy": db.validaciones.count_documents({"fecha_hora": {"$gte": start_of_day}}),
    }


def get_report_data():
    db = _get_database()
    start_of_month = datetime.combine(date.today().replace(day=1), datetime.min.time())
    total_validaciones = db.validaciones.count_documents({})
    usuarios_activos = db.usuarios.count_documents({"activo": True})
    promedio = round(total_validaciones / usuarios_activos, 2) if usuarios_activos else 0

    top_planes = list(
        db.suscripciones.aggregate(
            [
                {"$group": {"_id": "$plan_nombre", "total": {"$sum": 1}}},
                {"$sort": {"total": -1}},
                {"$limit": 5},
            ]
        )
    )

    recent_validations = list(db.validaciones.find().sort("fecha_hora", -1).limit(5))

    return {
        "suscripciones_mes": db.suscripciones.count_documents({"created_at": {"$gte": start_of_month}}),
        "usuarios_activos": usuarios_activos,
        "promedio_validaciones": promedio,
        "validaciones_totales": total_validaciones,
        "top_planes": [{"plan": item.get("_id") or "Sin nombre", "total": item.get("total", 0)} for item in top_planes],
        "validaciones_recientes": [_serialize_document(document) for document in recent_validations],
    }
