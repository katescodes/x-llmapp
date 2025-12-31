import psycopg
conn = psycopg.connect("host=postgres dbname=localgpt user=localgpt password=localgpt")
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='tender_project_assets' ORDER BY ordinal_position")
print('\n'.join([r[0] for r in cur.fetchall()]))

