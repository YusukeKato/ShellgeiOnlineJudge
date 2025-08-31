FROM python:3.10-slim

COPY backend/ backend/
COPY problems/ backend/problems/
WORKDIR /backend
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r docker && usermod -aG docker www-data

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]