import os
import requests
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from ValerieMusic import app  # main bot client


# Upload file to catbox.moe
def upload_catbox(file_path: str):
    url = "https://catbox.moe/user/api.php"
    data = {"reqtype": "fileupload", "json": "true"}
    files = {"fileToUpload": open(file_path, "rb")}

    try:
        response = requests.post(url, data=data, files=files)
        if response.status_code == 200:
            return True, response.text.strip()
        else:
            return False, f"❖ ᴇʀʀᴏʀ : {response.status_code} - {response.text}"
    except Exception as e:
        return False, f"❖ ᴇʀʀᴏʀ : {e}"


@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def catbox_uploader(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "❖ ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ."
        )

    media = message.reply_to_message

    # get file size
    file_size = 0
    if media.photo:
        file_size = media.photo.file_size
    elif media.video:
        file_size = media.video.file_size
    elif media.document:
        file_size = media.document.file_size

    # 200MB limit
    if file_size > 200 * 1024 * 1024:
        return await message.reply_text(
            "❖ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ғɪʟᴇ ᴜɴᴅᴇʀ 200MB"
        )

    status = await message.reply_text("❍ ᴘʀᴏᴄᴇssɪɴɢ...")

    async def progress(current, total):
        try:
            percent = current * 100 / total
            await status.edit_text(f"❍ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ... {percent:.1f}%")
        except:
            pass

    try:
        # download file
        local_path = await media.download(progress=progress)

        await status.edit_text("❍ ᴜᴘʟᴏᴀᴅɪɴɢ ᴛᴏ ᴄᴀᴛʙᴏx...")

        # upload to catbox
        success, result = upload_catbox(local_path)

        if success:
            await status.edit_text(
                f"❖ <b>ғɪʟᴇ ᴜᴘʟᴏᴀᴅᴇᴅ</b>\n\n"
                f"↬ <a href=\"{result}\">ᴄᴀᴛʙᴏx ʟɪɴᴋ</a>",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "• ᴏᴘᴇɴ ʟɪɴᴋ •", url=result
                            )
                        ]
                    ]
                ),
                disable_web_page_preview=True
            )
        else:
            await status.edit_text(
                f"❖ ᴇʀʀᴏʀ ᴜᴘʟᴏᴀᴅɪɴɢ ғɪʟᴇ\n\n{result}"
            )

        # remove file
        try:
            os.remove(local_path)
        except:
            pass

    except Exception as e:
        await status.edit_text(
            f"❖ <b>ғɪʟᴇ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ</b>\n\n<i>ʀᴇᴀsᴏɴ : {e}</i>"
        )
        try:
            os.remove(local_path)
        except:
            pass
