import re

def convert_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Replace login function
    content = re.sub(
        r"conn = get_db_connection\(\)\s*\n\s*user = conn\.execute\('SELECT \* FROM usuarios WHERE correo = \? AND password = \?', \(correo, password\)\)\.fetchone\(\)\s*\n\s*conn\.close\(\)",
        "user = query_db('SELECT * FROM usuarios WHERE correo = ? AND password = ?', (correo, password), fetch_one=True)",
        content
    )
    
    # 2. Replace conn.execute(...).fetchall() with query_db(..., fetch_all=True)
    content = re.sub(
        r"conn = get_db_connection\(\)\s*\n\s*(.*?)\s*=\s*conn\.execute\((.*?)\)\.fetchall\(\)\s*\n\s*conn\.close\(\)",
        r"\1 = query_db(\2, fetch_all=True)",
        content,
        flags=re.DOTALL
    )
    
    # 3. Replace conn.execute(...).fetchone() with query_db(..., fetch_one=True)
    content = re.sub(
        r"conn = get_db_connection\(\)\s*\n\s*(.*?)\s*=\s*conn\.execute\((.*?)\)\.fetchone\(\)\s*\n\s*conn\.close\(\)",
        r"\1 = query_db(\2, fetch_one=True)",
        content,
        flags=re.DOTALL
    )
    
    # 4. Replace INSERT with conn.commit() and last_insert_rowid
    content = re.sub(
        r"conn\.execute\(\"(.*?)\"\)\s*\n\s*conn\.commit\(\)\s*\n\s*reporte_id = conn\.execute\('SELECT last_insert_rowid\(\)'\)\.fetchone\(\)\[0\]",
        r"reporte_id = query_db('\1', commit=True)\n        reporte_id = query_db('SELECT last_insert_rowid()', fetch_one=True)[0]",
        content,
        flags=re.DOTALL
    )
    
    # Remove remaining conn = get_db_connection()
    content = re.sub(r'\n\s*conn = get_db_connection\(\)', '', content)
    
    # Remove remaining conn.close()
    content = re.sub(r'\n\s*conn\.close\(\)', '', content)
    
    # Fix remaining conn.execute patterns - those inside functions
    # Replace conn.execute with query_db and add .fetchall() removal
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Done")

if __name__ == "__main__":
    convert_file("app.py")