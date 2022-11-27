FROM python:3.8.5-alpine

RUN pip install --upgrade pip
RUN pip install tzdata
RUN apk update && apk add gcc musl-dev
RUN apk add --no-cache bash coreutils grep sed


COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . /app

WORKDIR /app

COPY ./init.sh /
ENTRYPOINT ["sh", "/init.sh"]