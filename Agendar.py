import asyncio
import re
import os
import time
import json
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
    "grupo1": -1002380759766
}

# Pastas e arquivos
PASTA_MIDIA = "/Midias"  # Mude se quiser outra pasta
LEGENDA1 = "Legenda.txt"
LEGENDA2 = "Legenda2.txt"
DB_FILE = "agendamentos_db.json"

os.makedirs(PASTA_MIDIA, exist_ok=True)

# Dicionários de agendamentos (agora guardam mais informações)
agendamentos_1 = {}  # canal_id → task
agendamentos_2 = {}  # canal_id → task

client = TelegramClient("bot_session", api_id, api_hash).start(bot_token=bot_token)

# ================================
# FUNÇÕES AUXILIARES
# ================================

def parse_time(text):
    text = text.lower().strip()
    if text.endswith("m"): return int(text[:-1]) * 60
    if text.endswith("h"): return int(text[:-1]) * 3600
    if text.endswith("s"): return int(text[:-1])
    raise ValueError("Formato inválido. Use 10s, 5m, 2h")

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

async def enviar_midia(canal_id, arquivo_path, legenda, botao):
    while True:
        try:
            if botao:
                txt, url = botao
                await client.send_file(
                    canal_id,
                    arquivo_path,
                    caption=legenda,
                    buttons=Button.url(txt, url)
                )
            else:
                await client.send_file(canal_id, arquivo_path, caption=legenda)
            return
        except FloodWaitError as e:
            print(f"FloodWait: esperando {e.seconds}s")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            print(f"Erro ao enviar mídia: {e}")
            await asyncio.sleep(10)

# ================================
# LOOP DE AGENDAMENTO (com proteção)
# ================================

async def loop_agendamento(tipo, canal_id, arquivo_path, intervalo, botao):
    nome_canal = next((k for k, v in CANAL_MAP.items() if v == canal_id), "desconhecido")
    print(f"Loop iniciado → #{nome_canal} | Intervalo: {intervalo}s | Tipo: {'1' if tipo==1 else '2'}")

    while True:
        try:
            if not os.path.exists(arquivo_path):
                print(f"Arquivo deletado! Parando agendamento em #{nome_canal}")
                break

            legenda = ler_legenda(LEGENDA1 if tipo == 1 else LEGENDA2)
            await enviar_midia(canal_id, arquivo_path, legenda, botao)
            await asyncio.sleep(intervalo)

        except asyncio.CancelledError:
            print(f"Agendamento cancelado manualmente → #{nome_canal}")
            break
        except Exception as e:
            print(f"Erro no loop #{nome_canal}: {e}")
            await asyncio.sleep(60)

# ================================
# PERSISTÊNCIA (salvar/carregar)
# ================================

def salvar_db():
    data = {
        "tipo1": {
            str(cid): {
                "file": info["file"],
                "intervalo": info["intervalo"],
                "botao": info["botao"]
            } for cid, info in agendamentos_1.items() if "file" in info
        },
        "tipo2": {
            str(cid): {
                "file": info["file"],
                "intervalo": info["intervalo"],
                "botao": info["botao"]
            } for cid, info in agendamentos_2.items() if "file" in info
        }
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar DB: {e}")

async def carregar_e_iniciar_agendamentos():
    if not os.path.exists(DB_FILE):
        return

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for cid_str, info in data.get("tipo1", {}).items():
            cid = int(cid_str)
            if os.path.exists(info["file"]):
                task = asyncio.create_task(loop_agendamento(1, cid, info["file"], info["intervalo"], info["botao"]))
                agendamentos_1[cid] = {"task": task, **info}

        for cid_str, info in data.get("tipo2", {}).items():
            cid = int(cid_str)
            if os.path.exists(info["file"]):
                task = asyncio.create_task(loop_agendamento(2, cid, info["file"], info["intervalo"], info["botao"]))
                agendamentos_2[cid] = {"task": task, **info}

        print(f"Agendamentos carregados do disco: {len(agendamentos_1)} + {len(agendamentos_2)}")
    except Exception as e:
        print(f"Erro ao carregar DB: {e}")

# ================================
# COMANDOS DO DONO
# ================================

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/start$"))
async def start(event):
    await event.reply("Bot de agendamento rodando!\nUse /help para ver comandos.")

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/help$"))
async def help_cmd(event):
    await event.reply(
        "Comandos:\n\n"
        "/agendar 45m (Botão|https://t.me/x) #canal1 #vip2025\n"
        "/agendar2 2h #canal2\n"
        "/parar #canal1\n"
        "/info → agendamentos com Legenda.txt\n"
        "/info2 → agendamentos com Legenda2.txt\n"
        "/todos → status de todos os canais\n"
        "/preview /preview2\n"
        "/parartodos"
    )

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/todos$"))
async def todos(event):
    msg = "Status dos canais:\n\n"
    for cod, cid in CANAL_MAP.items():
        s1 = "Ativo" if cid in agendamentos_1 else "Parado"
        s2 = "Ativo" if cid in agendamentos_2 else "Parado"
        msg += f"#{cod} → Normal: {s1} | Tipo2: {s2}\n"
    await event.reply(msg or "Nenhum canal configurado.")

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/parartodos$"))
async def parartodos(event):
    for info in list(agendamentos_1.values()):
        info["task"].cancel()
    for info in list(agendamentos_2.values()):
        info["task"].cancel()
    agendamentos_1.clear()
    agendamentos_2.clear()
    salvar_db()
    await event.reply("TODOS os agendamentos foram parados.")

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/parar (#[a-zA-Z0-9]+)$"))
async def parar(event):
    codigo = event.pattern_match.group(1)[1:].lower()
    canal_id = CANAL_MAP.get(codigo)
    if not canal_id:
        return await event.reply("Canal não encontrado.")

    parado = False
    if canal_id in agendamentos_1:
        agendamentos_1[canal_id]["task"].cancel()
        del agendamentos_1[canal_id]
        parado = True
    if canal_id in agendamentos_2:
        agendamentos_2[canal_id]["task"].cancel()
        del agendamentos_2[canal_id]
        parado = True

    salvar_db()
    await event.reply(f"Agendamento parado em #{codigo}" if parado else "Nenhum agendamento ativo nesse canal.")

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/info$"))
async def info(event):
    if not agendamentos_1:
        return await event.reply("Nenhum agendamento ativo (Legenda.txt)")
    msg = "Agendamentos ativos (Legenda.txt):\n\n"
    for cid, info in agendamentos_1.items():
        cod = next((k for k, v in CANAL_MAP.items() if v == cid), "???")
        msg += f"• #{cod} → a cada {info['intervalo']//60}m\n"
    await event.reply(msg)

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/info2$"))
async def info2(event):
    if not agendamentos_2:
        return await event.reply("Nenhum agendamento2 ativo (Legenda2.txt)")
    msg = "Agendamentos ativos (Legenda2.txt):\n\n"
    for cid, info in agendamentos_2.items():
        cod = next((k for k, v in CANAL_MAP.items() if v == cid), "???")
        msg += f"• #{cod} → a cada {info['intervalo']//60}m\n"
    await event.reply(msg)

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/preview$"))
async def preview(event):
    await event.reply(f"**Legenda.txt**\n\n{ler_legenda(LEGENDA1)}")

@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^/preview2$"))
async def preview2(event):
    await event.reply(f"**Legenda2.txt**\n\n{ler_legenda(LEGENDA2)}")

# ================================
# AGENDAR COM MÍDIA
# ================================

async def processar_agendamento(event, tipo):
    texto = event.raw_text
    legenda_path = LEGENDA1 if tipo == 1 else LEGENDA2
    cmd = "/agendar" if tipo == 1 else "/agendar2"

    match = re.search(rf"{cmd}\s+([0-9]+[smh])", texto)
    if not match:
        return await event.reply(f"Use: {cmd} 45m (Texto|url) #canal1")

    intervalo = parse_time(match.group(1))
    botao = extrair_botao(texto)
    canais = re.findall(r"#([a-zA-Z0-9]+)", texto)

    if not canais:
        return await event.reply("Adicione pelo menos um canal: #vip2025")

    # Salvar mídia permanentemente
    extensao = ".mp4" if event.video else ".jpg"
    nome_arquivo = f"{int(time.time())}_{event.id}_{canais[0]}{extensao}"
    caminho_final = os.path.join(PASTA_MIDIA, nome_arquivo)
    await event.download_media(file=caminho_final)

    sucesso = []
    for c in canais:
        c = c.lower()
        canal_id = CANAL_MAP.get(c)
        if not canal_id:
            continue

        # Cancelar antigo se existir
        if canal_id in (agendamentos_1 if tipo == 1 else agendamentos_2):
            (agendamentos_1 if tipo == 1 else agendamentos_2)[canal_id]["task"].cancel()

        task = asyncio.create_task(loop_agendamento(tipo, canal_id, caminho_final, intervalo, botao))
        info = {"task": task, "file": caminho_final, "intervalo": intervalo, "botao": botao}
        (agendamentos_1 if tipo == 1 else agendamentos_2)[canal_id] = info
        sucesso.append(c)

    salvar_db()
    await event.reply(f"Agendamento criado em: {', '.join([f'#{x}' for x in sucesso])}\nUsando: {os.path.basename(legenda_path)}")

@client.on(events.NewMessage(from_users=OWNER_ID, func=lambda e: e.media and "/agendar " in (e.raw_text or "")))
async def agendar(event):
    await processar_agendamento(event, 1)

@client.on(events.NewMessage(from_users=OWNER_ID, func=lambda e: e.media and "/agendar2 " in (e.raw_text or "")))
async def agendar2(event):
    await processar_agendamento(event, 2)

# ================================
# INICIAR BOT
# ================================

async def main():
    print("Carregando agendamentos antigos...")
    await carregar_e_iniciar_agendamentos()
    print("BOT RODANDO 24/7 — Pronto para agendar!")
    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())