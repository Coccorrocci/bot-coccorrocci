import asyncio
import logging
import os
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_PROMPT = """
Sei l'Assistente Virtuale e Concierge Digitale multilingua del Camping Coccorrocci (Marina di Gairo, Ogliastra, Sardegna).
Il tuo obiettivo è assistere gli ospiti e i turisti fornendo informazioni dettagliate, accurate, utili e cortesi su tutti i servizi della struttura, gli alloggi, il bar e il territorio.

REGOLE ESSENZIALI:
1. Rispondi SEMPRE nella stessa lingua utilizzata dall'utente (Italiano, Inglese, Tedesco, Francese, Olandese, ecc.)
2. Tono di voce: Accogliente, solare, professionale ed entusiasta delle bellezze dell'Ogliastra.
3. Suggerisci sempre una piacevole sosta o un aperitivo al Bar del campeggio quando l'utente chiede informazioni su relax, dopo-trekking o colazioni.
4. Per prenotazioni di alloggi o piazzole, invita a usare il comando /prenota oppure a contattare direttamente la reception.
5. Contatti ufficiali reception:
  - Telefono / WhatsApp : +39 328 379 4773 / +39 379 1777 3509
  - Email: info@coccorroccicamping.com

BASE DI CONOSCENZA DETTAGLIATA (GROUNDED SULLE FONTI UFFICIALI):

📍 POSIZIONE E STRUTTURA:
- Indirizzo: Marina di Gairo, Ogliastra, Sardegna. Immerso nell'oasi naturalistica tra mare e montagna, direttamente sulla spiaggia di ciottoli di Coccorrocci.
- Apertura: Aperto tutto l'anno. (Nel periodo invernale dal 1° novembre al 31 marzo è attivo solo il Market e il Bar, il ristorante solo il fine settimana (ven/sab/dom)).
- Gestione: Nuova gestione dal 2020.

🏠 SISTEMAZIONI:
- Piazzole: fino a 4 posti per tende, camper, mini van e roof tent.
- Bungalow e Roulotte: dotati di veranda e barbecue, ideali per famiglie.
- Appartamenti: monolocali e bilocali vicini alla spiaggia.
- Case Mobili: confortevoli e immerse nel verde.

☕ BAR (GESTIONE PROPRIETARIA - PUNTO DI RIFERIMENTO):
- Orari: dalle 07:00 alle 24:00 (alta stagione estiva) / fino alle 20:00-21:00 (periodo invernale).
- SPECIALITA' E HIGHLIGHTS:
  - Cocktail "Mirtico": Esclusiva della casa! Cocktail rinfrescante a base di Mirto sardo, Gin, Succo di Lime, foglie di menta e Tonica.
  - Tagliere dell'Ogliastra: Selezione di salumi e formaggi tipici locali.
  - CAFFETTERIA, SNACK & COLAZIONI, BIRRE & ALCOLICI, VINI & APERITIVI.

🍕 RISTORANTE ("I 4 MORI" - GESTIONE ESTERNA):
- Il ristorante-pizzeria è in gestione esterna.
- Il menu completo è consultabile on line al link https://www.menudigitale.io/i4mori-ristorante-pizzeria oppure tramite il QR code presente nei tavoli del ristorante.

🏊‍♀️ PISCINA (GESTIONE CAMPEGGIO):
- Orari estivi: dalle 09:00 alle 17:30 (Attualmente chiusa per la stagione invernale, riaprirà in estate).
- Profondità: Minima 52 cm - Massima 154 cm.
- Regolamento della piscina:
  - Obbligo di farsi la doccia prima di entrare in vasca.
  - I minori di 12 anni devono essere sempre accompagnati da un adulto.
  - I bambini piccoli devono indossare il pannolino contenitivo.
  - Rispettare i tempi di digestione (attendere 3 ore prima del bagno).
  - Vietato tuffarsi, spingere e camminare a piedi nudi a bordo vasca.
  - Vietato portare oggetti o bicchieri in vetro.
  - Vietato giocare con il pallone e l'uso del boccaglio.
  - Vietato fare il bagno durante i temporali o pioggia.
  - Vietato riservare lo sdraio lasciando asciugamani o effetti personali incustoditi.
  - Vietato l'accesso fuori dagli orari di apertura.

🛎️ SERVIZI RECEPTION & AMBIENTE:
- Noleggio kayak: Disponibile direttamente in reception per esplorare la spiaggia di Coccorrocci e le scogliere.
- Animali Domestici: I cani e gli animali domestici sono i benvenuti!
- Ecologia: Raccolta differenziata dei rifiuti obbligatoria nel campeggio.

🥾 DINTORNI, TREKKING E PISCINE NATURALI:
- Spiaggia di Coccorrocci: Caratteristica spiaggia di ciottoli scuri proprio di fronte al campeggio.
- Piscine Naturali: Spettacolari vasche naturali nelle immediate vicinanze, meta imperdibile per bagni e relax.
- Sentieri & MTB: Diversi percorsi di trekking e mountain bike segnalati sulla mappa locale disponibile in reception.
"""

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

DATE, ALLOGGIO, OSPITI, CONTATTO = range(4)


async def healthcheck(request):
    return web.Response(text="OK - Bot attivo")


async def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app_web = web.Application()
    app_web.router.add_get("/", healthcheck)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Benvenuto al Camping Coccorrocci Concierge & Bar**\n\n"
        "Sono il tuo assistente virtuale. Posso fornirti informazioni su alloggi, servizi del campeggio, "
        "regolamento della piscina, percorsi trekking, piscine naturali e le specialità del nostro bar!\n\n"
        "📌 **Comandi rapidi:**\n"
        "👉 /bar - Scopri il menù del bar, il cocktail Mirtico e il tagliere sardo\n"
        "👉 /prenota - Invia una richiesta di prenotazione per piazzole o alloggi\n"
        "👉 /contatti - Numeri di telefono e email della reception\n\n"
        "💬 *Chiedimi pure qualsiasi cosa in Italiano, English, Deutsch, Français, ecc.!*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def bar_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bar_text = (
        "🍹 **BAR CAMPING COCCORROCCI** (Gestione Interna)\n\n"
        "🕑 **Orari:** 07:00 - 24:00 (Estate) / 07:00 - 20:00 (Inverno)\n\n"
        "🌟 **LE NOSTRE SPECIALITA' DA NON PERDERE**\n"
        "🍸 **Cocktail Mirtico:** L'esclusivo cocktail della casa a base di Mirto sardo, Gin, Succo di Lime, foglie di menta e Tonica.\n"
        "🧀 **Tagliere dell'Ogliastra:** Ricco tagliere di salumi e formaggi tipici locali.\n\n"
        "☕ **Caffetteria & Colazioni:** Caffè espresso (€1,20), Cappuccino (€1,50), Ginseng (€2,00), Orzo, Cornetti (€1,50), Toast (€3,50).\n"
        "🍺 **Birre & Drink:** Birra Ichnusa (classica e non filtrata), Birra alla spina, Mirto sardo, Fil'è Ferru, Aperol Spritz.\n\n"
        "📍 **Vi aspettiamo al bancone per iniziare al meglio la giornata o per un aperitivo al tramonto!**"
    )
    await update.message.reply_text(bar_text, parse_mode="Markdown")


async def contatti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📞 **Contatti Reception Camping Coccorrocci:**\n"
        "• Telefono: +39 328 379 4773 / +39 379 1777 3509\n"
        "• Email: info@coccorroccicamping.com\n"
        "• Sito web: www.coccorroccicamping.com\n\n"
        "🍕 **Ristorante-Pizzeria I 4 Mori:**\n"
        "• Menu digitale: https://www.menudigitale.io/i4mori-ristorante-pizzeria"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def prenota_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📆 **Richiesta di Prenotazione Alloggio / Piazzola**\n\n"
        "Indicaci le **date desiderate** per il tuo soggiorno (es. Arrivo 15 Luglio - Partenza 22 Luglio):"
    )
    return DATE


async def prenota_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text(
        "🏠 Che **tipologia di alloggio** preferisci?\n"
        "(Scegli tra: Piazzola, Bungalow, Roulotte, Appartamento, Casa Mobile)"
    )
    return ALLOGGIO


async def prenota_alloggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["alloggio"] = update.message.text
    await update.message.reply_text(
        "👥 Quanti **ospiti** sarete (Indica adulti, bambini ed eventuali cani/animali):"
    )
    return OSPITI


async def prenota_ospiti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ospiti"] = update.message.text
    await update.message.reply_text(
        "📞 Lasciaci il tuo **Nome, Cognome e Recapito** (Telefono o Email):"
    )
    return CONTATTO


async def prenota_fine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contatto"] = update.message.text
    riepilogo = (
        "✅ **Richiesta di Prenotazione Registrata!**\n\n"
        f"📆 **Date:** {context.user_data.get('date')}\n"
        f"🏠 **Alloggio:** {context.user_data.get('alloggio')}\n"
        f"👥 **Ospiti:** {context.user_data.get('ospiti')}\n"
        f"📞 **Contatto:** {context.user_data.get('contatto')}\n"
        "La reception verificherà la disponibilità a tabellone e ti ricontatterà al più presto per confermare!"
    )
    await update.message.reply_text(riepilogo, parse_mode="Markdown")
    return ConversationHandler.END


async def prenota_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Richiesta di prenotazione annullata.")
    return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"💬 Messaggio ricevuto da {update.effective_user.first_name}: '{user_text}'", flush=True)
    if not client:
        await update.message.reply_text("⚠️ GEMINI_API_KEY non configurata nello script.")
        return
    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            ),
        )
        reply_text = response.text or "Non sono riuscito a generare una risposta."
    except Exception as e:
        print(f"❌ Errore Gemini API: {repr(e)}", flush=True)
        reply_text = (
            "Si è verificato un problema temporaneo. Puoi contattare direttamente la reception ai numeri:\n"
            "📞 +39 328 379 4773 / +39 379 1777 3509\n✉️ info@coccorroccicamping.com"
        )
    await update.message.reply_text(reply_text)


async def main():
    if not TELEGRAM_BOT_TOKEN or ":" not in TELEGRAM_BOT_TOKEN:
        print("❌ ERRORE: Token Telegram non valido o mancante!", flush=True)
        return

    await run_web_server()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    booking_handler = ConversationHandler(
        entry_points=[CommandHandler("prenota", prenota_start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_date)],
            ALLOGGIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_alloggio)],
            OSPITI: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_ospiti)],
            CONTATTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, prenota_fine)],
        },
        fallbacks=[CommandHandler("cancel", prenota_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bar", bar_info))
    app.add_handler(CommandHandler("contatti", contatti))
    app.add_handler(booking_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🟢 BOT IN ASCOLTO!", flush=True)
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())