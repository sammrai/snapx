FROM python:3.11

WORKDIR /app

# リポジトリをクローン
RUN git clone https://github.com/sammrai/sd-webui-infinite-image-browsing /app

# 依存パッケージのインストール
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# プラグインのインストール
ADD plugins /app/plugins/
ADD xdg-open /usr/local/bin/

# コンテナ起動時のコマンド
CMD ["python", "app.py", "--port=7888", "--host=0.0.0.0"]
