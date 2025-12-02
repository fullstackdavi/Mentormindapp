import sqlite3
import os
from datetime import datetime, timedelta
import json
import threading
import time

# SQLite Cloud connection string
SQLITECLOUD_URL = os.environ.get('SQLITECLOUD_URL', 'sqlitecloud://ck43o40wdz.g4.sqlite.cloud:8860/mentormind.db?apikey=5uGL1tWmzFabimtNUzz0LGPLyKO7QKe6PiyIliCuboE')

_db_initialized = False
_ping_thread = None

def dict_factory(cursor, row):
    """Factory customizado para retornar dicionários ao invés de Row objects"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def get_db():
    """Conecta ao SQLite Cloud"""
    global _db_initialized
    
    try:
        import sqlitecloud
        
        # Conecta ao SQLite Cloud
        conn = sqlitecloud.connect(SQLITECLOUD_URL)
        # Usa dict_factory ao invés de sqlite3.Row para compatibilidade
        conn.row_factory = dict_factory
        
        # Inicializa o banco de dados na primeira conexão
        if not _db_initialized:
            init_db_tables(conn)
            _db_initialized = True
            # Inicia o thread de ping apenas em ambientes não-serverless
            if not os.environ.get('VERCEL'):
                start_ping_thread()
        
        return conn
    except ImportError as e:
        print(f"Erro: sqlitecloud não está instalado. Certifique-se de que está em requirements.txt")
        raise
    except Exception as e:
        print(f"Erro ao conectar ao SQLite Cloud: {e}")
        raise

def ping_database():
    """Faz ping no banco de dados a cada 5 minutos para manter a conexão ativa"""
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            conn.close()
            print(f"[{datetime.now()}] Ping ao SQLite Cloud realizado com sucesso")
        except Exception as e:
            print(f"[{datetime.now()}] Erro no ping ao SQLite Cloud: {e}")
        
        # Aguarda 5 minutos (300 segundos)
        time.sleep(300)

def start_ping_thread():
    """Inicia o thread de ping automático"""
    global _ping_thread
    if _ping_thread is None or not _ping_thread.is_alive():
        _ping_thread = threading.Thread(target=ping_database, daemon=True)
        _ping_thread.start()
        print("Thread de ping ao SQLite Cloud iniciado")

def init_db_tables(conn):
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            total_focus_time INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_study_date TEXT,
            is_premium INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            preferences TEXT DEFAULT '{}'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            objective TEXT NOT NULL,
            daily_hours REAL DEFAULT 2,
            deadline TEXT,
            subjects TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT,
            description TEXT,
            scheduled_date TEXT,
            duration_minutes INTEGER DEFAULT 30,
            is_completed INTEGER DEFAULT 0,
            completed_at TEXT,
            priority INTEGER DEFAULT 1,
            FOREIGN KEY (plan_id) REFERENCES study_plans(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            session_type TEXT DEFAULT 'pomodoro',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed INTEGER DEFAULT 0,
            xp_earned INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            subject TEXT,
            tags TEXT DEFAULT '[]',
            content_text TEXT,
            page_count INTEGER DEFAULT 0,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pdf_id INTEGER,
            title TEXT NOT NULL,
            original_text TEXT,
            short_summary TEXT,
            full_summary TEXT,
            topics TEXT DEFAULT '[]',
            mind_map TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (pdf_id) REFERENCES pdfs(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            summary_id INTEGER,
            deck_name TEXT DEFAULT 'Geral',
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            difficulty REAL DEFAULT 2.5,
            interval_days INTEGER DEFAULT 1,
            repetitions INTEGER DEFAULT 0,
            next_review TEXT,
            last_reviewed TEXT,
            ease_factor REAL DEFAULT 2.5,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (summary_id) REFERENCES summaries(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcard_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flashcard_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            quality INTEGER NOT NULL,
            reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (flashcard_id) REFERENCES flashcards(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT,
            questions TEXT NOT NULL,
            total_questions INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            time_spent_seconds INTEGER DEFAULT 0,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            xp_reward INTEGER DEFAULT 50,
            requirement_type TEXT NOT NULL,
            requirement_value INTEGER NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_id INTEGER NOT NULL,
            earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (badge_id) REFERENCES badges(id),
            UNIQUE(user_id, badge_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentor_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'motivation',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            focus_goal_minutes INTEGER DEFAULT 60,
            focus_achieved_minutes INTEGER DEFAULT 0,
            flashcards_goal INTEGER DEFAULT 10,
            flashcards_done INTEGER DEFAULT 0,
            tasks_goal INTEGER DEFAULT 3,
            tasks_done INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weak_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            error_count INTEGER DEFAULT 1,
            last_error_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    default_badges = [
        ('Primeiro Passo', 'Complete sua primeira sessao de foco', 'fa-shoe-prints', 25, 'focus_sessions', 1),
        ('Focado', 'Complete 10 sessoes de foco', 'fa-bullseye', 100, 'focus_sessions', 10),
        ('Mestre do Foco', 'Complete 50 sessoes de foco', 'fa-brain', 500, 'focus_sessions', 50),
        ('Leitor Iniciante', 'Adicione seu primeiro PDF', 'fa-book-open', 25, 'pdfs', 1),
        ('Bibliotecario', 'Adicione 10 PDFs', 'fa-books', 150, 'pdfs', 10),
        ('Memorias', 'Revise 50 flashcards', 'fa-cards', 100, 'flashcard_reviews', 50),
        ('Memoria Fotografica', 'Revise 500 flashcards', 'fa-memory', 500, 'flashcard_reviews', 500),
        ('Estudante Dedicado', 'Estude por 7 dias seguidos', 'fa-fire', 200, 'streak', 7),
        ('Imparavel', 'Estude por 30 dias seguidos', 'fa-medal', 1000, 'streak', 30),
        ('Resumidor', 'Gere 5 resumos com IA', 'fa-file-lines', 75, 'summaries', 5),
        ('Nivel 5', 'Alcance o nivel 5', 'fa-star', 100, 'level', 5),
        ('Nivel 10', 'Alcance o nivel 10', 'fa-crown', 300, 'level', 10),
    ]
    
    for badge in default_badges:
        cursor.execute('''
            INSERT OR IGNORE INTO badges (name, description, icon, xp_reward, requirement_type, requirement_value)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', badge)
    
    conn.commit()

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            total_focus_time INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_study_date TEXT,
            is_premium INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            preferences TEXT DEFAULT '{}'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            objective TEXT NOT NULL,
            daily_hours REAL DEFAULT 2,
            deadline TEXT,
            subjects TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT,
            description TEXT,
            scheduled_date TEXT,
            duration_minutes INTEGER DEFAULT 30,
            is_completed INTEGER DEFAULT 0,
            completed_at TEXT,
            priority INTEGER DEFAULT 1,
            FOREIGN KEY (plan_id) REFERENCES study_plans(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            session_type TEXT DEFAULT 'pomodoro',
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed INTEGER DEFAULT 0,
            xp_earned INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            subject TEXT,
            tags TEXT DEFAULT '[]',
            content_text TEXT,
            page_count INTEGER DEFAULT 0,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pdf_id INTEGER,
            title TEXT NOT NULL,
            original_text TEXT,
            short_summary TEXT,
            full_summary TEXT,
            topics TEXT DEFAULT '[]',
            mind_map TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (pdf_id) REFERENCES pdfs(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            summary_id INTEGER,
            deck_name TEXT DEFAULT 'Geral',
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            difficulty REAL DEFAULT 2.5,
            interval_days INTEGER DEFAULT 1,
            repetitions INTEGER DEFAULT 0,
            next_review TEXT,
            last_reviewed TEXT,
            ease_factor REAL DEFAULT 2.5,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (summary_id) REFERENCES summaries(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcard_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flashcard_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            quality INTEGER NOT NULL,
            reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (flashcard_id) REFERENCES flashcards(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT,
            questions TEXT NOT NULL,
            total_questions INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            time_spent_seconds INTEGER DEFAULT 0,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            xp_reward INTEGER DEFAULT 50,
            requirement_type TEXT NOT NULL,
            requirement_value INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_id INTEGER NOT NULL,
            earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (badge_id) REFERENCES badges(id),
            UNIQUE(user_id, badge_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentor_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'motivation',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            focus_goal_minutes INTEGER DEFAULT 60,
            focus_achieved_minutes INTEGER DEFAULT 0,
            flashcards_goal INTEGER DEFAULT 10,
            flashcards_done INTEGER DEFAULT 0,
            tasks_goal INTEGER DEFAULT 3,
            tasks_done INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weak_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            error_count INTEGER DEFAULT 1,
            last_error_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    default_badges = [
        ('Primeiro Passo', 'Complete sua primeira sessao de foco', 'fa-shoe-prints', 25, 'focus_sessions', 1),
        ('Focado', 'Complete 10 sessoes de foco', 'fa-bullseye', 100, 'focus_sessions', 10),
        ('Mestre do Foco', 'Complete 50 sessoes de foco', 'fa-brain', 500, 'focus_sessions', 50),
        ('Leitor Iniciante', 'Adicione seu primeiro PDF', 'fa-book-open', 25, 'pdfs', 1),
        ('Bibliotecario', 'Adicione 10 PDFs', 'fa-books', 150, 'pdfs', 10),
        ('Memorias', 'Revise 50 flashcards', 'fa-cards', 100, 'flashcard_reviews', 50),
        ('Memoria Fotografica', 'Revise 500 flashcards', 'fa-memory', 500, 'flashcard_reviews', 500),
        ('Estudante Dedicado', 'Estude por 7 dias seguidos', 'fa-fire', 200, 'streak', 7),
        ('Imparavel', 'Estude por 30 dias seguidos', 'fa-medal', 1000, 'streak', 30),
        ('Resumidor', 'Gere 5 resumos com IA', 'fa-file-lines', 75, 'summaries', 5),
        ('Nivel 5', 'Alcance o nivel 5', 'fa-star', 100, 'level', 5),
        ('Nivel 10', 'Alcance o nivel 10', 'fa-crown', 300, 'level', 10),
    ]

    for badge in default_badges:
        cursor.execute('''
            INSERT OR IGNORE INTO badges (name, description, icon, xp_reward, requirement_type, requirement_value)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', badge)

    conn.commit()
    conn.close()

def calculate_level(xp):
    level = 1
    xp_needed = 100
    total_xp = 0
    while total_xp + xp_needed <= xp:
        total_xp += xp_needed
        level += 1
        xp_needed = int(xp_needed * 1.5)
    return level, xp - total_xp, xp_needed

def get_xp_for_level(level):
    if level <= 1:
        return 0, 100
    xp_needed = 100
    total_xp = 0
    for l in range(1, level):
        total_xp += xp_needed
        xp_needed = int(xp_needed * 1.5)
    return total_xp, xp_needed

def add_xp(user_id, amount):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT xp, level FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            new_xp = user['xp'] + amount
            new_level = calculate_level(new_xp)[0]
            cursor.execute('UPDATE users SET xp = ?, level = ? WHERE id = ?', (new_xp, new_level, user_id))
            conn.commit()
            return new_xp, new_level
        return 0, 1
    except Exception as e:
        conn.rollback()
        print(f"Erro ao adicionar XP: {e}")
        return 0, 1
    finally:
        conn.close()

def sm2_algorithm(quality, repetitions, ease_factor, interval):
    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = int(interval * ease_factor)
        repetitions += 1

    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease_factor < 1.3:
        ease_factor = 1.3

    return repetitions, ease_factor, interval

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")