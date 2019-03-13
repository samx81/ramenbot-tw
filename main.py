import configparser
import logging
import os, sys
from enum import Enum
import time,random
from typing import Dict

import dbHelper
import jieba_hant
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup,ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler

LIST_OF_ADMINS = [135035100]


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped


# Load data from config.ini file
config = configparser.ConfigParser()
config.read('config.ini')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
#gmaps = googlemaps.Client(key=config['GOOGLE']['API_KEY'])
mode = os.getenv("env")



jb = jieba_hant

area_dict = {
    0: ['站','車站','捷運站'],
    1: ['市','縣','區']
}


def check_valid_location(input):
    seg_list = jb.lcut(input)
    print(seg_list)
    # 台北的捷運站
    for word in area_dict[0]:
        if len(seg_list) == 1 and seg_list[0][-1] == word:
            return "tp."+input
        if seg_list.count(word) != 0:
            if word != '站':
                input = input[:-len(word)]+"站"
            return "tp."+input
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
format_template ="""
￭*店名*：{name}
￭*位置*：{loc}
￭*種類*：{soup} / {type}
￭*營業時間*：{A}{empty}{B}
￭*定休日*：{restday}
￭*價格帶*：{price}
{maplink}
"""


class QUERY_METHOD(Enum):
    LIKE, SPECIFY = range(2)

timeformattmp= "%H:%M"
def make_info_str(s, sql):
    if sql is True:
        i = s['loc'].find('.')
        loc_m = s['loc'][i+1:] if i != -1 else s['loc']
        # TODO: when depolying fix typo
        second_opening = ""
        first_opening = "{} - {}".format(s['opening'][0].strftime(timeformattmp),
                                       s['opening'][1].strftime(timeformattmp))
        if len(s['opening']) == 4:
            # tmp = s['opening'].split(',')
            second_opening = "{} - {}".format(s['opening'][2].strftime(timeformattmp),
                                            s['opening'][3].strftime(timeformattmp))

        info = format_template.format(name=s['name'], loc=loc_m, maplink="https://goo.gl/maps/" + s['gmapid'],
                                      soup=s['soup'], type=s['type'], A=first_opening,
                                      empty="\n￭－－－－▏" if second_opening else "",
                                      B=second_opening if second_opening else "",
                                      restday=week_day_dict[s['weekday']], price=s['price'])
    else:
        info = format_template.format(name=s[0], loc=s[2], maplink="https://goo.gl/maps/" + s[1],
                                      soup=s[6], type=s[5], A=s[4],empty="",B="", restday=week_day_dict[int(s[3])], price=s[7])

    return info


def make_info_inline_kb(gmapid,column,condition,method = QUERY_METHOD.SPECIFY):
    keyboard = [[InlineKeyboardButton("觀看照片", callback_data='comment,{}'.format(gmapid))],
                [InlineKeyboardButton("再找別家", callback_data='another,{},{},{},{}'
                                      .format(column, condition, gmapid,method.value))]]
    return InlineKeyboardMarkup(keyboard)

def is_int(value):
  try:
    int(value)
    return True
  except:
    return False

# 簡易搜尋 #
def search(update, context):
    ask_str = "點擊按鈕選擇搜尋條件:"
    keyboard = [[InlineKeyboardButton("吃法", callback_data="type")],
                [InlineKeyboardButton("湯頭", callback_data="soup")],
               # [InlineKeyboardButton("時間", callback_data="mealtime")],
                [InlineKeyboardButton("地點", callback_data="location")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message :
        update.message.reply_text(ask_str, reply_markup=reply_markup)
    else:
        query = update.callback_query
        query.edit_message_text(ask_str,
                              reply_markup=reply_markup)
    return 'condition'

def condition(update, context):
    query = update.callback_query
    print(query.data)
    if query.data == "mealtime":
        keyboard = [[InlineKeyboardButton("午餐", callback_data='noon')],
                    [InlineKeyboardButton("下午", callback_data='afternoon')],
                    [InlineKeyboardButton("晚餐", callback_data='night')],
                    [InlineKeyboardButton("宵夜(晚上9點後)", callback_data='midnight')]
                    ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="點擊按鈕選擇用餐時間",
                                reply_markup=reply_markup)

    if query.data == "location":
        keyboard = [[InlineKeyboardButton("台北市隨便找一間", callback_data='taipei')]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(text="你在哪個縣市，輸入文字或是傳送位置(開發中)\n"
                                     "若在台北可以輸入捷運站\n"
                                     "像是：「中山站」、「台中市」",
                                reply_markup=reply_markup)

    if query.data == "soup":
        query.edit_message_text(text="請輸入想要的湯頭")

    if query.data == "type":
        keyboard = [[InlineKeyboardButton("拉麵", callback_data='拉麵')],
                    [InlineKeyboardButton("沾麵", callback_data='沾麵')],
                    [InlineKeyboardButton("拌麵", callback_data='拌麵')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="點擊按鈕選擇拉麵吃法",
                                reply_markup=reply_markup)
    return query.data


def mealtime(update, context):
    cur_condition = "mealtime"
    if update.callback_query is not None:
        query = update.callback_query.data

        def f(x):
            return {
                'noon': 1200,
                'afternoon': 1500,
                'night': 1800,
                'midnight': 2130
            }.get(x, 1800)
        time_to_select = f(query)
        s = dbHelper.query_like(cur_condition, time_to_select)
        if s:
            reply_markup = reply_markup = make_info_inline_kb(s[0]['gmapid'], cur_condition, query, QUERY_METHOD.LIKE)
            update.callback_query.message.reply_markdown(make_info_str(s[0], True), reply_markup=reply_markup,
                                                         parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        else:
            update.callback_query.message.reply_text("查無店家，試著輸入其他條件")
            return cur_condition
    else:
        update.callback_query.message.reply_text("格式有誤，請再試一次")
        return cur_condition


def by_location(update, context):
    if update.message is not None:
        query = update.message.text
        valid_loc = check_valid_location(query)

        if valid_loc is not None:
            if valid_loc == "台北市":
                s = dbHelper.query_begin_with()
            else:
                s = dbHelper.query_specify(['loc'], [valid_loc])
            print(s)
            if s :
                reply_markup = reply_markup = make_info_inline_kb(s[0]['gmapid'], 'loc', valid_loc)
                update.message.reply_markdown(make_info_str(s[0], True), reply_markup=reply_markup,
                                              parse_mode=ParseMode.MARKDOWN)
                return ConversationHandler.END
            else:
                update.message.reply_text("查無店家，試著使用其他位置")
                return "location"
        else:
            update.message.reply_text("格式有誤，請再試一次")
            return "location"
    elif update.callback_query is not None:
        if update.callback_query.data == 'taipei':
            s = dbHelper.query_begin_with()

            reply_markup = make_info_inline_kb(s[0]['gmapid'],'loc','taipei')
            update.callback_query.edit_message_text(make_info_str(s[0], True), reply_markup=reply_markup,
                                                    parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
    else:
        update.message.reply_text("格式有誤，請再試一次")
        return "location"

    # query.edit_message_text(text= make_info(s),
    #                       chat_id=query.message.chat_id,
    #                       message_id=query.message.message_id
    #                       #,reply_markup=reply_markup
    #                      )
    # TODO: NLP?


def found(update, context):
    query = update.callback_query

# TODO: push location
# def getlocation(update, context):
#     geocode_result = gmaps.reverse_geocode((update.message.location.latitude, update.message.location.longitude))
#     print(geocode_result)


def by_soup(update, context):
    cur_condition = "soup"
    if update.message is not None:
        query = update.message.text
        s = dbHelper.query_like('soup', query)
        if s:
            reply_markup = reply_markup = make_info_inline_kb(s[0]['gmapid'], cur_condition, query,QUERY_METHOD.LIKE)
            update.message.reply_markdown(make_info_str(s[0], True), reply_markup=reply_markup,
                                          parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        else:
            update.message.reply_text("查無店家，試著輸入其他條件")
            return cur_condition
    else:
        update.message.reply_text("格式有誤，請再試一次")
        return cur_condition


def by_type(update, context):
    cur_condition = "type"
    if update.callback_query is not None:
        query = update.callback_query.data
        s = dbHelper.query_like(cur_condition, query)
        if s:
            reply_markup = reply_markup = make_info_inline_kb(s[0]['gmapid'], cur_condition, query,QUERY_METHOD.LIKE)
            update.callback_query.message.reply_markdown(make_info_str(s[0], True), reply_markup=reply_markup,
                                          parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        else:
            update.callback_query.message.reply_text("查無店家，試著輸入其他條件")
            return cur_condition
    else:
        update.callback_query.message.reply_text("格式有誤，請再試一次")
        return cur_condition


def cancel_search(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('已取消搜尋')

    return ConversationHandler.END


searchHandler = ConversationHandler(
    entry_points=[CommandHandler("search", search)],
    states={
        'condition':[CallbackQueryHandler(condition)],
        'mealtime':[CallbackQueryHandler(mealtime)],
        'soup':[MessageHandler(Filters.text,by_soup)],
        'type':[CallbackQueryHandler(by_type)],
        'location':[CallbackQueryHandler(by_location),MessageHandler(Filters.text,by_location)],
        'found' :[CallbackQueryHandler(by_location)]},
    fallbacks=[CommandHandler("cancel", cancel_search)])


newshop = list()


add_str_dict: Dict[int, str] = {
    -1:"店名:",
    0:"Google Map Short URL:",
    1:"位置:\n(台北填最近之捷運站，以外填城市)",
    2:"定休:\n無定休請填 -1",
    3:"營業時間:\n(格式為HHMM-HHMM)\n"
      "如果有上下午之分可用逗號間隔",
    4:"吃法:",
    5:"湯頭:",
    6:"價格:",
    7:"附註:"
}


# 增加新店功能區 #################################
@restricted
def add_new(update, context):
    if len(newshop) == 0:
        update.message.reply_markdown("請按照提示輸入對應的資料\n"
                                      "未知可填無")
        update.message.reply_text(add_str_dict[-1])
        return "gathering"
    else:
        update.message.reply_text('有人在新增中，請稍後再試')
        return ConversationHandler.END


def getinfo(update, context):
    if update.message:
        logger.info(update.message.text)
    else:
        logger.info(update.callback_query.data)
    logger.info(",".join(map(str, newshop)))
    if len(newshop) == 0:
        st = dbHelper.query_like('name',update.message.text)
        if st:
            update.message.reply_text('資料庫條目可能有重複，若為不同店家請繼續輸入')
            db_str = "重複列表：\n"
            for i in st:
                db_str += i['name']+"\n"
            update.message.reply_markdown(db_str)

        newshop.append(update.message.text)
        update.message.reply_text(add_str_dict[0]+
                                  "\n長的像這樣 goo.gl/maps/[key]\n"
                                  "請輸入 [key] 部分或是整個網址")
        return "gathering"
    if len(newshop) == 1:
        # if find a '/' do
        gid = ""
        if update.message.text.find('/') == -1:
            gid = update.message.text
        # else if find googl do
        elif update.message.text.find('goo.gl/maps/') != -1:
            gid = update.message.text[
                  (update.message.text.find('goo.gl/maps/')+len('goo.gl/maps/'))
                  :]
        else:
            update.message.reply_text('請檢查你輸入的是否有誤\n'
                                      '格式為https://goo.gl/maps/________')
            return "gathering"
        newshop.append(gid)
        update.message.reply_text(add_str_dict[1])

        return "gathering"
    if len(newshop) == 2:
        valid_loc = check_valid_location(update.message.text)
        if valid_loc is not None:
            newshop.append(valid_loc)
            update.message.reply_text(add_str_dict[2])
        else:
            update.message.reply_text("請檢查你輸入的位置，捷運站請加\"站\""
                                      "，城市請加縣市區")
        return "gathering"
    if len(newshop) == 3:
        input = update.message.text
        wd = ""
        try:
            # number
            if is_int(input) and int(input) != -1:
                wd = int(input)-1
            # only one char
            elif len(update.message.text) == 1:
                if update.message.text == "無":
                    wd = -1
                else:
                    wd = "星期"+input if input != "天" else "星期日"
                    wd = (list(week_day_dict.keys())[list(week_day_dict.values()).index(wd)])
            else:
                wd = (list(week_day_dict.keys())[list(week_day_dict.values()).index(input)])
            if wd != "":
                newshop.append(wd)
                print(wd)
                update.message.reply_text(add_str_dict[3])
                return "gathering"
        except ValueError:
            update.message.reply_text("check input")
    if len(newshop) == 4:
        # deal with time
        tmp = str(update.message.text)
        timelist = list()
        if tmp.find(","):
            tmp = tmp.split(",")
            timelist= tmp[0].split('-')+tmp[1].split('-')
        newshop.append(",".join(timelist))
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


def preview(update, context):
    if len(newshop) == 8:
        newshop.append(update.message.text)

    else:
        pass
    keyboard = [[InlineKeyboardButton("確認", callback_data='confirm')],
                [InlineKeyboardButton("修改", callback_data='edit')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_markdown("以下是資料預覽\n\n" + make_info_str(newshop, False), reply_markup=reply_markup)

def preview_callback(update, context):
    query = update.callback_query
    if query.data == 'confirm':
        dbHelper.insert_new(newshop)
        query.message.reply_text("新增成功！")
        return ConversationHandler.END
    elif query.data == 'edit':
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
                keyboardrow.append([InlineKeyboardButton(val_m, callback_data=key)])
        keyboardcol.append(InlineKeyboardButton("返回",callback_data="back"))
        update.callback_query.edit_message_text("請問要修改哪個欄位\n"+update.callback_query.message.text
                                                ,reply_markup=InlineKeyboardMarkup(keyboardcol))
        return 'edit'


def edit_notice(update, context):
    query = update.callback_query
    if query.data == 'back':
        keyboard = [[InlineKeyboardButton("確認", callback_data='confirm')],
                    [InlineKeyboardButton("修改", callback_data='edit')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.edit_message_text("以下是資料預覽\n\n" + make_info_str(newshop, False), reply_markup=reply_markup)
        return "preview"
    elif int(query.data) in add_str_dict:
        newshop[int(query.data)+1] = None
        query.edit_message_text(add_str_dict[int(query.data)])
    else:
        logger.info("incorrect query")
def edit_finish(update, context):
    newshop[newshop.index(None)] = update.message.text
    preview(update, context)
    return 'preview'

def addto_db(update, context):
    newshop.append(update.message.text)
    dbHelper.insert_new(newshop)


def canceladd(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('已取消新增')
    newshop.clear()

    return ConversationHandler.END


# 基本指令
def start(update, context):
    """Send a message when the command /start is issued."""
    # TODO: Add some welcome text
    update.message.reply_text('歡迎使用拉麵 bot!')


def echo(update, context):
    update.message.reply_text(update.message.text)


def tg_help(update, context):
    keyboard = [[InlineKeyboardButton("隨便幫我挑一家", callback_data="random")],
                [InlineKeyboardButton("簡易搜尋", callback_data="find")]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("需要幫忙ㄇ", reply_markup=reply_markup)


def find_another(update,context):
    # get callback from query
    query = update.callback_query
    querylist = query.data.split(',')
    # column, condition,gmapid, method
    repeat = True
    while repeat:
        if querylist[2] == 'taipei':
            s = dbHelper.query_begin_with()[0]
        elif QUERY_METHOD(int(querylist[4])) == QUERY_METHOD.LIKE:
            s = dbHelper.query_like(querylist[1], querylist[2])[0]
        else:
            s = dbHelper.query_specify([querylist[1]], [querylist[2]])[0]
        if len(s)==1 or s['gmapid'] != querylist[3]:
            repeat = False

    reply_kb = make_info_inline_kb(s['gmapid'],querylist[1],querylist[2],QUERY_METHOD(int(querylist[4])))
    update.callback_query.edit_message_text(update.callback_query.message.text)
    update.callback_query.message.reply_markdown(make_info_str(s,True),reply_markup=reply_kb)

def by_event(update, context):
    pass


def rare(update, context):
    pass


# TODO: search by index

def random_ramen(update, context):
    message = getTime() + "\n"
    # TODO: handle time
    # Find in database

    n = dbHelper.query_random_id()['id']

    # TODO: figure out where to put notes & fix query string below
    s = dbHelper.query_specify(['id'], [n])[0]
    message += make_info_str(s, True)
    if update.message:
        update.message.reply_markdown(message)
    else:
        query = update.callback_query
        query.edit_message_text(parse_mode=ParseMode.MARKDOWN,
                                text=message)


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


    if mode == "dev":
        def run():
            updater = Updater((config['TELEGRAM']['ACCESS_TOKEN']), use_context=True)
            updater.start_polling()
            updater.idle()
    elif mode == "prod":
        def run():
            TOKEN = os.environ.get('ACCESS_TOKEN')
            PORT = int(os.environ.get('PORT', '8443'))

            updater = Updater(TOKEN, use_context=True)
            # add handlers
            updater.start_webhook(listen="0.0.0.0",
                                  port=PORT,
                                  url_path=TOKEN)
            updater.bot.set_webhook("https://ramenbot-tw.herokuapp.com/" + TOKEN)
            updater.idle()
    else:
        logger.error("No MODE specified!")
        sys.exit(1)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("random", random_ramen))
    dp.add_handler(CommandHandler("event", by_event))
    dp.add_handler(CommandHandler("rare", rare))
    dp.add_handler(CommandHandler("help", tg_help))
    dp.add_handler(CallbackQueryHandler(random_ramen, pattern="random"))
    dp.add_handler(CallbackQueryHandler(search, pattern="find"))
    dp.add_handler(CallbackQueryHandler(find_another, pattern="^another"))
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
