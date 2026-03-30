FROM python:3.9-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CODE_DIR=/joko-app \
    BASE_DIR=/joko-app/data \
    CHROME_BINARY=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /joko-app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl unzip gnupg2 jq xvfb xauth \
    procps psmisc \
    ca-certificates \
    nano vim-tiny less \
    fonts-liberation \
    libnss3 libxss1 libasound2 \
    libgbm1 libu2f-udev libvulkan1 \
    libgtk-3-0 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxrandr2 libxdamage1 libxcomposite1 libxfixes3 libxi6 \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google.gpg; \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends google-chrome-stable; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /etc/opt/chrome/policies/managed; \
    printf '%s\n' \
    '{' \
    '  "SyncDisabled": true,' \
    '  "BrowserSignin": 0,' \
    '  "SigninAllowed": false,' \
    '  "PasswordManagerEnabled": false,' \
    '  "CredentialsEnableService": false' \
    '}' \
    > /etc/opt/chrome/policies/managed/policy.json

RUN set -eux;     CHROME_TRIPLE="$(google-chrome --version | awk '{print $3}' | cut -d '.' -f1-3)";     echo ">> Detected Chrome build: ${CHROME_TRIPLE}";     DRIVER_VERSION="$(curl -fsSL "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_TRIPLE}")";     echo ">> Resolved chromedriver version: ${DRIVER_VERSION}";     curl -fsSL -o /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip";     unzip /tmp/chromedriver.zip -d /tmp/;     mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver;     rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64;     chmod +x /usr/local/bin/chromedriver;     ln -sf /usr/local/bin/chromedriver /usr/bin/chromedriver

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      psutil requests \
      selenium==4.9.0 \
      Pillow pyvirtualdisplay mss pyautogui colorama

COPY login.py loop.py buat_link.py menu.sh entrypoint.sh ./

RUN chmod +x /joko-app/entrypoint.sh /joko-app/menu.sh && \
    mkdir -p /joko-app/data/chrome_profiles /joko-app/data/screenshots /joko-app/data/snapshots && \
    touch /joko-app/data/email.txt \
          /joko-app/data/emailshare.txt \
          /joko-app/data/mapping_profil.txt \
          /joko-app/data/bot_log.txt \
          /joko-app/data/login_log.txt \
          /joko-app/data/loop_log.txt \
          /joko-app/data/buat_link_log.txt \
          /joko-app/data/loop_status.json

VOLUME ["/joko-app/data"]

CMD ["./entrypoint.sh"]
