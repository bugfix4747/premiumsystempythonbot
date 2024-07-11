import discord
from discord.ext import commands, tasks
import random
import string
import aiosqlite
from datetime import datetime, timedelta
from discord.utils import format_dt
import os

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = "db/premium.db"

    @commands.Cog.listener()
    async def on_ready(self):
        async with aiosqlite.connect(self.db) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS premium_system (
                                code TEXT,
                                user_id INTEGER DEFAULT NULL,
                                expires_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                duration INTEGER,
                                duration_type TEXT,
                                created_by INTEGER
                                )''')
            await db.commit()
        self.check_premium_expiry.start()

    def generate_code(self, length=12):
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

    def generate_psn_code(self):
        raw_code = self.generate_code()
        formatted_code = f"{raw_code[:4]}-{raw_code[4:8]}-{raw_code[8:]}"
        return formatted_code

    def calculate_expiry(self, duration, duration_type):
        now = datetime.utcnow()
        if duration_type == "Seconds":
            return now + timedelta(seconds=duration)
        elif duration_type == "Minutes":
            return now + timedelta(minutes=duration)
        elif duration_type == "Hours":
            return now + timedelta(hours=duration)
        elif duration_type == "Days":
            return now + timedelta(days=duration)
        elif duration_type == "Weeks":
            return now + timedelta(weeks=duration)
        elif duration_type == "Months":
            return now + timedelta(days=duration*30)
        elif duration_type == "Years":
            return now + timedelta(days=duration*365)
        elif duration_type == "Lifetime":
            return None

    @tasks.loop(seconds=5)
    async def check_premium_expiry(self):
        async with aiosqlite.connect(self.db) as db:
            async with db.execute('SELECT code, user_id, expires_at FROM premium_system WHERE user_id IS NOT NULL') as cursor:
                async for row in cursor:
                    code, user_id, expires_at = row
                    expiry_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S") if expires_at != "Lifetime" else None
                    if expiry_date and expiry_date < datetime.utcnow():
                        await db.execute('UPDATE premium_system SET user_id = NULL WHERE user_id = ?', (user_id,))
                        await db.commit()

    @staticmethod
    async def is_premium(ctx):
        async with aiosqlite.connect("db/premium.db") as db:
            async with db.execute('SELECT expires_at FROM premium_system WHERE user_id = ?', (ctx.author.id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    embed = discord.Embed(title="Premium Feature", description="You do not have a premium.", color=0xFF0000)
                    await ctx.respond(embed=embed)
                    return False
                expires_at = row[0]
                expiry_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S") if expires_at != "Lifetime" else None
                if expiry_date and expiry_date < datetime.utcnow():
                    await db.execute('UPDATE premium_system SET user_id = NULL WHERE user_id = ?', (ctx.author.id,))
                    await db.commit()
                    return False
                return True


    @commands.slash_command(name="create-premium-code", description="Create a premium code/s (Admin only)")
    @commands.has_permissions(administrator=True)
    async def create_code(self, ctx, count: int, duration: int, duration_type: discord.Option(str, choices=["Seconds", "Minutes", "Hours", "Days", "Weeks", "Months", "Years", "Lifetime"])):
        async with aiosqlite.connect(self.db) as db:
            embed = discord.Embed(title="Creating Premium Codes", color=0x0083FF)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            
            codes = []
            for _ in range(count):
                code = self.generate_psn_code()
                expiry = self.calculate_expiry(duration, duration_type)
                expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S") if expiry else "Lifetime"
                await db.execute('INSERT INTO premium_system (code, expires_at, duration, duration_type, created_by) VALUES (?, ?, ?, ?, ?)', 
                                 (code, expiry_str, duration, duration_type, ctx.author.id))
                codes.append(code)
            await db.commit()
            with open("premium_codes.txt", "w") as f:
                f.write("\n".join(codes))
            
            with open("premium_codes.txt", "rb") as f:
                await ctx.author.send("⚠   Dont share this Codes", file=discord.File(f, "premium_codes.txt"))
                os.remove("premium_codes.txt")
            embed.description = f"Check your DMs for the list of premium codes [Total: {count}]."
        await ctx.respond(embed=embed, ephemeral=True)


    @commands.slash_command(name="redeem-premium-code", description="Redeem a premium code")
    async def redeem_code(self, ctx, code: str):
        async with aiosqlite.connect(self.db) as db:
            embed = discord.Embed(title="Redeeming Premium Code", color=0xFF0000)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            
            async with db.execute('SELECT expires_at, duration, duration_type, user_id FROM premium_system WHERE code = ?', (code,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    embed.description = "This code does not exist or has already been used."
                    await ctx.respond(embed=embed)
                    return
                
                expires_at, duration, duration_type, user_id = row
                if user_id is not None:
                    embed.description = "This code has already been used."
                    await ctx.respond(embed=embed)
                    return
                
                async with db.execute('SELECT expires_at FROM premium_system WHERE user_id = ?', (ctx.author.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row is not None:
                        embed.description = "You already have a premium. You can't redeem another code."
                        await ctx.respond(embed=embed)
                        return
                                 
                expiry_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S") if expires_at != "Lifetime" else None
                if expiry_date and expiry_date < datetime.utcnow():
                    embed.description = "This code has expired."
                    await ctx.respond(embed=embed)
                    return
                
                new_expiry_date = self.calculate_expiry(duration, duration_type).strftime("%Y-%m-%d %H:%M:%S") if duration_type != "Lifetime" else "Lifetime"
                timestamp = format_dt(datetime.strptime(new_expiry_date, "%Y-%m-%d %H:%M:%S"), "R") if new_expiry_date != "Lifetime" else "Lifetime"
                await db.execute('UPDATE premium_system SET user_id = ? WHERE code = ?', (ctx.author.id, code))
                await db.execute('UPDATE premium_system SET expires_at = ? WHERE user_id = ?', (new_expiry_date, ctx.author.id))
                await db.commit()
                
                embed.description = f"Premium code redeemed successfully! Your premium status expires at {timestamp}."
                await ctx.respond(embed=embed)

    @commands.slash_command(name="check-premium", description="Check your or someone else's premium status")
    async def check_premium(self, ctx, user: discord.Option(discord.Member, default=None)):
        user = user or ctx.author
        async with aiosqlite.connect(self.db) as db:
            embed = discord.Embed(title="Premium Status", color=0x0CFF00)
            embed.set_author(name=user.display_name, icon_url=user.avatar.url)
            
            async with db.execute('SELECT code, expires_at FROM premium_system WHERE user_id = ?', (user.id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    embed.description = f"{user.mention} does not have a premium."
                    await ctx.respond(embed=embed)
                    return
                
                code, expires_at = row
                if expires_at == "Lifetime":
                    embed.description = f"{user.mention} has premium Lifetime with code `{code}`."
                else:
                    expiry_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                    print(expiry_date)
                    timestamp = format_dt(expiry_date, "R")
                    embed.description = f"{user.mention} has a premium status that expires at {timestamp} with code `{code}`."
                    
            await ctx.respond(embed=embed)
    
    @commands.slash_command(name="delete-premium-code", description="Delete a premium code (Admin only)")
    @commands.has_permissions(administrator=True)
    async def delete_code(self, ctx, code: str):
        async with aiosqlite.connect(self.db) as db:
            embed = discord.Embed(title="Deleting Premium Code", color=0xFF0000)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            
            async with db.execute('SELECT code FROM premium_system WHERE code = ?', (code,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    embed.description = "This code does not exist."
                    await ctx.respond(embed=embed)
                    return
                
                await db.execute('DELETE FROM premium_system WHERE code = ?', (code,))
                await db.commit()
                
                embed.description = "Premium code deleted successfully."
                await ctx.respond(embed=embed)


    @commands.slash_command(name="delete-premium-user", description="Delete a user's premium status (Admin only)")
    @commands.has_permissions(administrator=True)
    async def delete_user(self, ctx, user: discord.Member):
        async with aiosqlite.connect(self.db) as db:
            embed = discord.Embed(title="Deleting Premium Status", color=0xFF0000)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            
            async with db.execute('SELECT user_id FROM premium_system WHERE user_id = ?', (user.id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    embed.description = f"{user.mention} does not have a premium."
                    await ctx.respond(embed=embed)
                    return
                
                await db.execute('UPDATE premium_system SET user_id = NULL WHERE user_id = ?', (user.id,))
                await db.commit()
                
                embed.description = f"{user.mention}'s premium status has been deleted."
                await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Premium(bot))
