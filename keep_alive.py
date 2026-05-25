from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "24/7 Alive"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def keep_alive():
    t = Thread(target=run)
    t.start()
