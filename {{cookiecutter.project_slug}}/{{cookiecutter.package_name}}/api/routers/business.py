"""Custom API routes for {{cookiecutter.project_name}}.

Add your business-specific API endpoints here.

Example:
    from fastapi import APIRouter, Depends
    from {{cookiecutter.package_name}}.business.services import OrderService
    from {{cookiecutter.package_name}}.business.entities import Order
    
    router = APIRouter(prefix="/orders", tags=["orders"])
    
    @router.post("/", response_model=Order)
    async def create_order(
        customer_id: str,
        product_ids: list[str],
        order_service: OrderService = Depends(get_order_service)
    ):
        return order_service.create_order(customer_id, product_ids)
        
    @router.get("/{order_id}", response_model=Order)  
    async def get_order(
        order_id: str,
        order_service: OrderService = Depends(get_order_service)
    ):
        return order_service.get_order(order_id)
"""

from fastapi import APIRouter

# Example business router - replace with your own
router = APIRouter(prefix="/{{cookiecutter.project_slug}}", tags=["{{cookiecutter.project_slug}}"])

@router.get("/example")
async def example_endpoint():
    """Example endpoint - replace with your business logic."""
    return {"message": "Hello from {{cookiecutter.project_name}}!"}

# Add your custom routes here