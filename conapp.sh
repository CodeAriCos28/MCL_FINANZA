#!/usr/bin/env bash
set -o errexit

echo "🔄 Actualizando pip, setuptools y wheel..."
python -m pip install --upgrade pip setuptools wheel

echo "📦 Instalando dependencias del proyecto..."
python -m pip install -r requirements.txt

echo "📁 Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "🧩 Creando migraciones..."
python manage.py makemigrations

echo "🗄️ Aplicando migraciones..."
python manage.py migrate

echo "👤 Creando superusuario si no existe..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model

User = get_user_model()
username = ""
email = ""
password = ""

user = User.objects.filter(username=username).first()

if not user:
    user = User(username=username, email=email, is_staff=True, is_superuser=True)
    user.set_password(password)
    user.save()
    print("Superusuario creado correctamente.")
else:
    print("El superusuario ya existe.")
EOF

echo "✅ Deploy terminado correctamente."
