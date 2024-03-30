FROM public.ecr.aws/docker/library/ubuntu:latest

# 必要なパッケージをインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg graphviz unzip ffmpeg gcc make git \
    ca-certificates python3-pip python3-dev \
    libnss3-dev libgdk-pixbuf2.0-dev libgtk-3-dev libxss-dev libasound2 fonts-ipafont-gothic libreoffice-impress poppler-utils libssl-dev && \
    update-ca-certificates && \
    curl -Lo "/tmp/chromedriver-linux64.zip" "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/119.0.6045.105/linux64/chromedriver-linux64.zip" && \
    curl -Lo "/tmp/chrome-linux64.zip" "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/119.0.6045.105/linux64/chrome-linux64.zip" && \
    unzip /tmp/chromedriver-linux64.zip -d /opt/ && \
    unzip /tmp/chrome-linux64.zip -d /opt/ && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /
COPY scripts /function
RUN git clone https://github.com/tatsuiman/GPTs-Actions && \
    cp -r GPTs-Actions/src/functions/* /function/functions/
WORKDIR /function
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie
RUN chmod 755 /usr/bin/aws-lambda-rie

ENTRYPOINT [ "/entrypoint.sh" ]
