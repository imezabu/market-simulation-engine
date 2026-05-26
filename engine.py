import random
import string
import numpy as np
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


class SalesEngine:
    def __init__(
        self,
        company: Company,
        starting_daily_demand: float = 1000,
        yearly_growth_rate: float = 0.20,
        units_per_production_employee: int = 50,
        sales_effectiveness: float = 0.001,
        stockout_penalty_strength: float = 0.02,
        saturation_penalty_strength: float = 0.02,
        max_market_demand: float = 100_000,
        price_sensitivity: float = 1.2,
        demand_noise_std: float = 0.08,
        product_noise_std: float = 0.08,
        seed: int | None = None
    ):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self.company = company

        self.base_demand = starting_daily_demand
        self.base_daily_growth = (1 + yearly_growth_rate) ** (1 / 365) - 1

        self.units_per_production_employee = units_per_production_employee
        self.sales_effectiveness = sales_effectiveness
        self.stockout_penalty_strength = stockout_penalty_strength
        self.saturation_penalty_strength = saturation_penalty_strength
        self.max_market_demand = max_market_demand
        self.price_sensitivity = price_sensitivity

        self.demand_noise_std = demand_noise_std
        self.product_noise_std = product_noise_std

        self.long_term_availability = 1.0

        self.daily_rows = []
        self.product_daily_rows = []


    def _bounded_noise(self, mean: float, std: float, low: float, high: float) -> float:
        value = np.random.normal(mean, std)
        return float(np.clip(value, low, high))

    
    def _calculate_capacity(self) -> int:
        ##Production Capacity = Workers * production_rate per worker
        production_workers = self.company.get_production_count()
        return production_workers * self.units_per_production_employee

    
    def _calculate_potential_demand(self) -> float:
        ##Daily Demand = Base Demand with noise to account for fluctuations in market
        noise = self._bounded_noise(1.0, self.demand_noise_std, 0.8, 1.2)
        return self.base_demand * noise

    #--------------------------------------------------------------------------------
    #Growth rate + Sales Boost- low stock penalty - market saturation penalty + noise
    ##todo: implement multiple markets each with their own saturation
    #--------------------------------------------------------------------------------
    def _calculate_growth_rate(self) -> float:
        sales_count = self.company.get_sales_count()

        #Sales Boost = salesman effectiveness coefficient * log(1+workers)
        #Increasing number of sales workers has diminishing returns
        sales_boost = self.sales_effectiveness * np.log(1+sales_count)


        #Availability = percentage of demand that can be fulfilled by production, optimal= 1.0
        # Low stock penalty= low stock penalty * (1-availability)
        stockout_penalty = self.stockout_penalty_strength * (1 - self.long_term_availability)

        #saturation penalty = penalty coefficient * (demand/market max)
        saturation_penalty = (
            self.saturation_penalty_strength
            * (self.base_demand / self.max_market_demand)
        )

        random_growth_noise = np.random.normal(0, 0.0005)

        growth_rate = (
            self.base_daily_growth
            + sales_boost
            - stockout_penalty
            - saturation_penalty
            + random_growth_noise
        )

        return float(np.clip(growth_rate, -0.05, 0.05))


    #----------------------------
    #Product Allocation
    #Takes into consideration price and quality then allocates total sales amongst products using weights
    #----------------------------
    def _allocate_sales_to_products(self, total_sales: int)->list[tuple[Product, int]]:
        products = self.company.get_inventory().get_products()

        if not products:
            raise ValueError("No products in inventory")

        weights = []

        for product in products:
            price_effect = 1 / (product.price ** self.price_sensitivity)
            quality_effect = product.quality
            noise = self._bounded_noise(1.0, self.product_noise_std, 0.8, 1.2)

            weight = price_effect * quality_effect * noise
            weights.append(weight)

        total_weight = sum(weights)

        ##Normalization
        # sales_i= total sales * (weight_i/ sum of weights)
        raw_allocations = [
            total_sales * (weight / total_weight)
            for weight in weights
        ]


        rounded_allocations = [int(x) for x in raw_allocations]

        remainder = total_sales - sum(rounded_allocations)

        #Allocate remainder of sales to top sold products
        fractional_parts = [
            raw_allocations[i] - rounded_allocations[i]
            for i in range(len(products))
        ]

        ranked_indices = sorted(
            range(len(products)),
            key=lambda i: fractional_parts[i],
            reverse=True
        )

        for i in ranked_indices[:remainder]:
            rounded_allocations[i] += 1

        return [
            (products[i], rounded_allocations[i])
            for i in range(len(products))
        ]

    def simulate_day(self, day: int) -> None:
        capacity = self._calculate_capacity()

        #noisy base demand for the day
        potential_demand = self._calculate_potential_demand()

        #sales are bounded by production capacity
        actual_sales = int(min(capacity, potential_demand))

        daily_availability = actual_sales / int(round(potential_demand)) if int(round(potential_demand)) > 0 else 1.0

        #Availability over the long term, aka customer memory
        #low stock on one day is not enough to damage demand significantly
        self.long_term_availability = (
            0.8 * self.long_term_availability
            + 0.2 * daily_availability
        )

        product_allocations = self._allocate_sales_to_products(actual_sales)

        growth_rate = self._calculate_growth_rate()
        self.base_demand *= 1 + growth_rate

        self.daily_rows.append({
            "day": day,
            "base_demand": self.base_demand,
            "potential_demand": potential_demand,
            "capacity": capacity,
            "actual_sales": actual_sales,
            "daily_availability": daily_availability,
            "long_term_availability": self.long_term_availability,
            "growth_rate": growth_rate,
            "sales_team_count": self.company.get_sales_count(),
            "production_team_count": self.company.get_production_count()
        })

        for product, units_sold in product_allocations:
            product.log_sales(units_sold)

            revenue = units_sold * product.price
            total_cost = units_sold * product.unit_cost
            profit = revenue - total_cost

            self.product_daily_rows.append({
                "day": day,
                "product_id": product.product_id,
                "product_name": product.name,
                "units_sold": units_sold,
                "unit_price": product.price,
                "unit_cost": product.unit_cost,
                "revenue": revenue,
                "total_cost": total_cost,
                "profit": profit
            })

    def simulate(self, days: int) -> None:
        for day in range(1, days + 1):
            self.simulate_day(day)
    
    def print_daily_summary(self, days: int = 10):
        print("\n=== DAILY SUMMARY ===\n")

        for row in self.daily_rows[:days]:
            print(
                f"Day {row['day']:3} | "
                f"Base Demand: {row['base_demand']:8.0f} | "
                f"Demand: {row['potential_demand']:8.0f} | "
                f"Sales: {row['actual_sales']:6} | "
                f"Capacity: {row['capacity']:6} | "
                f"Growth: {row['growth_rate']*100:7.3f}% | "
                f"Availability: {row['daily_availability']*100:6.2f}%"
            )
    def print_product_summary(self, day: int):
        print(f"\n=== PRODUCT SUMMARY DAY {day} ===\n")

        rows = [
                row for row in self.product_daily_rows
                if row["day"] == day
        ]

        for row in rows:
            print(
                    f"{row['product_name']:<15} | "
                    f"Units: {row['units_sold']:5} | "
                    f"Revenue: ${row['revenue']:10.2f} | "
                    f"Profit: ${row['profit']:10.2f}"
            )


# -------------------------
# Testing
# -------------------------

company = Company()

company.hire_production(count=100, salary=50_000)
company.hire_sales(count=3000, salary=70_000)

inventory = company.get_inventory()

inventory.add_product("Coca-Cola", price=10, material_cost=1.00, labor_cost=0.50, other_cost=0.25, quality=1.3)
inventory.add_product("Apple", price=1.5, material_cost=0.60, labor_cost=0.25, other_cost=0.15, quality=1.1)
inventory.add_product("Generator", price=1000, material_cost=100, labor_cost=1, other_cost=2, quality=1.8)

engine = SalesEngine(
    company=company,
    starting_daily_demand=1000,
    yearly_growth_rate=0.20,
    units_per_production_employee=50,
    seed=42
)

engine.simulate(365)

engine.print_daily_summary(365)
engine.print_product_summary(365)
