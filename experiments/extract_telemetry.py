import sqlite3
import pandas as pd
import os

# Define the absolute path to the sentinet database
# This allows the script to run from anywhere without touching the main codebase
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "admin-backend", "sentinet.db")

def fetch_threat_logs():
    """
    Fetches the threat log data from the admin backend's SQLite database.
    This is useful for extracting the exact timestamps for Phase 4 (Collaborative Response)
    and calculating Time-to-Block (TTB).
    """
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Ensure admin-backend has run at least once.")
        return None

    try:
        # Connect to the SQLite database (read-only mode is best practice for data extraction)
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        
        # Read the threats table into a Pandas DataFrame
        # Adjust the table name based on what's defined in admin-backend/state.py
        query = "SELECT * FROM threats" 
        df = pd.read_sql_query(query, conn)
        
        print("Successfully extracted threat logs:")
        print(df.head())
        
        # Example: Save to a CSV file in this experiments/ folder
        output_csv = os.path.join(os.path.dirname(__file__), "threat_logs_export.csv")
        df.to_csv(output_csv, index=False)
        print(f"Saved extracted data to {output_csv}")
        
        return df

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("SentiNet Telemetry Extraction Tool")
    print("-----------------------------------")
    fetch_threat_logs()
