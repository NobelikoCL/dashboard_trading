import getpass
import json
from pathlib import Path
from typing import Any


def ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def terminal_executable(value: str) -> str:
    path = Path(value.strip().strip('"'))
    if path.is_dir():
        path = path / "terminal64.exe"
    if path.name.lower() != "terminal64.exe":
        raise ValueError(f"La ruta debe apuntar a terminal64.exe: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"No se encontro el ejecutable: {path}")
    return str(path)


def create_postgres_database(settings: dict[str, Any]) -> None:
    import psycopg
    from psycopg import sql

    connection = psycopg.connect(host=settings["host"], port=settings["port"], dbname="postgres",
                                  user=settings["user"], password=settings["password"], connect_timeout=5)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings["name"],))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings["name"])))
                print(f"Base de datos '{settings['name']}' creada.")
            else:
                print("La base de datos ya existe.")
    finally:
        connection.close()


def main() -> None:
    print("\n=== Configuracion de capturadora MT5 ===\n")
    print("1) SQLite local (sin servidor)")
    print("2) PostgreSQL (permite guardar usando una IP de la red)")
    storage = ask("Tipo de almacenamiento", "1")
    if storage == "2":
        database = {"type": "postgres", "host": ask("IP del servidor PostgreSQL", "127.0.0.1"),
                    "port": int(ask("Puerto", "5432")), "name": ask("Nombre de la base", "mt5_monitor"),
                    "user": ask("Usuario PostgreSQL", "postgres"),
                    "password": getpass.getpass("Contrasena PostgreSQL: "), "connect_timeout": 5}
        print("Probando servidor y creando la base si no existe...")
        create_postgres_database(database)
    else:
        database = {"type": "sqlite", "path": "data/mt5_capture.sqlite3"}
        print("Se usara SQLite local.")

    terminals = []
    for number in range(1, 4):
        path = terminal_executable(ask(f"Ruta de carpeta o terminal64.exe para MT5 {number}"))
        if not path:
            raise ValueError("Debe indicar las tres rutas de MT5")
        terminals.append({"name": ask("Nombre identificador", f"Cuenta {number}"),
                          "terminal_path": path, "portable": False})
    config = {"poll_interval_seconds": int(ask("Intervalo en segundos", "60")),
              "mt5_terminals": terminals, "database": database}
    Path("config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    from collector import Database
    db = Database(database)
    db.connect()
    db.close()
    print("\nConfiguracion guardada. Conexion y tabla verificadas.")
    print("Ejecute iniciar.bat para comenzar.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        input("Presione Enter para cerrar...")
