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









