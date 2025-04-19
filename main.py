import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime
import schedule
import time
import threading

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize user data
user_data = {}

# Start function to send the initial message
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "👋 Hello! I'm your list management bot.\n"
        "Here are the available commands:\n"
        "/start - Start chatting with the bot.\n"
        "/setdate - Set a date to start counting days (format: YYYY-MM-DD).\n"
        "/checkdays - Check how many days have passed since the set date.\n"
        "/lists - Manage your lists.\n"
        "/like_dislike - Manage liked/disliked items.\n"
        "/reminder - Toggle daily reminders.\n"
        "/categories - Manage categories."
    )

# Command to set the date
def setdate(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    try:
        date_str = context.args[0]
        user_data[user_id] = {
            "start_date": datetime.strptime(date_str, "%Y-%m-%d"),
            "notified": False,
            "reminders_enabled": False,
            "lists": {},
            "liked": [],
            "disliked": [],
            "categories": set()  # Store categories as a set
        }
        update.message.reply_text(f"📅 Date set to {date_str}. I'll start counting days from this date.")
        schedule_daily_reminder(user_id)
    except (IndexError, ValueError):
        update.message.reply_text("❌ Please use the format: /setdate YYYY-MM-DD.")

# Function to schedule daily reminders
def schedule_daily_reminder(user_id):
    if user_id in user_data and user_data[user_id]["reminders_enabled"]:
        schedule.every().day.at("09:00").do(send_reminder, user_id)

def send_reminder(user_id):
    if user_id in user_data:
        start_date = user_data[user_id]["start_date"]
        days_passed = (datetime.now() - start_date).days
        message = f"🗓️ It's been {days_passed} days since you set the date."
        context.bot.send_message(chat_id=user_id, text=message)

# Command to check days
def checkdays(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in user_data:
        start_date = user_data[user_id]["start_date"]
        days_passed = (datetime.now() - start_date).days
        update.message.reply_text(f"🗓️ It has been {days_passed} days since you set the date.")
    else:
        update.message.reply_text("❌ No date set. Please use /setdate.")

# Command to manage lists and categories
def lists(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Add Item", callback_data='add_item')],
        [InlineKeyboardButton("View All Items", callback_data='view_all')],
        [InlineKeyboardButton("View Liked Items", callback_data='view_liked')],
        [InlineKeyboardButton("Manage Categories", callback_data='manage_categories')],
        [InlineKeyboardButton("Split Categories", callback_data='split_categories')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("📋 Manage your lists:", reply_markup=reply_markup)

# Handle button presses
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    if query.data == 'add_item':
        context.bot.send_message(chat_id=user_id, text="Please send the item name and category (e.g., Vampire: Dracula).")
        context.user_data['awaiting_item'] = True
    elif query.data == 'view_all':
        items = user_data[user_id].get("lists", {})
        message = "🗂️ All Items:\n" + "\n".join(f"{category}: {', '.join(items[category])}" for category in items) if items else "❌ No items found."
        query.edit_message_text(text=message)
    elif query.data == 'view_liked':
        liked_items = user_data[user_id].get("liked", [])
        message = "❤️ Liked Items:\n" + "\n".join(liked_items) if liked_items else "❌ No liked items."
        query.edit_message_text(text=message)
    elif query.data == 'manage_categories':
        context.bot.send_message(chat_id=user_id, text="Please send the category name to add or type /view_categories to see existing categories.")
        context.user_data['awaiting_category'] = True
    elif query.data == 'split_categories':
        context.bot.send_message(chat_id=user_id, text="Please provide the name of the category you want to split.")
        context.user_data['awaiting_split_category'] = True

# Command to handle received messages
def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in user_data and context.user_data.get('awaiting_item'):
        item_info = update.message.text.split(":")
        if len(item_info) == 2:
            category = item_info[0].strip()
            item_name = item_info[1].strip()

            if category not in user_data[user_id]["lists"]:
                user_data[user_id]["lists"][category] = []
            user_data[user_id]["lists"][category].append(item_name)

            update.message.reply_text(f"✅ Item '{item_name}' added to category '{category}'!")
            context.user_data['awaiting_item'] = False
        else:
            update.message.reply_text("❌ Please use the format: Category: Item Name.")
    elif user_id in user_data and context.user_data.get('awaiting_category'):
        category_name = update.message.text.strip()
        user_data[user_id]["categories"].add(category_name)
        update.message.reply_text(f"✅ Category '{category_name}' added!")
        context.user_data['awaiting_category'] = False
    elif user_id in user_data and context.user_data.get('awaiting_split_category'):
        category_name = update.message.text.strip()
        if category_name in user_data[user_id]["lists"]:
            new_category_name = f"{category_name}_split"
            user_data[user_id]["lists"][new_category_name] = user_data[user_id]["lists"].pop(category_name)
            update.message.reply_text(f"✅ Category '{category_name}' has been split into '{new_category_name}'!")
        else:
            update.message.reply_text(f"❌ Category '{category_name}' does not exist.")
        context.user_data['awaiting_split_category'] = False

# Command to toggle like/dislike
def like_dislike(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        update.message.reply_text("❌ No items available. Please add items first.")
        return

    keyboard = [
        [InlineKeyboardButton("Like Item", callback_data='like')],
        [InlineKeyboardButton("Dislike Item", callback_data='dislike')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("❤️ Choose an action:", reply_markup=reply_markup)

# Handle like/dislike button presses
def handle_like_dislike(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    if query.data == 'like':
        context.bot.send_message(chat_id=user_id, text="Please send the name of the item you want to like.")
        context.user_data['awaiting_like'] = True
    elif query.data == 'dislike':
        context.bot.send_message(chat_id=user_id, text="Please send the name of the item you want to dislike.")
        context.user_data['awaiting_dislike'] = True

# Command to handle liked/disliked items
def handle_like_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    item_name = update.message.text.strip()

    if user_id in user_data and context.user_data.get('awaiting_like'):
        user_data[user_id]['liked'].append(item_name)
        update.message.reply_text(f"❤️ You liked '{item_name}'!")
        context.user_data['awaiting_like'] = False
    elif user_id in user_data and context.user_data.get('awaiting_dislike'):
        user_data[user_id]['disliked'].append(item_name)
        update.message.reply_text(f"👎 You disliked '{item_name}'!")
        context.user_data['awaiting_dislike'] = False

# Command to toggle daily reminders
def reminder(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        update.message.reply_text("❌ No date set. Please use /setdate first.")
        return

    user_data[user_id]["reminders_enabled"] = not user_data[user_id]["reminders_enabled"]
    status = "enabled" if user_data[user_id]["reminders_enabled"] else "disabled"
    
    if status == "enabled":
        schedule_daily_reminder(user_id)
    
    update.message.reply_text(f"🔔 Daily reminders have been {status}.")

# Function to run the scheduler in a separate thread
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Main function
def main() -> None:
    # Replace 'YOUR_TOKEN' with your bot token
    updater = Updater("YOUR_TOKEN")

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("setdate", setdate))
    dispatcher.add_handler(CommandHandler("checkdays", checkdays))
    dispatcher.add_handler(CommandHandler("lists", lists))
    dispatcher.add_handler(CommandHandler("like_dislike", like_dislike))
    dispatcher.add_handler(CommandHandler("reminder", reminder))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_like_message))

    updater.start_polling()

    # Start the scheduler thread
    threading.Thread(target=run_scheduler, daemon=True).start()

    updater.idle()

if __name__ == '__main__':
    main()
