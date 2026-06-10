from snowflake.snowpark import Session
from snowflake.snowpark import Row
from dotenv import load_dotenv
import os
from engine import SalesEngine
from company import Company

load_dotenv()

class DatabaseManager:
    session: Session
    def __init__(self):
        self.params= {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "role": os.getenv("SNOWFLAKE_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
            "database": os.getenv("SNOWFLAKE_DATABASE"),
            "schema": os.getenv("SNOWFLAKE_SCHEMA")
        }

        
    def create_session(self):
        self.session=Session.builder.configs(self.params).create()

    def close_session(self):
        self.session.close()
    def databaseInventoryUpdate(self, engine: SalesEngine):
        company=engine.getCompany()
        inventory = company.get_inventory()
        product_rows = [
        {
            "product_id": p.product_id,
            "name": p.name,
            "price": float(p.price),
            "material_cost": float(p.material_cost),
            "labor_cost": float(p.labor_cost),
            "other_cost": float(p.other_cost),
            "quality": float(p.quality),
        }
            for p in inventory.items
        ]
        df = self.session.create_dataframe(product_rows)

        df.write.save_as_table(
            "PRODUCT",
            mode="overwrite"
        )

    def databaseWrite(self, daily_row, product_rows):

        daily_df=self.session.create_dataframe([daily_row])
        product_df=self.session.create_dataframe(product_rows)

        daily_df.write.save_as_table("DAILY_SALES", mode="append")
        product_df.write.save_as_table("PRODUCT_DAILY_SALES", mode="append")
    def wipeTables(self):
        self.session.sql(
            f"TRUNCATE TABLE {os.getenv('SNOWFLAKE_DATABASE')}.{os.getenv('SNOWFLAKE_SCHEMA')}.DAILY_SALES"
        ).collect()

        self.session.sql(
            f"TRUNCATE TABLE {os.getenv('SNOWFLAKE_DATABASE')}.{os.getenv('SNOWFLAKE_SCHEMA')}.PRODUCT_DAILY_SALES"
        ).collect()

        self.session.sql(
            f"TRUNCATE TABLE {os.getenv('SNOWFLAKE_DATABASE')}.{os.getenv('SNOWFLAKE_SCHEMA')}.PRODUCT"
        ).collect()


#SETUP COMPANY
company = Company()

company.hire_production(count=1000, salary=50_000)
company.hire_sales(count=150, salary=70_000)

inventory = company.get_inventory()

inventory.add_product("Coca-Cola", price=10, material_cost=1.00, labor_cost=0.50, other_cost=0.25, quality=1.3)
inventory.add_product("Apple", price=1.5, material_cost=0.60, labor_cost=0.25, other_cost=0.15, quality=1.1)
inventory.add_product("Generator", price=1000, material_cost=100, labor_cost=1, other_cost=2, quality=2)

#SETUP ENGINE
engine = SalesEngine(
    company=company,
    starting_daily_demand=5000,
    yearly_growth_rate=0.08,
    units_per_production_employee=500,
    max_market_demand=5_000_000,
    price_sensitivity=1.5,
    sales_effectiveness=0.003,
    demand_noise_std=0.03,
    product_noise_std=0.05,
    stockout_penalty_strength=1000,
    seed=42
)

#SETUP DATABASE
db=DatabaseManager()
db.create_session()
db.wipeTables()
db.databaseInventoryUpdate(engine)
try:
    for day in range(1, 366):
        daily_row,product_rows=engine.simulate_day()
        db.databaseWrite(daily_row, product_rows)
        print(f"Day {day} persisted")
    
finally:
    db.close_session()




