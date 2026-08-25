from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("mt5-collector")
SCHEMA = """
CREATE TABLE IF NOT EXISTS account_snapshots (
    id BIGINT PRIMARY KEY, account_login BIGINT NOT NULL, server TEXT NOT NULL,
    broker TEXT, account_name TEXT, balance NUMERIC NOT NULL, equity NUMERIC NOT NULL,
    open_positions INTEGER NOT NULL, captured_at TIMESTAMP NOT NULL, terminal_name TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Terminal:
    name: str
    path: str
    portable: bool = False


class Database:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.kind = settings.get("type", "sqlite").lower()
        self.connection: Any = None

    def connect(self) -> None:
        if self.kind == "sqlite":
            path = Path(self.settings.get("path", "data/mt5_capture.sqlite3"))
            path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(path)
            schema = SCHEMA.replace("BIGINT", "INTEGER").replace("NUMERIC", "REAL")
            self.connection.execute(schema)
        elif self.kind in {"postgres", "postgresql"}:
            import psycopg
            self.connection = psycopg.connect(host=self.settings["host"], port=self.settings.get("port", 5432),
                                              dbname=self.settings["name"], user=self.settings["user"],
                                              password=self.settings["password"],
                                              connect_timeout=self.settings.get("connect_timeout", 5))
            with self.connection.cursor() as cursor:
                cursor.execute(SCHEMA)
        else:
            raise ValueError("database.type debe ser sqlite o postgres")
        self.connection.commit()

    def insert(self, snapshot: dict[str, Any]) -> None:
        placeholder = "?" if self.kind == "sqlite" else "%s"
        query = f"INSERT INTO account_snapshots (id, account_login, server, broker, account_name, balance, equity, open_positions, captured_at, terminal_name) VALUES ({', '.join([placeholder] * 10)})"
        values = tuple(snapshot.values())
        if self.kind == "sqlite":
            self.connection.execute(query, values)
        else:
            with self.connection.cursor() as cursor:
                cursor.execute(query, values)
        self.connection.commit()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()


def load_config() -> dict[str, Any]:
    path = Path("config.json")
    if not path.exists():
        raise FileNotFoundError("No existe config.json. Ejecute configurar.bat")
    with path.open(encoding="utf-8") as file:
        config = json.load(file)
    if not 1 <= len(config.get("mt5_terminals", [])) <= 3:
        raise ValueError("Configure entre 1 y 3 terminales MT5")
    return config


def resolve_terminal_path(value: str) -> str:
    path = Path(value.strip().strip('"'))
    if path.is_dir():
        path = path / "terminal64.exe"
    if not path.is_file() or path.name.lower() != "terminal64.exe":
        raise FileNotFoundError(f"No se encontro terminal64.exe en: {path}")
    return str(path)


def read_terminal(terminal: Terminal) -> dict[str, Any]:
    import MetaTrader5 as mt5
    if not mt5.initialize(path=terminal.path, portable=terminal.portable):
        raise RuntimeError(f"initialize fallo: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        positions = mt5.positions_get()
        if account is None or positions is None:
            raise RuntimeError(f"lectura MT5 fallo: {mt5.last_error()}")
        return {"id": time.time_ns(), "account_login": int(account.login),
                "server": str(account.server or ""), "broker": str(getattr(account, "company", "") or ""),
                "account_name": str(getattr(account, "name", "") or ""), "balance": float(account.balance),
                "equity": float(account.equity), "open_positions": len(positions),
                "captured_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "terminal_name": terminal.name}
    finally:
        mt5.shutdown()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    terminals = [Terminal(x["name"], resolve_terminal_path(x["terminal_path"]),
                          x.get("portable", False)) for x in config["mt5_terminals"]]
    database = Database(config.get("database", {}))
    database.connect()
    interval = max(10, int(config.get("poll_interval_seconds", 60)))
    LOGGER.info("Colector activo: %d terminales, intervalo %ds", len(terminals), interval)
    try:
        while True:
            for terminal in terminals:
                try:
                    snapshot = read_terminal(terminal)
                    database.insert(snapshot)
                    LOGGER.info("%s: cuenta %s, equity %.2f, posiciones %d", terminal.name,
                                snapshot["account_login"], snapshot["equity"], snapshot["open_positions"])
                except Exception as error:
                    LOGGER.error("%s: %s", terminal.name, error)
            time.sleep(interval)
    except KeyboardInterrupt:
        LOGGER.info("Colector detenido")
    finally:
        database.close()


if __name__ == "__main__":
    main()
