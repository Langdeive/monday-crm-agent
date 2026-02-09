"""
Monday CRM Agent - Telegram Bot Only
Para rodar na VPS sem a parte web
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent_v2 import get_agent

# Inicializa agente
_agent = None

def get_agent_instance():
    global _agent
    if _agent is None:
        _agent = get_agent()
    return _agent

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🤖 *Monday CRM Agent*\n\n"
        "Olá! Sou seu assistente sarcástico para o CRM.\n\n"
        "Posso ajudar com:\n"
        "• 👥 Contatos (listar, buscar, criar)\n"
        "• 💼 Oportunidades (listar, contar, criar)\n"
        "• ✅ Tarefas (listar, criar)\n"
        "• 🏢 Empresas (listar)\n\n"
        "O que você precisa?",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await update.message.reply_text(
        "*Comandos disponíveis:*\n\n"
        "📋 *Contatos:*\n"
        "• `listar pessoas`\n"
        "• `tem alguma maria?`\n"
        "• `quem tem instagram?`\n"
        "• `criar pessoa João, email: joao@teste.com`\n\n"
        "💼 *Oportunidades:*\n"
        "• `quantas oportunidades?`\n"
        "• `oportunidades na etapa conversa estabelecida`\n"
        "• `criar oportunidade Cliente X, etapa: prospeccao`\n\n"
        "✅ *Tarefas:*\n"
        "• `listar tarefas`\n"
        "• `criar tarefa Ligação amanhã às 10h`\n\n"
        "🏢 *Empresas:*\n"
        "• `listar empresas`\n\n"
        "⏰ *Utilidades:*\n"
        "• `que horas são?`",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens normais"""
    if not update.message or not update.message.text:
        return
    
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    # Mostra "digitando..."
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action='typing'
    )
    
    try:
        agent = get_agent_instance()
        response = await agent.handle(user_id, 'telegram', message)
        await update.message.reply_text(response)
    except Exception as e:
        print(f"[Erro] {e}")
        await update.message.reply_text(
            "Buguei aqui... Tenta de novo? Se persistir, chama o administrador."
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tratamento de erros"""
    print(f'[Erro] Update {update} causou erro: {context.error}')
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Ops, deu ruim aqui nos bastidores. Já registrei o erro!"
        )

def main():
    """Entry point"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("[ERRO] TELEGRAM_BOT_TOKEN não configurado!")
        return
    
    print("[Monday] Iniciando bot do Telegram...")
    
    # Cria aplicação
    application = Application.builder().token(token).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    # Error handler
    application.add_error_handler(error_handler)
    
    print("[Monday] Bot iniciado! Aguardando mensagens...")
    
    # Roda em polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
