FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 python3-pip curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy fardrun binary (must be linux-x86_64)
# Build: docker build requires fardrun-linux-x86_64 in repo root
COPY fardrun-linux-x86_64 /usr/local/bin/fardrun
RUN chmod +x /usr/local/bin/fardrun

WORKDIR /repo
