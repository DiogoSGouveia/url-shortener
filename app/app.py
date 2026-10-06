import os
import string

from flask import Flask, request, redirect, jsonify
import redis
import psycopg2

app = Flask(__name__)

# Define the 62 characters used for short codes (0-9, a-z, A-Z) (Base62)
ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# Connect to Redis for fast lookups
cache = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)


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
