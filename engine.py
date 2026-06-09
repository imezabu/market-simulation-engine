import random
import string
import numpy as np
from company import Company, Product
class FinancialModel:
    def get_opex(self, company: Company, day):
        return company.daily_opex
    def compute_pnl(self, revenue, cogs, opex)->tuple[float, float]:
        gross_profit = revenue - cogs
        net_profit = gross_profit - opex

        return gross_profit, net_profit
    def compute_product_metrics(self, units_sold, price, unit_cost)->tuple[float, float, float]:
        revenue = units_sold * price
        cogs = units_sold * unit_cost
        profit = revenue - cogs
        return revenue, cogs, profit

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
        self.financial_model=FinancialModel()
        # -------------------------
        # SIM STATE
        # -------------------------
        self.day=1
        self.long_term_availability = 1.0

        #extract daily growth from base yearly growth rate
        self.base_demand = starting_daily_demand
        self.base_daily_growth = (1 + yearly_growth_rate) ** (1 / 365) - 1

        self.units_per_production_employee = units_per_production_employee
        self.sales_effectiveness = sales_effectiveness
        self.stockout_penalty_strength = stockout_penalty_strength
        self.saturation_penalty_strength = saturation_penalty_strength
        self.max_market_demand = max_market_demand
        self.price_sensitivity = price_sensitivity

        #noise randomness settings
        self.demand_noise_std = demand_noise_std
        self.product_noise_std = product_noise_std

        
        # -------------------------
        # DATA STORAGE
        # -------------------------
        self.daily_table = []
        self.product_daily_table = []

        # -------------------------
        # CUMALATIVE METRICS
        # ------------------------
        self.cumulative_revenue=0
        self.cumulative_cogs=0
        self.cumulative_opex=0


    def _bounded_noise(self, mean, std, low, high):
        value = np.random.normal(mean, std)
        return float(np.clip(value, low, high))

    def _calculate_capacity(self):
        workers = self.company.get_production_count()
        return workers * self.units_per_production_employee

    def _calculate_potential_demand(self):
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

    def _calculate_operating_expenses(self)->float:
        return self.company.daily_opex
    #----------------------------
    #Product Allocation
    #Takes into consideration price and quality then allocates total sales amongst products using weights
    #----------------------------
    def _allocate_sales_to_products(self, total_sales: int):
        products = self.company.get_inventory().get_products()

        if not products:
            raise ValueError("No products in inventory")

        weights = []

        for product in products:
            price_effect = 1 / (product.price ** self.price_sensitivity)
            quality_effect = product.quality
            noise = self._bounded_noise(1.0, self.product_noise_std, 0.8, 1.2)

            weights.append(price_effect * quality_effect * noise)

        total_weight = sum(weights)

        raw = [total_sales * (w / total_weight) for w in weights]
        rounded = [int(x) for x in raw]

        remainder = total_sales - sum(rounded)

        fractional = [raw[i] - rounded[i] for i in range(len(products))]
        ranked = sorted(range(len(products)), key=lambda i: fractional[i], reverse=True)

        for i in ranked[:remainder]:
            rounded[i] += 1

        return list(zip(products, rounded))

    def simulate_day(self) -> tuple[dict, list[dict]]:
        capacity = self._calculate_capacity()
        demand = self._calculate_potential_demand()

        #sales are bounded by production capacity
        actual_sales = int(min(capacity, demand))

        daily_availability = actual_sales / int(round(demand)) if int(round(demand)) > 0 else 1.0

        #Availability over the long term, aka customer memory
        #low stock on one day is not enough to damage demand significantly
        self.long_term_availability = (
            0.8 * self.long_term_availability
            + 0.2 * daily_availability
        )

        allocations = self._allocate_sales_to_products(actual_sales)

        growth_rate = self._calculate_growth_rate()
        


        # -------------------------
        # PRODUCT LAYER
        # -------------------------
        revenue = 0
        cogs = 0
        product_rows = []

        for product, units in allocations:
            product.log_sales(units)

            r, c, p = self.financial_model.compute_product_metrics(
                units, product.price, product.unit_cost
            )

            revenue += r
            cogs += c

            product_rows.append({
                "simulation_day": self.day,
                "product_id": product.product_id,
                "product_name": product.name,
                "units_sold": units,
                "unit_price": product.price,
                "unit_cost": product.unit_cost,
                "product_revenue": r,
                "cost_of_goods_sold": c,
                "product_profit": p
            })
        # -------------------------
        # FINANCIAL LAYER
        # -------------------------
        opex = self.financial_model.get_opex(self.company, self.day)

        gross_profit, net_profit = self.financial_model.compute_pnl(revenue, cogs, opex)

        

        daily_row={
            "simulation_day": self.day,

            "base_demand": self.base_demand,
            "potential_demand": demand,
            "capacity": capacity,
            "actual_sales": actual_sales,

            "rolling_availability": self.long_term_availability,
            "growth_rate": growth_rate,

            "sales_team_count": self.company.get_sales_count(),
            "production_team_count": self.company.get_production_count(),

            "total_revenue":revenue,
            "total_cogs": cogs,
            "gross_profit": gross_profit,
            "operating_expenses": opex,
            "net_profit": net_profit

        }
        # ---------------------
        # State Update
        # ---------------------
        #append tables
        self.daily_table.append(daily_row)
        self.product_daily_table.extend(product_rows)

        #update state
        self.cumulative_cogs+=cogs
        self.cumulative_opex+=opex
        self.cumulative_revenue+=revenue

        self.base_demand *= 1 + growth_rate
        self.day+=1

        return daily_row, product_rows

    def simulate(self, days: int) -> None:
        for day in range(days):
            self.simulate_day()
    
    def print_daily_summary(self, days: int = 10):
        print("\n=== DAILY SUMMARY ===\n")

        for row in self.daily_table[:days]:
            print(
                f"Day {row['simulation_day']:3} | "
                f"Base Demand: {row['base_demand']:8.0f} | "
                f"Demand: {row['potential_demand']:8.0f} | "
                f"Sales: {row['actual_sales']:6} | "
                f"Capacity: {row['capacity']:6} | "
                f"Growth: {row['growth_rate']*100:7.3f}% | "
                f"Availability: {row['rolling_availability']*100:6.2f}%"
            )
    def print_product_summary(self, day: int):
        print(f"\n=== PRODUCT SUMMARY DAY {day} ===\n")

        rows = [
                row for row in self.product_daily_table
                if row["simulation_day"] == day
        ]

        for row in rows:
            print(
                    f"{row['product_name']:<15} | "
                    f"Units: {row['units_sold']:5} | "
                    f"Revenue: ${row['product_revenue']:10.2f} | "
                    f"Profit: ${row['product_profit']:10.2f}"
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
