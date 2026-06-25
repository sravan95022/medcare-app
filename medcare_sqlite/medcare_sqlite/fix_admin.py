from database import engine
from sqlalchemy import text
conn = engine.connect()
conn.execute(text("UPDATE users SET role='ADMIN' WHERE email='admin@medcare.in'"))
conn.commit()
print('Done!')
