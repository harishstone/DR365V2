import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="dr365v_metrics",
    user="postgres",
    password="postgres"
)

cur = conn.cursor()

# Check if table exists and get grade counts
try:
    cur.execute("""
        SELECT recovery_grade, COUNT(*) as count
        FROM feature4.metrics_recovery_verification
        GROUP BY recovery_grade
        ORDER BY recovery_grade
    """)
    rows = cur.fetchall()
    print("Recovery Grade Counts:")
    for row in rows:
        print(f"Grade {row[0]}: {row[1]} jobs")
    
    # Also check total jobs
    cur.execute("SELECT COUNT(*) FROM feature4.metrics_recovery_verification")
    total = cur.fetchone()[0]
    print(f"Total jobs: {total}")
    
except Exception as e:
    print(f"Error: {e}")

cur.close()
conn.close()
