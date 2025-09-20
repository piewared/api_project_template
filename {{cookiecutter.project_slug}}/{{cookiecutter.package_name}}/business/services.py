"""Business services for {{cookiecutter.project_name}}.

Implement your business logic here. Services orchestrate domain entities
and coordinate with infrastructure through dependency injection.

Example:
    from typing import List
    from .entities import Product, Order
    
    class OrderService:
        def __init__(self, product_repo, order_repo):
            self.product_repo = product_repo
            self.order_repo = order_repo
            
        def create_order(self, customer_id: str, product_ids: List[str]) -> Order:
            products = [self.product_repo.get(pid) for pid in product_ids]
            total = sum(p.price for p in products)
            order = Order(
                id=generate_id(),
                customer_id=customer_id, 
                products=products,
                total=total
            )
            return self.order_repo.save(order)
"""

# Add your business services here
pass