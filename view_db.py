import sqlite3

def display_db():
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print(" 📊 VERBOLABS SQLITE DATABASE OVERVIEW (app.db)")
    print("=" * 60)

    tables = ["projects", "media_files", "subtitle_tracks", "subtitle_cues"]

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [c[1] for c in cursor.fetchall()]
        
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        print(f"\n📂 TABLE: {table.upper()} ({len(rows)} records)")
        print("-" * 60)
        
        if not rows:
            print("  (Empty)")
            continue
            
        # Print column headers
        header = " | ".join(cols[:6])
        print(header)
        print("-" * len(header))
        
        for r in rows:
            row_str = " | ".join(str(val) if val is not None else "NULL" for val in r[:6])
            print(row_str)

    print("\n" + "=" * 60 + "\n")
    conn.close()

if __name__ == "__main__":
    display_db()
