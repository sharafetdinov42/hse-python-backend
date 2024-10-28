import json
from http import HTTPStatus
from math import factorial
from typing import Any, Awaitable, Callable

from sympy import fibonacci


async def lifespan_handler(receive, send):
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            break


async def send_json(send: Callable[[dict[str, Any]], Awaitable[None]], status: int, content: dict):
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": json.dumps(content).encode("utf-8")})


async def calculate_factorial(n: int, send: Callable[[dict[str, Any]], Awaitable[None]]):
    if n < 0:
        await send_json(send, HTTPStatus.BAD_REQUEST, {"error": "Value must be non-negative."})
    else:
        await send_json(send, HTTPStatus.OK, {"result": factorial(n)})


async def calculate_fibonacci(n: int, send: Callable[[dict[str, Any]], Awaitable[None]]):
    if n < 0:
        await send_json(send, HTTPStatus.BAD_REQUEST, {"error": "Value must be non-negative."})
    else:
        result = fibonacci(n)
        await send_json(send, HTTPStatus.OK, {"result": int(result)})


async def calculate_average(values: list, send: Callable[[dict[str, Any]], Awaitable[None]]):
    if not values:
        await send_json(send, HTTPStatus.BAD_REQUEST, {"error": "List cannot be empty."})
    else:
        await send_json(send, HTTPStatus.OK, {"result": sum(values) / len(values)})


async def app(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
):
    if scope["type"] == "lifespan":
        await lifespan_handler(receive, send)
        return

    assert scope["type"] == "http"
    method = scope["method"]
    path = scope["path"]

    if method == "GET":
        if path == "/factorial":
            query_string = scope.get("query_string", b"").decode("utf-8")
            n_str = dict(param.split("=") for param in query_string.split("&") if "=" in param).get("n")
            if n_str is None or not n_str.lstrip("-").isdigit():
                await send_json(
                    send,
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"error": "Parameter 'n' is required and must be a valid integer."},
                )
                return
            await calculate_factorial(int(n_str), send)
        elif path.startswith("/fibonacci/"):
            try:
                n = int(path.split("/")[2])
            except (IndexError, ValueError):
                await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Invalid path parameter."})
                return
            await calculate_fibonacci(n, send)
        elif path == "/mean":
            request_data = await receive()
            try:
                body = json.loads(request_data.get("body", b"").decode("utf-8"))
                if not isinstance(body, list) or not all(isinstance(i, (int, float)) for i in body):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                await send_json(send, HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "Invalid request body."})
                return
            await calculate_average(body, send)
        else:
            await send(
                {
                    "type": "http.response.start",
                    "status": HTTPStatus.NOT_FOUND,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"404 Not Found"})

    elif method == "POST":
        await send(
            {
                "type": "http.response.start",
                "status": HTTPStatus.NOT_FOUND,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"404 Not Found"})

    else:
        await send(
            {
                "type": "http.response.start",
                "status": HTTPStatus.METHOD_NOT_ALLOWED,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"405 Method Not Allowed"})
