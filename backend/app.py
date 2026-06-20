from flask import Flask
from flask_cors import CORS
from routes.mirbase import mirbase_bp
from db import local_db

app = Flask(__name__)

# Ensure schema + indexes exist on every startup (CREATE IF NOT EXISTS — safe on existing DBs)
local_db.init_schema()

CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]}})

app.register_blueprint(mirbase_bp, url_prefix='/api')


@app.route('/api/health')
def health():
    return {"status": "ok", "message": "Backend is running", "version": "2.0.0"}


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
