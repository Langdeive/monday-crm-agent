# 🚀 Guia de Deploy - Monday CRM Agent

## Opções de Deploy

### Opção 1: Coolify (Recomendado)

O [Coolify](https://coolify.io/) é uma alternativa open-source ao Heroku/Vercel que roda na sua VPS.

#### Passo a passo:

1. **No Coolify, crie um novo serviço:**
   - Vá em "Projects" → "Add New Resource"
   - Escolha "Docker Compose"

2. **Configure o repositório:**
   - Repository: `https://github.com/seu-usuario/monday-crm-agent` (ou upload dos arquivos)
   - Branch: `main`

3. **Configure as variáveis de ambiente:**
   ```
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash-lite
   TWENTY_API_URL=https://crm.solveflow.cloud/rest/
   TWENTY_API_KEY=eyJhbG...
   TELEGRAM_BOT_TOKEN=8150639101:AAET...
   ```

4. **Deploy:**
   - Coolify vai automaticamente buildar e rodar
   - O bot já está online!

---

### Opção 2: Deploy Manual via Docker

```bash
# 1. Clone o repositório na VPS
git clone https://github.com/seu-usuario/monday-crm-agent.git
cd monday-crm-agent

# 2. Configure as variáveis
cp .env.example .env
nano .env  # Edite com suas credenciais

# 3. Deploy
chmod +x deploy.sh
./deploy.sh
```

---

### Opção 3: Deploy Automático (GitHub + VPS)

#### Configuração no GitHub:

1. **Adicione os Secrets no repositório:**
   - Vá em Settings → Secrets and variables → Actions
   - Adicione:
     - `VPS_HOST` (IP da sua VPS)
     - `VPS_USER` (usuário SSH)
     - `VPS_SSH_KEY` (chave privada SSH)
     - `VPS_PORT` (porta SSH, geralmente 22)
     - `GEMINI_API_KEY`
     - `TWENTY_API_URL`
     - `TWENTY_API_KEY`
     - `TELEGRAM_BOT_TOKEN`

2. **Crie uma Release:**
   - No GitHub, vá em "Releases" → "Create a new release"
   - Tag: `v1.0.0`
   - O deploy automático vai iniciar!

---

## 📁 Estrutura de arquivos para deploy

```
twenty-crm-agent/
├── .github/workflows/deploy.yml  # CI/CD automático
├── docker-compose.yml            # Configuração Docker
├── Dockerfile                    # Imagem Docker
├── telegram_bot.py               # Bot standalone (sem web)
├── deploy.sh                     # Script deploy manual
├── requirements.txt
├── .env.example
└── DEPLOY.md                     # Este arquivo
```

---

## 🔧 Comandos úteis

### Ver logs do bot:
```bash
docker logs -f monday-crm-bot
```

### Reiniciar bot:
```bash
docker compose restart
```

### Parar bot:
```bash
docker compose down
```

### Atualizar manualmente:
```bash
# Pull da última imagem
docker pull ghcr.io/seu-usuario/monday-crm-agent:latest

# Restart
docker compose up -d
```

---

## 💾 Persistência de dados

O banco SQLite é persistido em um volume Docker:
- Local: `./data/monday.db`
- Container: `/app/data/monday.db`

**Backup:**
```bash
docker cp monday-crm-bot:/app/data/monday.db ./backup-$(date +%Y%m%d).db
```

---

## 🔍 Troubleshooting

### Bot não responde:
```bash
# Verifique se está rodando
docker ps | grep monday

# Veja os logs
docker logs monday-crm-bot --tail 50
```

### Erro de permissão:
```bash
# Ajuste permissões da pasta data
chmod 777 ./data
```

### Token inválido:
- Verifique se o `TELEGRAM_BOT_TOKEN` está correto no arquivo `.env`
- Certifique-se de que o bot não está rodando em outro lugar (conflito de polling)

---

## 🔄 Workflow de desenvolvimento

1. **Desenvolva localmente:**
   ```bash
   python telegram_bot.py
   ```

2. **Teste:**
   - Use o bot no Telegram
   - Verifique logs

3. **Commit e push:**
   ```bash
   git add .
   git commit -m "feat: nova funcionalidade"
   git push origin main
   ```

4. **Crie uma release** (dispara deploy automático):
   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```

5. **Ou deploy manual:**
   ```bash
   ./deploy.sh
   ```

---

## 📞 Suporte

Problemas com o deploy? Verifique:
1. Variáveis de ambiente configuradas
2. Portas liberadas no firewall
3. Logs do container (`docker logs`)
