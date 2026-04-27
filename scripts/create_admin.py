import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from database import DatabaseError, count_admin_users, create_user


def _ask_required(label):
    value = input(f"{label}: ").strip()
    while not value:
        print("Este campo es obligatorio.")
        value = input(f"{label}: ").strip()
    return value


def _ask_password():
    password = getpass.getpass("Contrasena: ").strip()
    confirm = getpass.getpass("Confirmar contrasena: ").strip()
    while password != confirm:
        print("Las contrasenas no coinciden.")
        password = getpass.getpass("Contrasena: ").strip()
        confirm = getpass.getpass("Confirmar contrasena: ").strip()
    return password


def main():
    print("Crear administrador inicial")
    print("----------------------------")

    try:
        existing_admins = count_admin_users()
    except DatabaseError as exc:
        print(f"Error: {exc}")
        return 1

    if existing_admins:
        print(f"Ya existen {existing_admins} administradores activos.")
        answer = input("Quieres crear otro administrador? [s/N]: ").strip().lower()
        if answer not in {"s", "si", "y", "yes"}:
            print("Operacion cancelada.")
            return 0

    nombre = _ask_required("Nombre completo")
    correo = _ask_required("Correo")
    telefono = _ask_required("Telefono")
    password = _ask_password()

    try:
        user_id = create_user(
            {
                "nombre": nombre,
                "correo": correo,
                "telefono": telefono,
                "password": password,
                "rol": "admin",
                "activo": "true",
            }
        )
    except DatabaseError as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Administrador creado correctamente: {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
