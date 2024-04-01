FROM python:3.11

WORKDIR /bot

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "server.py"]
