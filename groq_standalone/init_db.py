import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("groundwater_data.db")


SAMPLE_ROWS = [
    ("Punjab", "Ludhiana", 338.4, 548.6, 162.1, "Over-Exploited"),
    ("Punjab", "Patiala", 276.2, 360.4, 130.5, "Over-Exploited"),
    ("Punjab", "Amritsar", 214.8, 263.2, 122.5, "Over-Exploited"),
    ("Punjab", "Bathinda", 189.6, 211.8, 111.7, "Over-Exploited"),
    ("Karnataka", "Bengaluru Urban", 92.5, 96.8, 104.6, "Over-Exploited"),
    ("Karnataka", "Tumakuru", 238.4, 166.3, 69.8, "Safe"),
    ("Karnataka", "Mandya", 144.6, 133.9, 92.6, "Critical"),
    ("Karnataka", "Mysuru", 181.2, 117.1, 64.6, "Safe"),
    ("Rajasthan", "Jaipur", 236.3, 284.7, 120.5, "Over-Exploited"),
    ("Rajasthan", "Jodhpur", 164.8, 156.5, 95.0, "Critical"),
    ("Rajasthan", "Ajmer", 142.4, 128.9, 90.5, "Critical"),
    ("Rajasthan", "Udaipur", 188.2, 108.4, 57.6, "Safe"),
]


def build_database():
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE district_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_name TEXT NOT NULL,
                district_name TEXT NOT NULL,
                annual_extractable_mcm REAL NOT NULL,
                total_extraction_mcm REAL NOT NULL,
                stage_extraction_percentage REAL NOT NULL,
                status_category TEXT NOT NULL CHECK (
                    status_category IN (
                        'Safe',
                        'Semi-Critical',
                        'Critical',
                        'Over-Exploited'
                    )
                )
            )
        """)

        conn.executemany("""
            INSERT INTO district_assessments (
                state_name,
                district_name,
                annual_extractable_mcm,
                total_extraction_mcm,
                stage_extraction_percentage,
                status_category
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, SAMPLE_ROWS)

        conn.execute("CREATE INDEX idx_state ON district_assessments(state_name)")
        conn.execute("CREATE INDEX idx_district ON district_assessments(district_name)")
        conn.execute("CREATE INDEX idx_category ON district_assessments(status_category)")

    print(f"Created {DB_PATH} with {len(SAMPLE_ROWS)} district rows.")


if __name__ == "__main__":
    build_database()
