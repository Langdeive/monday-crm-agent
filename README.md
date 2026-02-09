# 🤖 Monday CRM Agent

Assistente virtual sarcástico e direto para gerenciar seu CRM Twenty via Telegram.

## ✨ Funcionalidades

- **👥 Contatos**: Listar, buscar, criar com empresa
- **💼 Oportunidades**: Listar, contar por etapa, criar
- **✅ Tarefas**: Listar, criar com data/hora
- **🏢 Empresas**: Listar
- **📱 Social**: Buscar por Instagram, LinkedIn
- **⏰ Data/Hora**: Consultar data/hora atual de São Paulo

## 🚀 Deploy na VPS

### Opção 1: One-liner (mais fácil)

```bash
curl -fsSL https://raw.githubusercontent.com/seu-usuario/monday-crm-agent/main/setup-vps.sh | bash
```

Depois configure o `.env` e rode:
```bash
cd ~/monday-crm-agent
cp .env.example .env
nano .env  # Adicione suas credenciais
docker compose up -d
```

### Opção 2: Coolify (recomendado)

1. Adicione seu repositório no Coolify
2. Escolha "Docker Compose"
3. Configure as variáveis de ambiente
4. Deploy!

### Opção 3: Manual

```bash
# Clone
git clone https://github.com/seu-usuario/monday-crm-agent.git
cd monday-crm-agent

# Configure
cp .env.deploy.example .env
nano .env  # Preencha suas credenciais

# Deploy
./deploy.sh
```

## 🔧 Desenvolvimento Local

```bash
# Instale dependências
pip install -r requirements.txt

# Configure .env
cp .env.example .env
# Edite .env com suas credenciais

# Rode o bot
python telegram_bot.py
```

## 📝 Variáveis de Ambiente

```env
# Obrigatórios
GEMINI_API_KEY=sua_chave_gemini
TWENTY_API_URL=https://crm.solveflow.cloud/rest/
TWENTY_API_KEY=sua_chave_twenty
TELEGRAM_BOT_TOKEN=seu_token_bot

# Opcional
GEMINI_MODEL=gemini-2.5-flash-lite
```

## 🔄 Deploy Automático

Para ativar deploy automático quando criar uma release:

1. Configure os Secrets no GitHub:
   - `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
   - `GEMINI_API_KEY`, `TWENTY_API_KEY`, `TELEGRAM_BOT_TOKEN`

2. Crie uma release:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

O deploy será feito automaticamente!

## 📚 Documentação

- [Guia de Deploy Completo](DEPLOY.md)
- [Exemplos de uso](docs/EXEMPLOS.md)

## 🛠️ Comandos Úteis

```bash
# Ver logs
docker logs -f monday-crm-bot

# Reiniciar
docker compose restart

# Parar
docker compose down

# Backup do banco
docker cp monday-crm-bot:/app/data/monday.db ./backup.db
```

---

**Personalidade**: Monday é sarcástico, direto e humano. Não espere respostas robóticas! 😏
