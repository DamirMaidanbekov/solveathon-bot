import telebot
import json
import os
import threading
from datetime import datetime
from typing import Dict, List
import time

# Load configuration
try:
    from config import BOT_TOKEN, USERS_DB_FILE, BROADCAST_SCHEDULE, ALARM_CHECK_INTERVAL
except ImportError:
    print("❌ Error: config.py not found!")
    print("Please copy config_example.py to config.py and add your BOT_TOKEN")
    exit(1)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Database management
class Database:
    """Database for storing users"""
    
    @staticmethod
    def load_users() -> Dict:
        """Load users from JSON file"""
        if os.path.exists(USERS_DB_FILE):
            try:
                with open(USERS_DB_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def save_users(users: Dict):
        """Save users to JSON file"""
        with open(USERS_DB_FILE, 'w') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def add_user(user_id: int, username: str = ""):
        """Add or update user in database"""
        users = Database.load_users()
        users[str(user_id)] = {
            "user_id": user_id,
            "username": username,
            "registered_at": datetime.now().isoformat(),
            "active": True
        }
        Database.save_users(users)
        print(f"✅ User {user_id} ({username}) registered")
    
    @staticmethod
    def get_all_user_ids() -> List[int]:
        """Get all registered user IDs"""
        users = Database.load_users()
        return [int(uid) for uid in users.keys() if users[uid].get("active", True)]

# Broadcast manager
class BroadcastManager:
    """Background task for sending scheduled messages to all users"""
    
    def __init__(self, schedule: Dict[str, str]):
        self.schedule = schedule  # {HH:MM or YYYY-MM-DD HH:MM: message}
        self.running = False
        self.sent_times = set()  # Track which times we've already sent daily messages
        self.sent_dates = set()  # Track which date+time combos we've already sent
    
    def start(self):
        """Start broadcast manager in background thread"""
        if not self.running:
            self.running = True
            thread = threading.Thread(target=self._check_loop, daemon=True)
            thread.start()
            print("✅ Broadcast manager started")
            print(f"📋 Schedule: {list(self.schedule.keys())}")
    
    def stop(self):
        """Stop broadcast manager"""
        self.running = False
        print("❌ Broadcast manager stopped")
    
    def _check_loop(self):
        """Main loop for checking scheduled messages"""
        while self.running:
            try:
                self._check_broadcasts()
                time.sleep(ALARM_CHECK_INTERVAL)
            except Exception as e:
                print(f"Error in broadcast check loop: {e}")
                time.sleep(5)
    
    def _check_broadcasts(self):
        """Check if any broadcasts should be sent"""
        current_time = datetime.now().strftime("%H:%M")
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for schedule_key, message in self.schedule.items():
            # Check for specific date+time (YYYY-MM-DD HH:MM)
            if len(schedule_key) == 16 and ' ' in schedule_key:  # "YYYY-MM-DD HH:MM"
                if schedule_key == current_datetime and schedule_key not in self.sent_dates:
                    self._send_to_all_users(message, schedule_key)
                    self.sent_dates.add(schedule_key)
            # Check for daily time (HH:MM)
            elif len(schedule_key) == 5 and ':' in schedule_key:  # "HH:MM"
                if schedule_key == current_time and schedule_key not in self.sent_times:
                    self._send_to_all_users(message, schedule_key)
                    self.sent_times.add(schedule_key)
        
        # Clean up sent_times if time has passed (reset at midnight)
        if datetime.now().strftime("%H:%M") == "00:00":
            self.sent_times.clear()
    
    def _send_to_all_users(self, message: str, send_time: str):
        """Send message to all registered users"""
        user_ids = Database.get_all_user_ids()
        
        if not user_ids:
            print(f"⚠️  No active users to send broadcast at {send_time}")
            return
        
        sent_count = 0
        failed_count = 0
        
        print(f"📢 Broadcasting at {send_time} to {len(user_ids)} users...")
        
        for uid in user_ids:
            try:
                bot.send_message(uid, message)
                sent_count += 1
            except Exception as e:
                print(f"❌ Error sending to user {uid}: {e}")
                failed_count += 1
        
        print(f"✅ Broadcast completed: {sent_count} sent, {failed_count} failed")

# Initialize broadcast manager
broadcast_manager = BroadcastManager(BROADCAST_SCHEDULE)

# Bot handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "User"
    
    # Register user
    Database.add_user(user_id, username)
    
    # Start broadcast manager if not running
    if not broadcast_manager.running:
        broadcast_manager.start()
    
    welcome_text = """🤖 Добро пожаловать в рассылка-бота!

Я буду отправлять тебе сообщения по расписанию.

Команды:
/schedule - Показать расписание сообщений
/help - Помощь"""
    
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def send_help(message):
    """Handle /help command"""
    help_text = f"""📖 Справка:

/start - Начать работу с ботом
/schedule - Показать расписание рассылки
/help - Эта справка

Интервал проверки: {ALARM_CHECK_INTERVAL}с
Время проверяется по текущему времени сервера."""
    
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['schedule'])
def show_schedule(message):
    """Show broadcast schedule"""
    if not BROADCAST_SCHEDULE:
        bot.reply_to(message, "📭 Расписание пусто")
        return
    
    schedule_text = "📋 Расписание рассылки:\n\n"
    for time_str in sorted(BROADCAST_SCHEDULE.keys()):
        msg = BROADCAST_SCHEDULE[time_str]
        schedule_text += f"⏰ {time_str}\n{msg}\n\n"
    
    bot.reply_to(message, schedule_text)

@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    """Handle any other message"""
    bot.reply_to(message, 
        "👋 Привет! Используй /help для списка команд")

# Main execution
if __name__ == "__main__":
    print("🚀 Запуск рассылка-бота...")
    print(f"📅 Расписание: {BROADCAST_SCHEDULE}")
    
    # Start broadcast manager
    broadcast_manager.start()
    
    # Start polling
    try:
        print("✅ Бот запущен и готов к работе!")
        print("Нажмите Ctrl+C для остановки")
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        broadcast_manager.stop()
        bot.stop_polling()
        print("✅ Бот остановлен")
