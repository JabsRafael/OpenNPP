# Simulador de processo AP1000-like (planta OT do cyber range OpenNPP)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# dependencias primeiro (cache de camada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# codigo do simulador
COPY npp ./npp
COPY web ./web
COPY main.py .

# 502 = Modbus TCP (rede OT) | 5000 = HMI web + API
EXPOSE 502 5000

CMD ["python", "main.py"]
