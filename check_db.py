import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="dr365v_metrics",
    user="postgres",
    password="postgres"
)

cur = conn.cursor()
cur.execute("SELECT job_name, overall_score, dedup_ratio, compression_ratio FROM efficiency_scores ORDER BY overall_score DESC;")
rows = cur.fetchall()
for row in rows:
    print(row)
cur.close()
conn.close()
