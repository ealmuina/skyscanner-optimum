import datetime
import json
import logging

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler)

import skyscanner
import model

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

ORIGIN, DESTINATION, TRIP_TYPE, START_DATE, END_DATE, MIN_DAYS, MAX_DAYS = range(7)


def start(update, context):
    context.chat_data['query'] = model.Query(
        user_id=update.effective_user.id,
        username=update.effective_user.full_name,
        creation_date=datetime.datetime.now()
    )
    update.message.reply_text(
        'Hi! My name is SkyscannerBot. I will help you find a cheap flight. '
        'Send /cancel to stop talking to me.\n\n'
        'What is the origin of your flight?'
    )
    return ORIGIN


def origin(update, context):
    context.chat_data['origin'] = update.message.text
    context.chat_data['query'].origin = update.message.text
    update.message.reply_text(
        f'I have heard {context.chat_data["origin"]} is a very nice place! '
        'Where are you going to?'
    )
    return DESTINATION


def destination(update, context):
    context.chat_data['destination'] = update.message.text
    context.chat_data['query'].destination = update.message.text
    reply_keyboard = [['Round trip', 'One way']]
    update.message.reply_text(
        f'I would like to go to {context.chat_data["destination"]} as well! '
        'Are you planning to do a one way or a round trip?',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return TRIP_TYPE


def trip_type(update, context):
    context.chat_data['trip_type'] = update.message.text
    if update.message.text == 'Round trip':
        context.chat_data['query'].round_trip = True
    update.message.reply_text(
        'We are almost done, I just need a couple more questions. '
        'From which date should I start looking for flights? (DD/MM/YYYY)'
    )
    return START_DATE


def start_date(update, context):
    context.chat_data['start_date'] = datetime.datetime.strptime(update.message.text, '%d/%m/%Y').date()
    context.chat_data['query'].start_date = context.chat_data['start_date']
    update.message.reply_text(
        'And when should I stop? (DD/MM/YYYY)'
    )
    return END_DATE


def end_date(update, context):
    context.chat_data['end_date'] = datetime.datetime.strptime(update.message.text, '%d/%m/%Y').date()
    context.chat_data['query'].end_date = context.chat_data['end_date']
    if context.chat_data['trip_type'] == 'One way':
        return finish_conversation(update, context)
    else:
        update.message.reply_text(
            f"What is the minimum number of days you would like to stay in {context.user_data['destination']}?"
        )
        return MIN_DAYS


def min_days(update, context):
    context.chat_data['min_days'] = int(update.message.text)
    context.chat_data['query'].min_days = context.chat_data['min_days']
    update.message.reply_text(
        'Just one more question... '
        'What is the maximum number of days you could be there?'
    )
    return MAX_DAYS


def max_days(update, context):
    context.chat_data['max_days'] = int(update.message.text)
    context.chat_data['query'].max_days = context.chat_data['max_days']
    return finish_conversation(update, context)


def finish_conversation(update, context):
    context.chat_data['query'].save()
    update.message.reply_text(
        'Alright, I think I have everything I needed. '
        'I will be back as soon as I find the best flights for you...'
    )
    answer = 'Here are the best 5 options I have found:\n\n'
    if context.chat_data['trip_type'] == 'One way':
        results = skyscanner.search_one_way(CONFIG, context.chat_data)
        answer += '\n'.join([
            f'{date}: for {price} on {airline}.'
            for date, price, airline, _ in results[:5]
        ])
    else:
        results = skyscanner.search_round_trip(CONFIG, context.chat_data)
        answer += '\n'.join([
            f'{date}: {days} days for {price} on {airline1}/{airline2}.'
            for date, days, price, airline1, airline2 in results[:5]
        ])
    update.message.reply_text(answer)
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    context.chat_data['query'].cancelled = True
    context.chat_data['query'].save()


def cancel(update, context):
    user = update.message.from_user
    context.chat_data['query'].cancelled = True
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! I hope we can talk again some day.',
                              reply_markup=ReplyKeyboardRemove())
    context.chat_data['query'].save()
    return ConversationHandler.END


def main():
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(CONFIG['telegram_api_key'], use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            ORIGIN: [MessageHandler(Filters.text, origin)],
            DESTINATION: [MessageHandler(Filters.text, destination)],
            TRIP_TYPE: [MessageHandler(Filters.regex('^(One way|Round trip)$'), trip_type)],
            START_DATE: [MessageHandler(Filters.text, start_date)],
            END_DATE: [MessageHandler(Filters.text, end_date)],
            MIN_DAYS: [MessageHandler(Filters.text, min_days)],
            MAX_DAYS: [MessageHandler(Filters.text, max_days)]
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    with open('config.json') as config:
        CONFIG = json.load(config)
        main()
