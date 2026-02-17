FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec gunicorn app:app -w $(( $(nproc) * 2 + 1 )) --threads=4 --bind=0.0.0.0:5000 --timeout=30 --log-level=info"]
