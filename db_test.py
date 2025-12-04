from sqlalchemy import create_engine
engine = create_engine("mysql+pymysql://fueluser:fuelpass123@localhost:3306/fuelflux")
conn = engine.connect()
print("Connected:", not conn.closed)
conn.close()
