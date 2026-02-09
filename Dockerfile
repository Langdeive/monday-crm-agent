# Monday CRM Agent - Docker Image
# Otimizado para produção (Telegram only)

FROM python:3.11-slim as builder

# Instala dependências de build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copia e instala requirements
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ----------------------------------------
FROM python:3.11-slim as runtime

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=/root/.local/bin:$PATH

# Copia dependências instaladas
COPY --from=builder /root/.local /root/.local

# Diretório da aplicação
WORKDIR /app

# Copia código fonte
COPY telegram_bot.py .
COPY agent_v2.py .

# Cria diretório para dados persistentes
RUN mkdir -p /app/data

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import telegram; print('OK')" || exit 1

# Comando para rodar o bot
CMD ["python", "telegram_bot.py"]
