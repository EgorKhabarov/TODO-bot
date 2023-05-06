FROM python:3.11

RUN mkdir -p /bot

WORKDIR /bot

ENV BOT_TOKEN=""

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]
