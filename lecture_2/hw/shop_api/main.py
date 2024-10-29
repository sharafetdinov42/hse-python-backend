from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, FastAPI, HTTPException, Query, Request, Response, status
from prometheus_client import Counter, Histogram, generate_latest, start_http_server
from pydantic import BaseModel

# Metrics
REQUEST_COUNT = Counter("request_count", "Total number of requests", ["method", "endpoint"])
SUCCESSFUL_REQUEST_COUNT = Counter("successful_requests", "Total number of successful requests", ["method", "endpoint"])
ITEMS_CREATED_COUNT = Counter("items_created", "Total number of items created")
ITEMS_DELETED_COUNT = Counter("items_deleted", "Total number of items deleted")
CART_OPERATIONS_COUNT = Counter("cart_operations", "Total number of cart operations", ["operation"])
REQUEST_LATENCY = Histogram("request_latency_seconds", "Request latency in seconds")


class ItemCreate(BaseModel):
    """Model for creating an item with a name and price."""

    name: str
    price: float

    model_config = {"extra": "forbid"}


class ItemUpdate(BaseModel):
    """Model for updating an item with optional name and price."""

    name: Optional[str] = None
    price: Optional[float] = None

    model_config = {"extra": "forbid"}


class Item(BaseModel):
    """Model representing an item with an ID, name, price, and deletion status."""

    id: int
    name: str
    price: float
    deleted: bool = False


class CartItem(BaseModel):
    """Model representing an item in the cart with its quantity and availability."""

    id: int
    name: str
    quantity: int
    available: bool


class Cart(BaseModel):
    """Model representing a shopping cart with an ID, list of items, total price, and quantity."""

    id: int
    items: List[CartItem] = []
    price: float = 0.0
    quantity: int = 0


# Initialize FastAPI application
app = FastAPI(title="Shop API")

# Counter variables
item_counter: int = 0
cart_counter: int = 0

# In-memory databases
item_database: Dict[int, Item] = {}
cart_database: Dict[int, Cart] = {}

# Routers
item_router = APIRouter()
cart_router = APIRouter()


# Item router
@item_router.post("/item", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate, response: Response):
    """
    Create a new item in the database.

    Args:
        item (ItemCreate): The item data to create.
        response (Response): The response object to modify headers.

    Returns:
        Item: The created item.
    """
    global item_counter
    item_counter += 1
    new_item_id = item_counter
    new_item = Item(id=new_item_id, name=item.name, price=item.price, deleted=False)
    item_database[new_item_id] = new_item
    ITEMS_CREATED_COUNT.inc()
    response.headers["location"] = f"/item/{new_item_id}"
    return new_item.model_dump()


@item_router.get("/item/{item_id}")
def get_item(item_id: int):
    """
    Retrieve an item by its ID.

    Args:
        item_id (int): The ID of the item to retrieve.

    Returns:
        Item: The requested item.

    Raises:
        HTTPException: If the item is not found or has been deleted.
    """
    if item_id not in item_database or item_database[item_id].deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found or has been deleted")
    return item_database[item_id].model_dump()


@item_router.get("/item")
def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0.0),
    max_price: Optional[float] = Query(None, ge=0.0),
    show_deleted: bool = Query(False),
):
    """
    List items with optional filtering.

    Args:
        offset (int): The number of items to skip.
        limit (int): The maximum number of items to return.
        min_price (Optional[float]): Minimum price for filtering items.
        max_price (Optional[float]): Maximum price for filtering items.
        show_deleted (bool): Whether to include deleted items.

    Returns:
        List[Item]: A list of items matching the criteria.
    """
    items = list(item_database.values())
    filtered_items = [
        item
        for item in items
        if (not show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return [item.model_dump() for item in filtered_items[offset : offset + limit]]


@item_router.put("/item/{item_id}")
def replace_item(item_id: int, new_item: ItemCreate):
    """
    Replace an existing item with new data.

    Args:
        item_id (int): The ID of the item to replace.
        new_item (ItemCreate): The new item data.

    Returns:
        Item: The updated item.

    Raises:
        HTTPException: If the item is not found or is marked as deleted.
    """
    if item_id not in item_database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    existing_item = item_database[item_id]
    if existing_item.deleted:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)
    existing_item.name = new_item.name
    existing_item.price = new_item.price
    return existing_item.model_dump()


@item_router.patch("/item/{item_id}")
def update_item(item_id: int, item_updates: ItemUpdate = Body(default={})):
    """
    Update specific fields of an existing item.

    Args:
        item_id (int): The ID of the item to update.
        item_updates (ItemUpdate): The updates to apply.

    Returns:
        Item: The updated item.

    Raises:
        HTTPException: If the item is not found or is marked as deleted.
    """
    if item_id not in item_database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    existing_item = item_database[item_id]
    if existing_item.deleted:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)
    update_data = item_updates.model_dump(exclude_unset=True)
    if "deleted" in update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Field 'deleted' cannot be modified"
        )
    for key, value in update_data.items():
        setattr(existing_item, key, value)
    return existing_item.model_dump()


@item_router.delete("/item/{item_id}")
def delete_item(item_id: int):
    """
    Mark an item as deleted.

    Args:
        item_id (int): The ID of the item to delete.

    Returns:
        dict: A message indicating the result of the deletion.
    """
    if item_id not in item_database:
        return {"message": "The item is already marked as deleted"}
    existing_item = item_database[item_id]
    if existing_item.deleted:
        return {"message": "The item has already been deleted"}
    existing_item.deleted = True
    ITEMS_DELETED_COUNT.inc()
    return {"message": "Item has been successfully deleted"}


# Cart router
@cart_router.post("/cart", status_code=status.HTTP_201_CREATED)
def create_cart(response: Response):
    """
    Create a new shopping cart.

    Args:
        response (Response): The response object to modify headers.

    Returns:
        dict: The ID of the created cart.
    """
    global cart_counter
    cart_counter += 1
    new_cart_id = cart_counter
    new_cart = Cart(id=new_cart_id)
    cart_database[new_cart_id] = new_cart
    response.headers["location"] = f"/cart/{new_cart_id}"
    return {"id": new_cart_id}


@cart_router.get("/cart/{cart_id}")
def get_cart(cart_id: int):
    """
    Retrieve a shopping cart by its ID.

    Args:
        cart_id (int): The ID of the cart to retrieve.

    Returns:
        Cart: The requested cart.

    Raises:
        HTTPException: If the cart is not found.
    """
    if cart_id not in cart_database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    cart = cart_database[cart_id]
    total_price = sum(
        (
            item_database.get(cart_item.id).price * cart_item.quantity
            for cart_item in cart.items
            if item_database.get(cart_item.id) and not item_database[cart_item.id].deleted
        ),
        0,
    )
    total_quantity = sum(
        (
            cart_item.quantity
            for cart_item in cart.items
            if item_database.get(cart_item.id) and not item_database[cart_item.id].deleted
        ),
        0,
    )
    cart.price = total_price
    cart.quantity = total_quantity
    return cart.model_dump()


@cart_router.get("/cart")
def list_carts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    min_price: Optional[float] = Query(None, ge=0.0),
    max_price: Optional[float] = Query(None, ge=0.0),
    min_quantity: Optional[int] = Query(None, ge=0),
    max_quantity: Optional[int] = Query(None, ge=0),
):
    """
    List carts with optional filtering.

    Args:
        offset (int): The number of carts to skip.
        limit (int): The maximum number of carts to return.
        min_price (Optional[float]): Minimum price for filtering carts.
        max_price (Optional[float]): Maximum price for filtering carts.
        min_quantity (Optional[int]): Minimum quantity for filtering carts.
        max_quantity (Optional[int]): Maximum quantity for filtering carts.

    Returns:
        List[Cart]: A list of carts matching the criteria.
    """
    carts = list(cart_database.values())
    filtered_carts = []
    for cart in carts:
        total_price = sum(
            (
                item_database.get(cart_item.id).price * cart_item.quantity
                for cart_item in cart.items
                if item_database.get(cart_item.id) and not item_database[cart_item.id].deleted
            ),
            0,
        )
        total_quantity = sum(
            (
                cart_item.quantity
                for cart_item in cart.items
                if item_database.get(cart_item.id) and not item_database[cart_item.id].deleted
            ),
            0,
        )
        cart.price = total_price
        cart.quantity = total_quantity
        if (
            (min_price is None or total_price >= min_price)
            and (max_price is None or total_price <= max_price)
            and (min_quantity is None or total_quantity >= min_quantity)
            and (max_quantity is None or total_quantity <= max_quantity)
        ):
            filtered_carts.append(cart)
    return [cart.model_dump() for cart in filtered_carts[offset : offset + limit]]


@cart_router.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(cart_id: int, item_id: int):
    """
    Add an item to a shopping cart.

    Args:
        cart_id (int): The ID of the cart.
        item_id (int): The ID of the item to add.

    Returns:
        dict: A message indicating the result of the operation.

    Raises:
        HTTPException: If the cart or item is not found.
    """
    if cart_id not in cart_database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    if item_id not in item_database:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    cart = cart_database[cart_id]
    item = item_database[item_id]
    CART_OPERATIONS_COUNT.labels(operation="add").inc()
    for cart_item in cart.items:
        if cart_item.id == item_id:
            cart_item.quantity += 1
            return {"message": "Item successfully added to the cart"}

    cart_item = CartItem(id=item_id, name=item.name, quantity=1, available=not item.deleted)
    cart.items.append(cart_item)
    return {"message": "Item successfully added to the cart"}


# Add routers to the app
app.include_router(item_router)
app.include_router(cart_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_http_server(8001)
    yield


@app.middleware("http")
async def add_prometheus_metrics(request: Request, call_next):
    endpoint = request.url.path
    method = request.method

    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()

    try:
        response = await call_next(request)
        if response.status_code < 400:
            SUCCESSFUL_REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
        return response
    except HTTPException as http_exc:
        raise http_exc


@app.get("/metrics")
async def get_metrics():
    return Response(generate_latest(), media_type="text/plain")
