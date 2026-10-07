import os
import string
import time
from functools import wraps
from flask import Flask, request, redirect, jsonify
import redis
import psycopg2

app = Flask(__name__)

# Define the 62 characters used for short codes (0-9, a-z, A-Z) (Base62)
ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# Configuration: Max 15 requests, refilling 1 token every 2 seconds
BUCKET_LIMIT = 15
REFILL_RATE = 0.5  # tokens per second

# Connect to Redis for fast lookups
cache = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)

def token_bucket(f):
    """Decorator to implement token bucket rate limiting."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Identify the user using their IP address
        user_ip = request.remote_addr
        redis_key = f"bucket:{user_ip}"
        
        # Fetch current bucket state from Redis
        state = cache.hgetall(redis_key)
        current_time = time.time()
        
        if not state:
            # If the user has no bucket yet, initialize it to full capacity
            tokens = BUCKET_LIMIT
            last_updated = current_time
        else:
            tokens = float(state["tokens"])
            last_updated = float(state["last_updated"])
            
            # Refill the bucket based on how much time has passed
            elapsed_time = current_time - last_updated
            tokens = min(BUCKET_LIMIT, tokens + (elapsed_time * REFILL_RATE))
        
        # Check if there are enough tokens to allow the request
        if tokens >= 1:
            tokens -= 1  # Spend 1 token
            
            # Save updated state back to Redis
            cache.hset(redis_key, mapping={
                "tokens": tokens,
                "last_updated": current_time
            })
            
            return f(*args, **kwargs)
        else:
            # Bucket is empty! Reject request
            return jsonify({"error": "Too many requests. Please try again later."}), 429
            
    return decorated_function

def get_db():
    """Connect to PostgreSQL for permanent storage."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        database=os.environ.get("POSTGRES_DB", "urlshortener"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )

def base62_encode(num):
    """Convert a number (database ID) to a Base62 string."""
    if num == 0:
        return ALPHABET[0]
    base62 = []
    while num > 0:
        num, rem = divmod(num, 62)
        base62.append(ALPHABET[rem])
    return ''.join(reversed(base62))

def base62_decode(s):
    """Convert a Base62 string back to a number (database ID)."""
    num = 0
    for char in s:
        num = num * 62 + ALPHABET.index(char)
    return num

@app.route("/shorten", methods=["POST"])
@token_bucket
def shorten_url():
    """Endpoint to shorten a long URL."""
    # Grab the long URL from the request body
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing url field"}), 400

    long_url = data["url"]

    # Save to PostgreSQL - the database assigns an auto-incrementing ID
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO urls (long_url) VALUES (%s) RETURNING id", (long_url,))
    url_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    # Encode the database ID into a short code
    short_code = base62_encode(url_id)

    # Cache the mapping for fast redirects later
    cache.set(short_code, long_url)

    return jsonify({"short_url": f"http://localhost:5000/{short_code}", "short_code": short_code}), 201


@app.route("/<short_code>")
def redirect_url(short_code):
    """Endpoint to redirect from a short code to the original long URL."""
    # Check the fast cache first
    long_url = cache.get(short_code)

    if long_url:
        print("CACHE HIT", flush=True)
        return redirect(long_url, code=302)

    # Cache miss - fall back to the database
    print("CACHE MISS - querying database", flush=True)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT long_url FROM urls WHERE id = %s", (base62_decode(short_code),))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if not result:
        return jsonify({"error": "Short URL not found"}), 404

    # Found it in the database - cache it for next time
    long_url = result[0]
    cache.set(short_code, long_url)

    return redirect(long_url, code=302)

@app.route("/health")
def health_check():
    """Health check endpoint to verify the service is running."""
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)