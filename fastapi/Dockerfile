FROM python:3.9

WORKDIR /code

COPY requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code/app
COPY main.py /code/app/main.py

RUN ls -la /code
RUN ls -la /code/app

CMD ["fastapi", "dev", "./app/main.py", "--host", "0.0.0.0", "--port", "8000"]