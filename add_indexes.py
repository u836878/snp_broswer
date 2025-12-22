import sqlite3
import os

# Connect to database
db_path = 'SNPdata.db'
if not os.path.exists(db_path):
    print(f"Error: Database file '{db_path}' not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Adding indexes to improve query performance...")

# Check if indexes already exist and create them if they don't
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snp ON snp_data(SNP)")
    print("✓ Index on SNP column created/verified")
except Exception as e:
    print(f"Index on SNP: {e}")

try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gen ON snp_data(Gen)")
    print("✓ Index on Gen column created/verified")
except Exception as e:
    print(f"Index on Gen: {e}")

try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_color ON snp_data(Color)")
    print("✓ Index on Color column created/verified")
except Exception as e:
    print(f"Index on Color: {e}")

try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snp_gen_color ON snp_data(SNP, Gen, Color)")
    print("✓ Composite index on SNP+Gen+Color created/verified")
except Exception as e:
    print(f"Composite index: {e}")

conn.commit()
conn.close()

print("\n✅ Database optimization complete!")
print("This will significantly speed up query performance.")
