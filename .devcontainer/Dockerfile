FROM python:3.13-slim

# Install Java
RUN apt update &&  \
    apt install -y curl telnet git

## Pip dependencies
# Upgrade pip
RUN pip install --upgrade pip

# Install production dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Install development dependencies
COPY dev-requirements.txt /tmp/requirements-dev.txt
RUN pip install -r /tmp/requirements-dev.txt && \
    rm /tmp/requirements-dev.txt