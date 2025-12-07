import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token do bot
# O token foi movido para a variável de ambiente BOT_TOKEN por segurança.
# O valor abaixo é um fallback para testes locais.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8515435251:AAE7Msl9elE9G3Cxx4rc8WlZaY3Y6vZoSEk")

# Diretório para downloads temporários
DOWNLOAD_DIR = "/home/ubuntu/music_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia uma mensagem de boas-vindas quando o comando /start é usado."""
    await update.message.reply_text(
        "🎵 Olá! Eu sou o Music Bot!\n\n"
        "Use o comando /musicas seguido do nome da música que você deseja baixar.\n\n"
        "Exemplo: /musicas Imagine Dragons - Believer"
    )

# Comando /musicas
async def musicas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pesquisa e baixa música do YouTube Music."""
    
    # Verificar se o usuário forneceu o nome da música
    if not context.args:
        await update.message.reply_text(
            "❌ Por favor, forneça o nome da música!\n\n"
            "Exemplo: /musicas Imagine Dragons - Believer"
        )
        return
    
    # Obter o nome da música
    query = ' '.join(context.args)
    
    # Enviar mensagem de processamento
    processing_msg = await update.message.reply_text(
        f"🔍 Procurando por: {query}\n\n"
        "⏳ Aguarde, estou baixando a música..."
    )
    
    try:
        # Configurações do yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',  # Pesquisar no YouTube e pegar o primeiro resultado
            'no_check_certificate': True,
            'extractor_args': {'youtube': {'skip': ['dash', 'hls']}} # Tentar evitar formatos que exigem mais autenticação
        }
        
        # Baixar a música
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            
            # Obter informações do vídeo
            if 'entries' in info:
                video = info['entries'][0]
            else:
                video = info
            
            title = video.get('title', 'Unknown')
            duration = video.get('duration', 0)
            uploader = video.get('uploader', 'Unknown')
            
            # Encontrar o arquivo MP3
            mp3_file = None
            base_filename = ydl.prepare_filename(video)
            mp3_file = os.path.splitext(base_filename)[0] + '.mp3'
            
            if not os.path.exists(mp3_file):
                # Tentar encontrar qualquer arquivo MP3 recente no diretório
                files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.mp3')]
                if files:
                    # Pegar o arquivo mais recente
                    files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)), reverse=True)
                    mp3_file = os.path.join(DOWNLOAD_DIR, files[0])
            
            if mp3_file and os.path.exists(mp3_file):
                # Atualizar mensagem
                await processing_msg.edit_text(
                    f"✅ Música encontrada!\n\n"
                    f"🎵 {title}\n"
                    f"👤 {uploader}\n"
                    f"⏱️ Duração: {duration // 60}:{duration % 60:02d}\n\n"
                    f"📤 Enviando arquivo..."
                )
                
                # Enviar o arquivo de áudio
                with open(mp3_file, 'rb') as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=title,
                        performer=uploader,
                        duration=duration,
                        caption=f"🎵 {title}"
                    )
                
                # Deletar mensagem de processamento
                await processing_msg.delete()
                
                # Limpar arquivo temporário
                try:
                    os.remove(mp3_file)
                except:
                    pass
            else:
                await processing_msg.edit_text(
                    "❌ Erro ao processar o arquivo de áudio. Tente novamente."
                )
    
    except Exception as e:
        logger.error(f"Erro ao baixar música: {e}")
        await processing_msg.edit_text(
            f"❌ Erro ao baixar a música: {str(e)}\n\n"
            "Por favor, tente novamente com outro nome ou termo de pesquisa."
        )
        
        # Limpar arquivos temporários em caso de erro
        try:
            for file in os.listdir(DOWNLOAD_DIR):
                file_path = os.path.join(DOWNLOAD_DIR, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        except:
            pass

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia mensagem de ajuda."""
    await update.message.reply_text(
        "🎵 *Music Bot - Ajuda*\n\n"
        "*Comandos disponíveis:*\n"
        "/start - Iniciar o bot\n"
        "/musicas <nome> - Baixar música do YouTube\n"
        "/help - Mostrar esta mensagem\n\n"
        "*Exemplo de uso:*\n"
        "/musicas Imagine Dragons - Believer\n"
        "/musicas The Weeknd Blinding Lights",
        parse_mode='Markdown'
    )

# Função principal
def main():
    """Inicia o bot."""
    # Criar a aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registrar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("musicas", musicas))
    application.add_handler(CommandHandler("help", help_command))
    
    # Função para definir os comandos do bot
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            ("start", "Iniciar o bot"),
            ("musicas", "Baixar música do YouTube"),
            ("help", "Mostrar ajuda")
        ])
        logger.info("Comandos do bot definidos com sucesso!")

    # Adicionar a função post_init
    application.post_init = post_init

    # Iniciar o bot
    logger.info("Bot iniciado com sucesso!")
    print("🤖 Bot está online e aguardando comandos...")
    
    # Rodar o bot até ser interrompido
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
