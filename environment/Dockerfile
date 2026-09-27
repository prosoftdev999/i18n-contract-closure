FROM python:3.13-slim-bookworm
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
COPY data/ /evidence/
RUN mkdir -p /home/agent /app/output \
    && ln -s /evidence /app/data \
    && chown -R 1000:1000 /home/agent /app/output
USER 1000:1000
ENV HOME=/home/agent
CMD ["sleep","infinity"]
