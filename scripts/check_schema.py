import sqlite3

def check_schema():
    conn = sqlite3.connect('tander.db')
    cursor = conn.cursor()
    
    print("--- Enterprises Table ---")
    cursor.execute("PRAGMA table_info(enterprises)")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
        
    print("\n--- Individuals Table ---")
    cursor.execute("PRAGMA table_info(individuals)")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
        
    conn.close()

if __name__ == "__main__":
    check_schema()
