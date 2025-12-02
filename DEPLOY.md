
# Como fazer Deploy no Replit

Este projeto está otimizado para deploy no **Replit Deployments**.

## Passo 1: Configure as Secrets

1. Abra a ferramenta **Secrets** no painel lateral do Replit
2. Adicione as seguintes variáveis:

```
GOOGLE_API_KEY=sua_chave_aqui
SESSION_SECRET=seu_secret_aleatorio_aqui
```

## Passo 2: Escolha o tipo de Deployment

Recomendamos **Autoscale Deployment** para este projeto porque:
- Escala automaticamente com o tráfego
- Paga apenas pelo uso
- 99.95% de uptime
- Ideal para aplicações web Flask

## Passo 3: Configure o Deployment

1. Clique no botão **Deploy** no topo da tela
2. Selecione **Autoscale Deployment**
3. Configure:
   - **Run command**: `gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app`
   - **Build command**: (deixe vazio)
4. Clique em **Deploy**

## Passo 4: Domínio

Sua aplicação estará disponível em:
- `https://seu-repl-name.replit.app`

Você também pode configurar um domínio customizado nas configurações do deployment.

## Otimizações Aplicadas

✅ Gunicorn como servidor WSGI de produção
✅ Cache otimizado para arquivos estáticos (1 ano)
✅ Vídeo de fundo com lazy loading
✅ Compressão de assets
✅ Configurações de segurança para sessões
✅ 2 workers Gunicorn para melhor performance

## Troubleshooting

**Erro de API Key**: Verifique se GOOGLE_API_KEY está configurada nos Secrets

**Erro de porta**: O deployment usa automaticamente a porta 5000

**Vídeo não carrega**: Verifique se o arquivo `static/background.mp4` existe

## Performance

- Primeira carga: ~1-2s
- Navegação entre páginas: instantânea
- Vídeo background: carrega em paralelo sem bloquear UI

---

# Deploy no Vercel

Este projeto também pode ser deployado no Vercel como uma função serverless.

## Passo 1: Configure as Variáveis de Ambiente no Vercel

Acesse as configurações do seu projeto no Vercel e adicione as seguintes variáveis:

```
GOOGLE_API_KEY=sua_chave_api_do_google
SESSION_SECRET=um_secret_aleatorio_seguro
SQLITECLOUD_URL=sua_url_de_conexao_sqlitecloud
```

**Importante**: A `SQLITECLOUD_URL` já está configurada no código, mas você pode alterá-la nas variáveis de ambiente.

## Passo 2: Estrutura do Projeto

O projeto já está configurado corretamente:
- `api/index.py` - Ponto de entrada para o Vercel
- `vercel.json` - Configuração do Vercel
- `requirements.txt` - Dependências Python

## Passo 3: Deploy

1. Conecte seu repositório ao Vercel
2. Configure as variáveis de ambiente
3. O Vercel detectará automaticamente a configuração

## Otimizações para Serverless

O projeto inclui otimizações específicas para o ambiente serverless do Vercel:

✅ Thread de ping desabilitada em ambiente serverless
✅ Configurações de segurança de sessão para HTTPS
✅ Debug mode desabilitado em produção
✅ Runtime Python 3.11

## Troubleshooting Vercel

**Erro FUNCTION_INVOCATION_FAILED**:
1. Verifique se todas as variáveis de ambiente estão configuradas
2. Cheque os logs da função no dashboard do Vercel
3. Certifique-se de que as dependências em `requirements.txt` estão corretas

**Erro de timeout**:
- Algumas operações de IA podem demorar mais que o limite de 10s do plano gratuito
- Considere o plano Pro para timeouts maiores

**Erro de módulo não encontrado**:
- Verifique se o pacote está no `requirements.txt`
- Alguns nomes de pacotes diferem (ex: `python-dotenv` vs `dotenv`)
