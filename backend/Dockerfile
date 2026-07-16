FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir sentence-transformers==3.4.1 && \
    pip install --no-cache-dir -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

FROM python:3.11-slim
WORKDIR /app

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 --home /home/appuser appuser

ENV HF_HOME=/home/appuser/.cache/huggingface
COPY --from=builder --chown=appuser:appuser /root/.cache /home/appuser/.cache
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=appuser:appuser . .
RUN chmod +x entrypoint.sh

USER appuser
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
