FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY bootstrap_admin.py ./bootstrap_admin.py
COPY migrate_compat.py ./migrate_compat.py
CMD ["sh","-c","python migrate_compat.py && python bootstrap_admin.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
