from fastapi import FastAPI, Request, HTTPException, Body, status
import httpx
import os
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
from telebot.async_telebot import AsyncTeleBot
import telebot.types

# 1. 🔒 تحميل المتغيرات البيئية مع التحقق الإلزامي
required_vars = {
    "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN"),
    "OPENAI_KEY": os.getenv("OPENAI_KEY"),
    "RAILWAY_PUBLIC_URL": os.getenv("RAILWAY_PUBLIC_URL"),
    "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD"),
    "CHANNEL_USERNAME": os.getenv("CHANNEL_USERNAME")
}

for var_name, var_value in required_vars.items():
    if not var_value and var_name != "CHANNEL_USERNAME":
        raise RuntimeError(f"⛔ متغير البيئة {var_name} غير موجود!")

# 2. 🤖 تهيئة البوت
bot = AsyncTeleBot(
    required_vars["TELEGRAM_TOKEN"],
    parse_mode="HTML"
)

# 3. 🚀 تهيئة FastAPI
app = FastAPI(
    title="Telegram AI Assistant",
    description="بوت ذكاء اصطناعي متكامل يعمل على Railway",
    version="2.0",
    contact={"name": "الدعم الفني", "email": "support@example.com"},
    license_info={"name": "MIT"},
)

# 4. 🌍 إعدادات CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. 📊 نموذج بيانات الأخبار
class NewsItem(BaseModel):
    text: str
    password: str

# 6. 💡 وظيفة OpenAI
async def ask_chatgpt(message: str, user_id: Optional[int] = None) -> Optional[str]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {required_vars['OPENAI_KEY']}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.7,
        "max_tokens": 1500,
    }
    if user_id:
        data["user"] = str(user_id)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        print(f"🔴 OpenAI Error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        print(f"🔴 Unexpected Error: {str(e)}")
        return None

# 7. 📩 استقبال الرسائل
@bot.message_handler(func=lambda message: True)
async def handle_message(message):
    try:
        user = message.from_user
        print(f"👤 {user.first_name} (@{user.username}): {message.text}")
        await bot.send_chat_action(message.chat.id, 'typing')

        reply = await ask_chatgpt(message.text, user.id)
        if reply:
            if len(reply) > 4000:
                reply = reply[:3900] + "\n\n... [تم اختصار الرد]"
            reply += "\n\n—\nهذا الرد مقدم بواسطة الذكاء الاصطناعي"
            await bot.reply_to(message, reply)
            print(f"📨 تم إرسال الرد ({len(reply)} حرف)")
        else:
            await bot.reply_to(message, "⚠️ تعذر الحصول على رد. يرجى المحاولة لاحقًا.")
    except Exception as e:
        print(f"🔴 خطأ في handle_message: {str(e)}")
        await bot.reply_to(message, "❌ حدث عطل تقني. الرجاء إبلاغ الإدارة.")

# 8. ⚡ أحداث بدء التشغيل
@app.on_event("startup")
async def startup_events():
    try:
        me = await bot.get_me()
        print(f"🤖 تم تشغيل البوت: @{me.username}")

        webhook_url = f"{required_vars['RAILWAY_PUBLIC_URL'].rstrip('/')}/webhook"
        await bot.remove_webhook()
        await asyncio.sleep(1)
        await bot.set_webhook(url=webhook_url, max_connections=50)
        print(f"🌐 تم تعيين Webhook: {webhook_url}")

        # إرسال رسالة بدء التشغيل إذا تم تحديد القناة بشكل صحيح
        if required_vars["CHANNEL_USERNAME"]:
            try:
                await bot.send_message(f"@{required_vars['CHANNEL_USERNAME']}", "✅ تم تشغيل البوت بنجاح!")
            except Exception as e:
                print(f"⚠️ لم يتم إرسال رسالة بدء التشغيل للقناة: {str(e)}")

    except Exception as e:
        print(f"🔥 فشل تشغيل البوت: {str(e)}")
        raise

# 9. نقاط النهاية
@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = telebot.types.Update.de_json(data)
        await bot.process_new_updates([update])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, f"Webhook Error: {str(e)}")

@app.get("/")
async def health():
    me = await bot.get_me()
    return {"status": "running", "version": app.version, "bot": me.first_name, "platform": "Railway"}

@app.get("/webhook-info")
async def get_webhook_info():
    info = await bot.get_webhook_info()
    return {
        "url": info.url,
        "pending_updates": info.pending_update_count,
        "last_error_date": info.last_error_date,
        "max_connections": info.max_connections
    }

@app.post("/send-announcement")
async def send_announcement(news: NewsItem):
    if news.password != required_vars["ADMIN_PASSWORD"]:
        raise HTTPException(401, "كلمة السر غير صحيحة")

    if not required_vars["CHANNEL_USERNAME"]:
        raise HTTPException(501, "إرسال الإعلانات غير مفعل")

    try:
        await bot.send_message(f"@{required_vars['CHANNEL_USERNAME']}", news.text)
        return {"status": "success", "message": "تم إرسال الإعلان"}
    except Exception as e:
        raise HTTPException(500, f"فشل الإرسال: {str(e)}")

# 10. 🏁 لتشغيل uvicorn (عند التشغيل المحلي فقط)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
