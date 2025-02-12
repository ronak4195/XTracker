# from flask import Flask, request, jsonify
# import mysql.connector
# import requests
# import threading
# import time
# from celery import Celery
# import redis
# from datetime import datetime, timezone

# app = Flask(__name__)

# # Redis connection
# redis_client = redis.Redis(host='localhost', port=6379, db=0)
# try:
#     # Ping the Redis server to check if it's reachable
#     response = redis_client.ping()
#     print("Connected to Redis!" if response else "Failed to connect to Redis.")
# except redis.ConnectionError as e:
#     print(f"Could not connect to Redis: {e}")

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
#             stat_code = site["expected_status_code"]
#             check_int = site["check_interval_seconds"]
#             try:
#                 start_time = time.time()
#                 response = requests.get(url, timeout=5)
#                 response_time_ms = int((time.time() - start_time) * 1000)  # Calculate response time in milliseconds
#                 current_status = "up" if response.status_code == stat_code else "down"
#             except requests.RequestException:
#                 current_status = "down"

#             # Retrieve previous status from Redis
#             previous_status = redis_client.get(f"site_{site_id}")
#             if previous_status is None:
#                 previous_status = "unknown"
#             else:
#                 previous_status = previous_status.decode('utf-8')
#             print(f"{url} : {current_status}, {previous_status}")
#             # Send Discord alert only if the status has changed
#             if current_status != previous_status and webhook_url:
#                 send_discord_alert(url, current_status)
#                 redis_client.set(f"site_{site_id}", current_status)
#                 # Get current timestamp
#                 last_checked = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

#                 # Get last status change timestamp
#                 last_status_change = redis_client.get(f"site_{site_id}_last_change")
#                 if last_status_change is None:
#                     last_status_change = last_checked
#                 else:
#                     last_status_change = last_status_change.decode('utf-8')

#                 cursor.execute(
#                     "UPDATE monitored_sites SET status = %s WHERE id = %s",
#                     (current_status, site_id)
#                 )
#                 conn.commit()
#                 print({
#                     "url": url,
#                     "status": current_status,
#                     "response_time_ms": response_time_ms,
#                     "last_checked": last_checked,
#                     "last_status_change": last_status_change
#                 })

#         cursor.close()
#         conn.close()
#         time.sleep(check_int)  # Check sites every `check_int` seconds

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
import asyncio
import aiohttp
import redis
from datetime import datetime, timezone

app = Flask(__name__)

# Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Database connection

db_config = {
    "host": "localhost",
    "user": "root",  # Replace with your MySQL username
    "password": "Str0ng!Passw0rd",  # Replace with your MySQL password
    "database": "website_monitor"
}

webhook_url = None

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Asynchronous function to monitor a single site
async def monitor_site(session, site):
    site_id = site["id"]
    url = site["url"]
    stat_code = site["expected_status_code"]
    check_int = site["check_interval_seconds"]
    try:
        start_time = datetime.utcnow()
        async with session.get(url, timeout=5) as response:
            response_time_ms = (datetime.utcnow() - start_time).microseconds // 1000
            current_status = "up" if response.status == stat_code else "down"
    except Exception:
        current_status = "down"

    # Retrieve previous status from Redis
    previous_status = redis_client.get(f"site_{site_id}")
    previous_status = previous_status.decode('utf-8') if previous_status else "unknown"

    # Send Discord alert only if status changes
    if current_status != previous_status and webhook_url:
        await send_discord_alert(url, current_status)
        redis_client.set(f"site_{site_id}", current_status)
        last_checked = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        last_status_change = redis_client.get(f"site_{site_id}_last_change")
        last_status_change = last_status_change.decode('utf-8') if last_status_change else last_checked

        # Update database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE monitored_sites SET status = %s WHERE id = %s", (current_status, site_id))
        conn.commit()
        cursor.close()
        conn.close()

        print({
            "url": url,
            "status": current_status,
            "response_time_ms": response_time_ms,
            "last_checked": last_checked,
            "last_status_change": last_status_change
        })

    await asyncio.sleep(check_int)  # Wait before checking again

# Asynchronous function to monitor all sites
async def monitor_sites():
    while True:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM monitored_sites")
        sites = cursor.fetchall()
        cursor.close()
        conn.close()

        async with aiohttp.ClientSession() as session:
            tasks = [monitor_site(session, site) for site in sites]
            await asyncio.gather(*tasks)

# Function to send Discord alerts asynchronously
async def send_discord_alert(site_url, status):
    message = {"content": f"{'🚨' if status == 'down' else '✅'} The site {site_url} is {status}!"}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json=message)
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

# Start monitoring in background
loop = asyncio.get_event_loop()
loop.create_task(monitor_sites())

# Flask routes remain unchanged
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
@app.route('/sites', methods=['POST'])
def add_site():
    data = request.json
    url = data.get('url')
    check_interval_seconds = data.get('check_interval_seconds', 300)
    name = data.get('name')  # Defaults to NULL if not provided
    expected_status_code = data.get('expected_status_code', 200)
    status = data.get('status', 'unknown')
    response_time_ms = data.get('response_time_ms')  # Defaults to NULL if not provided

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO monitored_sites 
        (url, check_interval_seconds, name, expected_status_code, status, response_time_ms) 
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (url, check_interval_seconds, name, expected_status_code, status, response_time_ms))

    conn.commit()
    site_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({"message": "Site added", "id": site_id}), 201

@app.route('/sites/<int:site_id>', methods=['DELETE'])
def remove_site(site_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM monitored_sites WHERE id = %s", (site_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Site removed"})

@app.route('/sites', methods=['GET'])
def list_sites():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM monitored_sites")
    sites = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(sites)

@app.route('/webhook', methods=['POST'])
def configure_webhook():
    global webhook_url
    data = request.json
    webhook_url = data['url']
    return jsonify({"message": "Webhook configured"})

if __name__ == '__main__':
    app.run(debug=True)