FROM python:3.13-slim
WORKDIR /TODO-bot
COPY requirements.txt .
RUN pip install --no-cache-dir -U -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "server:app"]
