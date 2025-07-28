FROM python:3.9

WORKDIR /test

COPY ./requirements.txt /test/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /test/requirements.txt

COPY ./myapp /test/myapp

WORKDIR /test/myapp

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]