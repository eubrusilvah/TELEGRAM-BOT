import asyncio
import re
import os
import time
import json
import random
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError

# ================================
# CONFIGURAÇÃO
# ================================

api_id = 27997335
api_hash = "85f70f9f6a820fb358f516762c2c5df5"
bot_token = "7827558742:AAGswAIxTZMAGnYoEzzufarag33kbDw-a2Q"

OWNER_ID = 6483441979  # Seu ID

# Mapa de códigos → ID dos canais
CANAL_MAP = {
    "grupo1": -1002380759766,
    # adicione mais: "vip2025": -1001234567890,
}

# Pastas e arquivos
PASTA_MIDIA = "/Midias"
LEGENDA1 = "Legenda.txt"
LEGENDA2 = "Legenda2.txt"
DB_FILE = "agendamentos_db.json"

os.makedirs(PASTA_MIDIA, exist_ok=True)

# Agora guardamos uma LISTA de arquivos por canal
agendamentos_1 = {}  # canal_id → {"task": task, "files": [path1, path2...], "intervalo": int, "botao": (txt,url)}
agendamentos_2 = {}  # mesmo para tipo 2

client = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# ================================
# FUNÇÕES AUXILIARES
# ================================

def parse_time(text):
    text = text.lower().strip()
    if text.endswith("m"): return int(text[:-1]) * 60
    if text.endswith("h"): return int(text[:-1]) * 3600
    if text.endswith("s"): return int(text[:-1])
    raise ValueError("Formato inválido. Use 10s, 5m 2h")

def extrair_botao(texto):
    match = re.search(r"\(([^|]+)\|([^)]+)\)", texto)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None

def ler_legenda(caminho):
    if not os.path.exists(caminho):
        return "⚠️ Legenda não encontrada!"
    with open(caminho, "r", encoding="utf-8") as f:
        return f.read().strip()

async def enviar_midia_aleatoria(canal_id, arquivos, legenda, botao):
    if not arquivos:
        print("Nenhuma mídia disponível para envio!")
        return

    arquivo_escolhido = random.choice(arquivos)
    while True:
        try:
            if botao:
                txt, url = botao
                await client.send_file(
                    canal_id,
                    arquivo_escolhido,
                    caption=legenda,
                    buttons=Button.url(txt, url)
                )
            else:
                await client.send_file(canal_id, arquivo_escolhido, caption=legenda)
            print(f"Enviado: {os.path.basename(arquivo_escolhido)} → {canal_id}")
            return
        except FloodWaitError as e:
            print(f"FloodWait: {e.seconds}s")
            await asyncio.sleep(e.seconds + 10)
        except Exception as e:
            print(f"Erro ao enviar mídia: {e}")
            await asyncio.sleep(10)

# ================================
# LOOP DE AGENDAMENTO COM ROLETA RUSSA
# ================================

async def loop_agendamento(tipo, canal_id, arquivos, intervalo, botao):
    nome_canal = next((k for k, v in CANAL_MAP.items() if v == canal_id), "desconhecido")
    print(f"Loop iniciado → #{nome_canal} | {len(arquivos)} mídias | a cada {intervalo//60}m | Tipo: {tipo}")

    while True:
        try:
            # Verifica se ainda tem pelo menos 1 arquivo válido
            arquivos_validos = [f for f in arquivos if os.path.exists(f)]
            if not arquivos_validos:
                print(f"Todas as mídias foram deletadas! Parando agendamento em #{nome_canal}")
                break

            legenda = ler_legenda(LEGENDA1 if tipo == 1 else LEGENDA2)
            await enviar_midia_aleatoria(canal_id, arquivos_validos, legenda, botao)
            await asyncio.sleep(intervalo)

        except asyncio.CancelledError:
            print(f"Agendamento cancelado → #{nome_canal}")
            break
        except Exception as e:
            print(f"Erro no loop #{nome_canal}: {e}")
            await asyncio.sleep(60)

# ================================
# PERSISTÊNCIA NO DISCO
# ================================

def salvar_db():
    data = {
        "tipo1": {
            str(cid): {
                "files": info["files"],
                "intervalo": info["intervalo"],
                "botao": info["botao"]
            } for cid, info in agendamentos_1.items() if info.get("files")
        },
        "tipo2": {
            str(cid): {
                "files": info["files"],
                "intervalo": info["intervalo"],
                "botao": info["botao"]
            } for cid, info in agendamentos_2.items() if info.get("files")
        }
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("DB salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar DB: {e}")

async def carregar_e_iniciar_agendamentos():
    if not os.path.exists(DB_FILE):
        return

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for cid_str, info in data.get("tipo1", {}).items():
            cid = int(cid_str)
            arquivos_validos = [f for f in info["files"] if os.path.exists(f)]
            if arquivos_validos:
                task = asyncio.create_task(loop_agendamento(1, cid, arquivos_validos, info["intervalo"], info["botao"]))
                agendamentos_1[cid] = {"task": task, "files": arquivos_validos, **info}
                count += 1

        for cid_str, info in data.get("tipo2", {}).items():
            cid = int(cid_str)
            arquivos_validos = [f for f in info["files"] if os.path.exists(f)]
            if arquivos_validos_validos:
                task = asyncio.create_task(loop_agendamento(2, cid, arquivos_validos, info["intervalo"], info["botao"]))
                agendamentos_2[cid] = {"task": task, "files": arquivos_validos, **info}
                count += 1

        print(f"Agendamentos restaurados: {count} loops ativos")
    except Exception as e:
        print(f"Erro ao carregar DB: {e}")

# ================================
# COMANDOS DO DONO (mantidos + melhorados)
# ================================

# ... (os comandos /start, /help, /todos, /parar, /info, etc permanecem iguais)
# Só mudo os que precisam

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/info$"))
async def info(event):
    if not agendamentos_1:
        return await event.reply("Nenhum agendamento ativo com Legenda.txt")
    msg = "**Agendamentos ativos (Legenda.txt)**\n\n"
    for cid, info in agendamentos_1.items():
        cod = next((k for k, v in CANAL_MAP.items() if v == cid), "???")
        msg += f"• `#{cod}` → {len(info['files'])} mídias | a cada {info['intervalo']//60}min\n"
    await event.reply(msg)

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/info2$"))
async def info2(event):
    if not agendamentos_2:
        return await event.reply("Nenhum agendamento2 ativo")
    msg = "**Agendamentos ativos (Legenda2.txt)**\n\n"
    for cid, info in agendamentos_2.items():
        cod = next((k for k, v in CANAL_MAP.items() if v == cid), "???")
        msg += f"• `#{cod}` → {len(info['files'])} mídias | a cada {info['intervalo']//60}min\n"
    await event.reply(msg)

# ================================
# AGENDAR COM MÚLTIPLAS MÍDIAS (ÁLBUM OU VÁRIAS)
# ================================

async def processar_agendamento_multiplo(event, tipo):
    texto = event.raw_text
    cmd = "/agendar" if tipo == 1 else "/agendar2"
    legenda_path = LEGENDA1 if tipo == 1 else LEGENDA2

    match = re.search(rf"{cmd}\s+([0-9]+[smh])", texto)
    if not match:
        return await event.reply(f"Sintaxe: {cmd} 45m (Botão|https://link) #canal1 #vip")

    intervalo = parse_time(match.group(1))
    botao = extrair_botao(texto)
    canais = re.findall(r"#([a-zA-Z0-9]+)", texto)

    if not canais:
        return await event.reply("Informe pelo menos um canal com #")

    if not event.media and not (event.grouped_id and event.message.media):
        return await event.reply("Envie uma ou mais mídias junto com o comando!")

    # === BAIXAR TODAS AS MÍDIAS DO ÁLBUM OU MENSAGEM ===
    mensagens = [event]
    if event.grouped_id:
        mensagens = await client.get_messages(event.chat_id, ids=range(event.grouped_id, event.grouped_id + 20))
        mensagens = [m for m in mensagens if m and m.grouped_id == event.grouped_id and m.media]

    arquivos_salvos = []
    for msg in mensagens:
        if not msg.media:
            continue
        extensao = ".mp4" if getattr(msg, "video", None) else ".jpg"
        nome = f"{int(time.time())}_{msg.id}_{canais[0]}{extensao}"
        caminho = os.path.join(PASTA_MIDIA, nome)
        await msg.download_media(file=caminho)
        arquivos_salvos.append(caminho)

    if not arquivos_salvos:
        return await event.reply("Nenhuma mídia foi baixada.")

    sucesso = []
    for c in set(canais):  # evita duplicar
        c = c.lower()
        canal_id = CANAL_MAP.get(c)
        if not canal_id:
            continue

        # Cancelar agendamento antigo (se existir)
        dicionario = agendamentos_1 if tipo == 1 else agendamentos_2
        if canal_id in dicionario:
            dicionario[canal_id]["task"].cancel()

        task = asyncio.create_task(loop_agendamento(tipo, canal_id, arquivos_salvos, intervalo, botao))
        dicionario[canal_id] = {
            "task": task,
            "files": arquivos_salvos,
            "intervalo": intervalo,
            "botao": botao
        }
        sucesso.append(c)

    salvar_db()
    await event.reply(
        f"Agendamento criado em: {', '.join([f'#{x}' for x in sucesso])}\n"
        f"Mídias carregadas: **{len(arquivos_salvos)}**\n"
        f"Legenda usada: `{os.path.basename(legenda_path)}`\n"
        f"Envio a cada: **{intervalo//60} minutos**"
    )

@client.on(events.NewMessage(from_users=OWNER_ID, func=lambda e: e.media and "/agendar " in (e.raw_text or "")))
async def agendar_handler(event):
    await processar_agendamento_multiplo(event, 1)

@client.on(events.NewMessage(from_users=OWNER_ID, func=lambda e: e.media and "/agendar2 " in (e.raw_text or "")))
async def agendar2_handler(event):
    await processar_agendamento_multiplo(event, 2)

# ================================
# INICIAR BOT
# ================================

async def main():
    print("Bot iniciando...")
    await carregar_e_iniciar_agendamentos()
    print("BOT RODANDO 24/7 — Roleta Russa ATIVA!")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())