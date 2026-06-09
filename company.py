import random
import string
from dataclasses import dataclass, field


@dataclass
class Product:
    name: str
    product_id: str
    price: float
    material_cost: float
    labor_cost: float
    other_cost: float
    quality: float = 1.0
    daily_sales: int = 0
    total_sales: int = 0

    @property
    def unit_cost(self) -> float:
        return self.material_cost + self.labor_cost + self.other_cost

    def log_sales(self, count: int) -> None:
        self.daily_sales = count
        self.total_sales += count


class Inventory:
    def __init__(self):
        self.items: list[Product] = []

    def _create_unique_id(self) -> str:
        existing_ids = {product.product_id for product in self.items}

        while True:
            new_id = ''.join(random.choices(string.digits, k=9))
            if new_id not in existing_ids:
                return new_id

    def add_product(
        self,
        name: str,
        price: float,
        material_cost: float,
        labor_cost: float,
        other_cost: float,
        quality: float = 1.0
    ) -> Product:
        if price < 0:
            raise ValueError("Price cannot be negative")

        product = Product(
            name=name,
            product_id=self._create_unique_id(),
            price=price,
            material_cost=material_cost,
            labor_cost=labor_cost,
            other_cost=other_cost,
            quality=quality
        )

        self.items.append(product)
        return product

    def get_products(self) -> list[Product]:
        return self.items

    def get_product_count(self) -> int:
        return len(self.items)


@dataclass
class Employee:
    salary: float
    employee_id: str


class SalesEmployee(Employee):
    pass


class ProductionEmployee(Employee):
    pass


class Company:
    def __init__(self, operating_cost=0):
        self.inventory = Inventory()
        self.employees: list[Employee] = []
        self.operating_cost=operating_cost

    def _create_unique_id(self) -> str:
        existing_ids = {employee.employee_id for employee in self.employees}

        while True:
            new_id = ''.join(random.choices(string.digits, k=9))
            if new_id not in existing_ids:
                return new_id

    def hire_sales(self, count: int, salary: float) -> None:
        for _ in range(count):
            employee = SalesEmployee(
                salary=salary,
                employee_id=self._create_unique_id()
            )
            self.employees.append(employee)

    def hire_production(self, count: int, salary: float) -> None:
        for _ in range(count):
            employee = ProductionEmployee(
                salary=salary,
                employee_id=self._create_unique_id()
            )
            self.employees.append(employee)

    def get_sales_count(self) -> int:
        return sum(isinstance(emp, SalesEmployee) for emp in self.employees)

    def get_production_count(self) -> int:
        return sum(isinstance(emp, ProductionEmployee) for emp in self.employees)

    def get_inventory(self) -> Inventory:
        return self.inventory
    @property
    def payroll_costs(self) -> float:
        sum=0
        for emp in self.employees:
            sum+=emp.salary
        return sum
    @property
    def total_yearly_expenses(self)->float:
        return self.payroll_costs+self.operating_cost
