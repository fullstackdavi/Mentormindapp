# MentorMind - Aplicativo de Estudos com IA

## Visao Geral
MentorMind e um aplicativo de estudos completo que combina IA, gamificacao e tecnicas de estudo ativo para ajudar estudantes a aprender de forma mais eficiente.

## Stack Tecnologica
- **Backend**: Python Flask
- **Banco de Dados**: SQLite3 (puro, sem ORM)
- **Frontend**: HTML5, CSS3, JavaScript
- **IA**: OpenAI GPT-4o para resumos, tutor, e geracao de conteudo
- **Estilo**: Design moderno e responsivo com tema escuro

## Estrutura do Projeto
```
/
├── app.py              # Aplicacao Flask principal
├── database.py         # Gerenciamento do banco SQLite3
├── static/
│   ├── css/style.css   # Estilos CSS
│   └── js/app.js       # JavaScript do frontend
├── templates/          # Templates HTML Jinja2
│   ├── base.html       # Template base
│   ├── dashboard.html  # Dashboard principal
│   ├── focus.html      # Modo Foco Pomodoro
│   ├── library.html    # Biblioteca de PDFs
│   ├── summary.html    # Gerador de Resumos
│   ├── flashcards.html # Sistema de Flashcards
│   ├── study_plan.html # Plano de Estudos
│   ├── tutor.html      # Tutor IA 24h
│   ├── mentor.html     # Modo Mentor
│   ├── quiz.html       # Simulados
│   ├── gamification.html # Gamificacao
│   └── ...
├── uploads/            # PDFs enviados pelos usuarios
└── vercel.json         # Configuracao para deploy Vercel
```

## Funcionalidades Principais
1. **Dashboard Inteligente**: Resumo do dia, metas, progresso
2. **Modo Foco**: Pomodoro com sons de concentracao
3. **Gerador de Resumos**: IA gera resumos, topicos e flashcards
4. **Plano de Estudos**: Cronograma baseado em objetivos
5. **Biblioteca de PDFs**: Upload e organizacao de materiais
6. **Flashcards SM-2**: Revisao espacada para memorizacao
7. **Simulados Inteligentes**: Questoes adaptativas com IA
8. **Tutor IA 24h**: Chat para tirar duvidas
9. **Modo Mentor**: Motivacao e disciplina
10. **Gamificacao**: XP, niveis, badges, ranking

## Configuracoes
- Servidor roda na porta 5000
- Banco de dados SQLite em `mentormind.db`
- Uploads salvos em `uploads/`
- Requer OPENAI_API_KEY para funcionalidades de IA

## Comandos
- Iniciar: `python app.py`
- Producao: `gunicorn --bind 0.0.0.0:5000 app:app`

## Video Background Otimizado
- **Desktop**: Video original de alta qualidade (46MB)
- **Mobile**: Video comprimido (242KB) - reducao de 99.5%
- **Poster**: Imagem de preview enquanto carrega (36KB)
- **Deteccao automatica**: Dispositivo, conexao lenta, e preferencia de movimento reduzido
- **Fallback**: Gradiente estatico se video nao carregar

## Notas de Deploy
- Configurado para Vercel com `vercel.json`
- SQLite funciona mas dados sao efemeros na Vercel
- Para persistencia real, usar Replit Deployments ou PostgreSQL
