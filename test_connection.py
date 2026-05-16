import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

CONN_STR = (
    f"host={os.environ['DB_HOST']} "
    f"port={os.environ['DB_PORT']} "
    f"dbname={os.environ['DB_NAME']} "
    f"user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASSWORD']}"
)


def main():
    with psycopg.connect(CONN_STR) as conn:
        with conn.cursor() as cur:
            # Confirm pgvector is available
            cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            result = cur.fetchone()
            if result:
                print(f"Connected. pgvector version: {result[1]}")
            else:
                print("Connected, but pgvector extension is not installed.")
                return

            # Create a temp table, insert a vector, query it back
            cur.execute("""
                CREATE TEMP TABLE py_test_vectors (
                    id SERIAL PRIMARY KEY,
                    label TEXT,
                    embedding vector(3)
                );
            """)

            cur.execute("""
                INSERT INTO py_test_vectors (label, embedding) VALUES
                    ('apple',  '[1, 2, 3]'),
                    ('banana', '[1, 2, 4]'),
                    ('car',    '[9, 8, 7]');
            """)

            cur.execute("""
                SELECT label, embedding <=> '[1, 2, 3]' AS distance
                FROM py_test_vectors
                ORDER BY distance
                LIMIT 3;
            """)

            print("\nNearest neighbors to [1, 2, 3]:")
            for label, distance in cur.fetchall():
                print(f"  {label}: distance = {distance:.4f}")


if __name__ == "__main__":
    main()