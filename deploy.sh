#!/bin/bash
# Script de deploy manual para VPS
# Uso: ./deploy.sh

set -e

echo "🚀 Deploy do Monday CRM Agent"
echo "=============================="

# Verifica se está no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Erro: docker-compose.yml não encontrado"
    echo "Execute este script do diretório do projeto"
    exit 1
fi

# Verifica variáveis de ambiente
if [ -f ".env" ]; then
    echo "📋 Carregando variáveis do .env..."
    export $(cat .env | grep -v '#' | xargs)
fi

# Verifica se as variáveis obrigatórias estão configuradas
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Erro: TELEGRAM_BOT_TOKEN não configurado"
    echo "Adicione ao arquivo .env: TELEGRAM_BOT_TOKEN=seu_token"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ Erro: GEMINI_API_KEY não configurado"
    exit 1
fi

if [ -z "$TWENTY_API_KEY" ]; then
    echo "❌ Erro: TWENTY_API_KEY não configurado"
    exit 1
fi

echo "✅ Variáveis de ambiente OK"
echo ""

# Build da imagen
echo "🔨 Build da imagem Docker..."
docker compose build --no-cache

# Para o container antigo
echo "🛑 Parando container antigo..."
docker compose down || true

# Inicia o novo
echo "▶️ Iniciando container..."
docker compose up -d

# Aguarda inicialização
echo "⏳ Aguardando inicialização..."
sleep 5

# Verifica status
echo ""
echo "📊 Status do container:"
docker ps --filter "name=monday-crm-bot" --format "table {{.Names}}\t{{.Status}}"

# Verifica logs
echo ""
echo "📜 Últimas logs:"
docker logs --tail 10 monday-crm-bot 2>/dev/null || echo "Aguardando logs..."

echo ""
echo "✅ Deploy concluído!"
echo ""
echo "Comandos úteis:"
echo "  Ver logs:    docker logs -f monday-crm-bot"
echo "  Parar:       docker compose down"
echo "  Reiniciar:   docker compose restart"
