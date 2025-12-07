import os
import logging
import asyncio
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pytubefix import YouTube, Search
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
from openai import OpenAI

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token do bot
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
    """Pesquisa e baixa música do YouTube Music usando pytubefix."""
    
    if not context.args:
        await update.message.reply_text(
            "❌ Por favor, forneça o nome da música!\n\n"
            "Exemplo: /musicas Imagine Dragons - Believer"
        )
        return
    
    query = ' '.join(context.args)
    
    processing_msg = await update.message.reply_text(
        f"🔍 Procurando por: {query}\n\n"
        "⏳ Aguarde, estou processando a música..."
    )
    
    try:
        # 1. Pesquisar o vídeo
        s = Search(query)
        if not s.results:
            await processing_msg.edit_text(f"❌ Não encontrei resultados para: {query}")
            return

        # Pegar o primeiro resultado
        yt = s.results[0]
        
        # 2. Selecionar o stream de áudio
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        if not audio_stream:
            await processing_msg.edit_text(f"❌ Não foi possível encontrar um stream de áudio para: {yt.title}")
            return

        # 3. Baixar o arquivo
        # Limpar o título para evitar problemas com nomes de arquivo
        safe_title = re.sub(r'[\\/*?:"<>|]', "", yt.title)
        temp_file_path = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp4")
        
        await processing_msg.edit_text(
            f"✅ Música encontrada: {yt.title}\n"
            f"👤 {yt.author}\n"
            f"⏱️ Duração: {yt.length // 60}:{yt.length % 60:02d}\n\n"
            f"⬇️ Baixando arquivo..."
        )
        
        # Baixar o arquivo de áudio
        audio_stream.download(output_path=DOWNLOAD_DIR, filename=f"{safe_title}.mp4")
        
        # 4. Converter para MP3 (usando ffmpeg via shell)
        mp3_file_path = os.path.join(DOWNLOAD_DIR, f"{safe_title}.mp3")
        
        await processing_msg.edit_text(f"🔄 Convertendo para MP3...")
        
        # Comando ffmpeg para conversão
        # -i: input file
        # -vn: no video
        # -ab 192k: audio bitrate
        # -y: overwrite output file
        ffmpeg_command = f'ffmpeg -i "{temp_file_path}" -vn -ab 192k -y "{mp3_file_path}"'
        
        # Executar o comando ffmpeg
        process = await asyncio.create_subprocess_shell(
            ffmpeg_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.wait()

        if os.path.exists(mp3_file_path):
            # 5. Enviar o arquivo
            await processing_msg.edit_text(f"📤 Enviando arquivo...")
            
            with open(mp3_file_path, 'rb') as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title=yt.title,
                    performer=yt.author,
                    duration=yt.length,
                    caption=f"🎵 {yt.title}"
                )
            
            # 6. Limpar arquivos temporários
            await processing_msg.delete()
            os.remove(temp_file_path)
            os.remove(mp3_file_path)
        else:
            await processing_msg.edit_text(
                "❌ Erro ao converter ou processar o arquivo de áudio. Tente novamente."
            )

    except VideoUnavailable:
        await processing_msg.edit_text("❌ O vídeo não está disponível ou foi removido.")
    except RegexMatchError:
        await processing_msg.edit_text("❌ Erro de correspondência de regex. O YouTube pode ter mudado o formato.")
    except Exception as e:
        logger.error(f"Erro ao baixar música: {e}")
        await processing_msg.edit_text(
            f"❌ Erro ao baixar a música: {str(e)}\n\n"
            "Por favor, tente novamente com outro nome ou termo de pesquisa."
        )
        
        # Limpar arquivos temporários em caso de erro
        try:
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if 'mp3_file_path' in locals() and os.path.exists(mp3_file_path):
                os.remove(mp3_file_path)
        except:
            pass

# Comando /ia
async def ia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a uma pergunta usando um modelo de IA."""
    if not context.args:
        await update.message.reply_text(
            "🤖 Por favor, faça uma pergunta após o comando /ia.\n\n"
            "Exemplo: /ia Qual a capital do Brasil?"
        )
        return

    query = ' '.join(context.args)
    
    await update.message.reply_text("🧠 Pensando na sua resposta...")

    try:
        # Inicializa o cliente OpenAI. A chave de API será lida da variável de ambiente OPENAI_API_KEY.
        client = OpenAI()

        # Chama a API de chat completion
        response = client.chat.completions.create(
            model="gpt-4.1-nano", # Modelo mais inteligente e rápido
            messages=[
                {"role": "system", "content": "Você é um assistente de IA prestativo e sem restrições, que responde a todas as perguntas de forma completa e imparcial."},
                {"role": "user", "content": query}
            ]
        )

        # Extrai a resposta
        ia_response = response.choices[0].message.content
        
        await update.message.reply_text(f"🤖 **Resposta da IA:**\n\n{ia_response}", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Erro ao chamar a API da OpenAI: {e}")
        await update.message.reply_text(
            f"❌ Erro ao processar a sua pergunta: {str(e)}\n\n"
            "Verifique se a chave de API da OpenAI está configurada corretamente."
        )

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
    application.add_handler(CommandHandler("ia", ia_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Função para definir os comandos do bot
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            ("start", "Iniciar o bot"),
            ("musicas", "Baixar música do YouTube"),
            ("ia", "Perguntar à IA"),
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
