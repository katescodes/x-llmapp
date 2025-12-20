FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 第一层：安装系统依赖（不常变，可缓存）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
        libreoffice \
        libreoffice-writer \
        libreoffice-core \
        libreoffice-java-common \
        default-jre-headless \
        fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# 第二层：安装Python包（requirements.txt变化时才重建）
COPY requirements.txt ./
RUN pip install --no-cache-dir \
       -i https://mirrors.aliyun.com/pypi/simple/ \
       --trusted-host mirrors.aliyun.com \
       -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY testdata ./testdata
COPY worker.py ./worker.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
