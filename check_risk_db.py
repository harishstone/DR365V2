import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database='dr365v',
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'postgres')
)

cur = conn.cursor()
cur.execute("""
    SELECT job_name, composite_risk_score, business_impact_score, risk_category
    FROM dr365v.metrics_risk_analysis_consolidated
    ORDER BY composite_risk_score DESC
""")
rows = cur.fetchall()

print("Risk Scores from Feature 5:")
for row in rows:
    print(f"Job: {row[0]}, Composite Risk: {row[1]}, Business Impact: {row[2]}, Category: {row[3]}")

cur.close()
conn.close()
