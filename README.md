# URL Shortener

A simple URL shortener built with Flask, PostgreSQL, and Redis.

## Rate limit

`POST /shorten` uses a token bucket per client IP, stored in Redis. Each bucket holds up to 15 requests and refills at one request every two seconds. Requests are rejected with `429 Too Many Requests` when the bucket is empty.

## Run

Start the app and its dependencies with Docker Compose:

```sh
docker compose up --build
```

The service is available at `http://localhost:5000`. Stop it with `docker compose down`.

## API

Create a short URL:

```sh
curl -X POST http://localhost:5000/shorten \
	-H "Content-Type: application/json" \
	-d '{"url":"https://example.com"}'
```

The response includes a `short_url` and `short_code`. Opening the short URL redirects to the original URL.

Check service health at `GET /health`.