FROM python:3.11
WORKDIR /app
COPY requirements.txt /app
RUN mkdir /download && chown 8000 /download && pip install --no-cache-dir -r requirements.txt
COPY . /app

USER 8000
CMD [ "python", "./app.py" ]
EXPOSE 5000
