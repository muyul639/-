import os
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "24/7 Alive"

if __name__ == "__main__":
    # 렌더가 할당한 포트를 사용하거나, 없으면 10000 사용
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
