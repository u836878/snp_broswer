import sqlite3

conn = sqlite3.connect('SNPdata.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(snp_data)')
cols = cursor.fetchall()
print("Database columns:")
for col in cols:
    print(f'{col[0]}: {col[1]}')

cursor.execute('SELECT * FROM snp_data LIMIT 1')
sample = cursor.fetchone()
print(f"\nSample row: {sample}")
conn.close()
