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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("musicbot.log")],
)

logger = logging.getLogger("MusicBot")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True


class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.autoplay_enabled = {}

    async def setup_hook(self):
        node = wavelink.Node(
            bot=self,
            host=os.getenv("LAVALINK_HOST", "localhost"),
            port=int(os.getenv("LAVALINK_PORT", "2333")),
            password=os.getenv("LAVALINK_PASSWORD", "youshallnotpass"),
            https=False,
            heartbeat=30,
            region="us_central",
            spotify=None,
            identifier="MAIN",
            dumps=None,
            resume_key=None
        )
        await wavelink.NodePool.connect(node=node, client=self)
        await self.tree.sync()
        logger.info(f"Sincronizados {len(self.tree.get_commands())} comandos slash!")


bot = MusicBot()


@bot.event
async def on_ready():
    logger.info(f"{bot.user} ha iniciado sesión!")


@bot.event
async def on_wavelink_node_ready(node: wavelink.Node):
    logger.info(f"Nodo {node.identifier} está listo!")


@bot.tree.command(name="play", description="Reproduce una canción")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()

    try:
        if not interaction.user.voice:
            await interaction.followup.send(
                "¡Debes estar en un canal de voz!", ephemeral=True
            )
            return

        if not interaction.guild.voice_client:
            player: wavelink.Player = await interaction.user.voice.channel.connect(
                cls=wavelink.Player
            )
        else:
            player: wavelink.Player = interaction.guild.voice_client

        if player.channel != interaction.user.voice.channel:
            await interaction.followup.send(
                "Debes estar en mi mismo canal de voz!", ephemeral=True
            )
            return

        tracks = await wavelink.YouTubeTrack.search(query=busqueda, return_first=False)

        if not tracks:
            tracks = await wavelink.SoundCloudTrack.search(query=busqueda, return_first=False)

        if not tracks:
            await interaction.followup.send(
                f"❌ No encontré resultados para: **{busqueda}**", ephemeral=True
            )
            return

        track = tracks[0]

        if player.playing:
            player.queue.put(track)
            position = len(player.queue)
            embed = discord.Embed(
                title="➕ Agregado a la cola",
                description=f"**{track.title}**\n*Posición en cola: {position}*",
                color=0x2F3136,
            )
            await interaction.followup.send(embed=embed)
        else:
            await player.play(track)
            embed = discord.Embed(
                title="🎵 Reproduciendo ahora",
                description=f"**{track.title}**",
                color=0x2F3136,
            )
            await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        logger.error(f"Error en play: {e}", exc_info=True)


@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    if player.paused:
        await interaction.response.send_message(
            "La música ya está pausada!", ephemeral=True
        )
        return

    await player.pause(True)
    await interaction.response.send_message("⏸️ Música pausada")


@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    if not player.paused:
        await interaction.response.send_message(
            "La música no está pausada!", ephemeral=True
        )
        return

    await player.pause(False)
    await interaction.response.send_message("▶️ Música reanudada")


@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    if not player.playing:
        await interaction.response.send_message(
            "No hay música reproduciéndose!", ephemeral=True
        )
        return

    await player.skip()

    if player.queue:
        await interaction.response.send_message("⏭️ Saltando a la siguiente canción...")
    else:
        await interaction.response.send_message(
            "⏭️ Canción saltada. No hay más en la cola."
        )


@bot.tree.command(name="stop", description="Detiene la música y me desconecta")
async def stop(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    guild_id = interaction.guild.id
    if guild_id in bot.autoplay_enabled:
        del bot.autoplay_enabled[guild_id]

    await player.disconnect()
    await interaction.response.send_message("⏹️ Música detenida y desconectado")


@bot.tree.command(name="queue", description="Muestra la cola de reproducción")
async def queue(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    if not player.current and player.queue.is_empty:
        await interaction.response.send_message(
            "No hay canciones en la cola!", ephemeral=True
        )
        return

    embed = discord.Embed(title="📋 Cola de reproducción", color=0x2F3136)

    if player.current:
        embed.add_field(
            name="🎵 Reproduciendo ahora",
            value=f"**{player.current.title}**",
            inline=False,
        )

    if not player.queue.is_empty:
        queue_list = []
        for i, track in enumerate(list(player.queue)[:10], 1):
            queue_list.append(f"`{i}.` **{track.title}**")

        if len(player.queue) > 10:
            queue_list.append(f"*...y {len(player.queue) - 10} más*")

        embed.add_field(name="📋 En cola", value="\n".join(queue_list), inline=False)

    embed.set_footer(text=f"Total en cola: {len(player.queue)} canciones")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="autoplay", description="Activa/desactiva el modo radio")
async def autoplay(interaction: discord.Interaction):
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    if guild_id in bot.autoplay_enabled:
        del bot.autoplay_enabled[guild_id]
        embed = discord.Embed(
            title="📻 Modo Radio Desactivado",
            description="Ya no agregaré canciones automáticamente",
            color=0xFF0000,
        )
    else:
        bot.autoplay_enabled[guild_id] = True
        embed = discord.Embed(
            title="📻 Modo Radio Activado",
            description="Agregaré canciones similares automáticamente cuando se acabe la cola",
            color=0x00FF00,
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="radio", description="Inicia una radio basada en un género o artista"
)
async def radio(interaction: discord.Interaction, genero_o_artista: str):
    await interaction.response.defer()

    try:
        if not interaction.user.voice:
            await interaction.followup.send(
                "¡Debes estar en un canal de voz!", ephemeral=True
            )
            return

        if not interaction.guild.voice_client:
            player: wavelink.Player = await interaction.user.voice.channel.connect(
                cls=wavelink.Player
            )
        else:
            player: wavelink.Player = interaction.guild.voice_client

        tracks = await wavelink.SoundCloudTrack.search(query=genero_o_artista, return_first=False)

        if not tracks:
            await interaction.followup.send(
                f"❌ No encontré resultados para: **{genero_o_artista}**",
                ephemeral=True,
            )
            return

        bot.autoplay_enabled[interaction.guild.id] = True

        player.queue.clear()

        for track in tracks[:5]:
            player.queue.put(track)

        if not player.playing:
            first_track = player.queue.get()
            await player.play(first_track)

        embed = discord.Embed(
            title="📻 Radio Iniciada",
            description=f"**Tema:** {genero_o_artista}\n**Canciones en cola:** {len(player.queue)}",
            color=0x00FF00,
        )
        embed.set_footer(text="El modo autoplay está activado")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        logger.error(f"Error en radio: {e}", exc_info=True)


@bot.event
async def on_wavelink_track_end(player: wavelink.Player, track: wavelink.Track, reason):
    if reason == "FINISHED":
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
            logger.info(f"Playing next track: {next_track.title}")
        elif player.guild.id in bot.autoplay_enabled:
            try:
                if track:
                    search = track.title.split(" - ")[0]
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


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("No se encontró DISCORD_TOKEN en el archivo .env")
        exit(1)

    bot.run(token)
