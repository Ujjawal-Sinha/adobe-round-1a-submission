FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir pymupdf pandas

COPY main.py /app/main.py

RUN mkdir /app/input /app/output

ENTRYPOINT ["python", "main.py"]
