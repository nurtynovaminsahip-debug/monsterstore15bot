import os
import random
import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
import db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ── Состояние пользователей (в памяти) ────────────────
# { user_id: {"action": str, "data": dict} }
user_states = {}

def get_state(uid):
    return user_states.get(uid, {"action": "none", "data": {}})

def set_state(uid, action, data=None):
    user_states[uid] = {"action": action, "data": data or {}}

def clear_state(uid):
    user_states[uid] = {"action": "none", "data": {}}


# ── Клавиатуры ─────────────────────────────────────────
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛒Купить", "👤Профиль")
    kb.row("💼Проект", "🆘Помощь")
    kb.row("🤝Сотрудничество", "🎲Мини-игры")
    return kb

def profile_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💰Пополнить", callback_data="topup"))
    kb.add(types.InlineKeyboardButton("📜История покупок", callback_data="purchase_history"))
    return kb

def admin_panel_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎁Добавить товар", callback_data="admin_add_product"))
    kb.add(types.InlineKeyboardButton("➕Добавить администратора", callback_data="admin_add_admin"))
    kb.add(types.InlineKeyboardButton("🗂Список администраторов", callback_data="admin_list_admins"))
    kb.add(types.InlineKeyboardButton("❌Удалить товар", callback_data="admin_delete_product"))
    kb.add(types.InlineKeyboardButton("🧨Снять администратора", callback_data="admin_remove_admin"))
    return kb

def minigames_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎲 Бросить кубик", callback_data="game_dice"))
    kb.add(types.InlineKeyboardButton("🪙 Орёл или решка", callback_data="game_coin"))
    kb.add(types.InlineKeyboardButton("🔢 Угадай число (1-10)", callback_data="game_number"))
    return kb

def order_admin_keyboard(order_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅Подтвердить заказ", callback_data=f"confirm_order:{order_id}"))
    kb.add(types.InlineKeyboardButton("❌Отклонить заказ", callback_data=f"reject_order:{order_id}"))
    return kb

def topup_admin_keyboard(topup_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅Зачислить сумму", callback_data=f"approve_topup:{topup_id}"))
    kb.add(types.InlineKeyboardButton("❌Отклонить заявку", callback_data=f"reject_topup:{topup_id}"))
    return kb

def pay_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💳Оплатить", url="https://t.me/monsterban15"))
    return kb


# ── Вспомогательные функции ────────────────────────────
def moscow_time():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    return datetime.datetime.now(tz).strftime("%H:%M:%S  %d.%m.%Y")

def notify_all_admins(text, keyboard=None):
    """Отправляет сообщение всем администраторам. Возвращает (chat_id, message_id) первого."""
    result = None
    for admin in db.get_all_admins():
        try:
            sent = bot.send_message(admin["telegram_id"], text, reply_markup=keyboard)
            if result is None:
                result = (admin["telegram_id"], sent.message_id)
        except Exception as e:
            print(f"[WARN] Не удалось уведомить админа {admin['telegram_id']}: {e}")
    return result

def user_tag(message):
    un = message.from_user.username
    uid = message.from_user.id
    return (f"@{un}", uid) if un else (f"ID:{uid}", uid)


# ── /start ─────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    uid = msg.from_user.id
    clear_state(uid)
    db.get_or_create_user(uid, msg.from_user.username)
    bot.send_message(uid, "👋Добро пожаловать в MonsterStore15!", reply_markup=main_keyboard())


# ── /console (Админ-панель) ────────────────────────────
@bot.message_handler(commands=["console"])
def cmd_console(msg):
    uid = msg.from_user.id
    if not db.is_admin(uid):
        bot.send_message(uid, "❌ У вас нет доступа к админ-панели.")
        return
    clear_state(uid)
    bot.send_message(
        uid,
        f"🔐Админ панель\n"
        f"- - - - - - - - - - - - - - - - - - - - - - - - - -\n"
        f"🤖Состояние бота: ✅ Включён\n"
        f"⌛️Время: {moscow_time()}",
        reply_markup=admin_panel_keyboard()
    )


# ── 👤 Профиль ─────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "👤Профиль")
def handle_profile(msg):
    uid = msg.from_user.id
    clear_state(uid)
    user = db.get_or_create_user(uid, msg.from_user.username)
    bot.send_message(
        uid,
        f"👤Ваш профиль:\n\n"
        f"🆔TG ID: {uid}\n\n"
        f"🛒Кол-во покупок: {user['purchases_count']}\n\n"
        f"💰Баланс: {user['balance']} руб.",
        reply_markup=profile_keyboard()
    )


# ── 🛒 Купить ──────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🛒Купить")
def handle_buy(msg):
    uid = msg.from_user.id
    clear_state(uid)
    products = db.get_all_products()
    if not products:
        bot.send_message(uid, "😔 Товаров пока нет. Загляните позже!")
        return
    kb = types.InlineKeyboardMarkup()
    for p in products:
        kb.add(types.InlineKeyboardButton(
            f"{p['name']} — {p['price']} руб.",
            callback_data=f"buy_product:{p['id']}"
        ))
    bot.send_message(uid, "🛒 Выберите товар:", reply_markup=kb)


# ── 💼 Проект ──────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "💼Проект")
def handle_project(msg):
    clear_state(msg.from_user.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📒Проект", url="https://t.me/MonsterStoreNovostnik"))
    bot.send_message(msg.from_user.id, "💼Наш проект:", reply_markup=kb)


# ── 🆘 Помощь ──────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🆘Помощь")
def handle_help(msg):
    uid = msg.from_user.id
    set_state(uid, "awaiting_help_message")
    bot.send_message(uid, "❗️Напишите ваш вопрос или проблему, и поддержка ответит вам в ближайшее время")


# ── 🤝 Сотрудничество ─────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🤝Сотрудничество")
def handle_collab(msg):
    clear_state(msg.from_user.id)
    bot.send_message(msg.from_user.id, "🤝Для сотрудничества напишите @MonsterStore15helper")


# ── 🎲 Мини-игры ──────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "🎲Мини-игры")
def handle_games(msg):
    clear_state(msg.from_user.id)
    bot.send_message(msg.from_user.id, "🎮 Добро пожаловать в мини-игры!\nВыберите игру:", reply_markup=minigames_keyboard())


# ── Callback-кнопки ────────────────────────────────────
@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    uid = call.from_user.id
    data = call.data
    bot.answer_callback_query(call.id)

    # ── Профиль ──
    if data == "topup":
        set_state(uid, "awaiting_topup_amount")
        bot.send_message(uid, "⭐️Введите сумму пополнения в рублях цифрами:")

    elif data == "purchase_history":
        history = db.get_purchase_history(uid)
        if not history:
            bot.send_message(uid, "📭 История покупок пуста.")
        else:
            lines = "\n".join(f"{i+1}. {h['product_name']} — {h['price']} руб." for i, h in enumerate(history))
            bot.send_message(uid, f"📜 История покупок:\n\n{lines}")

    # ── Выбор товара ──
    elif data.startswith("buy_product:"):
        product_id = int(data.split(":")[1])
        product = db.get_product_by_id(product_id)
        if not product:
            bot.send_message(uid, "❌ Товар не найден.")
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳Оплатить", callback_data=f"place_order:{product['id']}"))
        bot.send_message(
            uid,
            f"⭐️Товар: {product['name']}\n"
            f"💰Стоимость: {product['price']} руб.\n\n"
            f"✅Описание: {product['description']}\n"
            f"❗️Оплатите товар по ссылке ниже и отправьте чек в раздел Помощь, "
            f"продавец выдаст товар и подтвердит заказ.",
            reply_markup=kb
        )

    elif data.startswith("place_order:"):
        product_id = int(data.split(":")[1])
        product = db.get_product_by_id(product_id)
        if not product:
            bot.send_message(uid, "❌ Товар не найден.")
            return
        order = db.create_order(uid, product["name"], product["price"])
        un = call.from_user.username
        tag = f"@{un}" if un else f"ID:{uid}"
        admin_text = (
            f"📋Новый заказ! #{order['order_ref']}\n"
            f"🆔{tag} и ID пользователя: {tag} и {uid}\n"
            f"🔑Цена: {product['price']} руб.\n"
            f"🛒Товар: {product['name']}"
        )
        sent = notify_all_admins(admin_text, order_admin_keyboard(order["id"]))
        if sent:
            db.update_order_status(order["id"], "pending", sent[1], sent[0])
        bot.send_message(
            uid,
            "✅ Заказ оформлен! Администратор уведомлён.\n\n❗️Для оплаты нажмите кнопку ниже:",
            reply_markup=pay_keyboard()
        )

    # ── Подтвердить/отклонить заказ (для админа) ──
    elif data.startswith("confirm_order:"):
        if not db.is_admin(uid):
            return
        order_id = int(data.split(":")[1])
        order = db.get_order(order_id)
        if not order or order["status"] != "pending":
            bot.send_message(uid, "⚠️ Заказ уже обработан или не найден.")
            return
        db.update_order_status(order_id, "confirmed")
        db.increment_purchases(order["user_telegram_id"])
        db.add_purchase_history(order["user_telegram_id"], order["product_name"], order["price"])
        try:
            bot.send_message(order["user_telegram_id"],
                "✅Заказ выдан и успешно подтвержден администратором. Проверьте получение. Благодарим за покупку!")
        except Exception as e:
            print(f"[WARN] Не удалось уведомить покупателя: {e}")
        bot.edit_message_text(f"✅ Заказ #{order['order_ref']} подтверждён.", uid, call.message.message_id)

    elif data.startswith("reject_order:"):
        if not db.is_admin(uid):
            return
        order_id = int(data.split(":")[1])
        order = db.get_order(order_id)
        if not order or order["status"] != "pending":
            bot.send_message(uid, "⚠️ Заказ уже обработан или не найден.")
            return
        db.update_order_status(order_id, "rejected")
        try:
            bot.send_message(order["user_telegram_id"],
                "❌Заказ отклонен. Это может быть потому что вы не оплатили заказ. В другом случае, обратитесь в поддержку.")
        except Exception as e:
            print(f"[WARN] Не удалось уведомить покупателя: {e}")
        bot.edit_message_text(f"❌ Заказ #{order['order_ref']} отклонён.", uid, call.message.message_id)

    # ── Одобрить/отклонить пополнение (для админа) ──
    elif data.startswith("approve_topup:"):
        if not db.is_admin(uid):
            return
        topup_id = int(data.split(":")[1])
        req = db.get_topup(topup_id)
        if not req or req["status"] != "pending":
            bot.send_message(uid, "⚠️ Заявка уже обработана или не найдена.")
            return
        db.update_topup_status(topup_id, "approved")
        db.update_balance(req["user_telegram_id"], req["amount"])
        user = db.get_user(req["user_telegram_id"])
        new_balance = user["balance"] if user else req["amount"]
        try:
            bot.send_message(req["user_telegram_id"],
                f"✅ Ваш баланс успешно пополнен на {req['amount']} руб.\n"
                f"💰Текущий баланс: {new_balance} руб.")
        except Exception as e:
            print(f"[WARN] Не удалось уведомить пользователя: {e}")
        bot.edit_message_text(
            f"✅ Пополнение #{req['request_ref']} на {req['amount']} руб. зачислено.",
            uid, call.message.message_id
        )

    elif data.startswith("reject_topup:"):
        if not db.is_admin(uid):
            return
        topup_id = int(data.split(":")[1])
        req = db.get_topup(topup_id)
        if not req or req["status"] != "pending":
            bot.send_message(uid, "⚠️ Заявка уже обработана или не найдена.")
            return
        db.update_topup_status(topup_id, "rejected")
        try:
            bot.send_message(req["user_telegram_id"],
                f"❌ Ваша заявка на пополнение #{req['request_ref']} отклонена. Обратитесь в поддержку.")
        except Exception as e:
            print(f"[WARN] Не удалось уведомить пользователя: {e}")
        bot.edit_message_text(
            f"❌ Пополнение #{req['request_ref']} отклонено.",
            uid, call.message.message_id
        )

    # ── Админ-панель ──
    elif data == "admin_add_product":
        if not db.is_admin(uid):
            return
        set_state(uid, "awaiting_add_product")
        bot.send_message(uid,
            "✍️Введите сообщение в формате:\n"
            "Название товара - цена - описание товара\n\n"
            "Пример: Аккаунт Steam - 500 - Премиум аккаунт с играми")

    elif data == "admin_add_admin":
        if not db.is_admin(uid):
            return
        set_state(uid, "awaiting_add_admin")
        bot.send_message(uid, "🆔Введите TG ID администратора, которого вы хотите добавить:")

    elif data == "admin_list_admins":
        if not db.is_admin(uid):
            return
        admins = db.get_all_admins()
        if not admins:
            bot.send_message(uid, "👤 Список администраторов пуст.")
        else:
            lines = "\n".join(f"🆔Администратор {i+1}: {a['telegram_id']}" for i, a in enumerate(admins))
            bot.send_message(uid, f"👤Список администраторов:\n\n{lines}")

    elif data == "admin_delete_product":
        if not db.is_admin(uid):
            return
        set_state(uid, "awaiting_delete_product")
        bot.send_message(uid, "✏️Введите название товара без опечаток, которое вы хотите удалить:")

    elif data == "admin_remove_admin":
        if not db.is_admin(uid):
            return
        set_state(uid, "awaiting_remove_admin")
        bot.send_message(uid, "✏️🆔Введите Telegram ID администратора (цифрами), которого вы хотите снять:")

    # ── Мини-игры ──
    elif data == "game_dice":
        roll = random.randint(1, 6)
        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣"]
        bot.send_message(uid, f"🎲 Вы бросили кубик!\n\nРезультат: {emojis[roll-1]} ({roll})",
                         reply_markup=minigames_keyboard())

    elif data == "game_coin":
        result = "🦅 Орёл!" if random.random() < 0.5 else "🔵 Решка!"
        bot.send_message(uid, f"🪙 Подброшена монетка...\n\n{result}", reply_markup=minigames_keyboard())

    elif data == "game_number":
        secret = random.randint(1, 10)
        set_state(uid, "awaiting_number_guess", {"secret": secret, "attempts": 3})
        bot.send_message(uid, "🔢 Я загадал число от 1 до 10.\nУ вас 3 попытки. Введите своё число:")


# ── Текстовые сообщения (обработка состояний) ──────────
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(msg):
    uid = msg.from_user.id
    text = msg.text.strip()
    state = get_state(uid)
    action = state["action"]

    db.get_or_create_user(uid, msg.from_user.username)

    # ── Ожидание суммы пополнения ──
    if action == "awaiting_topup_amount":
        if not text.isdigit() or int(text) <= 0:
            bot.send_message(uid, "❌ Введите корректную сумму цифрами (например: 500)")
            return
        amount = int(text)
        clear_state(uid)
        un = msg.from_user.username
        tag = f"@{un}" if un else f"ID:{uid}"
        req = db.create_topup(uid, un, amount)
        admin_text = (
            f"📋Пополнение #{req['request_ref']}\n"
            f"🆔{tag} и ID пользователя: {tag} и {uid}\n"
            f"🔑Сумма: {amount} руб."
        )
        sent = notify_all_admins(admin_text, topup_admin_keyboard(req["id"]))
        if sent:
            db.update_topup_status(req["id"], "pending", sent[1], sent[0])
        bot.send_message(uid,
            "❗️Для пополнения нажмите Оплатить и напишите администратору к которому вас переведет кнопка",
            reply_markup=pay_keyboard())

    # ── Ожидание обращения в поддержку ──
    elif action == "awaiting_help_message":
        clear_state(uid)
        un = msg.from_user.username
        tag = f"@{un}" if un else f"ID:{uid}"
        ticket = db.create_support_ticket(uid, un, text)
        admin_text = (
            f"📩 Обращение в поддержку от {tag} (ID: {uid}):\n\n{text}\n\n"
            f"💬 Ответьте на это сообщение, чтобы ответить пользователю."
        )
        sent = notify_all_admins(admin_text)
        if sent:
            db.update_support_ticket(ticket["id"], sent[1], sent[0])
        bot.send_message(uid, "✅ Ваше обращение отправлено. Поддержка ответит вам в ближайшее время.")

    # ── Угадай число ──
    elif action == "awaiting_number_guess":
        if not text.isdigit() or not (1 <= int(text) <= 10):
            bot.send_message(uid, "❌ Введите число от 1 до 10.")
            return
        guess = int(text)
        secret = state["data"]["secret"]
        attempts = state["data"]["attempts"] - 1
        if guess == secret:
            clear_state(uid)
            bot.send_message(uid, f"🎉 Правильно! Загаданное число — {secret}.", reply_markup=minigames_keyboard())
        elif attempts <= 0:
            clear_state(uid)
            bot.send_message(uid, f"😔 Попытки закончились! Загаданное число было — {secret}.", reply_markup=minigames_keyboard())
        else:
            hint = "🔼 Загаданное число больше" if guess < secret else "🔽 Загаданное число меньше"
            set_state(uid, "awaiting_number_guess", {"secret": secret, "attempts": attempts})
            bot.send_message(uid, f"{hint}. Осталось попыток: {attempts}")

    # ── Добавить товар (админ) ──
    elif action == "awaiting_add_product" and db.is_admin(uid):
        clear_state(uid)
        parts = text.split(" - ", 2)
        if len(parts) < 3:
            bot.send_message(uid, "❌ Неверный формат. Используйте:\nНазвание - цена - описание")
            return
        name, price_str, description = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not price_str.isdigit() or int(price_str) <= 0:
            bot.send_message(uid, "❌ Цена должна быть числом больше 0.")
            return
        db.add_product(name, int(price_str), description)
        bot.send_message(uid, f'✅ Товар "{name}" успешно добавлен!')

    # ── Добавить администратора ──
    elif action == "awaiting_add_admin" and db.is_admin(uid):
        clear_state(uid)
        if not text.isdigit():
            bot.send_message(uid, "❌ Введите корректный Telegram ID (только цифры).")
            return
        new_id = int(text)
        if not db.add_admin(new_id):
            bot.send_message(uid, "⚠️ Этот пользователь уже является администратором.")
            return
        bot.send_message(uid, "🔑Новый администратор успешно добавлен!")
        try:
            bot.send_message(new_id,
                "🔐 Вы были назначены администратором в MonsterStore15!\n"
                "Используйте /console для доступа к панели.")
        except Exception:
            pass

    # ── Снять администратора ──
    elif action == "awaiting_remove_admin" and db.is_admin(uid):
        clear_state(uid)
        if not text.isdigit():
            bot.send_message(uid, "❌ Введите корректный Telegram ID (только цифры).")
            return
        remove_id = int(text)
        if remove_id == ADMIN_ID:
            bot.send_message(uid, "❌ Нельзя снять главного администратора.")
            return
        if not db.remove_admin(remove_id):
            bot.send_message(uid, "⚠️ Администратор с таким ID не найден.")
            return
        bot.send_message(uid, "✅ Администратор успешно снят.")

    # ── Удалить товар ──
    elif action == "awaiting_delete_product" and db.is_admin(uid):
        clear_state(uid)
        if not db.delete_product(text):
            bot.send_message(uid, f'⚠️ Товар "{text}" не найден. Проверьте название.')
            return
        bot.send_message(uid, "📝Товар успешно удален!")

    # ── Ответ поддержки (реплай на тикет) ──
    elif db.is_admin(uid) and msg.reply_to_message:
        replied_id = msg.reply_to_message.message_id
        ticket = db.get_ticket_by_admin_msg(replied_id)
        if ticket:
            try:
                bot.send_message(ticket["user_telegram_id"], f"💬 Ответ поддержки:\n\n{text}")
                bot.send_message(uid, "✅ Ответ отправлен пользователю.")
            except Exception:
                bot.send_message(uid, "❌ Не удалось отправить ответ пользователю.")


# ── Запуск ─────────────────────────────────────────────
if __name__ == "__main__":
    print("[INFO] Инициализация базы данных...")
    db.init_db()

    # Добавить первого администратора если ещё нет
    if ADMIN_ID and not db.is_admin(ADMIN_ID):
        db.add_admin(ADMIN_ID)
        print(f"[INFO] Первый администратор добавлен: {ADMIN_ID}")

    print("[INFO] MonsterStore15 Bot запущен!")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
