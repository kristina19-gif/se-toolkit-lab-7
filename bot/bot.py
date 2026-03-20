from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import suppress

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BotConfig
from handlers import QUICK_ACTIONS, HandlerContext, route_any_text
from services import BackendClient, LLMClient


def build_context(config: BotConfig) -> HandlerContext:
    backend = BackendClient(
        base_url=config.lms_api_url,
        api_key=config.require_lms_api_key(),
    )
    llm = LLMClient(
        base_url=config.llm_api_base_url,
        api_key=config.llm_api_key,
        model=config.llm_api_model,
        backend=backend,
    )
    return HandlerContext(backend=backend, llm=llm)


def build_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=value) for label, value in row]
            for row in QUICK_ACTIONS
        ]
    )


async def _respond(update: Update, text: str) -> None:
    if update.message:
        await update.message.reply_text(text, reply_markup=build_keyboard())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            text,
            reply_markup=build_keyboard(),
        )


async def _handle_text(
    update: Update,
    app_context: HandlerContext,
    text: str,
) -> None:
    response = await asyncio.to_thread(route_any_text, text, app_context)
    await _respond(update, response)


async def command_entry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    app_context: HandlerContext = context.application.bot_data["app_context"]
    text = update.message.text if update.message else "/help"
    await _handle_text(update, app_context, text)


async def text_entry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    app_context: HandlerContext = context.application.bot_data["app_context"]
    if not update.message or not update.message.text:
        return
    await _handle_text(update, app_context, update.message.text)


async def callback_entry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    app_context: HandlerContext = context.application.bot_data["app_context"]
    if not update.callback_query:
        return
    await _handle_text(update, app_context, update.callback_query.data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram bot for the LMS backend")
    parser.add_argument(
        "--test",
        metavar="TEXT",
        help='Run offline mode and print the response for a command or plain query, e.g. --test "/health".',
    )
    return parser.parse_args()


def main() -> int:
    with suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    config = BotConfig.load()
    app_context = build_context(config)
    try:
        if args.test:
            print(route_any_text(args.test, app_context))
            return 0

        application = Application.builder().token(config.require_bot_token()).build()
        application.bot_data["app_context"] = app_context
        for command in ("start", "help", "health", "labs", "scores"):
            application.add_handler(CommandHandler(command, command_entry))
        application.add_handler(CallbackQueryHandler(callback_entry))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, text_entry)
        )
        application.run_polling()
        return 0
    finally:
        with suppress(Exception):
            app_context.backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
