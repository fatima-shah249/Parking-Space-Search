
import pandas as pd
from sqlalchemy import create_engine
import os

DATABASE_URL = "postgresql://parkingmanagement_user:lYskYRdkX7RopjtmZVD92jFzmp2uKEOb@dpg-d3ckgud6ubrc73esgf70-a.oregon-postgres.render.com/parkingmanagement"
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set!")

engine = create_engine(DATABASE_URL)
base_dir = os.path.join(os.path.dirname(__file__), "static", "data")

csv_mappings = {
    "location_of_slots.csv": "location_of_slots",
    "user_applications.csv": "user_applications",
    "user_concerns.csv": "user_concerns"
}

for file_name, table_name in csv_mappings.items():
    file_path = os.path.join(base_dir, file_name)
    print(f"Importing {file_name} into table {table_name}...")
    df = pd.read_csv(file_path, encoding='latin1')
    df.to_sql(table_name, engine, if_exists='append', index=False)
    print(f"{table_name} imported successfully!")
