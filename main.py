import asyncio
import logging
import os

from aiohttp import web
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

# --- VARIABILI D'AMBIENTE (RENDER) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "931253377")
tg_bot = None

SYSTEM_PROMPT = """
Sei l'Assistente Virtuale e Concierge Digitale multilingua del "Camping Coccorrocci" (Marina di Gairo, Ogliastra, Sardegna).
Il tuo obiettivo è assistere ospiti e turisti fornendo informazioni dettagliate, accurate e cortesi su tutti i servizi della struttura, gli alloggi, il bar ed il territorio.

STRUTTURA E GESTIONE DEL BAR:
- Il bar del campeggio è a GESTIONE ESTERNA E INDIPENDENTE (gestito direttamente dai titolari, la proprietaria e il suo compagno).
- È il punto di riferimento per colazioni, snack, aperitivi e relax.
- Per prenotazioni di tavoli, aperitivi, taglieri ed eventi al bar, invita gli utenti a usare il comando /prenota_tavolo o il modulo presente nella Web Chat.

REGOLE ESSENZIALI DI RISPOSTA:
1. Rispondi SEMPRE nella stessa lingua utilizzata dall'utente (Italiano, Inglese, Tedesco, Francese, Olandese, ecc.).
2. Tono di voce: Accogliente, solare, professionale ed estremamente utile per chi è in vacanza.
3. Rispondi prima di tutto in modo CHIARO e DIRETTO alla domanda del cliente.
4. Suggerisci il bar del campeggio in modo naturale e contestuale (es. se l'utente chiede di colazione, aperitivi, relax serale o dopo un trekking). Evita di menzionare il bar se la domanda riguarda solo aspetti pratici del campeggio (es. orari piscina, differenziata, regole alloggi).
5. Per prenotazioni di alloggi e piazzole del campeggio, indica chiaramente di contattare la reception del campeggio (+39 328 379 4773 / info@coccorroccicamping.com) oppure il comando /prenota.

BASE DI CONOSCENZA DETTAGLIATA:
☕ BAR (GESTIONE INDIPENDENTE):
- Orari: dalle 07:00 alle 24:00 (alta stagione estiva) / dalle 07:00 alle 20:00-21:00 (periodo invernale).
- SPECIALITÀ E HIGHLIGHTS:
  * Cocktail "Mirtico": Esclusiva della casa a base di Mirto sardo, Gin e Tonica.
  * Tagliere dell'Ogliastra: Selezione di salumi e formaggi tipici locali (€6,00 piccolo / €10,00 grande).
- CAFFETTERIA: Caffè espresso (€1,20), Macchiato (€1,30), Cappuccino (€1,50), Caffè Leccese/Shakerato (€3,00), Spremuta d'arancia (€5,00), Gin-Co (caffè al ginseng) e Orzo (anche senza lattosio/glutine).
- SNACK & COLAZIONI: Cornetti freschi (€1,50), Cornetti Veg (€2,00), Pizzette sfoglia (€2,00), Toast (€3,50).
- BIRRE & ALCOLICI: Ichnusa classica '33/'66, Ichnusa Non Filtrata '33, Heineken, Beck's, Corona, Birra alla spina (0,20l €2,50 / 0,30l €3,00 / 0,50l €6,00 / 1lt €15,00), Limoncello, Mirto sardo (€3,00), Fil'è Ferru (€3,00), Amari (€3,50).
- VINI & APERITIVI: Calice vino/prosecco (€3,50), Spritz (€6,00), Campari Spritz (€6,50), Cocktail classici e alla frutta.

📍 POSIZIONE E CAMPEGGIO:
- Indirizzo: Marina di Gairo, Ogliastra, Sardegna. Immerso tra mare e montagna, direttamente sulla spiaggia di ciottoli di Coccorrocci.
- Apertura: Aperto tutto l'anno (dal 1° novembre al 31 marzo è attivo solo il Market).
- Gestione campeggio: Nuova gestione dal 2020.
- Alloggi: Piazzole (fino a 4 posti per tende, camper, mini van, roof tent), Bungalow e Roulotte con veranda e bbq, Appartamenti vicini alla spiaggia, Case Mobili nel verde.
- Reception Campeggio: Telefono / WhatsApp +39 328 379 4773 / +39 379 177 3509 | Email: info@coccorroccicamping.com

🍕 RISTORANTE-PIZZERIA "I 4 MORI":
- Gestione esterna separata. Menu consultabile online su: https://www.menudigitale.io/i4mori-ristorante-pizzeria

🏊‍♂️ PISCINA (SERVIZIO CAMPEGGIO):
- Orari estivi: 09:00 - 17:30. Profondità: min 52 cm - max 154 cm.
- Regole principali: doccia obbligatoria prima del bagno, minori sotto i 12 anni accompagnati da un adulto, pannolino contenitivo per bimbi piccoli, rispettare 3 ore di digestione, vietato tuffarsi, vietato camminare a piedi nudi a bordo vasca, vietato il vetro, vietato giocare con il pallone o boccaglio, vietato riservare le sdraio con oggetti incustoditi.

🛶 AMBIENTE E ATTIVITÀ:
- Noleggio Kayak in reception campeggio.
- Animali domestici ammessi.
- Spiaggia di ciottoli di Coccorrocci e sentieri trekking/MTB segnalati nei dintorni.
"""


def ask_gemini(user_text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        return "⚠️ Servizio in fase di configurazione. Contatta la reception al +39 328 379 4773."
    try:
        local_client = genai.Client(api_key=api_key)
        response = local_client.models.generate_content(
            model="gemini-3.8-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            ),
        )
        return response.text or "Non sono riuscito a generare una risposta."
    except Exception as e:
        print(f"Errore Gemini: {e}", flush=True)
        return "Si è verificato un errore temporaneo. Puoi contattare la reception o il bar."


async def handle_web_chat(request):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }
    if request.method == "OPTIONS":
        return web.Response(status=200, headers=headers)
    try:
        data = await request.json()
        user_message = data.get("message", "")
        if not user_message:
            return web.json_response({"reply": "Messaggio vuoto."}, headers=headers)
        reply = ask_gemini(user_message)
        return web.json_response({"reply": reply}, headers=headers)
    except Exception as e:
        return web.json_response({"reply": "Errore nella richiesta."}, status=400, headers=headers)


# Endpoint per ricevere le prenotazioni dalla Web Chat ed inviarle su Telegram
async def handle_web_booking(request):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }
    if request.method == "OPTIONS":
        return web.Response(status=200, headers=headers)
    try:
        data = await request.json()
        nome = data.get("nome", "Cliente Web")
        data_ora = data.get("dataOra", "-")
        persone = data.get("persone", "-")
        telefono = data.get("telefono", "-")
        if tg_bot and OWNER_CHAT_ID:
            notifica = (
                "🍹 *NUOVA PRENOTAZIONE TAVOLO BAR (da Web Chat)!*\n\n"
                f"👤 *Cliente:* {nome}\n"
                f"📅 *Data e Ora:* {data_ora}\n"
                f"👥 *Persone:* {persone}\n"
                f"📞 *Recapito:* {telefono}"
            )
            target_id = int(OWNER_CHAT_ID) if str(OWNER_CHAT_ID).isdigit() else OWNER_CHAT_ID
            await tg_bot.send_message(chat_id=target_id, text=notifica, parse_mode="Markdown")
            print(f"✅ Notifica prenotazione inviata su Telegram a {target_id}", flush=True)
        return web.json_response({"status": "ok", "message": "Richiesta inviata con successo!"}, headers=headers)
    except Exception as e:
        print(f"❌ Errore invio prenotazione web: {e}", flush=True)
        return web.json_response({"status": "error", "message": str(e)}, status=400, headers=headers)


T_DATA, T_PERSONE, T_CONTATTO = range(3)
C_DATE, C_ALLOGGIO, C_OSPITI, C_CONTATTO = range(3, 7)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Benvenuto al Camping Coccorrocci!*\n\n"
        "Sono il tuo Concierge Digitale. Posso darti informazioni su alloggi, piscina, percorsi trekking e il bar del campeggio!\n\n"
        "📌 *Comandi rapidi:*\n"
        "👉 /bar - Menù e specialità del Bar\n"
        "👉 /prenota_tavolo - Prenota un tavolo al Bar\n"
        "👉 /prenota - Richiedi alloggio o piazzola nel campeggio\n"
        "👉 /contatti - Numeri ed email utili"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def bar_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bar_text = (
        "🍹 *BAR CAMPING COCCORROCCI* (Gestione Indipendente)\n\n"
        "🕒 *Orari:* 07:00 - 24:00 (Estate) / 07:00 - 20:00 (Inverno)\n\n"
        "🌟 *SPECIALITÀ DA NON PERDERE:*\n"
        "🍸 *Cocktail Mirtico:* Mirto sardo, Gin e Tonica!\n"
        "🧀 *Tagliere dell'Ogliastra:* Salumi e formaggi tipici (€6 piccolo / €10 grande).\n\n"
        "☕ *Caffetteria & Colazioni:* Espresso (€1,20), Cappuccino (€1,50), Cornetti freschi (€1,50).\n"
        "🍺 *Birre & Drink:* Ichnusa (classica e non filtrata), Spritz (€6,00), Amari.\n\n"
        "👉 Usa /prenota_tavolo per riservare il tuo posto!"
    )
    await update.message.reply_text(bar_text, parse_mode="Markdown")


async def contatti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📞 *CONTATTI UTILI:*\n\n"
        "🍹 *Bar Campeggio:* Usa /prenota_tavolo\n"
        "🏕️ *Reception Campeggio:* +39 328 379 4773 / +39 379 177 3509 | info@coccorroccicamping.com\n"
        "🍕 *Ristorante I 4 Mori:* https://www.menudigitale.io/i4mori-ristorante-pizzeria"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def prenota_tavolo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🍹 Prenotazione Tavolo Bar\nIndica la data e l'orario (es. Oggi 19:30):")
    return T_DATA


async def prenota_tavolo_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tavolo_data"] = update.message.text
    await update.message.reply_text("👥 Per quante persone?")
    return T_PERSONE


async def prenota_tavolo_persone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tavolo_persone"] = update.message.text
    await update.message.reply_text("📞 Lasciaci il tuo Nome e Recapito Telefonico:")
    return T_CONTATTO


async def prenota_tavolo_fine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tavolo_contatto"] = update.message.text
    nome_cliente = update.effective_user.first_name
    data_ora = context.user_data.get("tavolo_data")
    persone = context.user_data.get("tavolo_persone")
    contatto = context.user_data.get("tavolo_contatto")
    await update.message.reply_text(f"🥂 Richiesta inviata! Ti confermeremo a breve a questo recapito: {contatto}")
    if OWNER_CHAT_ID:
        notifica = (
            "🍹 *NUOVA PRENOTAZIONE TAVOLO BAR (da Telegram)!*\n\n"
            f"👤 *Cliente:* {nome_cliente}\n"
            f"📅 *Data/Ora:* {data_ora}\n"
            f"👥 *Persone:* {persone}\n"
            f"📞 *Recapito:* {contatto}"
        )
        try:
            target_id = int(OWNER_CHAT_ID) if str(OWNER_CHAT_ID).isdigit() else OWNER_CHAT_ID
            await context.bot.send_message(chat_id=target_id, text=notifica, parse_mode="Markdown")
        except Exception as e:
            print(f"Errore notifica: {e}", flush=True)
    return ConversationHandler.END


async def prenota_camp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏕️ Richiesta Alloggio / Piazzola\nIndica le date (es. 15-22 Luglio):")
    return C_DATE


async def prenota_camp_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["camp_date"] = update.message.text
    await update.message.reply_text("🏠 Tipologia alloggio (Piazzola, Bungalow, Roulotte, Casa Mobile, Appartamento):")
    return C_ALLOGGIO


async def prenota_camp_alloggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["camp_alloggio"] = update.message.text
    await update.message.reply_text("👥 Quanti ospiti (adulti, bimbi, animali):")
    return C_OSPITI


async def prenota_camp_ospiti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["camp_ospiti"] = update.message.text
    await update.message.reply_text("📞 Il tuo Nome e Recapito:")
    return C_CONTATTO


async def prenota_camp_fine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["camp_contatto"] = update.message.text
    await update.message.reply_text("✅ Richiesta per il campeggio registrata! La reception ti contatterà a breve.")
    return ConversationHandler.END


async def prenota_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Annullato.")
    return ConversationHandler.END


async def handle_tg_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = ask_gemini(update.message.text)
    await update.message.reply_text(reply)


async def on_startup(application):
    global tg_bot
    tg_bot = application.bot

    app_web = web.Application()
    app_web.router.add_post("/api/chat", handle_web_chat)
    app_web.router.add_options("/api/chat", handle_web_chat)
    app_web.router.add_post("/api/prenota_tavolo", handle_web_booking)
    app_web.router.add_options("/api/prenota_tavolo", handle_web_booking)

    port = int(os.getenv("PORT", 10000))
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    application.bot_data["web_runner"] = runner
    print(f"🌐 Server Web Chat attivo sulla porta {port}", flush=True)


async def on_shutdown(application):
    runner = application.bot_data.get("web_runner")
    if runner:
        await runner.cleanup()


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
    if not token or token == "INCOLLA_QUI_IL_TOKEN_DI_BOTFATHER":
        print("❌ TELEGRAM_BOT_TOKEN mancante!", flush=True)
        return

    tg_app = (
        ApplicationBuilder()
        .token(token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    tavolo_handler = ConversationHandler(
        entry_points=[CommandHandler("prenota_tavolo", prenota_tavolo_start)],
        states={
            T_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_tavolo_data)],
            T_PERSONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_tavolo_persone)],
            T_CONTATTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_tavolo_fine)],
        },
        fallbacks=[CommandHandler("annulla", prenota_cancel)],
    )

    camp_handler = ConversationHandler(
        entry_points=[CommandHandler("prenota", prenota_camp_start)],
        states={
            C_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_camp_date)],
            C_ALLOGGIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_camp_alloggio)],
            C_OSPITI: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_camp_ospiti)],
            C_CONTATTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_camp_fine)],
        },
        fallbacks=[CommandHandler("annulla", prenota_cancel)],
    )

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("bar", bar_info))
    tg_app.add_handler(CommandHandler("contatti", contatti))
    tg_app.add_handler(tavolo_handler)
    tg_app.add_handler(camp_handler)
    tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_tg_message))

    print("🟢 TELEGRAM BOT & WEB SERVER PRONTI SU RENDER!", flush=True)
    tg_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
