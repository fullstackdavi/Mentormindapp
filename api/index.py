import sys
import os

# Define que está rodando no Vercel (ambiente serverless)
os.environ['VERCEL'] = '1'

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importa a aplicação
from app import app

# Desabilita o modo debug em produção
app.config['DEBUG'] = False
app.config['TESTING'] = False

# Configurações de segurança para produção
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Exporta o app para o Vercel
# O Vercel usa automaticamente a variável 'app'
