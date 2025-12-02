
#!/usr/bin/env python3
"""Script para testar a conexão com SQLite Cloud"""

import os
from database import get_db

def test_connection():
    print("Testando conexão com SQLite Cloud...")
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Testa uma query simples
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        
        # Testa se há tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("✓ Conexão estabelecida com sucesso!")
        print(f"✓ Número de tabelas: {len(tables)}")
        
        if tables:
            print("\nTabelas encontradas:")
            for table in tables:
                print(f"  - {table['name']}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Erro ao conectar: {e}")
        return False

if __name__ == '__main__':
    test_connection()
