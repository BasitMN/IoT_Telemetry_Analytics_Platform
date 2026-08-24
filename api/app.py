import os
import time
import math
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
import yaml

app = Flask(__name__)

# Konfiguration från miljövariabler
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'telemetry_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASS', 'postgres')


def get_db_connection():
    """Skapar anslutning till databasen med retry-logik."""
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
            )
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            print("Väntar på databasanslutning...")
            time.sleep(2)
    raise Exception("Kunde inte ansluta till databasen")


def init_db():
    """Skapar tabellen om den inte finns.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id SERIAL PRIMARY KEY,
                sensor_id TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value NUMERIC NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Databasschema initierat.")
    except Exception as e:
        print(f"Fel vid databasinitiering: {e}")


def parse_timestamp(ts):
    """Tolkar en sträng till ett tidszons datum.
"""
    if not isinstance(ts, str):
        return None, "timestamp måste vara en ISO 8601-sträng"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None, "timestamp har ogiltigt format (förväntar ISO 8601)"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc), None


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route('/openapi.json', methods=['GET'])
def get_openapi():
    """Exponerar OpenAPI-kontraktet i JSON-format för Schemathesis."""
    openapi_path = os.path.join(os.path.dirname(__file__), '..', 'openapi.yaml')
    if os.path.exists(openapi_path):
        with open(openapi_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        return jsonify(spec), 200
    return jsonify({"error": "OpenAPI spec hittades inte"}), 404


@app.route('/api/v1/telemetry', methods=['GET'])
def get_telemetry():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, sensor_id, metric_type, value, timestamp FROM telemetry ORDER BY id DESC;")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for row in rows:
            ts = row['timestamp']
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                row['timestamp'] = ts.isoformat()
            row['value'] = float(row['value'])

        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/telemetry', methods=['POST'])
def post_telemetry():
    """Sparar ny telemetridata. Ogiltig indata -> alltid 400, aldrig 500."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Ingen giltig JSON-payload angiven"}), 400

    sensor_id = data.get('sensor_id')
    metric_type = data.get('metric_type')
    value = data.get('value')

    if not isinstance(sensor_id, str):
        return jsonify({"error": "sensor_id måste vara en sträng"}), 400
    if not isinstance(metric_type, str):
        return jsonify({"error": "metric_type måste vara en sträng"}), 400
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return jsonify({"error": "value måste vara ett tal"}), 400
    if isinstance(value, float) and not math.isfinite(value):
        return jsonify({"error": "value måste vara ett ändligt tal"}), 400

    # timestamp 
    ts_value = None
    if 'timestamp' in data:
        ts_value, err = parse_timestamp(data['timestamp'])
        if err is not None:
            return jsonify({"error": err}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if ts_value is not None:
            cur.execute(
                "INSERT INTO telemetry (sensor_id, metric_type, value, timestamp) VALUES (%s, %s, %s, %s);",
                (sensor_id, metric_type, value, ts_value)
            )
        else:
            cur.execute(
                "INSERT INTO telemetry (sensor_id, metric_type, value) VALUES (%s, %s, %s);",
                (sensor_id, metric_type, value)
            )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Telemetry data created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)