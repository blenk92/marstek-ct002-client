FROM python:3.13-alpine

COPY meter-reader.py /usr/bin/meter-reader.py
COPY requirements.txt /opt/app/requirements.txt

RUN python -m pip install -r /opt/app/requirements.txt

CMD ["python", "/usr/bin/meter-reader.py"]
