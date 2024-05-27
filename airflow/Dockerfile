FROM apache/airflow:2.7.3-python3.10 
COPY ./requirements.txt ./tmp/requirements.txt
COPY .env .env
RUN pip install -U pip
RUN pip install -r ./tmp/requirements.txt
ENV PYTHONPATH="${PYTHONPATH}:/home/mle-user/mle-pipeline-model-development/airflow"