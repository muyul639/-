from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "봇이 정상적으로 작동 중입니다!"

def run():
    # 렌더가 지정한 PORT를 최우선으로 사용합니다.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()