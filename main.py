import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

# โหลดตัวแปรจากไฟล์ .env
load_dotenv()

# ตั้งค่า intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# แมป ห้อง กับ ยศ
VOICE_CHANNEL_1 = int(os.getenv('VOICE_CHANNEL_1', '0'))
ROLE_1 = int(os.getenv('ROLE_1', '0'))

VOICE_CHANNEL_2 = int(os.getenv('VOICE_CHANNEL_2', '0'))
ROLE_2 = int(os.getenv('ROLE_2', '0'))

DESTINATION_CHANNEL = int(os.getenv('DESTINATION_CHANNEL', '0'))

# เวลาที่กำหนดคือ 2.5 นาที = 150 วินาที
WARNING_TIME_SECONDS = 90 # เตือนก่อนหมดเวลา 15 วินาที
TOTAL_TIME_SECONDS = 150

# เก็บสถานะการจับเวลา
active_timers = {}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

async def timer_task(member, channel, role_id):
    """ฟังก์ชันจับเวลาและแจ้งเตือน"""
    try:
        # รอจนถึงเวลาใกล้หมด (135 วินาที)
        await asyncio.sleep(WARNING_TIME_SECONDS)
        
        # ตรวจสอบว่าผู้ใช้ยังอยู่ในห้องเดิมหรือไม่
        if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
            # เชื่อมต่อห้องเสียง
            try:
                vc = await channel.connect()
                
                # เปลี่ยน 'warning.mp3' เป็นไฟล์เสียงที่คุณต้องการ
                if os.path.exists('alert.mp3'):
                    vc.play(discord.FFmpegPCMAudio('alert.mp3'))
                    
                    # รอจนกว่าเสียงจะเล่นจบ
                    while vc.is_playing():
                        await asyncio.sleep(1)
                else:
                    print("ไม่พบไฟล์เสียง alert.mp3")
                
                # ตัดการเชื่อมต่อหลังเล่นเสียงเสร็จ
                await vc.disconnect()
            except Exception as e:
                print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ/เล่นเสียง: {e}")
                if channel.guild.voice_client:
                    await channel.guild.voice_client.disconnect()

            # รออีกจนครบกำหนดเวลาเต็มที่ (TOTAL_TIME_SECONDS - WARNING_TIME_SECONDS)
            remaining_time = TOTAL_TIME_SECONDS - WARNING_TIME_SECONDS
            if remaining_time > 0:
                await asyncio.sleep(remaining_time)

            # ตรวจสอบอีกครั้งว่าต้องย้ายผู้ใช้และถอด role
            if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
                try:
                    # ถอดยศ
                    target_role = member.guild.get_role(role_id)
                    if target_role:
                        await member.remove_roles(target_role)
                        print(f"ถอดยศ {target_role.name} จาก {member.display_name}")

                    # ย้ายไปยังห้อง DESTINATION_CHANNEL
                    dest_channel = member.guild.get_channel(DESTINATION_CHANNEL)
                    if dest_channel:
                        await member.move_to(dest_channel)
                        print(f"ย้าย {member.display_name} ไปยัง {dest_channel.name}")
                    else:
                        print(f"ไม่พบห้องปลายทาง {DESTINATION_CHANNEL}")
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดในการจัดการยศหรือย้ายห้อง: {e}")

    except asyncio.CancelledError:
        print(f"ยกเลิกการจับเวลาของ {member.display_name}")
    finally:
        # ลบข้อมูลการจับเวลาออกเมื่อเสร็จสิ้นหรือถูกยกเลิก
        if member.id in active_timers:
            del active_timers[member.id]

@bot.event
async def on_voice_state_update(member, before, after):
    # กรณีที่ผู้ใช้ย้ายเข้าห้องเสียงใหม่ หรือเพิ่งเชื่อมต่อ
    if after.channel is not None and before.channel != after.channel:
        target_role_id_matched = None
        
        # เช็คว่าเป็น ห้อง 1 และมียศ 1 หรือไม่
        if after.channel.id == VOICE_CHANNEL_1:
            if any(role.id == ROLE_1 for role in member.roles):
                target_role_id_matched = ROLE_1
        # เช็คว่าเป็น ห้อง 2 และมียศ 2 หรือไม่
        elif after.channel.id == VOICE_CHANNEL_2:
            if any(role.id == ROLE_2 for role in member.roles):
                target_role_id_matched = ROLE_2
        
        # ถ้าตรงเงื่อนไข
        if target_role_id_matched:
            print(f"เริ่มจับเวลา 2.5 นาที สำหรับ {member.display_name} ในห้อง {after.channel.name}")
            
            # ถ้ายูสเซอร์นี้มีการจับเวลาอยู่แล้ว ให้ยกเลิกอันเก่าก่อน
            if member.id in active_timers:
                active_timers[member.id].cancel()
            
            # เริ่มจับเวลาใหม่ และส่ง role_id ที่ถูกจับคู่ไปด้วย
            task = bot.loop.create_task(timer_task(member, after.channel, target_role_id_matched))
            active_timers[member.id] = task

    # กรณีที่ผู้ใช้ออกจากห้อง หรือย้ายไปห้องอื่นที่ไม่ได้กำหนด ให้ยกเลิกการจับเวลา
    if before.channel is not None and before.channel != after.channel:
        if before.channel.id in [VOICE_CHANNEL_1, VOICE_CHANNEL_2]:
            if member.id in active_timers:
                print(f"{member.display_name} ออกจากห้อง {before.channel.name} ยกเลิกการจับเวลา")
                active_timers[member.id].cancel()
                del active_timers[member.id]

# รันบอทด้วย Token จาก .env
if __name__ == '__main__':
    bot_token = os.getenv('BOT_TOKEN', '')
    if bot_token and bot_token != 'YOUR_BOT_TOKEN_HERE':
        bot.run(bot_token)
    else:
        print("กรุณาใส่ BOT_TOKEN ของคุณในไฟล์ .env")
