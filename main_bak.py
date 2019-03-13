import configparser
import logging
import os, sys
import time,random
import dbHelper
import googlemaps
import jieba_hant
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup,ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler

LIST_OF_ADMINS = [135035100]


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = context.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped



format_template ="""
*店名*：{name}
*位置*：{loc}
*種類*：{soup} / {type}
*營業時間*：{A}
{empty}{B}
*定休日*：{restday}
*價格帶*：{price}
{maplink}
"""
# Load data from config.ini file
config = configparser.ConfigParser()
config.read('config.ini')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
gmaps = googlemaps.Client(key=config['GOOGLE']['API_KEY'])
mode = os.getenv("env")

if mode == "dev":
    def run(updater):

        updater.start_polling()
        updater.idle()
elif mode == "prod":
    def run(updater):
        TOKEN = (config['TELEGRAM']['ACCESS_TOKEN'])
        PORT = int(os.environ.get('PORT', '8443'))

        updater = Updater(TOKEN)
        # add handlers
        updater.start_webhook(listen="0.0.0.0",
                              port=PORT,
                              url_path=TOKEN)
        updater.bot.set_webhook("https://ramenbot-tw.herokuapp.com/" + TOKEN)
else:
    logger.error("No MODE specified!")
    sys.exit(1)

jb = jieba_hant

area_dict = {
    0: ['站','車站','捷運站'],
    1: ['市','縣','區']
}

def check_valid_location(input):
    seg_list = jb.lcut(input)
    print(seg_list)
    #台北的捷運站
    for word in area_dict[0]:
        if len(seg_list) == 1 and seg_list[0][-1] == word:
            return input
        if seg_list.count(word) != 0:
            if word != '站':
                input = input[:-len(word)]+"站"
            return input
    # 城市
    for word in area_dict[1]:
        if len(seg_list) == 1 and seg_list[0][-1] == word:
            return input
        if seg_list.count(word) != 0:
            return input
    return None


week_day_dict = {
        -1: '無定休',
        0: '星期一',
        1: '星期二',
        2: '星期三',
        3: '星期四',
        4: '星期五',
        5: '星期六',
        6: '星期日',
    }


def make_info(s,sql):
    if sql is True:
        info = format_template.format(name=s['name'], loc=s['loc'], maplink="https://goo.gl/maps/" + s['gmapid'],
                                      soup=s['soup'], type=s['type'], A=s['opeining'], empty="－－－－▏" if True else "",
                                      B="0030-2250", restday=week_day_dict[s['weekday']], price=s['price'])
    else:
        info = format_template.format(name=s[0], loc=s[2], maplink="https://goo.gl/maps/" + s[1],
                                      soup=s[6], type=s[5], A=s[4], empty="－－－－▏" if True else "",
                                      B="0030-2250", restday=week_day_dict[int(s[3])], price=s[7])

    return info


# 簡易搜尋 #
def find(bot, update):
    ask_str = "請選擇要根據什麼條件:"
    keyboard = [[InlineKeyboardButton("吃法", callback_data="type")],
                [InlineKeyboardButton("湯頭", callback_data="soup")],
                [InlineKeyboardButton("時間", callback_data="mealtime")],
                [InlineKeyboardButton("地點", callback_data="location")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message :
        update.message.reply_text(ask_str, reply_markup=reply_markup)
    else:
        query = update.callback_query
        bot.edit_message_text(ask_str,
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id,
                              reply_markup=reply_markup)
    return 'condition'

def condition(bot,update):
    query = update.callback_query
    print(query.data)
    if query.data == "mealtime":
        keyboard = [[InlineKeyboardButton("午餐", callback_data='noon')],
                    [InlineKeyboardButton("下午", callback_data='afternoon')],
                    [InlineKeyboardButton("晚餐", callback_data='night')],
                    [InlineKeyboardButton("宵夜(晚上9點後)", callback_data='midnight')]
                    ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.edit_message_text(text="用餐時間",
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id,
                              reply_markup=reply_markup)

    if query.data == "location":
        keyboard = [[InlineKeyboardButton("台北市隨便找一間", callback_data='taipei')]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        bot.edit_message_text(text="你在哪個縣市，輸入文字或是傳送位置\n"
                                   "若在台北可以輸入捷運站\n"
                                   "像是：「中山站」、「台中市」",
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id,
                              reply_markup=reply_markup)

    if query.data == "soup":
        bot.edit_message_text(text="請輸入想要的湯頭",
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id)

    if query.data == "type":
        keyboard = [[InlineKeyboardButton("拉麵", callback_data='ramen')],
                    [InlineKeyboardButton("沾麵", callback_data='tsukemen')],
                    [InlineKeyboardButton("拌麵", callback_data='aruba')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.edit_message_text(text="請選擇拉麵吃法",
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id,
                              reply_markup=reply_markup)
    return query.data



query_shop_list = list()
def mealtime(bot, update):
    query = update.callback_query.data



    bot.edit_message_text(text="用餐時間".format(query.data),
                          chat_id=query.message.chat_id,
                          message_id=query.message.message_id)


def by_location(bot, update):
    global query_shop_list

    query = update.message.text
    valid_loc = check_valid_location(query)

    # TODO: dicide which shop to be pop
    if valid_loc is not None:
        s = dbHelper.query_specify(['loc'], [valid_loc])[0]
        keyboard = [[InlineKeyboardButton("觀看照片", callback_data='comment,{}'.format(s['gmapid']))],
                    [InlineKeyboardButton("再找別家", callback_data='another,{},{}'.format(valid_loc, 1))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_markdown(make_info(s,True),reply_markup=reply_markup)
        return 'found'
    else:
        update.message.reply_text("格式有誤，請再試一次")
        return "location"

    # bot.edit_message_text(text= make_info(s),
    #                       chat_id=query.message.chat_id,
    #                       message_id=query.message.message_id
    #                       #,reply_markup=reply_markup
    #                      )
    # TODO: NLP?
def found(bot,update):
    query = update.callback_query


def getlocation(bot,update):
    geocode_result = gmaps.reverse_geocode((update.message.location.latitude, update.message.location.longitude))
    print(geocode_result)

def by_soup(bot,update):
    pass

def by_type(bot,update):
    pass

askedtime = False
newshop = list()


add_str_dict = {
    -1:"店名:",
    0:"GoogleMap Shortlink:",
    1:"位置:\n(台北填最近之捷運站，以外填城市)",
    2:"定休:",
    3:"營業時間:\n(格式為HHMM-HHMM)\n"
      "如果有上下午之分可用逗號間隔",
    4:"吃法:",
    5:"湯頭:",
    6:"價格:",
    7:"附註:"
}

# 增加新店功能區 #################################
@restricted
def add_new(bot, update):
    update.message.reply_text(add_str_dict[-1])
    return "gathering"


def getinfo(bot, update):
    if update.message:
        logger.info(update.message.text)
    else:
        logger.info(update.callback_query.data)

    if len(newshop) == 0:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[0])
        return "gathering"
    if len(newshop) == 1:
        st = dbHelper.check_dub(update.message.text)
        if st is not None:
            update.message.reply_text('店家重複，以下是資料庫中的條目：')
            update.message.reply_markdown(make_info(st,True))
            newshop.clear()
            return ConversationHandler.END
        newshop.append(update.message.text)
        # TODO: deal with different kinds of short link
        update.message.reply_text(add_str_dict[1])

        return "gathering"
    if len(newshop) == 2:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[2])
        return "gathering"
    if len(newshop) == 3:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[3])
        return "gathering"
    if len(newshop) == 4:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[4])
        return "gathering"

    if len(newshop) == 5:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[5])
        return "gathering"
    if len(newshop) == 6:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[6])
        return "gathering"
    if len(newshop) == 7:
        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[7])
        return "preview"


def preview(bot,update):
    if len(newshop) == 8:
        newshop.append(update.message.text)

    else:
        pass
    keyboard = [[InlineKeyboardButton("確認", callback_data='confirm')],
                [InlineKeyboardButton("修改", callback_data='edit')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_markdown("以下是資料預覽\n\n" + make_info(newshop,False), reply_markup=reply_markup)

def preview_callback(bot,update):
    query = update.callback_query.data
    if query == 'confirm':
        dbHelper.insert_new(newshop)
        update.message.reply_text("新增成功！")
        return ConversationHandler.END
    elif query == 'edit':
        keyboardrow =list()
        keyboardcol =list()
        for key,val in add_str_dict.items():
            val_m = val.split(":")[0]
            if len(keyboardrow)==2:

                keyboardcol.append(keyboardrow.copy())
                keyboardrow.clear()
                keyboardrow.append(InlineKeyboardButton(val_m,callback_data=key))
            else:
                print(key,val)
                keyboardrow.append(InlineKeyboardButton(val_m, callback_data=key))
        update.callback_query.message.reply_text("請問要修改哪個欄位",reply_markup=InlineKeyboardMarkup(keyboardcol))
        return 'edit'


def edit_notice(bot,update):
    query = update.callback_query.data
    newshop[int(query)+1] = None
    bot.edit_message_text(add_str_dict[int(query)],
                          chat_id=query.message.chat_id,
                          message_id=query.message.message_id)
def edit_finish(bot,update):
    newshop[newshop.index(None)] = update.message.text
    preview(bot,update)
    return 'preview'

def addto_db(bot,update):
    newshop.append(update.message.text)
    dbHelper.insert_new(newshop)


def canceladd(bot, update):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('已取消新增')
    newshop.clear()

    return ConversationHandler.END

# 基本指令
def start(bot, update):
    """Send a message when the command /start is issued."""
    # TODO: Add some welcome text
    update.message.reply_text('Hi!')


def echo(bot,update):
    update.message.reply_text(update.message.text)


def tg_help(bot, update):
    keyboard = [[InlineKeyboardButton("隨便幫我挑一家", callback_data="random")],
                [InlineKeyboardButton("簡易搜尋", callback_data="find")]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("需要幫忙ㄇ", reply_markup=reply_markup)


def by_event(bot,update):
    pass


def rare(bot,update):
    pass


def random_ramen(bot, update):
    message = getTime() + "\n"
    # TODO: handle time
    # Find in database

    n = dbHelper.query_random_id()['id']

    # TODO: figure out where to put notes & fix query string below
    s = dbHelper.query_specify(['id'], [n])[0]
    message += make_info(s,True)
    if update.message:
        update.message.reply_markdown(message)
    else:
        query = update.callback_query
        bot.edit_message_text(chat_id=query.message.chat_id,
                              message_id=query.message.message_id,
                              parse_mode=ParseMode.MARKDOWN,
                              text=message)


searchHandler = ConversationHandler(
    entry_points=[CommandHandler("search", find)],
    states={
        'condition':[CallbackQueryHandler(condition)],
        'mealtime':[CallbackQueryHandler(mealtime)],
        'soup':[CallbackQueryHandler(by_soup)],
        'type':[CallbackQueryHandler(by_type)],
        'location':[CallbackQueryHandler(by_location),MessageHandler(Filters.text,by_location)],
        'found' :[CallbackQueryHandler(by_location)]},
    fallbacks=[CommandHandler("cancel", canceladd)])

addHandler = ConversationHandler(
    entry_points=[CommandHandler("new", add_new)],
    states={
        # TODO: catch error on two handler section
       "gathering": [MessageHandler(Filters.text,getinfo),CallbackQueryHandler(getinfo)],
       "preview":[MessageHandler(Filters.text,preview),CallbackQueryHandler(preview_callback)],
       "edit":[CallbackQueryHandler(edit_notice),MessageHandler(Filters.text,edit_finish)],
       "insert":[MessageHandler(Filters.text,addto_db)]},
    fallbacks=[CommandHandler("cancel", canceladd)])


# Followed python telegram bot tutorial to use updater
def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater((config['TELEGRAM']['ACCESS_TOKEN']), use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("random", random_ramen))
    dp.add_handler(CommandHandler("event", by_event))
    dp.add_handler(CommandHandler("rare", rare))
    dp.add_handler(CommandHandler("help", tg_help))
    dp.add_handler(CallbackQueryHandler(random_ramen, pattern="random"))
    dp.add_handler(CallbackQueryHandler(find, pattern="find"))
    dp.add_handler(searchHandler)
    dp.add_handler(addHandler)
    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, echo))

    run(updater)


def getTime():

    APM = {
        "AM": "上午",
        "PM": "下午"
    }

    queryTime = time.localtime()
    return "查詢時間: %s %s %s" % (week_day_dict[queryTime.tm_wday],
                                  APM[time.strftime("%p", queryTime)],
                                  time.strftime("%I:%M", queryTime))


if __name__ == '__main__':
    main()
