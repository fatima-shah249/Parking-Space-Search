
import pandas as pd
from sqlalchemy import create_engine
import os

DATABASE_URL = "postgresql://parking_management_ywqc_user:v6Avfv0Ire0sfXOfyRfzNz7oxUhmWAIc@dpg-d40fe8uuk2gs73a2cij0-a.oregon-postgres.render.com/parking_management_ywqc"
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set!")

engine = create_engine(DATABASE_URL)
base_dir = os.path.join(os.path.dirname(__file__), "static", "data")

csv_mappings = {
    "location_of_slots.csv": "location_of_slots"
}

for file_name, table_name in csv_mappings.items():
    file_path = os.path.join(base_dir, file_name)
    print(f"Importing {file_name} into table {table_name}...")
    df = pd.read_csv(file_path, encoding='latin1',sep=';')
    df.to_sql(table_name, engine, if_exists='append', index=False)
    print(f"{table_name} imported successfully!")
