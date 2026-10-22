FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Recolectar estáticos al construir (la SECRET_KEY de acá solo vive durante el build)
RUN SECRET_KEY=solo-build python manage.py collectstatic --noinput

# Usuario sin privilegios, con el mismo UID que tu usuario del VPS (1000)
RUN useradd -u 1000 -m app && mkdir /data && chown app:app /data
USER app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn mise_core.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 30"]