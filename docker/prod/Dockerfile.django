FROM python:3.10

ENV PYTHONUNBUFFERED=1

WORKDIR /twist/

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --no-input

EXPOSE 8000
