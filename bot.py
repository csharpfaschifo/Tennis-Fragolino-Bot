# ============================================================================
# TELEGRAM BOT - TENNIS MATCH PROCESSOR
# Bot che riceve foto di match e aggiorna automaticamente l'Excel su Google Drive
# ============================================================================

import os
import re
import pandas as pd
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from openpyxl import load_workbook
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import json
import traceback
from googleapiclient.http import MediaIoBaseDownload
import io
import shutil
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
import subprocess
print("DEBUG: which tesseract =", shutil.which("tesseract"))
print("DEBUG: tesseract version:")
print(subprocess.run(["/usr/bin/tesseract", "--version"], capture_output=True, text=True).stdout)

# tesseract_path = shutil.which("tesseract")
# if tesseract_path:
#     pytesseract.pytesseract.tesseract_cmd = tesseract_path
# else:
#     raise RuntimeError("❌ Tesseract non trovato nel PATH")


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Il tuo token del bot (lo hai ottenuto da BotFather)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USERS = {
    8512235231,
    49697387
}


# Path del file Excel su Google Drive
EXCEL_FILE_ID = "ID_FILE_GOOGLE_DRIVE"  # ← Lo otterrai dopo
EXCEL_LOCAL_PATH = "Database_Tennis.xlsx"
SCOPES = ["https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]),
    scopes=SCOPES
)

drive_service = build("drive", "v3", credentials=creds)
EXCEL_FILE_ID = "1WaFe87w0bR2WlweXI-pUFupwUfl8g9g5"

# ============================================================================
# LISTA TENNISTI
# ============================================================================

tennisti = [
    "Carlos Alcaraz", "Jannik Sinner", "Alexander Zverev", "Novak Djokovic",
    "Lorenzo Musetti", "Alex de Minaur", "Ben Shelton", "Felix Auger-Aliassime",
    "Taylor Fritz", "Alexander Bublik", "Jack Draper", "Daniil Medvedev",
    "Casper Ruud", "Alejandro Davidovich Fokina", "Andrey Rublev", "Holger Rune",
    "Karen Khachanov", "Jakub Mensik", "Jiri Lehecka", "Tommy Paul",
    "Francisco Cerundolo", "Flavio Cobolli", "Denis Shapovalov", "Luciano Darderi",
    "Tallon Griekspoor", "Cameron Norrie", "Arthur Rinderknech", "Learner Tien",
    "Brandon Nakashima", "Tomas Machac", "Valentin Vacherot", "Joao Fonseca",
    "Ugo Humbert", "Frances Tiafoe", "Stefanos Tsitsipas", "Sebastian Baez",
    "Corentin Moutet", "Alex Michelsen", "Jaume Munar", "Lorenzo Sonego",
    "Gabriel Diallo", "Arthur Fils", "Zizou Bergs", "Daniel Altmaier",
    "Grigor Dimitrov", "Nuno Borges", "Fabian Marozsan", "Jenson Brooksby",
    "Camilo Ugo Carabelli", "Alexei Popyrin", "Marcos Giron", "Alexandre Muller",
    "Sebastian Korda", "Marton Fucsovics", "Hubert Hurkacz", "Aleksandar Kovacevic",
    "Matteo Berrettini", "Valentin Royer", "Kamil Majchrzak", "Miomir Kecmanovic",
    "Giovanni Mpetshi Perricard", "Tomas Martin Etcheverry", "Reilly Opelka",
    "Terence Atmane", "Matteo Arnaldi", "Damir Dzumhur", "Arthur Cazaux",
    "Francisco Comesana", "Adrian Mannarino", "Marin Cilic", "Pedro Martinez",
    "Raphael Collignon", "Jesper de Jong", "Mariano Navone", "Botic van de Zandschulp",
    "Mattia Bellucci", "Jacob Fearnley", "Aleksandar Vukic", "Alejandro Tabilo",
    "Ethan Quinn", "Adam Walton", "Cristian Garin", "Quentin Halys",
    "Filip Misolic", "Eliot Spizzirri", "Jan Lennard Struff", "Juan Manuel Cerundolo",
    "James Duckworth", "Emilio Nava", "Hamad Medjedovic", "Roberto Bautista Agut",
    "Laslo Djere", "Hugo Gaston", "Pablo Carreno Busta", "Dalibor Svrcina",
    "Alexander Blockx", "Alexander Shevchenko", "Tristan Schoolkate",
    "Carlos Taberner", "Ignacio Buse"
]

player_surname = [x.split()[-1].lower() for x in tennisti]

# ============================================================================
# FUNZIONI DI PREPROCESSING IMMAGINE
# ============================================================================

def gray_scale_img(img):
    """Prepara l'immagine per OCR"""
    img = img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    sharpener = ImageEnhance.Sharpness(img)
    img = sharpener.enhance(2.0)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    arr = np.array(img)
    threshold = arr.mean() + 20 # cambiato da 15 a 20
    arr = np.where(arr > threshold, 255, 0).astype("uint8")
    img = Image.fromarray(arr)
    return img

# ============================================================================
# FUNZIONI DI ESTRAZIONE DATI (dal tuo notebook)
# ============================================================================

def trova_cognome_nella_lista(lista_tennisti, candidati):
    i = 0
    l = []
    for nome in candidati:
        for tennista in lista_tennisti:
            if tennista == nome:
                i += 1
                l.append(tennista)
                if i == 2:
                    return l
    return l

def estrai_game_da_testo(testo, giocatori):
    if "vento" in testo.lower():
        sezione_punteggi = testo.split("vento")[1][:60].lower()
    else:
        sezione_punteggi = testo[0:100].lower() # Modificato da 50:100
    
    digit1 = [el.split(f"{giocatori[0]}")[1] for el in sezione_punteggi.split("\n") if giocatori[0] in el]
    digit2 = [el.split(f"{giocatori[1]}")[1] for el in sezione_punteggi.split("\n") if giocatori[1] in el]
    
    return list(map(int, re.findall(r'\d+', digit1[0]))), list(map(int, re.findall(r'\d+', digit2[0])))

def calcola_tie_break(game_g1, game_g2):
    tie_breaks = 0
    for g1, g2 in zip(game_g1, game_g2):
        if g1 + g2 >= 13:
            tie_breaks += 1
    return tie_breaks

def estrai_statistiche(testo):
    ace_match = re.search(r'(\d+)\s+Ace\s+(\d+)', testo, re.IGNORECASE)
    ace = [int(ace_match.group(1)), int(ace_match.group(2))] if ace_match else [0, 0]
    
    df_match = re.search(r'(\d+)\s+Doppi falli\s+(\d+)', testo, re.IGNORECASE)
    doppi_falli = [int(df_match.group(1)), int(df_match.group(2))] if df_match else [0, 0]
    
    for el in testo.lower().split("\n"):
        if "break point" in el:
            br1 = el.split("break point")[0].replace(" ", "")
            br2 = el.split("break point")[1].replace(" ", "")
    
    break_point = [br1, br2]
    return ace, doppi_falli, break_point

def processa_match(testo_match, lista_tennisti):
    pattern_nomi = r'\b\w+\b'
    nomi_trovati = re.findall(pattern_nomi, testo_match)
    nomi_candidati = [n.lower() for n in nomi_trovati if len(n) > 3]
    
    giocatori = trova_cognome_nella_lista(lista_tennisti, nomi_candidati)
    
    if len(giocatori) < 2:
        return None
    
    game = estrai_game_da_testo(testo_match, giocatori)
    game_g1 = game[0]
    game_g2 = game[1]
    
    ace, doppi_falli, break_point = estrai_statistiche(testo_match)
    
    risultati = []
    
    for idx, giocatore in enumerate(giocatori):
        if idx == 0:
            game_player = game_g1
            game_avversario = game_g2
            ace_player = ace[0]
            df_player = doppi_falli[0]
            bp_avversario = break_point[1]
        else:
            game_player = game_g2
            game_avversario = game_g1
            ace_player = ace[1]
            df_player = doppi_falli[1]
            bp_avversario = break_point[0]
        
        tot_game = sum(game_g1) + sum(game_g2)
        tot_game_player = sum(game_player)
        hnd = sum(game_player) - sum(game_avversario)
        tie_break = calcola_tie_break(game_g1, game_g2)
        
        risultati.append({
            'Giocatore': giocatore,
            'TOT GAME': tot_game,
            'TOT GAME PLAYER': tot_game_player,
            'DF': df_player,
            'BREAK': bp_avversario,
            'ACE': ace_player,
            'HND': hnd,
            'TIE BREAK': tie_break
        })
    
    return pd.DataFrame(risultati)

async def scrittura_in_excel(df, tennista, update):
    tennista = tennista.lower()
    if not os.path.exists(EXCEL_LOCAL_PATH):
        await update.message.reply_text(f"IN-FUNCTION: not os PATH exists")
        df_init = pd.DataFrame({"INIT": []})
        with pd.ExcelWriter(EXCEL_LOCAL_PATH, engine="openpyxl") as writer:
            df_init.to_excel(writer, sheet_name="INIT", index=False)
    await update.message.reply_text(f"IN-FUNCTION: read_excel")

    sheets = pd.read_excel(EXCEL_LOCAL_PATH, sheet_name=None)

    if tennista in sheets:
        await update.message.reply_text(f"IN-FUNCTION: {tennista} is in sheet")
        df_esistente = sheets[tennista]
    else:
        df_esistente = pd.DataFrame()

    await update.message.reply_text(f"IN-FUNCTION: Creazione df_match")
    df_match = df[df['Giocatore'] == tennista]
    df_aggiornato = pd.concat([df_esistente, df_match.iloc[:, 1:]], ignore_index=True)

    await update.message.reply_text(f"IN-FUNCTION: scrivo in excel il {tennista}")    
    with pd.ExcelWriter(
        EXCEL_LOCAL_PATH,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace"
    ) as writer:
        df_aggiornato.to_excel(writer, sheet_name=tennista, index=False)

# ============================================================================
# GOOGLE DRIVE FUNCTIONS
# ============================================================================

# Download Excel da Drive
def download_excel_from_drive():
    request = drive_service.files().get_media(fileId=EXCEL_FILE_ID)
    fh = io.FileIO(EXCEL_LOCAL_PATH, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    print("✅ Excel scaricato da Drive")

# Upload excel in Drive
def upload_excel_to_drive():
    media = MediaFileUpload(
        EXCEL_LOCAL_PATH,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=True
    )

    drive_service.files().update(
        fileId=EXCEL_FILE_ID,
        media_body=media
    ).execute()

    print("✅ Excel caricato su Drive")


# ============================================================================
# TELEGRAM BOT HANDLERS
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Messaggio di benvenuto"""
    await update.message.reply_text(
        "🎾 *Benvenuto nel Tennis Match Processor!*\n\n"
        "📸 Inviami una foto del tabellino del match e aggiornerò automaticamente il database.\n\n"
        "Comandi disponibili:\n"
        "/start - Mostra questo messaggio\n"
        "/help - Aiuto",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Messaggio di aiuto"""
    await update.message.reply_text(
        "❓ *Come usare il bot:*\n\n"
        "1️⃣ Scatta una foto del tabellino del match\n"
        "2️⃣ Inviamela qui\n"
        "3️⃣ Aspetta qualche secondo\n"
        "4️⃣ Riceverai conferma dell'aggiornamento!\n\n"
        "✅ Il database sarà aggiornato automaticamente su Google Drive.",
        parse_mode='Markdown'
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce le foto ricevute"""

    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Non sei autorizzato a usare questo bot.")
        return

    try:
        # Messaggio di attesa
        await update.message.reply_text("📸 Foto ricevuta! Sto processando...")
        
        # Download foto
        photo_file = await update.message.photo[-1].get_file()
        photo_path = "temp_match.jpg"
        await photo_file.download_to_drive(photo_path)
        print("DEBUG: immagine salvata in:", photo_path)
        
        from PIL import Image
        img = Image.open(photo_path)
        print("DEBUG: formato immagine:", img.format, img.mode, img.size)

        # Preprocessing immagine
        img = Image.open(photo_path)
        img = gray_scale_img(img)
        
        # OCR
        await update.message.reply_text("🔍 Estrazione testo...")
        print("DEBUG: sto per chiamare pytesseract.image_to_string")
        try:
            text = pytesseract.image_to_string(
                img,
                lang="ita+eng",
                config="--psm 6"
            )
            print("DEBUG: OCR completato")
        except Exception as e:
            print("❌ ERRORE DURANTE OCR")
            traceback.print_exc()
            raise

        
        # Processa match
        await update.message.reply_text("⚙️ Processamento dati...")
        df_match = processa_match(text, player_surname)
        
        if df_match is None or len(df_match) == 0:
            await update.message.reply_text("❌ Non sono riuscito a identificare i giocatori. Riprova con un'immagine più chiara.")
            return
        
        # Salva in Excel
        giocatori = df_match['Giocatore'].values.tolist()
                
        download_excel_from_drive()
        
        for player in giocatori:
            async scrittura_in_excel(df_match, player, update)
            await update.message.reply_text(f"📊 Scrittura in Excel del {player}...")
        
        upload_excel_to_drive()
        
        # Messaggio di conferma
        print("DEBUG: giocatori estratti =", giocatori)
        print("DEBUG: len(giocatori) =", len(giocatori))
        if len(giocatori) != 2:
            await update.message.reply_text(
                f"❌ Numero giocatori non valido ({len(giocatori)}): {giocatori}"
            )
            return
        
        g1, g2 = giocatori
        stats1 = df_match[df_match['Giocatore'] == g1].iloc[0]
        stats2 = df_match[df_match['Giocatore'] == g2].iloc[0]
        
        await update.message.reply_text(
            f"✅ *Match salvato con successo!*\n\n"
            f"🎾 *{g1.upper()}*\n"
            f"   • Game: {stats1['TOT GAME PLAYER']}\n"
            f"   • Ace: {stats1['ACE']}\n"
            f"   • DF: {stats1['DF']}\n"
            f"   • Handicap: {stats1['HND']:+d}\n\n"
            f"🎾 *{g2.upper()}*\n"
            f"   • Game: {stats2['TOT GAME PLAYER']}\n"
            f"   • Ace: {stats2['ACE']}\n"
            f"   • DF: {stats2['DF']}\n"
            f"   • Handicap: {stats2['HND']:+d}\n\n"
            f"💾 Database aggiornato!",
            parse_mode='Markdown'
        )
        
        # Cleanup
        os.remove(photo_path)
        
        # except Exception:
        #     await update.message.reply_text(
        #         "❌ Errore durante il processamento:\n"
        #         "tesseract is not installed or it's not in your PATH"
        #     )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Errore durante il processamento:\n{type(e).__name__}: {e}"
        )
        raise


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce messaggi di testo"""
    await update.message.reply_text(
        "📸 Inviami una *foto* del tabellino, non testo!\n\n"
        "Usa /help per maggiori informazioni.",
        parse_mode='Markdown'
    )

# ============================================================================
# MAIN
# ============================================================================

# ============================================================================
# Questa parte va alla FINE del tuo bot.py
# Cancella tutto dal "def main():" in giù e sostituisci con questo
# ============================================================================

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    PORT = int(os.environ.get("PORT", 10000))
    RENDER_URL = "https://tennis-fragolino-bot-1.onrender.com"

    print("🤖 Bot avviato in modalità WEBHOOK")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/",
        webhook_url=RENDER_URL
    )


if __name__ == '__main__':
    main()







