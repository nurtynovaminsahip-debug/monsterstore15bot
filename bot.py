import os
import logging
import asyncio
import random
import string
from datetime import datetime
import pytz

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
INITIAL_ADMIN_ID = 6626508454
PAYMENT_USERNAME = "monsterban15"
PROJECT_CHANNEL = "https://t.me/MonsterStoreNovostnik"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# --- Conversation states ---
(
    TOPUP_AMOUNT,
    HELP_MESSAGE,
    ADD_PRODUCT,
    ADD_ADMIN,
    DELETE_PRODUCT,
    REMOVE_ADMIN,
    ADMIN_REPLY,
    DICE_BET,
    COIN_BET,
    SLOTS_BET,
) = range(10)


def generate_id(length=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def main_menu():
    return ReplyKeyboardMarkup(
        [
            ["🛒Купить", "👤Профиль"],
            ["💼Проект", "🆘Помощь"],
            ["🤝Сотрудничество", "🎲Мини-игры"],
        ],
        resize_keyboard=True,
    )


def ensure_user(update: Update):
    u = update.effective_user
    db.create_user(u.id, u.username)
    db.update_username(u.id, u.username)


# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    await update.message.reply_text(
        "👋Добро пожаловать в MonsterStore15!",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  /console  — admin panel
# ─────────────────────────────────────────────
async def console_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    user_id = update.effective_user.id
    if not db.is_admin(user_id):
        await update.message.reply_text("❌У вас нет доступа к админ-панели.")
        return ConversationHandler.END

    bot_active = db.get_setting("bot_active") == "true"
    status = "✅ Включен" if bot_active else "❌ Выключен"
    moscow_time = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S %d.%m.%Y")

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎁Добавить товар", callback_data="adm_add_product")],
            [InlineKeyboardButton("➕Добавить администратора", callback_data="adm_add_admin")],
            [InlineKeyboardButton("🗂Список администраторов", callback_data="adm_list_admins")],
            [InlineKeyboardButton("❌Удалить товар", callback_data="adm_del_product")],
            [InlineKeyboardButton("🧨Снять администратора", callback_data="adm_rm_admin")],
        ]
    )
    await update.message.reply_text(
        f"🔐Админ панель\n"
        f"- - - - - - - - - - - - - - - - - - - - - - - - - -\n"
        f"🤖Состояние бота: {status}\n"
        f"⌛️Время: {moscow_time}",
        reply_markup=kb,
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Main text message router
# ─────────────────────────────────────────────
async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update)
    text = update.message.text

    if text == "👤Профиль":
        await show_profile(update, context)
        return ConversationHandler.END
    elif text == "🛒Купить":
        await show_shop(update, context)
        return ConversationHandler.END
    elif text == "💼Проект":
        await show_project(update, context)
        return ConversationHandler.END
    elif text == "🆘Помощь":
        return await help_start(update, context)
    elif text == "🤝Сотрудничество":
        await show_cooperation(update, context)
        return ConversationHandler.END
    elif text == "🎲Мини-игры":
        await show_minigames(update, context)
        return ConversationHandler.END
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Profile
# ─────────────────────────────────────────────
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳Пополнить", callback_data="topup_start")],
            [InlineKeyboardButton("📜История покупок", callback_data="history")],
        ]
    )
    await update.message.reply_text(
        f"👤Ваш профиль:\n\n"
        f"🆔TG ID: {user['telegram_id']}\n\n"
        f"🛒Кол-во покупок: {user['purchases_count']}\n\n"
        f"💰Баланс: {user['balance']:.2f} руб.",
        reply_markup=kb,
    )


# ─────────────────────────────────────────────
#  Shop
# ─────────────────────────────────────────────
async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = db.get_products()
    if not products:
        await update.message.reply_text("🛒В магазине пока нет товаров.")
        return
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"⭐️ {p['name']} — {p['price']:.0f}₽", callback_data=f"prod_{p['id']}")]
            for p in products
        ]
    )
    await update.message.reply_text("🛒Выберите товар:", reply_markup=kb)


# ─────────────────────────────────────────────
#  Project / Cooperation
# ─────────────────────────────────────────────
async def show_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📒Проект", url=PROJECT_CHANNEL)]])
    await update.message.reply_text("💼Наш проект:", reply_markup=kb)


async def show_cooperation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤝Для сотрудничества напишите @MonsterStore15helper")


# ─────────────────────────────────────────────
#  Help / Support
# ─────────────────────────────────────────────
async def help_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❗️Напишите ваш вопрос или проблему, и поддержка ответит вам в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([["🔙Назад"]], resize_keyboard=True),
    )
    return HELP_MESSAGE


async def help_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Назад":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    user = update.effective_user
    username_str = f"@{user.username}" if user.username else f"ID:{user.id}"
    msg_text = update.message.text

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("💬Ответить", callback_data=f"reply_{user.id}")]]
    )
    for admin in db.get_admins():
        try:
            await context.bot.send_message(
                chat_id=admin["telegram_id"],
                text=(
                    f"📩Новое обращение в поддержку!\n\n"
                    f"👤От: {username_str} (ID: {user.id})\n\n"
                    f"💬Сообщение: {msg_text}"
                ),
                reply_markup=kb,
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅Ваше сообщение отправлено в поддержку. Ожидайте ответа.",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Mini-games
# ─────────────────────────────────────────────
async def show_minigames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎲 Кубик удачи", callback_data="game_dice")],
            [InlineKeyboardButton("🪙 Орёл или решка", callback_data="game_coin")],
            [InlineKeyboardButton("🎰 Слот-машина", callback_data="game_slots")],
        ]
    )
    await update.message.reply_text(
        "🎲Мини-игры MonsterStore15!\n\n"
        "Выберите игру:\n\n"
        "🎲 Кубик удачи — угадайте больше 3, выиграйте x2 ставки!\n"
        "🪙 Орёл или решка — 50/50, выиграйте x2!\n"
        "🎰 Слот-машина — 3 одинаковых = x3, 2 одинаковых = возврат!\n\n"
        f"💰Ваш баланс: {user['balance']:.2f} руб.",
        reply_markup=kb,
    )


# ─────────────────────────────────────────────
#  Callback query handler (all inline buttons)
# ─────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    # ── Profile: top-up start ──────────────────────────────
    if data == "topup_start":
        await query.answer()
        await query.message.reply_text(
            "⭐️Введите сумму пополнения в рублях цифрами:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return TOPUP_AMOUNT

    # ── Profile: purchase history ─────────────────────────
    elif data == "history":
        await query.answer()
        history = db.get_purchase_history(user_id)
        if not history:
            await query.message.reply_text("📜У вас пока нет покупок.")
        else:
            text = "📜История покупок:\n\n"
            for i, item in enumerate(history, 1):
                text += f"{i}. {item['product_name']} — {item['price']:.2f}₽\n"
            await query.message.reply_text(text)

    # ── Shop: product detail ───────────────────────────────
    elif data.startswith("prod_"):
        await query.answer()
        product_id = int(data.split("_")[1])
        product = db.get_product_by_id(product_id)
        if not product:
            await query.message.reply_text("❌Товар не найден.")
            return
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💳Оплатить", callback_data=f"order_{product_id}")]]
        )
        await query.message.reply_text(
            f"⭐️Товар: {product['name']}\n"
            f"💰Стоимость: {product['price']:.2f}₽\n\n"
            f"✅Описание: {product['description']}\n\n"
            f"❗️Оплатите товар по ссылке ниже и отправьте чек в раздел Помощь, "
            f"продавец выдаст товар и подтвердит заказ.",
            reply_markup=kb,
        )

    # ── Shop: place order ─────────────────────────────────
    elif data.startswith("order_") and not data.startswith("order_confirm_") and not data.startswith("order_reject_"):
        await query.answer()
        product_id = int(data.split("_")[1])
        product = db.get_product_by_id(product_id)
        if not product:
            await query.message.reply_text("❌Товар не найден.")
            return

        u = update.effective_user
        order_id = generate_id()
        username_str = f"@{u.username}" if u.username else f"ID:{u.id}"
        db.create_order(order_id, u.id, u.username or str(u.id), product["name"], product["price"])

        kb_admin = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅Подтвердить заказ", callback_data=f"order_confirm_{order_id}")],
                [InlineKeyboardButton("❌Отклонить заказ", callback_data=f"order_reject_{order_id}")],
            ]
        )
        for admin in db.get_admins():
            try:
                await context.bot.send_message(
                    chat_id=admin["telegram_id"],
                    text=(
                        f"📋Новый заказ! #{order_id}\n"
                        f"🆔{username_str} и ID пользователя: {username_str} и {u.id}\n"
                        f"🔑Цена: {product['price']:.2f}₽\n"
                        f"🛒Товар: {product['name']}"
                    ),
                    reply_markup=kb_admin,
                )
            except Exception:
                pass

        kb_pay = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💳Оплатить", url=f"https://t.me/{PAYMENT_USERNAME}")]]
        )
        await query.message.reply_text(
            f"📋Ваш заказ #{order_id} оформлен!\n\n"
            f"🛒Товар: {product['name']}\n"
            f"💰Цена: {product['price']:.2f}₽\n\n"
            f"💳Оплатите товар и отправьте чек администратору:",
            reply_markup=kb_pay,
        )

    # ── Admin: confirm order ──────────────────────────────
    elif data.startswith("order_confirm_"):
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        order_id = data.replace("order_confirm_", "")
        order = db.get_order(order_id)
        if not order:
            await query.answer("Заказ не найден.", show_alert=True)
            return
        if order["status"] != "pending":
            await query.answer("Заказ уже обработан.", show_alert=True)
            return
        db.update_order_status(order_id, "confirmed")
        db.increment_purchases(order["user_id"])
        db.add_purchase_history(order["user_id"], order["product_name"], order["price"])
        try:
            await query.edit_message_text(query.message.text + "\n\n✅ Заказ подтверждён")
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text="✅Заказ выдан и успешно подтверждён администратором. Проверьте получение. Благодарим за покупку!",
            )
        except Exception:
            pass
        await query.answer("✅Заказ подтверждён!")

    # ── Admin: reject order ───────────────────────────────
    elif data.startswith("order_reject_"):
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        order_id = data.replace("order_reject_", "")
        order = db.get_order(order_id)
        if not order:
            await query.answer("Заказ не найден.", show_alert=True)
            return
        if order["status"] != "pending":
            await query.answer("Заказ уже обработан.", show_alert=True)
            return
        db.update_order_status(order_id, "rejected")
        try:
            await query.edit_message_text(query.message.text + "\n\n❌ Заказ отклонён")
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text="❌Заказ отклонён. Это может быть потому что вы не оплатили заказ. В другом случае, обратитесь в поддержку.",
            )
        except Exception:
            pass
        await query.answer("❌Заказ отклонён.")

    # ── Admin: approve top-up ─────────────────────────────
    elif data.startswith("topup_approve_"):
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        request_id = data.replace("topup_approve_", "")
        req = db.get_topup_request(request_id)
        if not req:
            await query.answer("Заявка не найдена.", show_alert=True)
            return
        if req["status"] != "pending":
            await query.answer("Заявка уже обработана.", show_alert=True)
            return
        db.update_topup_status(request_id, "approved")
        db.update_user_balance(req["user_id"], req["amount"])
        try:
            await query.edit_message_text(query.message.text + "\n\n✅ Зачислено")
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=req["user_id"],
                text=f"✅Ваш баланс успешно пополнен на {req['amount']:.2f} руб.!",
            )
        except Exception:
            pass
        await query.answer("✅Баланс пополнен!")

    # ── Admin: reject top-up ──────────────────────────────
    elif data.startswith("topup_reject_"):
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        request_id = data.replace("topup_reject_", "")
        req = db.get_topup_request(request_id)
        if not req:
            await query.answer("Заявка не найдена.", show_alert=True)
            return
        if req["status"] != "pending":
            await query.answer("Заявка уже обработана.", show_alert=True)
            return
        db.update_topup_status(request_id, "rejected")
        try:
            await query.edit_message_text(query.message.text + "\n\n❌ Отклонено")
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=req["user_id"],
                text="❌Ваша заявка на пополнение отклонена. Обратитесь в поддержку.",
            )
        except Exception:
            pass
        await query.answer("❌Заявка отклонена.")

    # ── Admin: reply to support message ──────────────────
    elif data.startswith("reply_"):
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        await query.answer()
        target_id = int(data.replace("reply_", ""))
        context.user_data["reply_to"] = target_id
        await query.message.reply_text(
            f"💬Введите ответ пользователю (ID: {target_id}):",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return ADMIN_REPLY

    # ── Admin panel buttons ───────────────────────────────
    elif data == "adm_add_product":
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "✍️Введите сообщение в формате:\nНазвание товара - цена - описание товара",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return ADD_PRODUCT

    elif data == "adm_add_admin":
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "🆔Введите TG ID администратора, которого вы хотите добавить:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return ADD_ADMIN

    elif data == "adm_list_admins":
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        await query.answer()
        admins = db.get_admins()
        if not admins:
            await query.message.reply_text("📋Список администраторов пуст.")
            return
        text = "👤Список администраторов:\n\n"
        for i, adm in enumerate(admins, 1):
            text += f"🆔Администратор {i}: {adm['telegram_id']}\n"
        await query.message.reply_text(text)

    elif data == "adm_del_product":
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "✏️Введите название товара без опечаток, которое вы хотите удалить:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return DELETE_PRODUCT

    elif data == "adm_rm_admin":
        if not db.is_admin(user_id):
            await query.answer("❌Нет доступа.", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "✏️🆔Введите Telegram ID администратора (цифрами), которого вы хотите снять:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return REMOVE_ADMIN

    # ── Mini-games ────────────────────────────────────────
    elif data == "game_dice":
        await query.answer()
        user = db.get_user(user_id)
        await query.message.reply_text(
            f"🎲Кубик удачи!\n\n"
            f"Если выпадет больше 3 — выигрываете ставку x2!\n"
            f"Если 3 или меньше — теряете ставку.\n\n"
            f"💰Ваш баланс: {user['balance']:.2f} руб.\n\n"
            f"Введите ставку в рублях:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return DICE_BET

    elif data == "game_coin":
        await query.answer()
        user = db.get_user(user_id)
        await query.message.reply_text(
            f"🪙Орёл или решка!\n\n"
            f"50/50 — угадайте и выиграйте x2 ставки!\n\n"
            f"💰Ваш баланс: {user['balance']:.2f} руб.\n\n"
            f"Введите ставку в рублях:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return COIN_BET

    elif data == "game_slots":
        await query.answer()
        user = db.get_user(user_id)
        await query.message.reply_text(
            f"🎰Слот-машина!\n\n"
            f"3 одинаковых символа — x3 к ставке!\n"
            f"2 одинаковых — возврат ставки!\n"
            f"Нет совпадений — теряете ставку.\n\n"
            f"💰Ваш баланс: {user['balance']:.2f} руб.\n\n"
            f"Введите ставку в рублях:",
            reply_markup=ReplyKeyboardMarkup([["🔙Отмена"]], resize_keyboard=True),
        )
        return SLOTS_BET

    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Top-up conversation step
# ─────────────────────────────────────────────
async def topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    try:
        amount = float(update.message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌Введите корректную сумму цифрами.")
        return TOPUP_AMOUNT

    u = update.effective_user
    request_id = generate_id()
    username_str = f"@{u.username}" if u.username else f"ID:{u.id}"
    db.create_topup_request(request_id, u.id, u.username or str(u.id), amount)

    kb_admin = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅Зачислить сумму", callback_data=f"topup_approve_{request_id}")],
            [InlineKeyboardButton("❌Отклонить заявку", callback_data=f"topup_reject_{request_id}")],
        ]
    )
    for admin in db.get_admins():
        try:
            await context.bot.send_message(
                chat_id=admin["telegram_id"],
                text=(
                    f"📋Пополнение #{request_id}\n"
                    f"🆔{username_str} и ID пользователя: {username_str} и {u.id}\n"
                    f"🔑Сумма: {amount:.2f} руб."
                ),
                reply_markup=kb_admin,
            )
        except Exception:
            pass

    kb_pay = InlineKeyboardMarkup(
        [[InlineKeyboardButton("💳Оплатить", url=f"https://t.me/{PAYMENT_USERNAME}")]]
    )
    await update.message.reply_text(
        f"📋Заявка #{request_id} создана!\n\n"
        f"💰Сумма: {amount:.2f} руб.\n\n"
        f"❗️Для пополнения нажмите Оплатить и напишите администратору к которому вас переведет кнопка",
        reply_markup=kb_pay,
    )
    await update.message.reply_text("Главное меню:", reply_markup=main_menu())
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Admin reply step
# ─────────────────────────────────────────────
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    target_id = context.user_data.get("reply_to")
    if not target_id:
        await update.message.reply_text("❌Ошибка.", reply_markup=main_menu())
        return ConversationHandler.END

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"💬Ответ поддержки:\n\n{update.message.text}",
        )
        await update.message.reply_text("✅Ответ отправлен.", reply_markup=main_menu())
    except Exception:
        await update.message.reply_text("❌Не удалось отправить.", reply_markup=main_menu())

    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Admin product/admin management steps
# ─────────────────────────────────────────────
async def add_product_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    try:
        parts = [p.strip() for p in update.message.text.split("-", 2)]
        if len(parts) != 3:
            raise ValueError
        name, price_str, description = parts
        price = float(price_str.replace(",", "."))
    except ValueError:
        await update.message.reply_text(
            "❌Неверный формат. Введите:\nНазвание товара - цена - описание товара"
        )
        return ADD_PRODUCT

    try:
        db.add_product(name, price, description)
    except Exception:
        await update.message.reply_text("❌Товар с таким названием уже существует.")
        return ADD_PRODUCT

    await update.message.reply_text(
        f"✅Товар «{name}» успешно добавлен!", reply_markup=main_menu()
    )
    return ConversationHandler.END


async def add_admin_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    try:
        new_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌Введите корректный Telegram ID (только цифры).")
        return ADD_ADMIN

    db.add_admin(new_id, update.effective_user.id)
    await update.message.reply_text("🔑Новый администратор успешно добавлен!", reply_markup=main_menu())
    return ConversationHandler.END


async def delete_product_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    name = update.message.text.strip()
    if db.delete_product(name):
        await update.message.reply_text("📝Товар успешно удалён!", reply_markup=main_menu())
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌Товар с таким названием не найден. Проверьте название.")
        return DELETE_PRODUCT


async def remove_admin_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌Введите корректный Telegram ID (только цифры).")
        return REMOVE_ADMIN

    if target_id == INITIAL_ADMIN_ID:
        await update.message.reply_text("❌Нельзя снять главного администратора.", reply_markup=main_menu())
        return ConversationHandler.END

    if db.remove_admin(target_id):
        await update.message.reply_text("✅Администратор успешно снят!", reply_markup=main_menu())
    else:
        await update.message.reply_text("❌Администратор с таким ID не найден.")
        return REMOVE_ADMIN

    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Mini-game bet steps
# ─────────────────────────────────────────────
def _parse_bet(text: str, user_id: int):
    bet = float(text.replace(",", "."))
    if bet <= 0:
        raise ValueError
    user = db.get_user(user_id)
    if bet > user["balance"]:
        raise OverflowError
    return bet, user


async def dice_bet_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    user_id = update.effective_user.id
    try:
        bet, user = _parse_bet(update.message.text, user_id)
    except (ValueError, AttributeError):
        await update.message.reply_text("❌Введите корректную ставку.")
        return DICE_BET
    except OverflowError:
        await update.message.reply_text(
            f"❌Недостаточно средств. Ваш баланс: {db.get_user(user_id)['balance']:.2f} руб."
        )
        return DICE_BET

    dice_msg = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(4)
    value = dice_msg.dice.value

    if value > 3:
        db.update_user_balance(user_id, bet)
        result = f"🎲Выпало: {value}\n\n🎉Вы выиграли {bet:.2f} руб.!"
    else:
        db.update_user_balance(user_id, -bet)
        result = f"🎲Выпало: {value}\n\n😔Вы проиграли {bet:.2f} руб."

    new_balance = db.get_user(user_id)["balance"]
    await update.message.reply_text(
        f"{result}\n\n💰Ваш баланс: {new_balance:.2f} руб.",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


async def coin_bet_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    user_id = update.effective_user.id
    try:
        bet, user = _parse_bet(update.message.text, user_id)
    except (ValueError, AttributeError):
        await update.message.reply_text("❌Введите корректную ставку.")
        return COIN_BET
    except OverflowError:
        await update.message.reply_text(
            f"❌Недостаточно средств. Ваш баланс: {db.get_user(user_id)['balance']:.2f} руб."
        )
        return COIN_BET

    # Use random for coin since Telegram has no coin dice
    won = random.random() < 0.5
    side = "🦅 Орёл" if won else "🔢 Решка"

    if won:
        db.update_user_balance(user_id, bet)
        result = f"{side}!\n\n🎉Вы выиграли {bet:.2f} руб.!"
    else:
        db.update_user_balance(user_id, -bet)
        result = f"{side}!\n\n😔Вы проиграли {bet:.2f} руб."

    new_balance = db.get_user(user_id)["balance"]
    await update.message.reply_text(
        f"🪙Монетка брошена!\n\n{result}\n\n💰Ваш баланс: {new_balance:.2f} руб.",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


async def slots_bet_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙Отмена":
        await update.message.reply_text("Главное меню:", reply_markup=main_menu())
        return ConversationHandler.END

    user_id = update.effective_user.id
    try:
        bet, user = _parse_bet(update.message.text, user_id)
    except (ValueError, AttributeError):
        await update.message.reply_text("❌Введите корректную ставку.")
        return SLOTS_BET
    except OverflowError:
        await update.message.reply_text(
            f"❌Недостаточно средств. Ваш баланс: {db.get_user(user_id)['balance']:.2f} руб."
        )
        return SLOTS_BET

    slot_msg = await update.message.reply_dice(emoji="🎰")
    await asyncio.sleep(4)
    value = slot_msg.dice.value  # 1–64

    # Telegram slots: value 1 = BAR, 22 = lemon x3, 43 = seven x3, 64 = jackpot
    if value in (1, 22, 43, 64):  # jackpot: triple match
        db.update_user_balance(user_id, bet * 2)
        result = f"🎰ДЖЕКПОТ! Три одинаковых!\n\n🎉🎉🎉Вы выиграли {bet * 2:.2f} руб.!"
    elif value % 11 == 0:  # ~6 values → two matching
        result = f"🎰Два одинаковых!\n\nВозврат ставки {bet:.2f} руб."
    else:
        db.update_user_balance(user_id, -bet)
        result = f"🎰Нет совпадений!\n\n😔Вы проиграли {bet:.2f} руб."

    new_balance = db.get_user(user_id)["balance"]
    await update.message.reply_text(
        f"{result}\n\n💰Ваш баланс: {new_balance:.2f} руб.",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────
def main():
    db.init_db()
    db.add_admin(INITIAL_ADMIN_ID, INITIAL_ADMIN_ID)

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("console", console_cmd),
            MessageHandler(filters.TEXT & ~filters.COMMAND, route_message),
            CallbackQueryHandler(callback_handler),
        ],
        states={
            TOPUP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_amount)],
            HELP_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, help_message_received)],
            ADD_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_step)],
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_step)],
            DELETE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_product_step)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_step)],
            ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply)],
            DICE_BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, dice_bet_step)],
            COIN_BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, coin_bet_step)],
            SLOTS_BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, slots_bet_step)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    logger.info("MonsterStore15 bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
