#!/usr/bin/env python3
# pylint: disable=C0116,W0613
# This program is dedicated to the public domain under the CC0 license.
"""
Muellbot
hg -> git

TODO
    - change to inline Keyboard... seems nicer in Groupchat... too many messages
    
"""
# from email import message
from distutils.ccompiler import get_default_compiler
from email.message import Message
import logging
from multiprocessing import context

# python-telegram-bot
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
    #   InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler,  CallbackContext, MessageHandler,\
    Filters, ConversationHandler, PicklePersistence
    #   CallbackQueryHandler

# Data Manipulation
from datetime import timedelta, datetime
from pytz import timezone
import pandas as pd

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

DAYS = ['MONTAG', 'DIENSTAG', 'MITTWOCH', 'DONNERSTAG', 'FREITAG', 'SAMSTAG', 'SONNTAG']
DAYS_SHORT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
HELP_MSG =f"""Schau im Menü was der Bot alles kann. 😎
/start um das Hauptmenü zu starten;
kann auch helfen, falls der Bot unerwartet oder gar nicht reagiert.
"""

# turn debug mode on/off
global DEBUG
DEBUG = True

global TIMEZONEOFFSET, TIMEZONE, DATEFORMAT # use only where it matters => usually human reading
TIMEZONE = timezone('Europe/Berlin')
DATEFORMAT = "%d.%m.%Y"

# FILTERED_CSV = f'AK_{YEAR}_{RESTMUELL_BEZIRK}{RECYCLING_BEZIRK}-{BEZIRK}.csv'
FULL_CSV = f'AK_2022_komplett.csv'
 
MAIN_MENU, SETTINGS_MENU, RESTMUELL_SETTING, RECYCLING_SETTING, SETTINGS_DONE = range(5)

main_menu_keyboard = [["👏 Heute", "📅 Nächster Termin"],
                      ["🌇 Morgen", "⏰ auto. Erinnerungen"],
                      ['🔚 Schließen', '⚙ Einstellungen']]
main_menu_markup = ReplyKeyboardMarkup(main_menu_keyboard,
                                       resize_keyboard = True)

settings_keyboard = [["Restmüllbezirk", "♻ Recyclingbezirk"], ["🔙 Fertig"]]
settings_markup = ReplyKeyboardMarkup(settings_keyboard, resize_keyboard = True)


def filter_df(df, pat=r'', row=True, dropna=True):
    """Returns whole rows with pat if row, 
    and drop the rest if dropna.\\
    Maybe sth. like this exists somewhere in pandas already?"""
    
    if row:
        f = lambda row : row.str.contains(pat).any()
    else:
        f = lambda row : row.str.contains(pat)
    filterframe = df.apply(f, axis=1)
    if dropna and row:
        return df.loc[filterframe]
    elif dropna and not row: # drop as much na as possible
        return df.where(filterframe).dropna(axis=0, how='all').dropna(axis=1, how='all')
    else:
        return df.where(filterframe)
    
def get_df(fn: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(fn,
                        index_col=0,
                        keep_default_na=False,
                        parse_dates=True,
                        )
    except FileNotFoundError:
        message = f"Something went wrong..."
        print(message)
        
    return df

def get_day_info(lookday: datetime, df) -> pd.Series:
    
    lookdate = lookday.date()
    if lookdate in df.index.date:
        return df.loc[str(lookdate)]
    else:
        return pd.Series()

def format_day_info(day_info, pat) -> str:
    """Takes day's infos and makes a pretty string output.
    """
    global DATEFORMAT
    
    filter_func = lambda s, pat : s.loc[s.str.contains(pat)]
    # make header (Weekday + Date)
    timestamp = day_info.name
    r_date = timestamp.strftime(DATEFORMAT)
    r_weekday = DAYS[timestamp.weekday()]
    header = f"<b>{r_weekday}, {r_date}</b>\n"
    r_info = filter_func(day_info, pat)
    
    message = ""
    if r_info.empty:
        message = f"Nichts relevantes gefunden."        
    else:
        for k in r_info.index.values:
            message += f"{k} "
                
    return header+message
    
def start(update: Update, context: CallbackContext) -> int:

    chat_keys = context.chat_data.keys()
    # Initialize additional chat_data variables
    if 'reminders_flag' not in chat_keys:
        context.chat_data['reminders_flag'] = False
        
    if 'RM_bezirk' not in chat_keys or 'REC_bezirk' not in chat_keys:
        update.message.reply_text('Restmuellbezirk und Recyclingbezirk einstellen',
                                  reply_markup=settings_markup)
        return SETTINGS_MENU
    
    update.message.reply_text('Siehe Auswahlmenü unten', reply_markup=main_menu_markup)
    return MAIN_MENU

def settings(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Einstellung wählen:', reply_markup=settings_markup)
    return SETTINGS_MENU

def select_restmuellbezirk(update: Update, context: CallbackContext):
    keyboard1 = [['1', '2', '3', '4'], ['5', '6', '7', '8']]
    reply_markup = ReplyKeyboardMarkup(keyboard1, resize_keyboard = True)
    update.message.reply_text('RESTMUELLBEZIRK:', reply_markup=reply_markup)    
    return RESTMUELL_SETTING

def select_recyclingbezirk(update: Update, context: CallbackContext):
    keyboard2 = [['A', 'B', 'C'], ['D', 'E']]
    reply_markup = ReplyKeyboardMarkup(keyboard2, resize_keyboard = True)
    update.message.reply_text('RECYCLINGBEZIRK (Papier, Gelber Sack):',
                              reply_markup=reply_markup)
    return RECYCLING_SETTING

def set_restmuellbezirk(update: Update, context: CallbackContext):
    context.chat_data['RM_bezirk'] = update.message.text
    update.message.reply_text(f'Restmüllbezirk eingestellt: {update.message.text}\nWeitere Einstellungen?',
                              reply_markup=settings_markup)
    return SETTINGS_MENU

def set_recyclingbezirk(update: Update, context: CallbackContext):
    context.chat_data['REC_bezirk'] = update.message.text
    update.message.reply_text(f'Recyclingbezirk eingestellt: {update.message.text}\nWeitere Einstellungen?',
                              reply_markup=settings_markup)
    return SETTINGS_MENU

def heute(update: Update, context: CallbackContext) -> int:
    """Send today's info."""
    
    cd = context.chat_data
    if 'RM_bezirk' in cd.keys() and 'REC_bezirk' in cd.keys():
        rm_bez = cd['RM_bezirk']
        rec_bez = cd['REC_bezirk']
        pat = fr"Bez. {rm_bez}|Bez. {rec_bez}|{rec_bez} "
    
        # fetch data
        today = datetime.today()
        df = get_df(FULL_CSV)
            
        # pack message
        message = format_day_info(get_day_info(today, df), pat=pat)
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Bitte Einstellungen anpassen. /start", parse_mode='HTML')
        
    return MAIN_MENU

def morgen(update: Update, context: CallbackContext) -> int:
    """Send tomorrow's info."""
    
    cd = context.chat_data
    if 'RM_bezirk' in cd.keys() and 'REC_bezirk' in cd.keys():
        rm_bez = cd['RM_bezirk']
        rec_bez = cd['REC_bezirk']
        pat = fr"Bez. {rm_bez}|Bez. {rec_bez}|{rec_bez} "
    
        # fetch data
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        df = get_df(FULL_CSV)

        # pack & send message
        message = format_day_info(get_day_info(tomorrow, df), pat=pat)
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Bitte Einstellungen anpassen. /start", parse_mode='HTML')
        
    return MAIN_MENU

def next_date(update: Update, context: CallbackContext) -> int:
    
    cd = context.chat_data    
    if 'RM_bezirk' in cd.keys() and 'REC_bezirk' in cd.keys():
        rm_bez = cd['RM_bezirk']
        rec_bez = cd['REC_bezirk']
        pat = fr"Bez. {rm_bez}|Bez. {rec_bez}|{rec_bez} "
    
        df = filter_df(get_df(FULL_CSV), pat=pat)
        
        message = format_day_info(get_next_day(df), pat=pat)
        # message =  f"{BEZIRK}\nRestmüll: Bez. {RESTMUELL_BEZIRK}\nRecycling: Bez.{RECYCLING_BEZIRK}\n {r_df}"
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Bitte Einstellungen anpassen. /start", parse_mode='HTML')
        
    return MAIN_MENU

def send_reminder(context: CallbackContext, message = ''):
    
    reminders_flag = context.job.context['chat_data']['reminders_flag']
    if reminders_flag:
        context.bot.send_message(chat_id=context.job.context['chat_id'],
                                 text=message,
                                 parse_mode='HTML')
    else:
        pass

def schedule_reminders(context: CallbackContext, 
                       lookahead = 30, # days to look ahead and schedule
                       reminder_time = 20, # int of hour when reminders get sent (the day before)
                       ):
    """schedules new reminders and removes scheduled reminders if reminders_flag==False"""
    
    global DEBUG, DEV_ID
    j_chat_data = context.job.context['chat_data']
    reminders_flag = j_chat_data['reminders_flag']
    chat_id = context.job.context['chat_id']

    
    rm_bez = j_chat_data['RM_bezirk']
    rec_bez = j_chat_data['REC_bezirk']
    pat = fr"Bez. {rm_bez}|Bez. {rec_bez}|{rec_bez} "
    
    today = datetime.today()
    df = filter_df(get_df(FULL_CSV), pat=pat)
    
    diff_df = df.index-today
    future_df = df.loc[(diff_df < timedelta(days=lookahead)) & (diff_df >= timedelta(days=0))]    
    filter_func = lambda s, pat : s.loc[s.str.contains(pat)]
    
    if DEBUG:
        jobs = context.job_queue.jobs()
        jobdict = {j.name: [j.next_t, j.context] for j in jobs}
        print('-------------------JOBS-------------------')
        print(jobdict)
        print('------------------------------------------')
    
    if reminder_time < 24:
        first_call = timedelta(days=1)-timedelta(hours = reminder_time)
    else:
        first_call = timedelta(days=1)-timedelta(hours = 20)
        
    # todo 
    # maybe for future version: Fragen ob Müll raus, sonst last call
    # reminder_time = 22
    # last_call = timedelta(days=1)-timedelta(hours=reminder_time)
    
    mdict = {}
    for col in future_df.columns:
        mdict[col] = filter_func(future_df[col], pat=pat).index.to_pydatetime()
        
    # k = Kategorie, aka Restmüll/Papiermüll, ...
    for k, dates in mdict.items():
        for datum in dates:
            
            new_jobname = "reminder_"+str(k)+"_"+str(chat_id)
            jobs = context.job_queue.jobs()
            jobdict = {j.name: [j.next_t, j.context] for j in jobs}
            
            # schedule one reminder per category k
            when = (datum-first_call)
            localwhen = TIMEZONE.localize(when)
            message = f"""\
Heute noch rausstellen:
<b>{k}</b>
(Abholung: {DAYS_SHORT[datum.weekday()]}, {datum.strftime('%d.%m.%Y')}, \
Bez. {j_chat_data['RM_bezirk']}|{j_chat_data['REC_bezirk']})"""
            if new_jobname in jobdict.keys():
                pass
            else:
                context.job_queue.run_once(send_reminder,
                                    when = localwhen,
                                    context = context.job.context,
                                    name = new_jobname,
                                    job_kwargs={'kwargs':
                                        {'message': message}},
                                    )
                if DEBUG:
                    context.bot.send_message(chat_id=DEV_ID,parse_mode='HTML',
                        text=f"Message scheduled\nWhen:\n{localwhen}\
                            \nMessage:\n{message}\nJobname: {new_jobname}\nContext: {j_chat_data}")
    return None

def set_reminders(update: Update, context: CallbackContext) -> int:

    cd = context.chat_data
    if 'RM_bezirk' in cd.keys() and 'REC_bezirk' in cd.keys():
        rm_bez = cd['RM_bezirk']
        rec_bez = cd['REC_bezirk']
        pat = fr"Bez. {rm_bez}|Bez. {rec_bez}|{rec_bez} "
        
        # set flag
        if context.chat_data['reminders_flag']:
            context.chat_data['reminders_flag'] = False
            
            # remove ALL! jobs for this chat,
            # todo maybe only jobs containing "reminder" in future version
            jobs = context.job_queue.jobs()
            chat_id = update.message.chat_id
            for j in jobs:
                if j.context['chat_id'] == chat_id:
                    j.schedule_removal()
                    # print(f"Job removed, {j.name}")
                    if DEBUG:
                        context.bot.send_message(chat_id=DEV_ID,parse_mode='HTML',\
                            text=f"Job REMOVED: {j.name}")
                        
            message = "Erinnerungen in diesem Chat sind jetzt AUS."
            context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
            return None
        
        else:
            context.chat_data['reminders_flag'] = True
            message = "Erinnerungen in diesem Chat sind jetzt AN."
            message += f"\nBezirk: {rm_bez}|{rec_bez}"
            
            # check/renew schedule every hour
            scheduler_interval = 3600 # seconds
            context.job_queue.run_repeating(schedule_reminders,
                                            interval= scheduler_interval,
                                            first=2,
                                            context= {'chat_id': update.message.chat_id,
                                                    'chat_data' : context.chat_data},
                                            name=f"schedule_reminders_repeating_{update.message.chat_id}")
        
            # # initially schedule/remove jobs
            # context.job_queue.run_once(schedule_reminders,
            #                         when = 2,
            #                         context = {'chat_id': update.message.chat_id,
            #                                     'chat_data' : context.chat_data,},
            #                         name=f"schedule_reminders_initial_{update.message.chat_id}")
        
            context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
            
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Bitte Einstellungen anpassen. /start", parse_mode='HTML')
        
    return MAIN_MENU

def scheduled_jobs(update: Update, context: CallbackContext):
    """Send scheduled jobs to chat_id DEV_ID"""
    global DEV_ID
    jobs = context.job_queue.jobs()
    message = "<b>SCHEDULED JOBS:</b>\n"
    if jobs:
        for j in jobs:
            message += f"<b>{j.name}</b>\n- Next Trigger: {j.next_t}\n- context: {j.context}\n\n"
    else:
        message += "keine Jobs"
        
    if DEBUG:
        context.bot.send_message(chat_id=DEV_ID,parse_mode='HTML',\
            text= message)

def get_next_day(df, lookday=None):
    """take df and get next row from today or lookday"""
    
    if not lookday:
        lookday =  datetime.today()
    diff_df = df.index-lookday
    return df.loc[diff_df >= timedelta(days=0)].iloc[0]
    
def unknown_cmd(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Befehl versteh ich nicht. /start ?',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
    
def unknown_msg(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Nachricht versteh ich nicht. /start ?',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    
    # maybe add something here later
    return MAIN_MENU
    
def close_menu(update: Update, context: CallbackContext) -> int:
    # reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard = True)
    update.message.reply_text('tschau',
                              reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def settings_done(update: Update, context: CallbackContext) -> int:
    # reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard = True)
    cdk = context.chat_data.keys()
    if 'RM_bezirk' in cdk and 'REC_bezirk' in cdk:
        update.message.reply_text(
            f"Einstellungen: \nRestmuellbezirk: {context.chat_data['RM_bezirk']}\
                \nRecyclingbezirk: {context.chat_data['REC_bezirk']}",
            reply_markup=main_menu_markup)
    elif 'RM_bezirk' in cdk:
        update.message.reply_text(
            f"Einstellungen: \nRestmuellbezirk: {context.chat_data['RM_bezirk']}\nRecyclingbezirk: N/A",
            reply_markup=main_menu_markup)
    elif 'REC_bezirk' in cdk:
        update.message.reply_text(
            f"Einstellungen: \nRestmuellbezirk: N/A\nRecyclingbezirk: N/A",
            reply_markup=main_menu_markup)
    return MAIN_MENU

def help_command(update: Update, context: CallbackContext) -> None:
    """Displays info on how to use the bot."""
    update.message.reply_text(HELP_MSG)
    
def timeout(update: Update, context: CallbackContext) -> None:

    update.message.reply_text('timeout',
                              reply_markup=ReplyKeyboardRemove())
    
def main() -> None:
    """Run the bot."""
    
    # read config and store each line in config_dict
    config_filename = "devbot.conf"
    # config_filename = "muellbot.conf"
    with open(config_filename) as f:
        config_dict = {
            'token'     : None,
            'dev_id'    : None,
        }
        for line in f.readlines():
            k, v = line.strip().split()
            if k.lower() in config_dict.keys():
                config_dict[k.lower()] = v
                
    global DEV_ID
    DEV_ID = config_dict['dev_id']
    persistence = PicklePersistence(filename="muellbot_pickle")
    
    updater = Updater(config_dict['token'], persistence=persistence)
    dispatcher = updater.dispatcher

    # Add conversation handler with predefined states:
    conv_handler = ConversationHandler(
        # per_message = True,
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                MessageHandler(Filters.regex(r"Heute$"), heute),
                MessageHandler(Filters.regex(r"Nächster Termin$"), next_date),
                MessageHandler(Filters.regex(r"Morgen$"), morgen),
                MessageHandler(Filters.regex(r"Erinnerungen$"), set_reminders),
                MessageHandler(Filters.regex(r"Schließen$"), close_menu),
                MessageHandler(Filters.regex(r"Einstellungen$"), settings),
            ],
            SETTINGS_MENU: [
                MessageHandler(Filters.regex(r"Restmüllbezirk$"), select_restmuellbezirk),
                MessageHandler(Filters.regex(r"Recyclingbezirk$"), select_recyclingbezirk),
                MessageHandler(Filters.regex(r"Fertig$"), settings_done),
            ],
            RESTMUELL_SETTING: [
                MessageHandler(Filters.regex(r"^([1-8])$"), set_restmuellbezirk), # Restmuellbezirke 1-8
            ],
            RECYCLING_SETTING: [
                MessageHandler(Filters.regex(r"^([A-E])$"), set_recyclingbezirk), # Recyclingbezirke A-D
            ],
        },
        fallbacks=[CommandHandler("close", close_menu)]
    )
    
    dispatcher.add_handler(conv_handler)
    # dispatcher.add_handler(settings_conv_handler)
    dispatcher.add_handler(CommandHandler('start', start))
    # dispatcher.add_handler(CommandHandler('settings', settings))
    dispatcher.add_handler(CommandHandler('heute', heute))
    dispatcher.add_handler(CommandHandler('morgen', morgen))
    dispatcher.add_handler(CommandHandler('next', next_date))
    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(CommandHandler('reminders_toggle', set_reminders))
    dispatcher.add_handler(CommandHandler('scheduled_jobs', scheduled_jobs)) # nur dev/debug
    
    dispatcher.add_handler(MessageHandler(Filters.command, unknown_cmd))
    dispatcher.add_handler(MessageHandler(Filters.all, help_command))
    
    COMMANDS = [
    ("start", "Hauptmenü starten"),
    ("heute", "Kalendereintrag für heute."),
    ("morgen", "Kalendereintrag für morgen."),
    ("next", "Nächster relevanter Mülltermin"),
    ("help", "kleine Hilfe"),
    ("reminders_toggle", "Erinnerungen in diesem Chat an/aus"),
    # ("settings", "Einstellungen (pro Chat)"),
    # ("scheduled_reminders", "geplante Erinnerungen"), # nur dev/debug
    ]
    
    dispatcher.bot.set_my_commands(COMMANDS)
    
    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()

if __name__ == '__main__':
    main()