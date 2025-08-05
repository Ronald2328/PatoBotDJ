import discord
from discord.ext import commands
import wavelink
import asyncio
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('musicbot.log')
    ]
)

logger = logging.getLogger('MusicBot')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.autoplay_enabled = {}

    async def setup_hook(self):
        await self.tree.sync()
        logger.info(f'Sincronizados {len(self.tree.get_commands())} comandos slash!')

bot = MusicBot()

@bot.event
async def on_ready():
    logger.info(f'{bot.user} ha iniciado sesión!')
    bot.loop.create_task(connect_nodes())

async def connect_nodes():
    await bot.wait_until_ready()
    try:
        await wavelink.NodePool.create_node(
            bot=bot,
            host=os.getenv('LAVALINK_HOST', 'localhost'),
            port=int(os.getenv('LAVALINK_PORT', 2333)),
            password=os.getenv('LAVALINK_PASSWORD', 'youshallnotpass'),
            https=False
        )
        logger.info('Conectado a Lavalink!')
    except Exception as e:
        logger.error(f'Error conectando a Lavalink: {e}')

@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    logger.info(f'Nodo {node.identifier} está listo!')

@bot.tree.command(name='play', description='Reproduce una canción')
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    
    try:
        if not interaction.user.voice:
            await interaction.followup.send('¡Debes estar en un canal de voz!', ephemeral=True)
            return
        
        if not interaction.guild.voice_client:
            vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = interaction.guild.voice_client
            
        if vc.channel != interaction.user.voice.channel:
            await interaction.followup.send('Debes estar en mi mismo canal de voz!', ephemeral=True)
            return
        
        tracks = await wavelink.YouTubeTrack.search(query=busqueda, return_first=False)
        
        if not tracks:
            tracks = await wavelink.SoundCloudTrack.search(query=busqueda, return_first=False)
        
        if not tracks:
            await interaction.followup.send(f'❌ No encontré resultados para: **{busqueda}**', ephemeral=True)
            return
        
        track = tracks[0]
        
        if vc.is_playing():
            vc.queue.put(track)
            position = vc.queue.count
            embed = discord.Embed(
                title="➕ Agregado a la cola",
                description=f"**{track.title}**\n*Posición en cola: {position}*",
                color=0x2F3136
            )
            await interaction.followup.send(embed=embed)
        else:
            await vc.play(track)
            embed = discord.Embed(
                title="🎵 Reproduciendo ahora",
                description=f"**{track.title}**",
                color=0x2F3136
            )
            await interaction.followup.send(embed=embed)
            
    except Exception as e:
        await interaction.followup.send(f'❌ Error: {str(e)}', ephemeral=True)
        logger.error(f'Error en play: {e}', exc_info=True)

@bot.tree.command(name='pause', description='Pausa la música')
async def pause(interaction: discord.Interaction):
    vc: wavelink.Player = interaction.guild.voice_client
    
    if not vc:
        await interaction.response.send_message('No estoy en un canal de voz!', ephemeral=True)
        return
    
    if vc.is_paused():
        await interaction.response.send_message('La música ya está pausada!', ephemeral=True)
        return
    
    await vc.pause()
    await interaction.response.send_message('⏸️ Música pausada')

@bot.tree.command(name='resume', description='Reanuda la música')
async def resume(interaction: discord.Interaction):
    vc: wavelink.Player = interaction.guild.voice_client
    
    if not vc:
        await interaction.response.send_message('No estoy en un canal de voz!', ephemeral=True)
        return
    
    if not vc.is_paused():
        await interaction.response.send_message('La música no está pausada!', ephemeral=True)
        return
    
    await vc.resume()
    await interaction.response.send_message('▶️ Música reanudada')

@bot.tree.command(name='skip', description='Salta a la siguiente canción')
async def skip(interaction: discord.Interaction):
    vc: wavelink.Player = interaction.guild.voice_client
    
    if not vc:
        await interaction.response.send_message('No estoy en un canal de voz!', ephemeral=True)
        return
    
    if not vc.is_playing():
        await interaction.response.send_message('No hay música reproduciéndose!', ephemeral=True)
        return
    
    await vc.stop()
    
    if vc.queue:
        await interaction.response.send_message('⏭️ Saltando a la siguiente canción...')
    else:
        await interaction.response.send_message('⏭️ Canción saltada. No hay más en la cola.')

@bot.tree.command(name='stop', description='Detiene la música y me desconecta')
async def stop(interaction: discord.Interaction):
    vc: wavelink.Player = interaction.guild.voice_client
    
    if not vc:
        await interaction.response.send_message('No estoy en un canal de voz!', ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    if guild_id in bot.autoplay_enabled:
        del bot.autoplay_enabled[guild_id]
    
    await vc.disconnect()
    await interaction.response.send_message('⏹️ Música detenida y desconectado')

@bot.tree.command(name='queue', description='Muestra la cola de reproducción')
async def queue(interaction: discord.Interaction):
    vc: wavelink.Player = interaction.guild.voice_client
    
    if not vc:
        await interaction.response.send_message('No estoy en un canal de voz!', ephemeral=True)
        return
    
    if not vc.track and vc.queue.is_empty:
        await interaction.response.send_message('No hay canciones en la cola!', ephemeral=True)
        return
    
    embed = discord.Embed(title="📋 Cola de reproducción", color=0x2F3136)
    
    if vc.track:
        embed.add_field(
            name="🎵 Reproduciendo ahora",
            value=f"**{vc.track.title}**",
            inline=False
        )
    
    if not vc.queue.is_empty:
        queue_list = []
        for i, track in enumerate(list(vc.queue)[:10], 1):
            queue_list.append(f"`{i}.` **{track.title}**")
        
        if vc.queue.count > 10:
            queue_list.append(f"*...y {vc.queue.count - 10} más*")
        
        embed.add_field(
            name="📋 En cola",
            value="\n".join(queue_list),
            inline=False
        )
    
    embed.set_footer(text=f"Total en cola: {vc.queue.count} canciones")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='autoplay', description='Activa/desactiva el modo radio')
async def autoplay(interaction: discord.Interaction):
    vc: wavelink.Player = interaction.guild.voice_client
    
    if not vc:
        await interaction.response.send_message('No estoy en un canal de voz!', ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    
    if guild_id in bot.autoplay_enabled:
        del bot.autoplay_enabled[guild_id]
        embed = discord.Embed(
            title="📻 Modo Radio Desactivado",
            description="Ya no agregaré canciones automáticamente",
            color=0xFF0000
        )
    else:
        bot.autoplay_enabled[guild_id] = True
        embed = discord.Embed(
            title="📻 Modo Radio Activado",
            description="Agregaré canciones similares automáticamente cuando se acabe la cola",
            color=0x00FF00
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='radio', description='Inicia una radio basada en un género o artista')
async def radio(interaction: discord.Interaction, genero_o_artista: str):
    await interaction.response.defer()
    
    try:
        if not interaction.user.voice:
            await interaction.followup.send('¡Debes estar en un canal de voz!', ephemeral=True)
            return
        
        if not interaction.guild.voice_client:
            vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = interaction.guild.voice_client
        
        tracks = await wavelink.SoundCloudTrack.search(query=genero_o_artista, return_first=False)
        
        if not tracks:
            await interaction.followup.send(f'❌ No encontré resultados para: **{genero_o_artista}**', ephemeral=True)
            return
        
        bot.autoplay_enabled[interaction.guild.id] = True
        
        vc.queue.clear()
        
        for track in tracks[:5]:
            vc.queue.put(track)
        
        if not vc.is_playing():
            first_track = vc.queue.get()
            await vc.play(first_track)
        
        embed = discord.Embed(
            title="📻 Radio Iniciada",
            description=f"**Tema:** {genero_o_artista}\n**Canciones en cola:** {vc.queue.count}",
            color=0x00FF00
        )
        embed.set_footer(text="El modo autoplay está activado")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f'❌ Error: {str(e)}', ephemeral=True)
        logger.error(f'Error en radio: {e}', exc_info=True)

@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.Track, reason):
    logger.info(f"Track ended: {track.title} - Reason: {reason}")
    
    try:
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
            logger.info(f"Playing next track: {next_track.title}")
        elif player.guild.id in bot.autoplay_enabled:
            try:
                search = track.title.split(' - ')[0] if ' - ' in track.title else track.title.split()[0]
                tracks = await wavelink.SoundCloudTrack.search(query=search, return_first=False)
                
                if tracks:
                    for t in tracks[:3]:
                        if t.title != track.title:
                            player.queue.put(t)
                            break
                    
                    if not player.queue.is_empty:
                        next_track = player.queue.get()
                        await player.play(next_track)
                        logger.info(f"Autoplay: Playing {next_track.title}")
            except Exception as e:
                logger.error(f"Autoplay error: {e}")
    except Exception as e:
        logger.error(f"Error in track_end: {e}")

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('No se encontró DISCORD_TOKEN en el archivo .env')
        exit(1)
    
    bot.run(token)