FROM --platform=linux/arm64 ubuntu:22.04

RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*

COPY ci/fardrun /usr/local/bin/fardrun
RUN chmod +x /usr/local/bin/fardrun

WORKDIR /repo
COPY . .

RUN mkdir -p out

CMD ["bash", "-c", \
  "fardrun run --program programs/regression.fard --out /tmp/reg && \
   chmod +x out/r_* 2>/dev/null || true && \
   python3 programs/regression_run.py /tmp/reg/result.json && \
   python3 programs/regression_python.py"]
