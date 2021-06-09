FROM python:3.7 as base

COPY ./dist /app/dist
COPY ./requirements.txt /app/requirements.txt

ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple
ENV PIP_FIND_LINKS=/wheeley

RUN pip3 install wheel \
    && pip3 wheel --wheel-dir=/wheeley -r /app/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley /app/dist/*

FROM python:3.7-slim
EXPOSE 5000
WORKDIR /app

ARG service_info=UNKNOWN
ENV SERVICE_INFO=${service_info}

COPY --from=base /wheeley /wheeley

RUN pip3 install --no-index --find-links=/wheeley YOUR-PACKAGE \
    && rm -rf /wheeley \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "YOUR_PACKAGE"]
