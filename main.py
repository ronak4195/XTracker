# from flask import Flask, request, jsonify
# import mysql.connector
# import requests
# import threading
# import time
# from celery import Celery
# import redis

# app = Flask(__name__)

# # Database connection
# db_config = {
#     "host": "localhost",
#     "user": "root",   # Replace with your MySQL username
#     "password": "Str0ng!Passw0rd",  # Replace with your MySQL password
#     "database": "website_monitor"
# }

# webhook_url = None

# def get_db_connection():
#     return mysql.connector.connect(**db_config)

# # Function to monitor sites
# def monitor_sites():
#     while True:
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)
#         cursor.execute("SELECT * FROM monitored_sites")
#         sites = cursor.fetchall()

#         for site in sites:
#             site_id = site["id"]
#             url = site["url"]
#             try:
#                 response = requests.get(url, timeout=5)
#                 current_status = "up" if response.status_code == 200 else "down"
#             except requests.RequestException:
#                 current_status = "down"

#             cursor.execute("SELECT status FROM monitored_sites WHERE id = %s", (site_id,))
#             previous_status = cursor.fetchone()
#             previous_status = previous_status["status"] if previous_status else "unknown"
#             # if previous_status is None:
#             #     previous_status = "unknown"

#             # Insert new status into status_history table
#             cursor.execute(
#                 "INSERT INTO status_history (site_id, status) VALUES (%s, %s)",
#                 (site_id, current_status)
#             )
#             conn.commit()

#             # Send Discord alert only if the status has changed
#             if current_status != previous_status and webhook_url:
#                 send_discord_alert(url, current_status)
#                 cursor.execute(
#                     "UPDATE monitored_sites SET status = %s WHERE id = %s",
#                     (current_status, site_id)
#                 )
#                 conn.commit()

#         cursor.close()
#         conn.close()
#         time.sleep(1)  # Check sites every 60 seconds

# def send_discord_alert(site_url, status):
#     message = {
#         "content": f"{'🚨' if status == 'down' else '✅'} The site {site_url} is {status}!"
#     }
#     try:
#         requests.post(webhook_url, json=message)
#     except requests.RequestException as e:
#         print(f"Failed to send Discord alert: {e}")


# # Start monitoring in a background thread
# monitoring_thread = threading.Thread(target=monitor_sites, daemon=True)
# monitoring_thread.start()

# # Add new site to monitor
# @app.route('/sites', methods=['POST'])
# def add_site():
#     data = request.json
#     url = data['url']

#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("INSERT INTO monitored_sites (url) VALUES (%s)", (url,))
#     conn.commit()
#     site_id = cursor.lastrowid
#     cursor.close()
#     conn.close()

#     return jsonify({"message": "Site added", "id": site_id}), 201

# # Remove site from monitoring
# @app.route('/sites/<int:site_id>', methods=['DELETE'])
# def remove_site(site_id):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("DELETE FROM status_history WHERE site_id = %s", (site_id,))
#     cursor.execute("DELETE FROM monitored_sites WHERE id = %s", (site_id,))
#     conn.commit()
#     cursor.close()
#     conn.close()

#     return jsonify({"message": "Site removed"})

# # List all monitored sites
# @app.route('/sites', methods=['GET'])
# def list_sites():
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM monitored_sites")
#     sites = cursor.fetchall()
#     cursor.close()
#     conn.close()

#     return jsonify(sites)

# # Get status history for a site
# @app.route('/sites/<int:site_id>/history', methods=['GET'])
# def get_status_history(site_id):
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("SELECT * FROM status_history WHERE site_id = %s ORDER BY timestamp DESC", (site_id,))
#     history = cursor.fetchall()
#     cursor.close()
#     conn.close()

#     if history:
#         return jsonify(history)
#     else:
#         return jsonify({"error": "No history found for this site"}), 404

#     redis_client.get(site_id)

# # Configure Discord webhook
# @app.route('/webhook', methods=['POST'])
# def configure_webhook():
#     global webhook_url
#     data = request.json
#     webhook_url = data['url']
#     return jsonify({"message": "Webhook configured"})

# if __name__ == '__main__':
#     app.run(debug=True)

from flask import Flask, request, jsonify
import mysql.connector
import requests
import threading
import time
from celery import Celery
import redis

app = Flask(__name__)

# Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)
try:
    # Ping the Redis server to check if it's reachable
    response = redis_client.ping()
    print("Connected to Redis!" if response else "Failed to connect to Redis.")
except redis.ConnectionError as e:
    print(f"Could not connect to Redis: {e}")

# Database connection
db_config = {
    "host": "localhost",
    "user": "root",   # Replace with your MySQL username
    "password": "Str0ng!Passw0rd",  # Replace with your MySQL password
    "database": "website_monitor"
}

webhook_url = None

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Function to monitor sites
def monitor_sites():
    while True:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM monitored_sites")
        sites = cursor.fetchall()

        for site in sites:
            site_id = site["id"]
            url = site["url"]
            try:
                response = requests.get(url, timeout=5)
                current_status = "up" if response.status_code == 200 else "down"
            except requests.RequestException:
                current_status = "down"

            # Retrieve previous status from Redis
            previous_status = redis_client.get(site_id)
            if previous_status is None:
                previous_status = "unknown"

            previous_status = previous_status.decode('utf-8')        
            print(f"{url} : {current_status}, {previous_status}")
            # Send Discord alert only if the status has changed
            if current_status != previous_status and webhook_url:
                send_discord_alert(url, current_status)
                redis_client.set(site_id, current_status)
                cursor.execute(
                    "UPDATE monitored_sites SET status = %s WHERE id = %s",
                    (current_status, site_id)
                )
                conn.commit()

        cursor.close()
        conn.close()
        time.sleep(1)  # Check sites every 60 seconds

def send_discord_alert(site_url, status):
    message = {
        "content": f"{'🚨' if status == 'down' else '✅'} The site {site_url} is {status}!"
    }
    try:
        requests.post(webhook_url, json=message)
    except requests.RequestException as e:
        print(f"Failed to send Discord alert: {e}")


# Start monitoring in a background thread
monitoring_thread = threading.Thread(target=monitor_sites, daemon=True)
monitoring_thread.start()

# Add new site to monitor
@app.route('/sites', methods=['POST'])
def add_site():
    data = request.json
    url = data['url']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO monitored_sites (url) VALUES (%s)", (url,))
    conn.commit()
    site_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({"message": "Site added", "id": site_id}), 201

# Remove site from monitoring
@app.route('/sites/<int:site_id>', methods=['DELETE'])
def remove_site(site_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # cursor.execute("DELETE FROM monitored_sites WHERE id = %s", (site_id,))
    cursor.execute("DELETE FROM status_history WHERE site_id = %s", (site_id,))
    cursor.execute("DELETE FROM monitored_sites WHERE id = %s", (site_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Site removed"})

# List all monitored sites
@app.route('/sites', methods=['GET'])
def list_sites():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM monitored_sites")
    sites = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(sites)

# Get status history for a site
@app.route('/sites/<int:site_id>/history', methods=['GET'])
def get_status_history(site_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM status_history WHERE site_id = %s ORDER BY timestamp DESC", (site_id,))
    history = cursor.fetchall()
    cursor.close()
    conn.close()

    if history:
        return jsonify(history)
    else:
        return jsonify({"error": "No history found for this site"}), 404

    redis_client.get(site_id)

# Configure Discord webhook
@app.route('/webhook', methods=['POST'])
def configure_webhook():
    global webhook_url
    data = request.json
    webhook_url = data['url']
    return jsonify({"message": "Webhook configured"})

if __name__ == '__main__':
    app.run(debug=True)