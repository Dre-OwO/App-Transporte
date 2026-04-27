# App-Transporte

Aplicacion Flask para gestionar suscripciones de transporte publico con MongoDB.

## 1. Preparar entorno Python

```bash
cd "put your path here cawn"
python3 -m venv app_transporte
source app_transporte/bin/activate
pip install -r requirements.txt
```

## 2. Iniciar MongoDB

En macOS con Homebrew:

```bash
brew services start mongodb-community@8.0
brew services list | grep mongodb
```

Para comprobar conexion:

```bash
mongosh "mongodb://localhost:27017/"
```

## 3. Configurar variables

```bash
export MONGO_URI="mongodb://localhost:27017/"
export MONGO_DB_NAME="app_transporte"
```

## 4. Crear primer administrador

Con MongoDB encendido y el entorno virtual activo:

```bash
python3 scripts/create_admin.py
```

El script pide nombre, correo, telefono y contrasena. Si ya existe un administrador activo, pregunta antes de crear otro.

## 5. Ejecutar aplicacion

```bash
python3 app.py
```

Abrir en navegador:

```text
http://127.0.0.1:5000
```

