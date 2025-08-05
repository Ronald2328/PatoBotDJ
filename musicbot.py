import discord
from discord.ext import commands
import wavelink
import asyncio
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("musicbot.log")],
)

logger = logging.getLogger("MusicBot")

logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.client").setLevel(logging.ERROR)
logging.getLogger("discord.gateway").setLevel(logging.ERROR)
logging.getLogger("discord.http").setLevel(logging.ERROR)
logging.getLogger("wavelink").setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"{bot.user} ha iniciado sesión!")

    try:
        node = wavelink.Node(
            uri=f'ws://{os.getenv("LAVALINK_HOST")}:{os.getenv("LAVALINK_PORT")}',
            password=os.getenv("LAVALINK_PASSWORD"),
            inactive_player_timeout=300,
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])
        logger.info("Conectado a Lavalink!")
    except Exception as e:
        logger.error(f"Error conectando a Lavalink: {e}")

    try:
        synced = await bot.tree.sync()
        logger.info(f"Sincronizados {len(synced)} comandos slash!")
    except Exception as e:
        logger.error(f"Error sincronizando comandos: {e}")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    logger.info(f"Nodo {payload.node.identifier} está listo!")


@bot.event
async def on_wavelink_inactive_player(player: wavelink.Player):
    pass


autoplay_enabled = {}


@bot.tree.command(name="play", description="Reproduce una canción")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()

    try:
        if not interaction.user.voice:
            await interaction.followup.send(
                "¡Debes estar en un canal de voz!", ephemeral=True
            )
            return

        player = interaction.guild.voice_client

        if not player:
            channel = interaction.user.voice.channel
            player = await channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.disabled
        elif player.channel != interaction.user.voice.channel:
            await interaction.followup.send(
                "Debes estar en mi mismo canal de voz!", ephemeral=True
            )
            return

        tracks = None
        search_msg = ""

        try:
            logger.info(f"Buscando: {busqueda}")

            if busqueda.startswith(("http://", "https://")):
                tracks = await wavelink.Playable.search(busqueda)
                search_msg = "URL directa"
            else:
                tracks = await wavelink.Playable.search(
                    busqueda, source=wavelink.TrackSource.SoundCloud
                )
                search_msg = "SoundCloud"

                if not tracks:
                    simplified = (
                        busqueda.lower()
                        .replace(" ft ", " ")
                        .replace(" feat ", " ")
                        .replace(" & ", " ")
                    )
                    tracks = await wavelink.Playable.search(
                        simplified, source=wavelink.TrackSource.SoundCloud
                    )

        except Exception as e:
            logger.error(f"Error buscando: {e}")

        if not tracks:
            await interaction.followup.send(
                f"❌ No encontré resultados para: **{busqueda}**\n"
                f"💡 Intenta buscar en SoundCloud o usa un link directo.",
                ephemeral=True,
            )
            return

        track = tracks[0] if isinstance(tracks, list) else tracks

        if player.current:
            player.queue.put(track)
            position = len(player.queue)
            embed = discord.Embed(
                title="➕ Agregado a la cola",
                description=f"**{track.title}**\n*Posición en cola: {position}*\n*Fuente: {search_msg}*",
                color=0x2F3136,
            )
            await interaction.followup.send(embed=embed)
        else:
            await player.play(track)
            embed = discord.Embed(
                title="🎵 Reproduciendo ahora",
                description=f"**{track.title}**\n*Fuente: {search_msg}*",
                color=0x2F3136,
            )
            await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        logger.error(f"Error en play: {e}", exc_info=True)


@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    player = interaction.guild.voice_client

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
    player = interaction.guild.voice_client

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
    player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    if not player.current:
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
    player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    guild_id = interaction.guild.id
    if guild_id in autoplay_enabled:
        del autoplay_enabled[guild_id]

    await player.disconnect()
    await interaction.response.send_message("⏹️ Música detenida y desconectado")


@bot.tree.command(name="queue", description="Muestra la cola de reproducción")
async def queue(interaction: discord.Interaction):
    player = interaction.guild.voice_client

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


@bot.tree.command(name="nowplaying", description="Muestra la canción actual")
async def nowplaying(interaction: discord.Interaction):
    player = interaction.guild.voice_client

    if not player or not player.current:
        await interaction.response.send_message(
            "No hay música reproduciéndose!", ephemeral=True
        )
        return

    track = player.current
    embed = discord.Embed(
        title="🎵 Reproduciendo ahora", description=f"**{track.title}**", color=0x2F3136
    )

    if track.length:
        position = player.position
        length = track.length

        bar_length = 20
        progress = int((position / length) * bar_length)
        progress_bar = "▓" * progress + "░" * (bar_length - progress)

        time_string = f"{position // 60000}:{(position % 60000) // 1000:02d} / {length // 60000}:{(length % 60000) // 1000:02d}"

        embed.add_field(
            name="Progreso", value=f"`{progress_bar}`\n{time_string}", inline=False
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="autoplay",
    description="Activa/desactiva el modo radio (reproduce canciones automáticamente)",
)
async def autoplay(interaction: discord.Interaction):
    player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message(
            "No estoy en un canal de voz!", ephemeral=True
        )
        return

    guild_id = interaction.guild.id

    if guild_id in autoplay_enabled:
        del autoplay_enabled[guild_id]
        embed = discord.Embed(
            title="📻 Modo Radio Desactivado",
            description="Ya no agregaré canciones automáticamente",
            color=0xFF0000,
        )
    else:
        autoplay_enabled[guild_id] = True
        embed = discord.Embed(
            title="📻 Modo Radio Activado",
            description="Agregaré canciones similares automáticamente cuando se acabe la cola",
            color=0x00FF00,
        )

        if not player.current and player.queue.is_empty:
            embed.add_field(
                name="💡 Tip",
                value="Usa `/play` para comenzar con una canción",
                inline=False,
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

        player = interaction.guild.voice_client

        if not player:
            channel = interaction.user.voice.channel
            player = await channel.connect(cls=wavelink.Player)
            player.autoplay = wavelink.AutoPlayMode.disabled

        tracks = await wavelink.Playable.search(
            genero_o_artista, source=wavelink.TrackSource.SoundCloud
        )

        if not tracks:
            await interaction.followup.send(
                f"❌ No encontré resultados para: **{genero_o_artista}**",
                ephemeral=True,
            )
            return

        autoplay_enabled[interaction.guild.id] = True

        player.queue.clear()

        for track in tracks[:5]:
            player.queue.put(track)

        if not player.current:
            first_track = player.queue.get()
            await player.play(first_track)

        embed = discord.Embed(
            title="📻 Radio Iniciada",
            description=f"**Tema:** {genero_o_artista}\n**Canciones en cola:** {len(player.queue)}",
            color=0x00FF00,
        )
        embed.add_field(
            name="🎵 Reproduciendo",
            value=player.current.title if player.current else "Iniciando...",
            inline=False,
        )
        embed.set_footer(
            text="El modo autoplay está activado - agregaré más canciones automáticamente"
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        logger.error(f"Error en radio: {e}", exc_info=True)


async def add_recommended_track(player: wavelink.Player):
    """Agrega una canción recomendada basada en la última reproducida"""
    try:
        if not player.current:
            return

        current_title = player.current.title.lower()
        artist = (
            current_title.split(" - ")[0]
            if " - " in current_title
            else current_title.split()[0]
        )

        search_terms = [artist, " ".join(current_title.split()[:3]), "music " + artist]

        added = False
        for term in search_terms:
            if added or len(player.queue) >= 10:
                break

            try:
                tracks = await wavelink.Playable.search(
                    term, source=wavelink.TrackSource.SoundCloud
                )
                if tracks:
                    for track in tracks[:5]:
                        if (
                            track.title.lower() != current_title
                            and track.length > 30000
                        ):
                            player.queue.put(track)
                            logger.info(f"Autoplay: Added {track.title} to queue")
                            added = True
                            break
            except Exception as e:
                logger.error(f"Error searching for {term}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error adding recommended track: {e}")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    track = payload.track
    logger.info(f"Started playing: {track.title}")


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player

    logger.info(f"Track ended with reason: {payload.reason}")

    if payload.reason in ["finished", "stopped"]:
        await asyncio.sleep(0.5)

        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
            logger.info(f"Auto-playing next track: {next_track.title}")
        elif player.guild.id in autoplay_enabled and payload.reason == "finished":
            await add_recommended_track(player)
            if not player.queue.is_empty:
                next_track = player.queue.get()
                await asyncio.sleep(0.5)
                await player.play(next_track)
                logger.info(f"Autoplay: Playing recommended track: {next_track.title}")


@bot.event
async def on_wavelink_track_stuck(payload: wavelink.TrackStuckEventPayload):
    player = payload.player
    logger.warning(
        f"Track stuck: {payload.track.title} - Threshold: {payload.threshold}ms"
    )

    await player.skip(force=True)


@bot.event
async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
    player = payload.player
    logger.error(f"Track exception: {payload.track.title} - Error: {payload.exception}")

    if not player.queue.is_empty:
        await player.skip(force=True)


@bot.event
async def on_wavelink_websocket_closed(payload: wavelink.WebsocketClosedEventPayload):
    logger.warning(f"Websocket closed: {payload.code} - {payload.reason}")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("No se encontró DISCORD_TOKEN en el archivo .env")
        exit(1)

    bot.run(token)
