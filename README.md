# VillaCapital Monitor

Dashboard local de gestión y monitorización de cuentas MT5. La aplicación mantiene el colector existente y añade un frontend React con API Django para tratar los snapshots guardados en PostgreSQL.

## Dashboard local

1. Copie `.env.example` como `.env` y revise la conexión a PostgreSQL. Los valores iniciales apuntan a `192.168.1.34:5432`, base `mt5_monitor`, usuario `hernan`.
2. Compruebe que la máquina Docker puede alcanzar `192.168.1.34` y que PostgreSQL acepta conexiones remotas.
3. Ejecute `docker compose up --build`.
4. Abra `http://localhost:5173`.

La API queda disponible en `http://localhost:8000/api/health/` y `http://localhost:8000/api/dashboard/?period=30D`. Si PostgreSQL no responde, el dashboard indica que no hay conexión y no muestra cifras ficticias.

## Despliegue en servidor Linux desde GitHub

### 1. Subir el proyecto a GitHub

Desde la raíz del proyecto en Windows:

```powershell
git init
git add .
git commit -m "Add VillaCapital trading monitor"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

No subas `.env`, `config.json`, contraseñas ni claves privadas. `.gitignore` ya excluye esos archivos.

### 2. Preparar el servidor Linux

Instala Docker Engine y el plugin Compose. Después clona el repositorio:

```bash
git clone https://github.com/USUARIO/REPOSITORIO.git villacapital-monitor
cd villacapital-monitor
cp .env.example .env
nano .env
```

En `.env` configura la IP del PostgreSQL y el resto de credenciales. `POSTGRES_HOST` debe ser accesible desde el servidor Linux; si PostgreSQL está en la misma red, utiliza `192.168.1.34`.

### 3. Arrancar los servicios

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/api/health/
```

Los contenedores tienen `restart: unless-stopped`, por lo que se levantan de nuevo tras un reinicio del servidor.

### 4. Verlo desde la misma red

Obtén la IP LAN del servidor:

```bash
hostname -I
```

Desde otro equipo de la red abre:

```text
http://IP_DEL_SERVIDOR:5173
```

El backend queda accesible en `http://IP_DEL_SERVIDOR:8000`. Docker publica ambos puertos en `0.0.0.0`.

### 5. Abrir el firewall

En Ubuntu con UFW:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 5173 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 8000 proto tcp
sudo ufw status
```

Si solo quieres exponer el dashboard, no abras el puerto `8000` fuera del servidor; el frontend lo utiliza internamente mediante el proxy Docker.

### 6. Mantenimiento

```bash
docker compose logs -f --tail 100
docker compose pull
git pull origin main
docker compose up --build -d
docker compose down
```

Para producción pública se recomienda colocar Nginx o un proxy inverso delante del puerto `5173` y proteger el acceso con HTTPS y autenticación.

El backend espera la tabla creada por el colector existente:

`account_snapshots (account_login, server, broker, account_name, balance, equity, open_positions, captured_at, terminal_name)`

El dashboard es de solo lectura: no envía órdenes a MetaTrader 5.

## Colector MT5

Solucion liviana para capturar desde hasta tres terminales MetaTrader 5:
numero de cuenta, broker, nombre, balance, equity, posiciones abiertas y fecha.

## Uso

1. Instale Python 3 para Windows.
2. Ejecute `configurar.bat` con doble clic.
3. Seleccione SQLite local o PostgreSQL e ingrese la IP, puerto, usuario y contrasena.
4. Ingrese la ruta completa de cada `terminal64.exe`.
5. El asistente prueba la conexion, crea la base PostgreSQL si no existe y crea la tabla.
6. Ejecute `iniciar.bat`.

Para PostgreSQL, la cuenta usada debe tener permiso para crear bases de datos. Si el servidor no responde, el asistente informa el error sin iniciar el colector.

El intervalo minimo es 10 segundos; se recomienda 60. Las terminales se consultan una por una y la conexion MT5 se cierra despues de cada lectura para reducir consumo. El colector solo lee informacion, no envia ordenes.

La contrasena de PostgreSQL queda en `config.json`; mantenga ese archivo privado.
