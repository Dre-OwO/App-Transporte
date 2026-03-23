# App-Transporte

Aplicacion Flask para gestionar suscripciones de transporte publico.

## Dependencias

```bash
source app_transporte/bin/activate
pip install -r requirements.txt
```

## MongoDB

La app usa MongoDB con estas variables opcionales:

```bash
export MONGO_URI="mongodb://localhost:27017/"
export MONGO_DB_NAME="app_transporte"
```

## Ejecutar

```bash
python3 app.py
```
