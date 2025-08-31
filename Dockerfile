FROM python:3.10-slim

COPY backend/ backend/
COPY problems/ backend/problems/
WORKDIR /backend
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r docker && usermod -aG docker www-data

RUN touch z.bash && chown www-data:www-data z.bash
RUN touch unixtime.txt && chown www-data:www-data unixtime.txt && echo 0.0 > unixtime.txt
RUN touch shellgei_id.txt && chown www-data:www-data shellgei_id.txt && echo 0 > shellgei_id.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "main:app"]