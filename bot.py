import datetime
import json
import logging
import threading

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler)

import model
from api.skyscanner import FlightQuery
from api.base import get_place

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

ORIGIN, DESTINATION, TRIP_TYPE, START_DATE, END_DATE, MIN_DAYS, MAX_DAYS = range(7)


def _remove_previous_task(update):
    if update.effective_user.id in TASKS:
        TASKS.pop(update.effective_user.id)
        update.message.reply_text('Your previous query has been cancelled.')


def _send_result_message(update, context):
    def report(direct, with_stops):
        direct = direct[:5]
        with_stops = with_stops[:5]
        if direct or with_stops:
            message = 'Here are the best options I have found:\n\n'
            flights = direct if direct else with_stops
            for f in flights:
                message += str(f) + '\n'
            message += '\nYou can go to https://www.skyscanner.com/ to confirm a reservation if you wish.'
        else:
            message = f"I am sorry, there are no flights from {context.chat_data['query'].origin} to " \
                      f"{context.chat_data['query'].destination} that meet the conditions you have specified. :'("
        update.message.reply_text(message)
        TASKS.pop(update.effective_user.id)
        context.chat_data['query'].results_date = datetime.datetime.now()
        context.chat_data['query'].save()
        logger.info('"%s" has received the result.', update.effective_user.full_name)

    return report


def _validate_date(update):
    try:
        date = update.message.text
        date = date.replace('-', '/')
        date = datetime.datetime.strptime(date, '%d/%m/%Y').date()
    except ValueError:
        update.message.reply_text(
            f'{update.message.text} is not a valid date. '
            'Please be careful and try again...'
        )
        return None
    if date < datetime.datetime.now().date():
        update.message.reply_text(
            'The date you have provided is in the past. '
            'I am not a magician! '
            'Please be careful and try again with a date from the future...'
        )
        return None
    if date > datetime.date.today() + datetime.timedelta(days=365):
        update.message.reply_text(
            'The date you have provided is too far in the future. '
            'I am not a magician! '
            'Please be careful and try again with a date closer than a year from today...'
        )
        return None
    return date


def _validate_integer(update, end_date):
    try:
        n = int(update.message.text)
    except ValueError:
        update.message.reply_text(
            f'{update.message.text} is not a valid number of days. '
            'Please be careful and try again...'
        )
        return None
    if n <= 0:
        update.message.reply_text(
            'You have to specify a positive number of days. '
            'Please be careful and try again...'
        )
        return None
    if end_date + n > datetime.date.today() + datetime.timedelta(days=365):
        update.message.reply_text(
            'Flights that far from today have not been scheduled yet. '
            'Please try again with less days...'
        )
        return None
    return n


def start(update, context):
    logger.info('Received /start from "%s".', update.effective_user.full_name)
    if update.effective_user.id in TASKS:
        update.message.reply_text('Please wait until your previous query finishes.')
        return ConversationHandler.END
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
    origin_code = get_place(CONFIG['x-rapidapi-keys'][0], update.message.text)
    if not origin_code:
        update.message.reply_text(
            'It seems like you made a mistake spelling it or there are no flights from a city named '
            f'{update.message.text}. '
            'Try again with a different origin...'
        )
        return ORIGIN
    context.chat_data['origin'] = origin_code
    context.chat_data['query'].origin = update.message.text
    update.message.reply_text(
        f'I have heard {update.message.text} is a very nice place! '
        'Where are you going to?'
    )
    return DESTINATION


def destination(update, context):
    destination_code = get_place(CONFIG['x-rapidapi-keys'][0], update.message.text)
    if not destination_code:
        update.message.reply_text(
            'It seems like you made a mistake spelling it or there are no flights from a city named '
            f'{update.message.text}. '
            'Try again with a different destination...'
        )
        return DESTINATION
    if destination_code == context.chat_data['origin']:
        update.message.reply_text(
            f'Your origin and destination cannot be both {update.message.text}! '
            'Try again with a different destination...'
        )
        return DESTINATION
    context.chat_data['destination'] = destination_code
    context.chat_data['query'].destination = update.message.text
    reply_keyboard = [['Round trip', 'One way']]
    update.message.reply_text(
        f'I would like to go to {update.message.text} as well! '
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
    date = _validate_date(update)
    if not date:
        return START_DATE
    context.chat_data['start_date'] = date
    context.chat_data['query'].start_date = context.chat_data['start_date']
    update.message.reply_text(
        'And when should I stop? (DD/MM/YYYY)'
    )
    return END_DATE


def end_date(update, context):
    date = _validate_date(update)
    if not date:
        return END_DATE
    if date < context.chat_data['start_date']:
        update.message.reply_text(
            f'You must set a date after the one you set before {context.chat_data["start_date"].strftime("%d/%m/%Y")}. '
            'Please try again...'
        )
        return END_DATE
    if (date - context.chat_data['start_date']).days > 60:
        update.message.reply_text(
            'That range of dates for search is too broad. '
            'Please, set a date with less than 60 days of difference with one you set before '
            f'({context.chat_data["start_date"]})...'
        )
        return END_DATE
    context.chat_data['end_date'] = date
    context.chat_data['query'].end_date = context.chat_data['end_date']
    if context.chat_data['trip_type'] == 'One way':
        return finish_conversation(update, context)
    else:
        update.message.reply_text(
            f"What is the minimum number of days you would like to stay in {context.chat_data['query'].destination}?"
        )
        return MIN_DAYS


def min_days(update, context):
    days = _validate_integer(update, context.chat_data['end_date'])
    if not days:
        return MIN_DAYS
    context.chat_data['min_days'] = days
    context.chat_data['query'].min_days = context.chat_data['min_days']
    update.message.reply_text(
        'Just one more question... '
        'What is the maximum number of days you could be there?'
    )
    return MAX_DAYS


def max_days(update, context):
    days = _validate_integer(update, context.chat_data['end_date'])
    if not days:
        return MAX_DAYS
    if days < context.chat_data['min_days']:
        update.message.reply_text(
            'You have to set a maximum number of days greater or equal than the minimum you set before '
            f"({context.chat_data['min_days']}). "
            'Please, set a maximum of days with less than 30 days of difference with the minimum...'
        )
        return MAX_DAYS
    if days - context.chat_data['min_days'] > 30:
        update.message.reply_text(
            'That range of days for search is too broad. '
            'Please, set a maximum of days with less than 30 days of difference with the minimum...'
        )
        return MAX_DAYS
    context.chat_data['max_days'] = days
    context.chat_data['query'].max_days = context.chat_data['max_days']
    return finish_conversation(update, context)


def finish_conversation(update, context):
    context.chat_data['query'].save()
    update.message.reply_text(
        'Alright, I think I have everything I needed. '
        'I will be back as soon as I find the best flights for you...'
    )
    fq = FlightQuery(
        CONFIG,
        context.chat_data,
        _send_result_message(update, context)
    )
    t = threading.Thread(target=fq.execute)
    t.start()
    TASKS[update.effective_user.id] = t
    logger.info('Completed query for "%s".', update.effective_user.full_name)
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    _remove_previous_task(update)
    context.chat_data['query'].cancelled = True
    context.chat_data['query'].save()


def cancel(update, context):
    user = update.message.from_user
    context.chat_data['query'].cancelled = True
    _remove_previous_task(update)
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
    TASKS = {}
    with open('config.json') as config:
        CONFIG = json.load(config)
        main()
