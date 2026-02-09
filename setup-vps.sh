#!/bin/bash
# Script de setup inicial para VPS
# Uso: curl -fsSL https://raw.githubusercontent.com/seu-usuario/monday-crm-agent/main/setup-vps.sh | bash

set -e

PROJECT_DIR="~/monday-crm-agent"

echo "🚀 Setup do Monday CRM Agent na VPS"
echo "===================================="
echo ""

# Verifica se Docker está instalado
if ! command -v docker &> /dev/null; then
    echo "📦 Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "✅ Docker instalado!"
    echo "⚠️  Faça logout e login novamente para usar Docker sem sudo"
    exit 0
fi

# Verifica se Docker Compose está instalado
if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "📦 Instalando Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    echo "✅ Docker Compose instalado!"
fi

# Cria diretório do projeto
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Download dos arquivos necessários
echo "📥 Baixando arquivos de configuração..."

# Se estiver no Git, clone. Senão, cria estrutura mínima
if command -v git &> /dev/null; then
    if [ ! -d ".git" ]; then
        git clone https://github.com/seu-usuario/monday-crm-agent.git . 2>/dev/null || true
    fi
fi

# Se não conseguiu clonar, cria estrutura mínima
if [ ! -f "docker-compose.yml" ]; then
    echo "Criando estrutura mínima..."
    
    # Cria docker-compose.yml
    cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  monday-bot:
    image: ghcr.io/seu-usuario/monday-crm-agent:latest
    container_name: monday-crm-bot
    restart: unless-stopped
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash-lite}
      - TWENTY_API_URL=${TWENTY_API_URL}
      - TWENTY_API_KEY=${TWENTY_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DATABASE_URL=sqlite:///app/data/monday.db
    volumes:
      - ./data:/app/data
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

    # Cria .env.example
    cat > .env.example << 'EOF'
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash-lite
TWENTY_API_URL=https://crm.solveflow.cloud/rest/
TWENTY_API_KEY=
TELEGRAM_BOT_TOKEN=
EOF

fi

# Cria diretório de dados
mkdir -p data

echo ""
echo "✅ Setup concluído!"
echo ""
echo "Próximos passos:"
echo "1. Configure as variáveis de ambiente:"
echo "   cd $PROJECT_DIR"
echo "   cp .env.example .env"
echo "   nano .env"
echo ""
echo "2. Inicie o bot:"
echo "   docker compose up -d"
echo ""
echo "3. Verifique os logs:"
echo "   docker logs -f monday-crm-bot"
echo ""
