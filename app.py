
import os
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import PyPDF2
from database import get_db, init_db, add_xp, calculate_level, sm2_algorithm, start_ping_thread

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Inicia o ping automático ao SQLite Cloud apenas em ambientes não-serverless
# Vercel define VERCEL=1 em produção, não iniciar thread lá
if not os.environ.get('VERCEL'):
    start_ping_thread()

# Configurações de produção
if os.environ.get('REPLIT_DEPLOYMENT'):
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_gemini_client():
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("GOOGLE_API_KEY nao encontrada nas variaveis de ambiente")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_stats(user_id):
    conn = get_db()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('SELECT SUM(duration_minutes) as total FROM focus_sessions WHERE user_id = ? AND DATE(started_at) = ?', (user_id, today))
    focus_today = cursor.fetchone()['total'] or 0
    
    cursor.execute('SELECT COUNT(*) as count FROM flashcards WHERE user_id = ? AND (next_review IS NULL OR DATE(next_review) <= ?)', (user_id, today))
    pending_flashcards = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM study_tasks WHERE user_id = ? AND scheduled_date = ? AND is_completed = 0', (user_id, today))
    pending_tasks = cursor.fetchone()['count']
    
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute('SELECT DATE(started_at) as day, SUM(duration_minutes) as total FROM focus_sessions WHERE user_id = ? AND DATE(started_at) >= ? GROUP BY DATE(started_at)', (user_id, week_ago))
    weekly_progress = {row['day']: row['total'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'focus_today': focus_today,
        'pending_flashcards': pending_flashcards,
        'pending_tasks': pending_tasks,
        'weekly_progress': weekly_progress
    }

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        
        if not all([username, email, password, name]):
            flash('Preencha todos os campos', 'error')
            return render_template('register.html')
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            flash('Usuario ou email ja existe', 'error')
            conn.close()
            return render_template('register.html')
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, name)
            VALUES (?, ?, ?, ?)
        ''', (username, email, generate_password_hash(password), name))
        
        user_id = cursor.lastrowid
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO daily_goals (user_id, date) VALUES (?, ?)
        ''', (user_id, today))
        
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        session['username'] = username
        flash('Conta criada com sucesso! Bem-vindo ao MentorMind!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        
        flash('Usuario ou senha incorretos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        return redirect(url_for('logout'))
    
    stats = get_user_stats(session['user_id'])
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT * FROM study_tasks WHERE user_id = ? AND scheduled_date = ? ORDER BY priority DESC, is_completed ASC LIMIT 5', 
                  (session['user_id'], today))
    tasks = cursor.fetchall()
    
    cursor.execute('SELECT * FROM mentor_messages WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT 3', (session['user_id'],))
    mentor_msgs = cursor.fetchall()
    
    level, current_xp, xp_needed = calculate_level(user['xp'])
    
    conn.close()
    
    return render_template('dashboard.html', 
                          user=user, 
                          stats=stats, 
                          tasks=tasks,
                          mentor_msgs=mentor_msgs,
                          level=level,
                          current_xp=current_xp,
                          xp_needed=xp_needed)

@app.route('/focus')
@login_required
def focus():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('''
        SELECT u.username, u.name, SUM(f.duration_minutes) as total_focus 
        FROM users u 
        LEFT JOIN focus_sessions f ON u.id = f.user_id AND DATE(f.started_at) >= DATE('now', '-7 days')
        GROUP BY u.id 
        ORDER BY total_focus DESC 
        LIMIT 10
    ''')
    ranking = cursor.fetchall()
    
    conn.close()
    return render_template('focus.html', user=user, ranking=ranking)

@app.route('/api/focus/complete', methods=['POST'])
@login_required
def complete_focus():
    data = request.get_json()
    duration = data.get('duration', 25)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO focus_sessions (user_id, duration_minutes, completed)
        VALUES (?, ?, 1)
    ''', (session['user_id'], duration))
    
    xp_earned = duration * 2
    add_xp(session['user_id'], xp_earned)
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO daily_goals (user_id, date, focus_achieved_minutes)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
        focus_achieved_minutes = focus_achieved_minutes + ?
    ''', (session['user_id'], today, duration, duration))
    
    cursor.execute('SELECT last_study_date, streak_days FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if user['last_study_date'] == yesterday:
        new_streak = user['streak_days'] + 1
    elif user['last_study_date'] == today:
        new_streak = user['streak_days']
    else:
        new_streak = 1
    
    cursor.execute('UPDATE users SET last_study_date = ?, streak_days = ?, total_focus_time = total_focus_time + ? WHERE id = ?',
                  (today, new_streak, duration, session['user_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'xp_earned': xp_earned})

@app.route('/library')
@login_required
def library():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pdfs WHERE user_id = ? ORDER BY uploaded_at DESC', (session['user_id'],))
    pdfs = cursor.fetchall()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('library.html', pdfs=pdfs, user=user)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        content_text = ""
        page_count = 0
        
        if filename.lower().endswith('.pdf'):
            try:
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    page_count = len(reader.pages)
                    for page in reader.pages[:10]:
                        content_text += page.extract_text() or ""
            except:
                pass
        
        subject = request.form.get('subject', 'Geral')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pdfs (user_id, filename, original_name, subject, content_text, page_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], unique_filename, filename, subject, content_text[:10000], page_count))
        
        pdf_id = cursor.lastrowid
        add_xp(session['user_id'], 10)
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'pdf_id': pdf_id})
    
    return jsonify({'error': 'Tipo de arquivo nao permitido'}), 400

@app.route('/summary')
@login_required
def summary():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM summaries WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (session['user_id'],))
    summaries = cursor.fetchall()
    
    conn.close()
    return render_template('summary.html', user=user, summaries=summaries)

@app.route('/api/generate-summary', methods=['POST'])
@login_required
def generate_summary():
    text = request.form.get('text', '')
    
    if not text:
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename.endswith('.pdf'):
                try:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages[:20]:
                        text += page.extract_text() or ""
                except:
                    return jsonify({'error': 'Erro ao ler PDF'}), 400
    
    if not text or len(text) < 50:
        return jsonify({'error': 'Texto muito curto para gerar resumo'}), 400
    
    client = get_gemini_client()
    if not client:
        return jsonify({'error': 'Chave da API Google nao configurada. Configure GOOGLE_API_KEY nas configuracoes.'}), 400
    
    try:
        prompt = f"""Voce e um assistente educacional especializado em criar resumos de estudo. 
        Responda sempre em portugues brasileiro.
        Retorne APENAS um JSON valido, sem texto adicional, com a seguinte estrutura:
        {{
            "title": "titulo do conteudo",
            "short_summary": "resumo curto em 2-3 frases",
            "full_summary": "resumo completo e detalhado",
            "topics": ["topico 1", "topico 2", "topico 3"],
            "flashcards": [{{"front": "pergunta", "back": "resposta"}}],
            "mind_map": {{"central": "tema central", "branches": [{{"name": "subtema", "items": ["item1", "item2"]}}]}}
        }}
        
        Crie um resumo educacional completo do seguinte texto:
        
        {text[:8000]}"""
        
        response = client.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            response_text = response_text[start_idx:end_idx+1]
        
        result = json.loads(response_text)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO summaries (user_id, title, original_text, short_summary, full_summary, topics, mind_map)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            result.get('title', 'Resumo'),
            text[:5000],
            result.get('short_summary', ''),
            result.get('full_summary', ''),
            json.dumps(result.get('topics', [])),
            json.dumps(result.get('mind_map', {}))
        ))
        
        summary_id = cursor.lastrowid
        
        for fc in result.get('flashcards', [])[:10]:
            cursor.execute('''
                INSERT INTO flashcards (user_id, summary_id, front, back, next_review)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['user_id'], summary_id, fc['front'], fc['back'], datetime.now().strftime('%Y-%m-%d')))
        
        conn.commit()
        add_xp(session['user_id'], 25)
        conn.close()
        
        return jsonify({'success': True, 'summary': result, 'summary_id': summary_id})
        
    except json.JSONDecodeError as e:
        return jsonify({'error': 'Erro ao processar resposta da IA. Tente novamente.'}), 500
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar resumo: {str(e)}'}), 500

@app.route('/flashcards')
@login_required
def flashcards():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT * FROM flashcards 
        WHERE user_id = ? AND (next_review IS NULL OR next_review <= ?)
        ORDER BY next_review ASC
    ''', (session['user_id'], today))
    pending = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT deck_name, COUNT(*) as count FROM flashcards WHERE user_id = ? GROUP BY deck_name', (session['user_id'],))
    decks = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT DATE(reviewed_at) as day, COUNT(*) as count, 
               SUM(CASE WHEN quality >= 3 THEN 1 ELSE 0 END) as correct
        FROM flashcard_reviews 
        WHERE user_id = ? AND reviewed_at >= DATE('now', '-7 days')
        GROUP BY DATE(reviewed_at)
    ''', (session['user_id'],))
    stats = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return render_template('flashcards.html', user=user, pending=pending, decks=decks, stats=stats)

@app.route('/api/flashcard/review', methods=['POST'])
@login_required
def review_flashcard():
    data = request.get_json()
    flashcard_id = data.get('flashcard_id')
    quality = data.get('quality', 3)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM flashcards WHERE id = ? AND user_id = ?', (flashcard_id, session['user_id']))
    fc = cursor.fetchone()
    
    if not fc:
        conn.close()
        return jsonify({'error': 'Flashcard nao encontrado'}), 404
    
    repetitions, ease_factor, interval = sm2_algorithm(
        quality, fc['repetitions'], fc['ease_factor'], fc['interval_days']
    )
    
    next_review = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
    
    cursor.execute('''
        UPDATE flashcards 
        SET repetitions = ?, ease_factor = ?, interval_days = ?, next_review = ?, last_reviewed = ?
        WHERE id = ?
    ''', (repetitions, ease_factor, interval, next_review, datetime.now().strftime('%Y-%m-%d'), flashcard_id))
    
    cursor.execute('''
        INSERT INTO flashcard_reviews (flashcard_id, user_id, quality)
        VALUES (?, ?, ?)
    ''', (flashcard_id, session['user_id'], quality))
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO daily_goals (user_id, date, flashcards_done)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET
        flashcards_done = flashcards_done + 1
    ''', (session['user_id'], today))
    
    xp = 5 if quality >= 3 else 2
    add_xp(session['user_id'], xp)
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'next_review': next_review, 'xp_earned': xp})

@app.route('/api/flashcard/create', methods=['POST'])
@login_required
def create_flashcard():
    data = request.get_json()
    front = data.get('front', '').strip()
    back = data.get('back', '').strip()
    deck_name = data.get('deck_name', 'Geral')
    
    if not front or not back:
        return jsonify({'error': 'Frente e verso sao obrigatorios'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO flashcards (user_id, front, back, deck_name, next_review)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], front, back, deck_name, datetime.now().strftime('%Y-%m-%d')))
    
    flashcard_id = cursor.lastrowid
    add_xp(session['user_id'], 5)
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'flashcard_id': flashcard_id})

@app.route('/study-plan')
@login_required
def study_plan():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM study_plans WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC', (session['user_id'],))
    plans = cursor.fetchall()
    
    cursor.execute('''
        SELECT * FROM study_tasks 
        WHERE user_id = ? AND scheduled_date >= DATE('now') 
        ORDER BY scheduled_date ASC, priority DESC
        LIMIT 20
    ''', (session['user_id'],))
    tasks = cursor.fetchall()
    
    conn.close()
    return render_template('study_plan.html', user=user, plans=plans, tasks=tasks)

@app.route('/api/create-plan', methods=['POST'])
@login_required
def create_plan():
    data = request.get_json()
    
    title = data.get('title', 'Meu Plano de Estudos')
    objective = data.get('objective', 'ENEM')
    daily_hours = float(data.get('daily_hours', 2))
    deadline = data.get('deadline')
    subjects = data.get('subjects', [])
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO study_plans (user_id, title, objective, daily_hours, deadline, subjects)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], title, objective, daily_hours, deadline, json.dumps(subjects)))
    
    plan_id = cursor.lastrowid
    
    if deadline and subjects:
        client = get_gemini_client()
        if client:
            try:
                prompt = f"""Voce e um planejador de estudos. Crie um cronograma de tarefas.
                Responda em JSON:
                {{"tasks": [{{"title": "titulo", "subject": "materia", "description": "descricao", "duration_minutes": 30, "priority": 1-5}}]}}
                Crie tarefas variadas e distribuidas entre as materias. Maximo 20 tarefas.
                
                Crie um plano de estudos para {objective}. Materias: {', '.join(subjects)}. {daily_hours}h por dia ate {deadline}."""
                
                response = client.generate_content(prompt)
                result = json.loads(response.text)
                
                start_date = datetime.now()
                end_date = datetime.strptime(deadline, '%Y-%m-%d')
                days_available = (end_date - start_date).days
                
                for i, task in enumerate(result.get('tasks', [])[:20]):
                    task_date = start_date + timedelta(days=i % max(1, days_available))
                    cursor.execute('''
                        INSERT INTO study_tasks (plan_id, user_id, title, subject, description, scheduled_date, duration_minutes, priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (plan_id, session['user_id'], task['title'], task.get('subject', ''), 
                          task.get('description', ''), task_date.strftime('%Y-%m-%d'),
                          task.get('duration_minutes', 30), task.get('priority', 3)))
            except:
                pass
    
    add_xp(session['user_id'], 20)
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'plan_id': plan_id})

@app.route('/api/task/complete', methods=['POST'])
@login_required
def complete_task():
    data = request.get_json()
    task_id = data.get('task_id')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE study_tasks SET is_completed = 1, completed_at = ?
        WHERE id = ? AND user_id = ?
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id, session['user_id']))
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO daily_goals (user_id, date, tasks_done)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET
        tasks_done = tasks_done + 1
    ''', (session['user_id'], today))
    
    add_xp(session['user_id'], 15)
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'xp_earned': 15})

@app.route('/quiz')
@login_required
def quiz():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM quizzes WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (session['user_id'],))
    quizzes = cursor.fetchall()
    
    cursor.execute('''
        SELECT q.title, qa.score, qa.total, qa.completed_at
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        WHERE qa.user_id = ?
        ORDER BY qa.completed_at DESC LIMIT 10
    ''', (session['user_id'],))
    attempts = cursor.fetchall()
    
    conn.close()
    return render_template('quiz.html', user=user, quizzes=quizzes, attempts=attempts)

@app.route('/api/generate-quiz', methods=['POST'])
@login_required
def generate_quiz():
    data = request.get_json()
    subject = data.get('subject', 'Geral')
    topic = data.get('topic', '')
    num_questions = min(int(data.get('num_questions', 5)), 15)
    
    client = get_gemini_client()
    if not client:
        return jsonify({'error': 'Chave da API Google nao configurada. Configure GOOGLE_API_KEY nas configuracoes.'}), 400
    
    try:
        prompt = f"""Voce cria questoes de estudo. Responda em JSON:
        {{"questions": [{{"question": "pergunta", "options": ["a", "b", "c", "d"], "correct": 0, "explanation": "explicacao"}}]}}
        Crie questoes educativas e claras. O campo 'correct' e o indice da resposta correta (0-3).
        
        Crie {num_questions} questoes sobre {subject}. Topico especifico: {topic}"""
        
        response = client.generate_content(prompt)
        result = json.loads(response.text)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO quizzes (user_id, title, subject, questions, total_questions)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], f"Quiz de {subject}", subject, json.dumps(result['questions']), len(result['questions'])))
        
        quiz_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'quiz_id': quiz_id, 'questions': result['questions']})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/submit', methods=['POST'])
@login_required
def submit_quiz():
    data = request.get_json()
    quiz_id = data.get('quiz_id')
    answers = data.get('answers', [])
    time_spent = data.get('time_spent', 0)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    quiz = cursor.fetchone()
    
    if not quiz:
        conn.close()
        return jsonify({'error': 'Quiz nao encontrado'}), 404
    
    questions = json.loads(quiz['questions'])
    score = 0
    results = []
    
    for i, q in enumerate(questions):
        user_answer = answers[i] if i < len(answers) else -1
        correct = q['correct']
        is_correct = user_answer == correct
        if is_correct:
            score += 1
        results.append({
            'question': q['question'],
            'user_answer': user_answer,
            'correct_answer': correct,
            'is_correct': is_correct,
            'explanation': q.get('explanation', '')
        })
        
        if not is_correct:
            cursor.execute('''
                INSERT INTO weak_points (user_id, subject, topic)
                VALUES (?, ?, ?)
            ''', (session['user_id'], quiz['subject'], q['question'][:100]))
    
    cursor.execute('''
        INSERT INTO quiz_attempts (quiz_id, user_id, answers, score, total, time_spent_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (quiz_id, session['user_id'], json.dumps(answers), score, len(questions), time_spent))
    
    xp_earned = score * 10
    add_xp(session['user_id'], xp_earned)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'score': score,
        'total': len(questions),
        'percentage': round(score / len(questions) * 100, 1),
        'results': results,
        'xp_earned': xp_earned
    })

@app.route('/tutor')
@login_required
def tutor():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (session['user_id'],))
    messages = list(reversed(cursor.fetchall()))
    
    conn.close()
    return render_template('tutor.html', user=user, messages=messages)

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados invalidos'}), 400
            
        message = data.get('message', '').strip()
        
        if not message or len(message) < 1:
            return jsonify({'error': 'Mensagem vazia'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'error': 'Usuario nao encontrado'}), 404
        
        user_name = user['name']
        user_level = user['level']
        
        cursor.execute('''
            INSERT INTO chat_messages (user_id, role, content)
            VALUES (?, 'user', ?)
        ''', (session['user_id'], message))
        conn.commit()
        conn.close()
        
        client = get_gemini_client()
        if not client:
            return jsonify({'error': 'Chave da API Google nao configurada. Configure GOOGLE_API_KEY nas Secrets.'}), 400
        
        prompt = f"""Voce e o MentorMind, um tutor de estudos inteligente e amigavel.
O aluno se chama {user_name} e esta no nivel {user_level}.

Suas funcoes:
- Explicar materias de forma clara e didatica
- Ajudar com exercicios passo a passo
- Dar dicas de estudo e memorizacao
- Motivar o aluno
- Adaptar a linguagem ao nivel do aluno
- Corrigir redacoes quando solicitado

Seja amigavel, paciente e encorajador. Use exemplos praticos.
Responda sempre em portugues brasileiro.

Pergunta do aluno: {message}"""
        
        response = client.generate_content(prompt)
        
        if not response or not response.text:
            return jsonify({'error': 'API retornou resposta vazia. Tente novamente.'}), 500
            
        reply = response.text
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_messages (user_id, role, content)
            VALUES (?, 'assistant', ?)
        ''', (session['user_id'], reply))
        conn.commit()
        add_xp(session['user_id'], 2)
        conn.close()
        
        return jsonify({'success': True, 'reply': reply})
        
    except Exception as e:
        error_msg = str(e)
        print(f"Erro completo no chat: {error_msg}")
        
        if "API_KEY" in error_msg.upper() or "GOOGLE_API_KEY" in error_msg.upper():
            return jsonify({'error': 'Chave da API nao configurada. Configure GOOGLE_API_KEY nas Secrets.'}), 400
        
        if "quota" in error_msg.lower():
            return jsonify({'error': 'Limite de uso da API atingido. Tente novamente mais tarde.'}), 429
            
        return jsonify({'error': f'Erro ao processar mensagem: {error_msg}'}), 500

@app.route('/mentor')
@login_required
def mentor():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT * FROM daily_goals WHERE user_id = ? AND date = ?', (session['user_id'], today))
    goals = cursor.fetchone()
    
    if not goals:
        cursor.execute('INSERT INTO daily_goals (user_id, date) VALUES (?, ?)', (session['user_id'], today))
        conn.commit()
        cursor.execute('SELECT * FROM daily_goals WHERE user_id = ? AND date = ?', (session['user_id'], today))
        goals = cursor.fetchone()
    
    cursor.execute('SELECT * FROM mentor_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (session['user_id'],))
    messages = cursor.fetchall()
    
    conn.close()
    return render_template('mentor.html', user=user, goals=goals, messages=messages)

@app.route('/api/mentor/message', methods=['POST'])
@login_required
def get_mentor_message():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT * FROM daily_goals WHERE user_id = ? AND date = ?', (session['user_id'], today))
    goals = cursor.fetchone()
    
    client = get_gemini_client()
    if not client:
        conn.close()
        return jsonify({'error': 'Chave da API Google nao configurada. Configure GOOGLE_API_KEY nas configuracoes.'}), 400
    
    try:
        prompt = f"""Voce e um mentor de estudos DISCIPLINADOR.
        Seu estilo e: firme, direto, motivador mas exigente.
        
        - Se o aluno nao estudou: cobre com firmeza
        - Se estudou pouco: incentive a fazer mais
        - Se esta bem: elogie mas desafie a ir alem
        - Use frases de impacto e motivacao
        
        Seja breve (2-3 frases). Use um tom de coach rigoroso.
        Responda em portugues brasileiro.
        
        Gere uma mensagem de mentor para este aluno:
        Nome: {user['name']}
        Nivel: {user['level']}
        Streak: {user['streak_days']} dias
        Foco hoje: {goals['focus_achieved_minutes'] if goals else 0}/{goals['focus_goal_minutes'] if goals else 60} min
        Flashcards: {goals['flashcards_done'] if goals else 0}/{goals['flashcards_goal'] if goals else 10}
        Tarefas: {goals['tasks_done'] if goals else 0}/{goals['tasks_goal'] if goals else 3}"""
        
        response = client.generate_content(prompt)
        message = response.text
        
        cursor.execute('''
            INSERT INTO mentor_messages (user_id, message, message_type)
            VALUES (?, ?, 'motivation')
        ''', (session['user_id'], message))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/gamification')
@login_required
def gamification():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    level, current_xp, xp_needed = calculate_level(user['xp'])
    
    cursor.execute('''
        SELECT b.*, ub.earned_at 
        FROM badges b 
        LEFT JOIN user_badges ub ON b.id = ub.badge_id AND ub.user_id = ?
        ORDER BY ub.earned_at DESC NULLS LAST
    ''', (session['user_id'],))
    badges = cursor.fetchall()
    
    cursor.execute('''
        SELECT u.username, u.name, u.level, u.xp, u.streak_days
        FROM users u
        ORDER BY u.xp DESC
        LIMIT 20
    ''')
    ranking = cursor.fetchall()
    
    conn.close()
    return render_template('gamification.html', user=user, badges=badges, ranking=ranking,
                          level=level, current_xp=current_xp, xp_needed=xp_needed)

@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) as count FROM focus_sessions WHERE user_id = ?', (session['user_id'],))
    focus_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM flashcard_reviews WHERE user_id = ?', (session['user_id'],))
    review_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM summaries WHERE user_id = ?', (session['user_id'],))
    summary_count = cursor.fetchone()['count']
    
    level, current_xp, xp_needed = calculate_level(user['xp'])
    
    conn.close()
    return render_template('profile.html', user=user, focus_count=focus_count, 
                          review_count=review_count, summary_count=summary_count,
                          level=level, current_xp=current_xp, xp_needed=xp_needed)

@app.route('/api/explain', methods=['POST'])
@login_required
def explain_text():
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'Texto vazio'}), 400
    
    client = get_gemini_client()
    if not client:
        return jsonify({'error': 'Chave da API Google nao configurada. Configure GOOGLE_API_KEY nas configuracoes.'}), 400
    
    try:
        prompt = f"""Voce e um professor. Explique o texto de forma simples e didatica. Use exemplos se necessario. Responda em portugues brasileiro.
        
        Explique este trecho:
        
        {text}"""
        
        response = client.generate_content(prompt)
        explanation = response.text
        return jsonify({'success': True, 'explanation': explanation})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/weak-points')
@login_required
def weak_points():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('''
        SELECT subject, COUNT(*) as error_count
        FROM weak_points
        WHERE user_id = ?
        GROUP BY subject
        ORDER BY error_count DESC
    ''', (session['user_id'],))
    subjects = cursor.fetchall()
    
    cursor.execute('''
        SELECT * FROM weak_points
        WHERE user_id = ?
        ORDER BY error_count DESC, last_error_at DESC
        LIMIT 20
    ''', (session['user_id'],))
    details = cursor.fetchall()
    
    conn.close()
    return render_template('weak_points.html', user=user, subjects=subjects, details=details)

@app.before_request
def before_request():
    # No Vercel, inicializa o banco na primeira requisição
    if os.environ.get('VERCEL'):
        try:
            get_db()  # Isso vai inicializar as tabelas se necessário
        except Exception as e:
            print(f"Erro ao inicializar banco: {e}")
    if request.endpoint and request.endpoint not in ['static', 'index', 'login', 'register']:
        pass

@app.after_request
def after_request(response):
    response.headers['Cache-Control'] = 'public, max-age=31536000' if request.path.startswith('/static/') else 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Inicializa o banco de dados apenas em ambientes não-serverless
# No Vercel, a inicialização acontece na primeira requisição
if not os.environ.get('VERCEL'):
    with app.app_context():
        init_db()

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
