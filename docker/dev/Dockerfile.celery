FROM python:3.10

ENV PYTHONUNBUFFERED=1

WORKDIR /twist/

COPY ./requirements.txt /twist
RUN pip install --no-cache-dir -r requirements.txt
