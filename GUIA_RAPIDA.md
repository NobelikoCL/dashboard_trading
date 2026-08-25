# Uso sencillo

1. Instale Python 3 en Windows.
2. Haga doble clic en `configurar.bat`.
3. Seleccione SQLite para guardar en el mismo PC, o PostgreSQL para ingresar la IP de otro equipo.
4. Ingrese las credenciales de PostgreSQL y las rutas de las tres instalaciones `terminal64.exe`.
5. El asistente prueba la conexion, crea la base si no existe y crea la tabla.
6. Haga doble clic en `iniciar.bat`.

Si PostgreSQL no responde, el asistente se detiene y muestra el error. Debe verificar que PostgreSQL este instalado, que el servicio este iniciado y que el firewall permita el puerto 5432.

La contrasena se guarda en `config.json`, por lo que ese archivo debe mantenerse privado. El colector no envia ordenes ni credenciales de trading a la base.
