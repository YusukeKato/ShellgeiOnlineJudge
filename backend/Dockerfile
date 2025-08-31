FROM python:3.10
WORKDIR /backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN groupadd -r docker && usermod -aG docker www-data

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]